import streamlit as st
import pytesseract
import edge_tts
import asyncio
import tempfile
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageOps
import base64
import time
import os
import sys
import shutil

# --- CẤU HÌNH ĐƯỜNG DẪN TỰ ĐỘNG (AUTO DETECT) ---
# Logic: Nếu tìm thấy Tesseract trong đường dẫn hệ thống (Linux/Web) thì dùng nó.
# Nếu không (đang ở Windows), thì mới dùng đường dẫn cứng.

if sys.platform.startswith('win'):
    # Cấu hình cho máy Windows của bạn
    PATH_TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    POPPLER_PATH = r'C:\Program Files\poppler\poppler-25.12.0\Library\bin' 
else:
    # Cấu hình cho Streamlit Cloud (Linux) - Tự động tìm
    PATH_TESSERACT = shutil.which("tesseract")
    POPPLER_PATH = None # Linux cài poppler-utils tự động vào path chuẩn

# Thiết lập Tesseract
if PATH_TESSERACT:
    pytesseract.pytesseract.tesseract_cmd = PATH_TESSERACT

# --- CẤU HÌNH GIỌNG ĐỌC ---
VOICES = {
    "Nữ - Hoài My": "vi-VN-HoaiMyNeural",
    "Nam - Nam Minh": "vi-VN-NamMinhNeural"
}

# --- HÀM XỬ LÝ (GIỮ NGUYÊN TỪ V16) ---
@st.cache_data(show_spinner=False)
def get_page_content_parallel(pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number - 1)
        
        # Render ảnh
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_visual = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Xử lý OCR
        img_ocr = ImageOps.grayscale(img_visual)
        enhancer = ImageEnhance.Contrast(img_ocr)
        img_ocr = enhancer.enhance(2.0)
        
        # OCR
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img_ocr, lang='vie', config=custom_config)
        
        return img_visual, text
    except Exception as e:
        return None, str(e)

async def generate_audio_file(text, voice_key):
    if not text or len(text.strip()) < 2: return None
    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    communicate = edge_tts.Communicate(text, VOICES[voice_key], rate="+15%")
    await communicate.save(tfile.name)
    return tfile.name

def get_auto_player_html(file_path, page_num, total_pages):
    with open(file_path, "rb") as f:
        audio_bytes = f.read()
    audio_base64 = base64.b64encode(audio_bytes).decode()
    unique_id = f"audio_{page_num}_{int(time.time())}"
    
    js_script = ""
    if page_num < total_pages:
        js_script = f"""
        <script>
            var audio = document.getElementById("{unique_id}");
            audio.onended = function() {{
                var buttons = window.parent.document.getElementsByTagName('button');
                for (var i = 0; i < buttons.length; i++) {{
                    if (buttons[i].innerText.includes("Auto Next")) {{
                        buttons[i].click(); break;
                    }}
                }}
            }};
        </script>
        """
    return f"""
        <audio id="{unique_id}" autoplay controls style="width: 100%; margin-top: 10px;">
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
        </audio>
        {js_script}
    """

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="PDF Reader Online", layout="wide")

with st.sidebar:
    st.header("Cài đặt")
    selected_voice = st.selectbox("Giọng đọc:", list(VOICES.keys()))
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file:
    if 'current_page' not in st.session_state: st.session_state.current_page = 1
    if 'is_auto' not in st.session_state: st.session_state.is_auto = False

    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total_pages = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    col_vis, col_ctrl = st.columns([1.3, 1])
    img_show, text_content = get_page_content_parallel(bytes_data, st.session_state.current_page)

    with col_vis:
        if img_show: st.image(img_show, use_container_width=True)
    
    with col_ctrl:
        c1, c3 = st.columns([1, 1])
        with c1:
            if st.button("⬅️ Trước") and st.session_state.current_page > 1:
                st.session_state.current_page -= 1
                st.rerun()
        with c3:
            if st.button("⏭️ Auto Next") and st.session_state.current_page < total_pages:
                st.session_state.current_page += 1
                st.session_state.is_auto = True
                st.rerun()
        
        st.markdown("---")
        
        if st.session_state.is_auto:
            if st.button("⛔ DỪNG AUTO", type="primary", use_container_width=True):
                st.session_state.is_auto = False
                st.rerun()
        else:
            if st.button("▶️ BẮT ĐẦU", use_container_width=True):
                st.session_state.is_auto = True
                st.rerun()
                
        if st.session_state.is_auto and text_content:
            with st.spinner("⏳ Đang tải..."):
                audio_path = asyncio.run(generate_audio_file(text_content, selected_voice))
                if audio_path:
                    st.components.v1.html(get_auto_player_html(audio_path, st.session_state.current_page, total_pages), height=80)
                else:
                    time.sleep(1)
                    if st.session_state.current_page < total_pages:
                        st.session_state.current_page += 1
                        st.rerun()