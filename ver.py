import streamlit as st
import pytesseract
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageOps
import sys
import shutil
import time
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
        
        text = text.replace('\n', ' ').strip()
        return img_visual, text
    except Exception as e:
        return None, str(e)

# --- JAVASCRIPT TỰ ĐỌC ---
def speak_client_side(text, page_num):
    safe_text = text.replace('"', '\\"').replace("'", "\\'").replace('\n', ' ')
    
    html_code = f"""
    <script>
        window.speechSynthesis.cancel();

        function startSpeaking() {{
            var msg = new SpeechSynthesisUtterance();
            msg.text = "{safe_text}";
            msg.lang = 'vi-VN';
            msg.rate = 1.1;
            
            var voices = window.speechSynthesis.getVoices();
            var vnVoice = voices.find(v => v.lang.includes('vi') && v.name.includes('Microsoft')) || 
                          voices.find(v => v.lang.includes('vi'));
            
            if (vnVoice) {{ msg.voice = vnVoice; }}

            msg.onend = function(event) {{
                // Tìm nút Auto Next để bấm
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

        if (window.speechSynthesis.getVoices().length === 0) {{
            window.speechSynthesis.addEventListener('voiceschanged', startSpeaking);
        }} else {{
            startSpeaking();
        }}
    </script>
    """
    components.html(html_code, height=0)

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="PDF Reader V20", layout="wide")

with st.sidebar:
    st.header("📂 Cài đặt")
    st.info("💡 Mở bằng **Microsoft Edge** để có giọng đọc hay nhất.")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file:
    # Khởi tạo session
    if 'current_page' not in st.session_state: st.session_state.current_page = 1
    if 'is_auto' not in st.session_state: st.session_state.is_auto = False

    # Đọc file PDF
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total_pages = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    # --- GIAO DIỆN CHIA CỘT ---
    col_vis, col_ctrl = st.columns([1.3, 1])

    # --- CỘT PHẢI: BẢNG ĐIỀU KHIỂN & CHỌN SỐ TRANG ---
    with col_ctrl:
        st.subheader("🎛️ Bảng Điều Khiển")

        # 1. TÍNH NĂNG MỚI: NHẬP SỐ TRANG
        col_input, col_total = st.columns([2, 1])
        with col_input:
            # Ô nhập số trang: Khi bạn nhập số mới và Enter, nó sẽ nhảy ngay
            selected_page = st.number_input(
                "Đi tới trang số:", 
                min_value=1, 
                max_value=total_pages, 
                value=st.session_state.current_page
            )
        
        with col_total:
            st.write(f" / {total_pages}")

        # Logic: Nếu người dùng thay đổi số ở ô trên -> Cập nhật trang hiện tại
        if selected_page != st.session_state.current_page:
            st.session_state.current_page = selected_page
            # Nếu đang auto thì giữ nguyên auto (nhảy cóc và đọc tiếp)
            # Nếu muốn nhảy trang là dừng đọc thì bỏ comment dòng dưới:
            # st.session_state.is_auto = False 
            st.rerun()

        st.markdown("---")

        # 2. Các nút điều khiển
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.session_state.is_auto:
                if st.button("⛔ DỪNG ĐỌC", type="primary", use_container_width=True):
                    components.html("<script>window.speechSynthesis.cancel();</script>", height=0)
                    st.session_state.is_auto = False
                    st.rerun()
            else:
                if st.button("▶️ BẮT ĐẦU ĐỌC", use_container_width=True):
                    st.session_state.is_auto = True
                    st.rerun()
        
        with c2:
            # Nút Next này ẩn mình để JS bấm, nhưng người dùng bấm cũng được
            if st.button("⏭️ Auto Next", use_container_width=True):
                if st.session_state.current_page < total_pages:
                    st.session_state.current_page += 1
                    st.session_state.is_auto = True
                    st.rerun()

    # --- CỘT TRÁI: HIỂN THỊ ẢNH & OCR ---
    # Lấy nội dung trang (Dựa theo số trang đã chọn)
    img_show, text_content = get_page_content(bytes_data, st.session_state.current_page)

    with col_vis:
        if img_show: 
            st.image(img_show, caption=f"Trang {st.session_state.current_page}", use_container_width=True)

    # --- LOGIC ĐỌC ---
    if st.session_state.is_auto:
        with col_ctrl:
            if text_content:
                st.toast(f"🔊 Đang đọc trang {st.session_state.current_page}...")
                speak_client_side(text_content, st.session_state.current_page)
                
                with st.expander("Xem văn bản đang đọc", expanded=True):
                    st.write(text_content)
            else:
                st.warning("Trang trắng. Đang chuyển tiếp...")
                time.sleep(1)
                if st.session_state.current_page < total_pages:
                    st.session_state.current_page += 1
                    st.rerun()
