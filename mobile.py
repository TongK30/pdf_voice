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

# --- HÀM XỬ LÝ ẢNH SIÊU NHẸ (LITE) ---
@st.cache_data(show_spinner=False)
def get_page_lite(pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number - 1)
        
        # Matrix 1.2: Đủ nét để đọc, nhẹ RAM điện thoại
        mat = fitz.Matrix(1.2, 1.2) 
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_visual = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # OCR
        img_ocr = ImageOps.grayscale(img_visual)
        img_ocr = ImageEnhance.Contrast(img_ocr).enhance(1.5)
        
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img_ocr, lang='vie', config=custom_config)
        
        # Làm sạch cơ bản (Không dùng Regex để tránh lỗi)
        text = text.replace('\n', ' ').replace('|', '').strip()
        
        return img_visual, text
    except Exception as e:
        return None, str(e)

# --- JS ĐỌC CHO MOBILE (KHÔNG REGEX) ---
def mobile_speak_final(text):
    # Lọc ký tự gây lỗi JS
    safe_text = text.replace('\\', '').replace('"', '').replace("'", "").replace('\n', ' ')
    
    html = f"""
    <script>
        window.speechSynthesis.cancel();
        
        var msg = new SpeechSynthesisUtterance();
        msg.text = "{safe_text}";
        msg.lang = 'vi-VN';
        msg.rate = 1.0; 
        
        var voices = window.speechSynthesis.getVoices();
        var vn = voices.find(v => v.lang.includes('vi'));
        if (vn) {{ msg.voice = vn; }}

        // Tự bấm nút Tiếp theo khi đọc xong
        msg.onend = function(e) {{
            var buttons = window.parent.document.getElementsByTagName('button');
            for (var i = 0; i < buttons.length; i++) {{
                if (buttons[i].innerText.toUpperCase().includes("TIẾP THEO")) {{
                    buttons[i].click();
                    break;
                }}
            }}
        }};
        
        window.speechSynthesis.speak(msg);
        
        // Anti-Sleep cho Chrome Android
        if (window.speechInterval) clearInterval(window.speechInterval);
        window.speechInterval = setInterval(function() {{
            if (!window.speechSynthesis.speaking) {{
                clearInterval(window.speechInterval);
            }} else {{
                window.speechSynthesis.pause();
                window.speechSynthesis.resume();
            }}
        }}, 10000);
    </script>
    """
    components.html(html, height=0)

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="PDF Mobile Pro", layout="centered")

st.markdown("<h3 style='text-align: center;'>📱 PDF Reader V25 (Pro)</h3>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Chọn file PDF:", type="pdf")

if uploaded_file:
    # Quản lý trạng thái
    if 'curr_page' not in st.session_state: st.session_state.curr_page = 1
    if 'auto' not in st.session_state: st.session_state.auto = False

    # Load File
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    # --- KHU VỰC CHỌN SỐ TRANG (TÍNH NĂNG MỚI) ---
    st.write("---")
    col_jump, col_label = st.columns([2, 1])
    
    with col_jump:
        # Ô nhập số trang
        new_page = st.number_input(
            "Nhập số trang:", 
            min_value=1, 
            max_value=total, 
            value=st.session_state.curr_page,
            label_visibility="collapsed" # Ẩn nhãn cho gọn
        )
    
    with col_label:
        # Hiển thị tổng số trang bên cạnh
        st.markdown(f"** / {total} trang**")

    # Logic nhảy trang: Nếu số trong ô nhập khác số hiện tại -> Cập nhật ngay
    if new_page != st.session_state.curr_page:
        st.session_state.curr_page = new_page
        st.rerun()

    # --- NÚT ĐIỀU HƯỚNG ---
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ LÙI LẠI", use_container_width=True):
            if st.session_state.curr_page > 1:
                st.session_state.curr_page -= 1
                st.rerun()
    with c2:
        if st.button("TIẾP THEO ➡️", type="primary", use_container_width=True):
            if st.session_state.curr_page < total:
                st.session_state.curr_page += 1
                st.session_state.auto = True
                st.rerun()

    # --- NÚT PLAY/STOP ---
    if st.session_state.auto:
        if st.button("🟥 DỪNG ĐỌC", use_container_width=True):
            components.html("<script>window.speechSynthesis.cancel()</script>", height=0)
            st.session_state.auto = False
            st.rerun()
    else:
        if st.button("▶️ BẮT ĐẦU TỰ ĐỘNG", use_container_width=True):
            st.session_state.auto = True
            st.rerun()

    # --- HIỂN THỊ & ĐỌC ---
    img, text = get_page_lite(bytes_data, st.session_state.curr_page)
    
    if img:
        st.image(img, use_container_width=True)
    
    if st.session_state.auto:
        if text and len(text) > 5:
            st.toast(f"🔊 Đang đọc trang {st.session_state.curr_page}...")
            mobile_speak_final(text)
        else:
            st.warning("Trang trắng. Tự qua trang sau...")
            time.sleep(1)
            if st.session_state.curr_page < total:
                st.session_state.curr_page += 1
                st.rerun()
