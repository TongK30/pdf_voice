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

# --- HÀM XỬ LÝ ẢNH (OPENCV) ---
@st.cache_data(show_spinner=False)
def get_page_v29(pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number - 1)
        
        mat = fitz.Matrix(1.5, 1.5) 
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        img_np = np.array(img_pil) 
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        processed_img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 9)
        final_img = Image.fromarray(processed_img)
        
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(final_img, lang='vie', config=custom_config)
        
        # Làm sạch text: Xóa xuống dòng thừa, giữ lại dấu câu quan trọng
        clean_text = text.replace('\n', ' ').replace('|', '').strip()
        
        if not clean_text or len(clean_text) < 2:
            return img_pil, "Trang này chỉ có hình ảnh."
            
        return img_pil, clean_text
    except Exception as e:
        return None, str(e)

# --- JS CHIA NHỎ CÂU (KHẮC PHỤC LỖI DỪNG GIỮA CHỪNG) ---
def speak_chunks(text):
    # Xử lý text để JS không lỗi
    safe_text = text.replace('\\', '').replace('"', '').replace("'", "").replace('\n', ' ')
    
    html = f"""
    <script>
        // 1. Hủy lệnh cũ
        window.speechSynthesis.cancel();
        
        // 2. Chia văn bản thành các câu nhỏ (Dựa vào dấu . ! ? ;)
        // Regex này tách câu nhưng vẫn giữ lại dấu câu
        var textContent = "{safe_text}";
        var sentences = textContent.match(/[^.!?]+[.!?]+|[^.!?]+$/g);
        
        if (!sentences || sentences.length === 0) {{
            sentences = [textContent]; // Nếu không chia được thì đọc cả cục
        }}

        var currentIndex = 0;

        function speakNextSentence() {{
            // Nếu đã đọc hết các câu -> Bấm Next trang
            if (currentIndex >= sentences.length) {{
                console.log("Đã đọc hết trang. Chuyển trang...");
                var buttons = window.parent.document.getElementsByTagName('button');
                for (var i = 0; i < buttons.length; i++) {{
                    if (buttons[i].innerText.toUpperCase().includes("TIẾP THEO")) {{
                        buttons[i].click();
                        return;
                    }}
                }}
                return;
            }}

            // Lấy câu hiện tại
            var sentence = sentences[currentIndex];
            if (!sentence || sentence.trim().length === 0) {{
                currentIndex++;
                speakNextSentence();
                return;
            }}

            // Tạo lệnh đọc
            var msg = new SpeechSynthesisUtterance();
            msg.text = sentence;
            msg.lang = 'vi-VN';
            msg.rate = 1.0;

            // Tìm giọng
            var voices = window.speechSynthesis.getVoices();
            var vn = voices.find(v => v.lang.includes('vi'));
            if (vn) msg.voice = vn;

            // QUAN TRỌNG: Khi đọc xong câu này -> Đọc câu tiếp theo
            msg.onend = function(e) {{
                console.log("Xong câu " + currentIndex);
                currentIndex++;
                speakNextSentence(); // Đệ quy: Gọi lại chính nó
            }};

            msg.onerror = function(e) {{
                console.log("Lỗi câu " + currentIndex + ", bỏ qua...");
                currentIndex++;
                speakNextSentence();
            }};

            window.speechSynthesis.speak(msg);
        }}

        // Bắt đầu quy trình
        if (window.speechSynthesis.getVoices().length === 0) {{
            window.speechSynthesis.addEventListener('voiceschanged', function() {{
                speakNextSentence();
            }});
        }} else {{
            speakNextSentence();
        }}
        
        // Anti-Sleep (Giữ cho trình duyệt không ngủ gật)
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

# --- GIAO DIỆN ---
st.set_page_config(page_title="PDF Chunk Reader", layout="centered")
st.markdown("<h3 style='text-align: center;'>📖 Đọc PDF (Không bao giờ ngắt)</h3>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Upload PDF:", type="pdf")

if uploaded_file:
    if 'curr_page' not in st.session_state: st.session_state.curr_page = 1
    if 'auto' not in st.session_state: st.session_state.auto = False

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

    # Nút bấm
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ BACK", use_container_width=True):
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
        if st.button("▶️ BẮT ĐẦU ĐỌC", use_container_width=True):
            st.session_state.auto = True
            st.rerun()

    # Xử lý & Hiển thị
    img, text = get_page_v29(bytes_data, st.session_state.curr_page)
    
    if img: st.image(img, use_container_width=True)
    
    st.info("📝 Văn bản đang xử lý:")
    st.text_area("", text, height=100, label_visibility="collapsed")

    if st.session_state.auto:
        st.toast(f"🔊 Đang đọc từng câu trang {st.session_state.curr_page}...")
        speak_chunks(text)
