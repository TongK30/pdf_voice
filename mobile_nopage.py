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

# --- HÀM XỬ LÝ ẢNH (CHẾ ĐỘ LITE) ---
@st.cache_data(show_spinner=False)
def get_page_lite(pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number - 1)
        
        # Matrix 1.2: Đủ nét để đọc, đủ nhẹ cho điện thoại
        mat = fitz.Matrix(1.2, 1.2) 
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_visual = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # OCR
        img_ocr = ImageOps.grayscale(img_visual)
        # Tăng tương phản nhẹ để Tesseract đọc tốt hơn
        img_ocr = ImageEnhance.Contrast(img_ocr).enhance(1.5)
        
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img_ocr, lang='vie', config=custom_config)
        
        # Làm sạch văn bản bằng lệnh cơ bản (Không dùng Regex)
        text = text.replace('\n', ' ').replace('|', '').strip()
        
        return img_visual, text
    except Exception as e:
        return None, str(e)

# --- JS ĐỌC CHO MOBILE ---
def mobile_speak_v24(text):
    # Lọc bỏ các ký tự có thể gây lỗi JS
    safe_text = text.replace('\\', '').replace('"', '').replace("'", "").replace('\n', ' ')
    
    html = f"""
    <script>
        // Hủy lệnh cũ
        window.speechSynthesis.cancel();
        
        var msg = new SpeechSynthesisUtterance();
        msg.text = "{safe_text}";
        msg.lang = 'vi-VN';
        msg.rate = 1.0; 
        
        // Tìm giọng Việt Nam (Google hoặc Linh/Khôi trên iOS)
        var voices = window.speechSynthesis.getVoices();
        var vn = voices.find(v => v.lang.includes('vi'));
        if (vn) {{
            msg.voice = vn;
            console.log("Voice: " + vn.name);
        }}

        // Khi đọc xong -> Tự bấm nút Tiếp theo
        msg.onend = function(e) {{
            console.log("Done reading");
            var buttons = window.parent.document.getElementsByTagName('button');
            for (var i = 0; i < buttons.length; i++) {{
                // Tìm nút có chữ 'TIẾP THEO' (phân biệt hoa thường)
                if (buttons[i].innerText.toUpperCase().includes("TIẾP THEO")) {{
                    buttons[i].click();
                    break;
                }}
            }}
        }};
        
        // Fix lỗi Chrome Android hay bị ngắt
        window.speechSynthesis.speak(msg);
        
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

# --- GIAO DIỆN MOBILE ---
st.set_page_config(page_title="PDF Lite V24", layout="centered")

st.markdown("<h2 style='text-align: center;'>📱 PDF Reader V24</h2>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Chọn file PDF:", type="pdf")

if uploaded_file:
    # Quản lý trạng thái
    if 'curr_page' not in st.session_state: st.session_state.curr_page = 1
    if 'auto' not in st.session_state: st.session_state.auto = False

    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    # --- THANH ĐIỀU KHIỂN ---
    st.info(f"📄 Trang: {st.session_state.curr_page} / {total}")

    # Nút bấm to hết cỡ (Full Width)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ LÙI LẠI", use_container_width=True):
            if st.session_state.curr_page > 1:
                st.session_state.curr_page -= 1
                st.rerun()
    with c2:
        # Nút Next để JS tự bấm
        if st.button("TIẾP THEO ➡️", type="primary", use_container_width=True):
            if st.session_state.curr_page < total:
                st.session_state.curr_page += 1
                st.session_state.auto = True
                st.rerun()

    # Nút Play/Stop
    if st.session_state.auto:
        if st.button("🟥 DỪNG ĐỌC", use_container_width=True):
            components.html("<script>window.speechSynthesis.cancel()</script>", height=0)
            st.session_state.auto = False
            st.rerun()
    else:
        if st.button("▶️ BẮT ĐẦU TỰ ĐỘNG", use_container_width=True):
            st.session_state.auto = True
            st.rerun()

    # --- HIỂN THỊ ẢNH ---
    # Load ảnh chế độ nhẹ
    img, text = get_page_lite(bytes_data, st.session_state.curr_page)
    
    if img:
        st.image(img, use_container_width=True)
    
    # --- XỬ LÝ ĐỌC ---
    if st.session_state.auto:
        if text and len(text) > 5:
            st.toast(f"🔊 Đang đọc trang {st.session_state.curr_page}...")
            mobile_speak_v24(text)
        else:
            st.warning("Trang trắng hoặc ít chữ. Tự qua trang sau...")
            time.sleep(1)
            if st.session_state.curr_page < total:
                st.session_state.curr_page += 1
                st.rerun()
