import streamlit as st
import pytesseract
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageOps
import sys
import shutil
import time
import re
import base64
import streamlit.components.v1 as components

# --- CẤU HÌNH HỆ THỐNG ---
if sys.platform.startswith('win'):
    PATH_TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    PATH_TESSERACT = shutil.which("tesseract")

if PATH_TESSERACT:
    pytesseract.pytesseract.tesseract_cmd = PATH_TESSERACT

# --- HÀM XỬ LÝ ẢNH (TURBO) ---
@st.cache_data(show_spinner=False)
def get_page_content(pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number - 1)
        
        # Render ảnh
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_visual = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # OCR
        img_ocr = ImageOps.grayscale(img_visual)
        img_ocr = ImageEnhance.Contrast(img_ocr).enhance(2.0)
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img_ocr, lang='vie', config=custom_config)
        
        # Làm sạch text sơ bộ (xóa xuống dòng thừa để đọc mượt hơn)
        text = text.replace('\n', ' ').strip()
        return img_visual, text
    except Exception as e:
        return None, str(e)

# --- JAVASCRIPT ĐỂ TRÌNH DUYỆT TỰ ĐỌC (QUAN TRỌNG) ---
def speak_client_side(text, page_num):
    # Escape các ký tự đặc biệt để không lỗi JS
    safe_text = text.replace('"', '\\"').replace("'", "\\'").replace('\n', ' ')
    
    html_code = f"""
    <script>
        // Hủy các giọng đọc cũ đang chạy (nếu có)
        window.speechSynthesis.cancel();

        function startSpeaking() {{
            var msg = new SpeechSynthesisUtterance();
            msg.text = "{safe_text}";
            msg.lang = 'vi-VN'; // Bắt buộc tiếng Việt
            msg.rate = 1.1; // Tốc độ đọc nhanh hơn chút (1.0 là bình thường)
            
            // LẤY GIỌNG ĐỌC (Ưu tiên giọng Microsoft nếu dùng Edge)
            var voices = window.speechSynthesis.getVoices();
            
            // Tìm giọng Microsoft Tiếng Việt (Edge) hoặc Google Tiếng Việt (Chrome)
            var vnVoice = voices.find(v => v.lang.includes('vi') && v.name.includes('Microsoft')) || 
                          voices.find(v => v.lang.includes('vi'));
            
            if (vnVoice) {{
                msg.voice = vnVoice;
                console.log("Using voice: " + vnVoice.name);
            }}

            // SỰ KIỆN: KHI ĐỌC XONG -> BẤM NEXT
            msg.onend = function(event) {{
                console.log('Đọc xong. Next...');
                var buttons = window.parent.document.getElementsByTagName('button');
                for (var i = 0; i < buttons.length; i++) {{
                    if (buttons[i].innerText.includes("Auto Next")) {{
                        buttons[i].click();
                        break;
                    }}
                }}
            }};

            window.speechSynthesis.speak(msg);
        }}

        // Chrome/Edge cần load voices không đồng bộ
        if (window.speechSynthesis.getVoices().length === 0) {{
            window.speechSynthesis.addEventListener('voiceschanged', startSpeaking);
        }} else {{
            startSpeaking();
        }}
    </script>
    """
    # Nhúng vào web nhưng ẩn đi (height=0)
    components.html(html_code, height=0)

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Browser Native PDF Reader", layout="wide")

with st.sidebar:
    st.header("Cài đặt")
    st.info("💡 Mẹo: Mở bằng trình duyệt **Microsoft Edge** để có giọng đọc 'Hoài My' hay nhất.")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file:
    if 'current_page' not in st.session_state: st.session_state.current_page = 1
    if 'is_auto' not in st.session_state: st.session_state.is_auto = False

    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total_pages = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    col_vis, col_ctrl = st.columns([1.3, 1])
    
    # 1. OCR (Python làm)
    img_show, text_content = get_page_content(bytes_data, st.session_state.current_page)

    with col_vis:
        if img_show: st.image(img_show, use_container_width=True)

    with col_ctrl:
        # Điều hướng
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
        
        # Nút Auto
        if st.session_state.is_auto:
            if st.button("⛔ DỪNG ĐỌC", type="primary", use_container_width=True):
                # Hủy lệnh đọc JS
                components.html("<script>window.speechSynthesis.cancel();</script>", height=0)
                st.session_state.is_auto = False
                st.rerun()
        else:
            if st.button("▶️ BẮT ĐẦU ĐỌC", use_container_width=True):
                st.session_state.is_auto = True
                st.rerun()

        # 2. ĐỌC (Trình duyệt làm - Client Side)
        if st.session_state.is_auto and text_content:
            st.success(f"🔊 Đang đọc trang {st.session_state.current_page}...")
            
            # Gọi hàm JS để đọc
            speak_client_side(text_content, st.session_state.current_page)
            
            with st.expander("Xem văn bản"):
                st.write(text_content)
        elif st.session_state.is_auto and not text_content:
            st.warning("Trang trắng. Đang chuyển...")
            time.sleep(1)
            if st.session_state.current_page < total_pages:
                st.session_state.current_page += 1
                st.rerun()
