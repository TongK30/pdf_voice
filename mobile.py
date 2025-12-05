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

# --- HÀM XỬ LÝ ẢNH ---
@st.cache_data(show_spinner=False)
def get_page_content(pdf_bytes, page_number):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(page_number - 1)
        
        # Giảm chất lượng ảnh hiển thị một chút để load nhanh trên 4G
        mat = fitz.Matrix(1.5, 1.5) 
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_visual = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # OCR vẫn dùng chất lượng cao ngầm bên dưới
        img_ocr = ImageOps.grayscale(img_visual)
        img_ocr = ImageEnhance.Contrast(img_ocr).enhance(2.0)
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img_ocr, lang='vie', config=custom_config)
        
        text = text.replace('\n', ' ').strip()
        return img_visual, text
    except Exception as e:
        return None, str(e)

# --- JAVASCRIPT CHO MOBILE (QUAN TRỌNG) ---
def speak_mobile_optimized(text, page_num):
    # Làm sạch kỹ văn bản
    safe_text = text.replace('\\', '').replace('"', '').replace("'", "").replace('\n', ' ')
    
    html_code = f"""
    <script>
        // Hàm chính
        function startSpeaking() {{
            window.speechSynthesis.cancel(); // Reset

            var msg = new SpeechSynthesisUtterance();
            msg.text = "{safe_text}";
            msg.lang = 'vi-VN'; 
            msg.rate = 1.0; // Tốc độ chuẩn (1.0) an toàn nhất cho Android
            
            // --- LOGIC TÌM GIỌNG CHO ĐIỆN THOẠI ---
            var voices = window.speechSynthesis.getVoices();
            
            // 1. Tìm bất kỳ giọng nào có chữ 'vi' hoặc 'Vietnamese'
            // Trên iPhone nó sẽ tìm thấy 'Linh', trên Android là 'Google Vietnamese'
            var vnVoice = voices.find(v => v.lang.includes('vi') || v.name.includes('Vietnu'));
            
            if (vnVoice) {{
                msg.voice = vnVoice;
                console.log("Mobile Voice Found: " + vnVoice.name);
            }} else {{
                console.log("Không tìm thấy giọng Việt, dùng giọng mặc định");
            }}

            // --- SỰ KIỆN CHUYỂN TRANG ---
            msg.onend = function(event) {{
                var buttons = window.parent.document.getElementsByTagName('button');
                for (var i = 0; i < buttons.length; i++) {{
                    if (buttons[i].innerText.includes("Auto Next")) {{
                        buttons[i].click();
                        break;
                    }}
                }}
            }};

            // Khắc phục lỗi iOS Safari hay bị sleep
            msg.onerror = function(e) {{
                console.log("Audio Error, trying to skip...");
                // Nếu lỗi, vẫn bấm next để không bị kẹt
                var buttons = window.parent.document.getElementsByTagName('button');
                for (var i = 0; i < buttons.length; i++) {{
                    if (buttons[i].innerText.includes("Auto Next")) {{
                        buttons[i].click(); break;
                    }}
                }}
            }};

            window.speechSynthesis.speak(msg);
            
            // --- HACK CHO ANDROID CHROME ---
            // Android Chrome hay bị ngắt giữa chừng, cần 'resume' liên tục
            if (window.speechInterval) clearInterval(window.speechInterval);
            window.speechInterval = setInterval(function() {{
                if (!window.speechSynthesis.speaking) {{
                    clearInterval(window.speechInterval);
                }} else {{
                    window.speechSynthesis.pause();
                    window.speechSynthesis.resume();
                }}
            }}, 5000);
        }}

        // Đợi giọng load xong (iPhone load giọng chậm)
        if (window.speechSynthesis.getVoices().length === 0) {{
            window.speechSynthesis.addEventListener('voiceschanged', startSpeaking);
        }} else {{
            startSpeaking();
        }}
    </script>
    """
    components.html(html_code, height=0)

# --- GIAO DIỆN CHÍNH ---
st.set_page_config(page_title="Mobile PDF Reader", layout="centered") # Layout centered tốt cho điện thoại

st.header("📱 Đọc PDF trên Điện thoại")

with st.expander("Cài đặt & Upload", expanded=True):
    uploaded_file = st.file_uploader("Chọn file PDF:", type="pdf")
    st.info("⚠️ iPhone: Nhớ tắt chế độ Im Lặng (gạt nút bên hông máy) để nghe tiếng.")

if uploaded_file:
    if 'current_page' not in st.session_state: st.session_state.current_page = 1
    if 'is_auto' not in st.session_state: st.session_state.is_auto = False

    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total_pages = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    # --- ĐIỀU KHIỂN ---
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown(f"<h3 style='text-align: center'>Trang {st.session_state.current_page}/{total_pages}</h3>", unsafe_allow_html=True)
        
        # Chọn trang (Dùng Selectbox cho dễ bấm trên điện thoại thay vì number_input)
        # Tạo danh sách trang để chọn
        page_options = list(range(1, total_pages + 1))
        selected_page = st.selectbox("Chọn trang nhảy tới:", page_options, index=st.session_state.current_page-1, label_visibility="collapsed")
        
        if selected_page != st.session_state.current_page:
            st.session_state.current_page = selected_page
            st.rerun()

    with col1:
        if st.button("⬅️"):
            if st.session_state.current_page > 1:
                st.session_state.current_page -= 1
                st.rerun()

    with col3:
        # Nút Next cho JS bấm
        if st.button("Auto Next ➡️"):
            if st.session_state.current_page < total_pages:
                st.session_state.current_page += 1
                st.session_state.is_auto = True
                st.rerun()

    # Nút Bắt đầu to dễ bấm
    if st.session_state.is_auto:
        if st.button("🟥 DỪNG LẠI", type="primary", use_container_width=True):
             components.html("<script>window.speechSynthesis.cancel();</script>", height=0)
             st.session_state.is_auto = False
             st.rerun()
    else:
        if st.button("▶️ BẮT ĐẦU ĐỌC", use_container_width=True):
            st.session_state.is_auto = True
            st.rerun()

    # --- HIỂN THỊ & ĐỌC ---
    img_show, text_content = get_page_content(bytes_data, st.session_state.current_page)
    
    if img_show:
        st.image(img_show, use_container_width=True)

    if st.session_state.is_auto:
        if text_content:
            st.toast(f"🔊 Đang đọc trang {st.session_state.current_page}...")
            speak_mobile_optimized(text_content, st.session_state.current_page)
        else:
            st.warning("Trang trắng. Qua trang sau...")
            time.sleep(1)
            if st.session_state.current_page < total_pages:
                st.session_state.current_page += 1
                st.rerun()
