import streamlit as st
import pytesseract
import edge_tts
import asyncio
import tempfile
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageOps
import base64
import time
import re
from gtts import gTTS # Thư viện Google TTS (Dự phòng)
import shutil
import sys
import os

# --- CẤU HÌNH ĐƯỜNG DẪN TỰ ĐỘNG ---
if sys.platform.startswith('win'):
    PATH_TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    PATH_TESSERACT = shutil.which("tesseract")

if PATH_TESSERACT:
    pytesseract.pytesseract.tesseract_cmd = PATH_TESSERACT

# --- CẤU HÌNH GIỌNG ĐỌC EDGE (CHÍNH) ---
EDGE_VOICES = {
    "Nữ - Hoài My (Microsoft)": "vi-VN-HoaiMyNeural",
    "Nam - Nam Minh (Microsoft)": "vi-VN-NamMinhNeural"
}

# --- HÀM LÀM SẠCH VĂN BẢN ---
def clean_text_for_tts(text):
    if not text: return ""
    if re.fullmatch(r'[\.\-_\|\s]*', text): return ""
    return text.strip()

# --- HÀM XỬ LÝ ẢNH ---
@st.cache_data(show_spinner=False)
def get_page_content_safe(pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number - 1)
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_visual = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        img_ocr = ImageOps.grayscale(img_visual)
        img_ocr = ImageEnhance.Contrast(img_ocr).enhance(2.0)
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img_ocr, lang='vie', config=custom_config)
        return img_visual, text
    except Exception as e:
        return None, str(e)

# --- HÀM TẠO AUDIO GOOGLE (DỰ PHÒNG) ---
def generate_google_audio(text):
    """Hàm này chạy khi Microsoft bị lỗi"""
    try:
        tts = gTTS(text=text, lang='vi')
        tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tfile.name)
        return tfile.name
    except Exception as e:
        return None

# --- HÀM TẠO AUDIO THÔNG MINH (HYBRID) ---
async def generate_audio_hybrid(text, voice_key):
    clean_text = clean_text_for_tts(text)
    if not clean_text or len(clean_text) < 2:
        return None, "Văn bản rỗng"

    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    filename = tfile.name

    # CÁCH 1: Thử dùng Microsoft Edge TTS (Ưu tiên)
    try:
        communicate = edge_tts.Communicate(clean_text, EDGE_VOICES[voice_key], rate="+15%")
        await communicate.save(filename)
        return filename, "Microsoft"
    except Exception as e:
        # CÁCH 2: Nếu lỗi (do bị chặn IP), chuyển sang Google TTS
        # st.toast là thông báo nhỏ góc màn hình
        print(f"Microsoft TTS Failed: {e}. Switching to Google...")
        google_file = generate_google_audio(clean_text)
        if google_file:
            return google_file, "Google (Backup)"
        else:
            return None, "Lỗi cả Google lẫn Microsoft"

# --- TRÌNH PHÁT AUTO-NEXT ---
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

# --- GIAO DIỆN ---
st.set_page_config(page_title="Hybrid PDF Reader", layout="wide")

with st.sidebar:
    st.header("Cài đặt")
    selected_voice = st.selectbox("Giọng đọc (Ưu tiên):", list(EDGE_VOICES.keys()))
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")
    st.info("💡 Nếu máy chủ Microsoft chặn, hệ thống sẽ tự động dùng giọng Google.")

if uploaded_file:
    if 'current_page' not in st.session_state: st.session_state.current_page = 1
    if 'is_auto' not in st.session_state: st.session_state.is_auto = False

    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total_pages = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    col_vis, col_ctrl = st.columns([1.3, 1])
    img_show, text_content = get_page_content_safe(bytes_data, st.session_state.current_page)

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

        if st.session_state.is_auto:
            with st.spinner("⏳ Đang xử lý âm thanh..."):
                # Gọi hàm Hybrid mới
                audio_path, source = asyncio.run(generate_audio_hybrid(text_content, selected_voice))
                
                if audio_path:
                    # Hiển thị nguồn giọng đọc để bạn biết
                    if "Google" in source:
                        st.caption("⚠️ Microsoft bị chặn -> Đang dùng giọng Google.")
                    
                    st.components.v1.html(
                        get_auto_player_html(audio_path, st.session_state.current_page, total_pages),
                        height=80
                    )
                else:
                    st.warning("Trang lỗi -> Nhảy trang...")
                    time.sleep(1)
                    if st.session_state.current_page < total_pages:
                        st.session_state.current_page += 1
                        st.rerun()
                    else:
                        st.session_state.is_auto = False