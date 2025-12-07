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

# --- HÀM XỬ LÝ ẢNH (LITE) ---
@st.cache_data(show_spinner=False)
def get_page_lite(pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number - 1)
        
        # Matrix 1.2 cho nhẹ máy
        mat = fitz.Matrix(1.2, 1.2) 
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_visual = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # OCR
        img_ocr = ImageOps.grayscale(img_visual)
        img_ocr = ImageEnhance.Contrast(img_ocr).enhance(1.5)
        
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img_ocr, lang='vie', config=custom_config)
        
        # Làm sạch cơ bản
        text = text.replace('\n', ' ').replace('|', '').strip()
        
        return img_visual, text
    except Exception as e:
        return None, str(e)

# --- JS ĐỌC TỪNG CÂU (CHỐNG NGẮT QUÃNG) ---
def mobile_speak_smooth(text):
    # Lọc ký tự gây lỗi
    safe_text = text.replace('\\', '').replace('"', '').replace("'", "").replace('\n', ' ')
    
    html = f"""
    <script>
        // 1. Hủy lệnh cũ
        window.speechSynthesis.cancel();
        
        // 2. Chia văn bản thành mảng các câu (Dựa vào dấu . ! ? ;)
        var fullText = "{safe_text}";
        // Regex này tách câu nhưng giữ lại dấu câu để đọc có ngữ điệu
        var sentences = fullText.match(/[^.!?]+[.!?]+|[^.!?]+$/g);
        
        if (!sentences || sentences.length === 0) {{
            sentences = [fullText]; // Nếu không chia được thì đọc cả cục
        }}

        var currentIndex = 0;

        function playNextChunk() {{
            // NẾU ĐÃ ĐỌC HẾT CÁC CÂU -> BẤM NEXT TRANG
            if (currentIndex >= sentences.length) {{
                console.log("Xong trang. Chuyển tiếp...");
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

            // TẠO LỆNH ĐỌC CHO CÂU HIỆN TẠI
            var msg = new SpeechSynthesisUtterance();
            msg.text = chunk;
            msg.lang = 'vi-VN';
            msg.rate = 1.0; 

            var voices = window.speechSynthesis.getVoices();
            var vn = voices.find(v => v.lang.includes('vi'));
            if (vn) msg.voice = vn;

            // QUAN TRỌNG: Đọc xong câu này -> Gọi lại hàm để đọc câu sau
            msg.onend = function(e) {{
                currentIndex++;
                playNextChunk(); 
            }};
            
            // Nếu lỗi câu này -> Bỏ qua đọc câu sau luôn
            msg.onerror = function(e) {{
                console.log("Lỗi chunk, skip...");
                currentIndex++;
                playNextChunk();
            }};

            window.speechSynthesis.speak(msg);
        }}
        
        // --- CHỜ LOAD GIỌNG RỒI MỚI ĐỌC ---
        if (window.speechSynthesis.getVoices().length === 0) {{
            window.speechSynthesis.addEventListener('voiceschanged', function() {{
                playNextChunk();
            }});
        }} else {{
            playNextChunk();
        }}
        
        // --- ANTI SLEEP (GIỮ KẾT NỐI) ---
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
st.set_page_config(page_title="PDF Smooth V30", layout="centered")

st.markdown("<h3 style='text-align: center;'>📱 PDF Smooth (V30)</h3>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Chọn file PDF:", type="pdf")

if uploaded_file:
    if 'curr_page' not in st.session_state: st.session_state.curr_page = 1
    if 'auto' not in st.session_state: st.session_state.auto = False

    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    # --- CHỌN TRANG ---
    st.write("---")
    col_jump, col_label = st.columns([2, 1])
    
    with col_jump:
        new_page = st.number_input(
            "Nhập số trang:", 
            min_value=1, 
            max_value=total, 
            value=st.session_state.curr_page,
            label_visibility="collapsed"
        )
    with col_label:
        st.markdown(f"** / {total} trang**")

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

    # --- PLAY / STOP ---
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
    img, text = get_page_lite(bytes_data, st.session_state.curr_page)
    
    if img:
        st.image(img, use_container_width=True)
    
    # --- XỬ LÝ ĐỌC ---
    if st.session_state.auto:
        # ÉP ĐỌC: Kể cả ít chữ cũng đọc
        if text:
            st.toast(f"🔊 Đang đọc trang {st.session_state.curr_page}...")
            mobile_speak_smooth(text)
            
            # Hiển thị text mờ mờ bên dưới để biết nó đang đọc cái gì
            with st.expander("Xem văn bản đang đọc"):
                st.write(text)
        else:
            st.warning("Trang trắng. Chuyển trang...")
            time.sleep(1)
            if st.session_state.curr_page < total:
                st.session_state.curr_page += 1
                st.rerun()
