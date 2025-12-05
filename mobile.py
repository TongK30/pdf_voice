import streamlit as st
import pytesseract
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageOps
import sys
import shutil
import time
import streamlit.components.v1 as components

# --- CẤU HÌNH ---
if sys.platform.startswith('win'):
    PATH_TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    PATH_TESSERACT = shutil.which("tesseract")

if PATH_TESSERACT:
    pytesseract.pytesseract.tesseract_cmd = PATH_TESSERACT

# --- HÀM XỬ LÝ (CHẾ ĐỘ TIẾT KIỆM RAM) ---
@st.cache_data(show_spinner=False)
def get_page_lite(pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number - 1)
        
        # GIẢM DPI XUỐNG 1.2 (Thay vì 2.0) -> Ảnh nhẹ hơn 4 lần -> Không bị sập
        mat = fitz.Matrix(1.2, 1.2) 
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_visual = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # OCR vẫn đọc tốt
        img_ocr = ImageOps.grayscale(img_visual)
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img_ocr, lang='vie', config=custom_config)
        
        return img_visual, text.replace('\n', ' ').strip()
    except Exception as e:
        return None, str(e)

# --- JS ĐỌC CHO MOBILE ---
def mobile_speak(text):
    safe_text = text.replace('\\', '').replace('"', '').replace("'", "").replace('\n', ' ')
    html = f"""
    <script>
        window.speechSynthesis.cancel();
        var msg = new SpeechSynthesisUtterance();
        msg.text = "{safe_text}";
        msg.lang = 'vi-VN';
        msg.rate = 1.0;
        
        // Tìm giọng
        var voices = window.speechSynthesis.getVoices();
        var vn = voices.find(v => v.lang.includes('vi'));
        if (vn) msg.voice = vn;

        // Tự động bấm nút Next khi đọc xong
        msg.onend = function(e) {{
            var btn = window.parent.document.querySelector('button[kind="primary"]');
            if (btn && btn.innerText.includes("TIẾP THEO")) btn.click();
        }};
        
        window.speechSynthesis.speak(msg);
    </script>
    """
    components.html(html, height=0)

# --- GIAO DIỆN ĐƠN GIẢN (KHÔNG CHIA CỘT) ---
st.set_page_config(page_title="Mobile Lite", layout="centered")

st.title("📱 PDF Reader Lite")

# 1. Upload
uploaded_file = st.file_uploader("Chọn PDF:", type="pdf")

if uploaded_file:
    if 'curr_page' not in st.session_state: st.session_state.curr_page = 1
    if 'auto' not in st.session_state: st.session_state.auto = False

    # Load File
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    # 2. Thanh điều khiển (Nút bấm to rõ)
    st.write(f"📖 **Trang {st.session_state.curr_page} / {total}**")
    
    # Dùng 2 nút Next/Back đơn giản
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ Lùi lại", use_container_width=True):
            if st.session_state.curr_page > 1:
                st.session_state.curr_page -= 1
                st.rerun()
    with c2:
        # Nút này JS sẽ tự bấm
        if st.button("TIẾP THEO ➡️", type="primary", use_container_width=True):
            if st.session_state.curr_page < total:
                st.session_state.curr_page += 1
                st.session_state.auto = True
                st.rerun()

    # Nút Bắt đầu / Dừng
    if st.session_state.auto:
        if st.button("🟥 DỪNG ĐỌC", use_container_width=True):
            components.html("<script>window.speechSynthesis.cancel()</script>", height=0)
            st.session_state.auto = False
            st.rerun()
    else:
        if st.button("▶️ BẮT ĐẦU TỰ ĐỘNG", use_container_width=True):
            st.session_state.auto = True
            st.rerun()

    # 3. Hiển thị Ảnh & Đọc
    img, text = get_page_lite(bytes_data, st.session_state.curr_page)
    
    if img:
        st.image(img, use_container_width=True) # Ảnh tự co giãn theo màn hình điện thoại
    
    if st.session_state.auto:
        if text:
            st.toast(f"Đang đọc trang {st.session_state.curr_page}...")
            mobile_speak(text)
        else:
            st.warning("Trang trắng. Đang chuyển...")
            time.sleep(1)
            if st.session_state.curr_page < total:
                st.session_state.curr_page += 1
                st.rerun()
