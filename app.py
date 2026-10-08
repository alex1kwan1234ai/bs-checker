import os
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="屋宇裝備多功能智能審查員", layout="centered")
st.title("屋宇裝備文件智能審查員")
st.caption("🚀 手機隨身版 —— 隨時隨地工程審查")

api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("❌ 未偵測到 GEMINI_API_KEY，請在 Streamlit 後台設定。")
    st.stop()

# 初始化 Client
client = genai.Client(api_key=api_key)

# 1. 下拉選單：只決定當前選擇的範疇
task_mode = st.selectbox(
    "請選擇今日要查閱的工程範疇：",
    ["機電收貨對照 (GS + PS)", "電力安全審查 (CoP)", "消防出牌合規 (消防紅皮書)"]
)

# 2. 根據選單動態指定本地 PDF 路徑
if task_mode == "機電收貨對照 (GS + PS)":
    DOC_PATHS = {
        "gs_general": "docs/BSGS_2022.pdf",
        "project_spec": "docs/BSPS.pdf"
    }
elif task_mode == "電力安全審查 (CoP)":
    DOC_PATHS = {"cop": "docs/COP_E_2025_TEST.pdf"}
else:
    DOC_PATHS = {"fsd_red": "docs/FSD_Red_Book.pdf"}

# 3. 初始化 Session State 用來儲存已上傳的檔案對象與對話紀錄
if "active_docs" not in st.session_state:
    st.session_state.active_docs = None
if "current_loaded_mode" not in st.session_state:
    st.session_state.current_loaded_mode = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# 💡 核心改動：加入一個明確的觸發按鈕
st.write("---")
col1, col2 = st.columns([3, 1])
with col1:
    st.write(f"當前準備加載：{', '.join(DOC_PATHS.keys())}")
with col2:
    load_clicked = st.button("⚡ 開始加載通道", type="primary")

# 4. 當點擊按鈕時，才觸發上傳檔案至 Google
if load_clicked:
    uploaded_files_list = []
    progress_text = f"正在上傳【{task_mode}】規格書至 Google AI 記憶體..."
    
    with st.spinner(progress_text):
        for doc_name, path in DOC_PATHS.items():
            if os.path.exists(path):
                google_file = client.files.upload(file=path)
                uploaded_files_list.append(google_file)
            else:
                st.warning(f"溫馨提示：找不到檔案 {path}")
        
        if uploaded_files_list:
            # 將成功上傳的檔案對象和當前通道名稱存入系統記憶體
            st.session_state.active_docs = uploaded_files_list
            st.session_state.current_loaded_mode = task_mode
            st.session_state.messages = [] # 切換通道時自動清空舊的對話
            st.success(f"🎉 【{task_mode}】通道成功啟用！")
        else:
            st.error("❌ 無法讀取任何本地 PDF，請檢查路徑。")

# 5. 側邊欄（Sidebar）狀態看板
if st.session_state.active_docs and st.session_state.current_loaded_mode == task_mode:
    st.sidebar.success(f"🟢 【{task_mode}】已就緒")
    with st.sidebar.spinner("正在免費測量 Token 水位..."):
        total_tokens = client.models.count_tokens(
            model='gemini-3.8-flash', 
            contents=st.session_state.active_docs
        )
    st.sidebar.metric(label="📚 當前文件 Token 總量", value=f"{total_tokens.total_tokens:,}")
else:
    st.sidebar.warning("⚠️ 請先點擊「開始加載通道」按鈕")

# 6. 渲染聊天對話紀錄
if st.session_state.active_docs and st.session_state.current_loaded_mode == task_mode:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # 7. 對話輸入框
    if user_query := st.chat_input("想對照邊份 Spec 嘅要求？"):
        with st.chat_message("user"):
            st.write(user_query)
        st.session_state.messages.append({"role": "user", "content": user_query})

        with st.chat_message("assistant"):
            with st.spinner("大腦正在跨文件檢索中..."):
                system_instruction = "你是一位熟讀香港工程標準與合約規範的註冊屋宇裝備工程師。請用專業地道的香港地盤廣東話回答。"
                
                # 免費版核心：打包上傳的文件 + 用戶提問
                response_stream = client.models.generate_content_stream(
                    model='gemini-3.8-flash',
                    contents=st.session_state.active_docs + [user_query],
                    config=types.GenerateContentConfig(system_instruction=system_instruction),
                )
                answer = st.write_stream(chunk.text for chunk in response_stream)
                
        st.session_state.messages.append({"role": "assistant", "content": answer})
elif load_clicked == False and st.session_state.current_loaded_mode != task_mode:
    st.info("💡 請在上方選好你想查閱的範疇，然後點擊「開始加載通道」按鈕啟動大腦。")