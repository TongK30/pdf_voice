import streamlit as st
import pytesseract
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance, ImageOps
import sys
import shutil
import time
import streamlit.components.v1 as components
import cv2
import numpy as np

# --- CẤU HÌNH ---
if sys.platform.startswith('win'):
    PATH_TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    PATH_TESSERACT = shutil.which("tesseract")

if PATH_TESSERACT:
    pytesseract.pytesseract.tesseract_cmd = PATH_TESSERACT

# --- HÀM XỬ LÝ ẢNH (2 CHẾ ĐỘ) ---
@st.cache_data(show_spinner=False)
def get_page_content_v31(pdf_bytes, page_number, use_opencv=False):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number - 1)
        
        # Matrix 1.5: Cân bằng giữa tốc độ và độ nét
        mat = fitz.Matrix(1.5, 1.5) 
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        final_img = img_pil
        
        # --- NẾU BẬT OPENCV (CHẾ ĐỘ LÀM NÉT) ---
        if use_opencv:
            # Chuyển sang định dạng OpenCV
            img_np = np.array(img_pil)
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            
            # Thuật toán Adaptive Threshold: Tự động tách chữ khỏi nền
            # Giúp chữ tiếng Việt đậm hơn, rõ dấu hơn
            processed = cv2.adaptiveThreshold(
                gray, 255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 
                15, 8
            )
            final_img = Image.fromarray(processed)
        else:
            # Chế độ thường: Chỉ tăng tương phản nhẹ
            gray = ImageOps.grayscale(img_pil)
            final_img = ImageEnhance.Contrast(gray).enhance(1.5)

        # OCR
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(final_img, lang='vie', config=custom_config)
        
        # Làm sạch text
        text = text.replace('\n', ' ').replace('|', '').strip()
        
        return img_pil, final_img, text
    except Exception as e:
        return None, None, str(e)

# --- JS ĐỌC TỪNG CÂU (SMOOTH V30) ---
def mobile_speak_smooth(text):
    safe_text = text.replace('\\', '').replace('"', '').replace("'", "").replace('\n', ' ')
    html = f"""
    <script>
        window.speechSynthesis.cancel();
        
        var fullText = "{safe_text}";
        var sentences = fullText.match(/[^.!?]+[.!?]+|[^.!?]+$/g);
        
        if (!sentences || sentences.length === 0) {{
            sentences = [fullText];
        }}

        var currentIndex = 0;

        function playNextChunk() {{
            if (currentIndex >= sentences.length) {{
                var buttons = window.parent.document.getElementsByTagName('button');
                for (var i = 0; i < buttons.length; i++) {{
                    if (buttons[i].innerText.toUpperCase().includes("TIẾP THEO")) {{
                        buttons[i].click(); return;
                    }}
                }}
                return;
            }}

            var chunk = sentences[currentIndex];
            if (!chunk || chunk.trim().length === 0) {{
                currentIndex++; playNextChunk(); return;
            }}

            var msg = new SpeechSynthesisUtterance();
            msg.text = chunk;
            msg.lang = 'vi-VN';
            msg.rate = 1.0; 

            var voices = window.speechSynthesis.getVoices();
            var vn = voices.find(v => v.lang.includes('vi'));
            if (vn) msg.voice = vn;

            msg.onend = function(e) {{
                currentIndex++; playNextChunk(); 
            }};
            
            msg.onerror = function(e) {{
                currentIndex++; playNextChunk();
            }};

            window.speechSynthesis.speak(msg);
        }}
        
        if (window.speechSynthesis.getVoices().length === 0) {{
            window.speechSynthesis.addEventListener('voiceschanged', function() {{ playNextChunk(); }});
        }} else {{
            playNextChunk();
        }}
        
        if (window.speechInterval) clearInterval(window.speechInterval);
        window.speechInterval = setInterval(function() {{
            if (window.speechSynthesis.speaking) {{
                window.speechSynthesis.pause();
                window.speechSynthesis.resume();
            }}
        }}, 8000);
    </script>
    """
    components.html(html, height=0)

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="PDF OpenCV V31", layout="centered")
st.markdown("<h3 style='text-align: center;'>📱 PDF Pro (OpenCV)</h3>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Chọn file PDF:", type="pdf")

if uploaded_file:
    if 'curr_page' not in st.session_state: st.session_state.curr_page = 1
    if 'auto' not in st.session_state: st.session_state.auto = False
    
    # --- CÔNG TẮC OPENCV ---
    # Mặc định tắt cho nhanh, cần thì bật lên
    use_opencv = st.checkbox("✅ Bật chế độ làm nét (OpenCV) - Đọc chậm nhưng chuẩn hơn")

    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    # Chọn trang
    st.write("---")
    c_jump, c_label = st.columns([2, 1])
    with c_jump:
        new_page = st.number_input("Trang:", 1, total, st.session_state.curr_page, label_visibility="collapsed")
    with c_label:
        st.write(f"/ {total}")

    if new_page != st.session_state.curr_page:
        st.session_state.curr_page = new_page
        st.rerun()

    # Điều hướng
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

    if st.session_state.auto:
        if st.button("🟥 DỪNG LẠI", use_container_width=True):
            components.html("<script>window.speechSynthesis.cancel()</script>", height=0)
            st.session_state.auto = False
            st.rerun()
    else:
        if st.button("▶️ BẮT ĐẦU TỰ ĐỘNG", use_container_width=True):
            st.session_state.auto = True
            st.rerun()

    # --- XỬ LÝ ---
    img_org, img_proc, text = get_page_content_v31(bytes_data, st.session_state.curr_page, use_opencv)
    
    # Hiển thị ảnh (Nếu bật OpenCV thì hiện ảnh đã xử lý để biết nó nét thế nào)
    if use_opencv and img_proc:
        st.image(img_proc, caption="Ảnh đã qua OpenCV (Trắng đen)", use_container_width=True)
    elif img_org:
        st.image(img_org, caption="Ảnh gốc", use_container_width=True)
    
    # Logic Đọc
    if st.session_state.auto:
        if text:
            st.toast(f"🔊 Đang đọc trang {st.session_state.curr_page}...")
            mobile_speak_smooth(text)
            
            with st.expander("Xem chữ"):
                st.write(text)
        else:
            st.warning("Trang trắng. Chuyển tiếp...")
            time.sleep(1)
            if st.session_state.curr_page < total:
                st.session_state.curr_page += 1
                st.rerun()
