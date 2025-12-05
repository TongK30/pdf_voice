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
        
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_visual = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        img_ocr = ImageOps.grayscale(img_visual)
        img_ocr = ImageEnhance.Contrast(img_ocr).enhance(2.0)
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img_ocr, lang='vie', config=custom_config)
        
        text = text.replace('\n', ' ').strip()
        return img_visual, text
    except Exception as e:
        return None, str(e)

# --- JAVASCRIPT FIXED (SỬA LỖI DỪNG ĐỘT NGỘT) ---
def speak_client_side(text, page_num):
    # Xử lý ký tự đặc biệt kỹ hơn
    safe_text = text.replace('\\', '').replace('"', '').replace("'", "").replace('\n', ' ')
    
    html_code = f"""
    <script>
        // Hủy lệnh cũ
        window.speechSynthesis.cancel();

        function startSpeaking() {{
            // FIX LỖI 20 TRANG: Gán vào window để không bị dọn rác bộ nhớ
            window.utterance = new SpeechSynthesisUtterance();
            window.utterance.text = "{safe_text}";
            window.utterance.lang = 'vi-VN';
            window.utterance.rate = 1.1;
            
            var voices = window.speechSynthesis.getVoices();
            var vnVoice = voices.find(v => v.lang.includes('vi') && v.name.includes('Microsoft')) || 
                          voices.find(v => v.lang.includes('vi'));
            
            if (vnVoice) {{ window.utterance.voice = vnVoice; }}

            // Sự kiện đọc xong
            window.utterance.onend = function(event) {{
                console.log('Page {page_num} finished.');
                var buttons = window.parent.document.getElementsByTagName('button');
                for (var i = 0; i < buttons.length; i++) {{
                    if (buttons[i].innerText.includes("Auto Next")) {{
                        buttons[i].click();
                        break;
                    }}
                }}
            }};

            // Sự kiện lỗi (Nếu gặp lỗi thì cũng tự Next luôn để không bị kẹt)
            window.utterance.onerror = function(event) {{
                console.log('Error occurred: ' + event.error);
                // Nếu lỗi không phải do hủy thủ công thì mới Next
                if (event.error !== 'interrupted') {{
                    var buttons = window.parent.document.getElementsByTagName('button');
                    for (var i = 0; i < buttons.length; i++) {{
                        if (buttons[i].innerText.includes("Auto Next")) {{
                            buttons[i].click();
                            break;
                        }}
                    }}
                }}
            }};

            // Thêm delay nhỏ 100ms để trình duyệt kịp thở
            setTimeout(function() {{
                window.speechSynthesis.speak(window.utterance);
                
                // FIX LỖI CHROME: Kích hoạt lại mỗi 10 giây để trình duyệt không ngủ gật
                if (window.speechInterval) clearInterval(window.speechInterval);
                window.speechInterval = setInterval(function() {{
                    if (!window.speechSynthesis.speaking) {{
                        clearInterval(window.speechInterval);
                    }} else {{
                        window.speechSynthesis.pause();
                        window.speechSynthesis.resume();
                    }}
                }}, 10000);
                
            }}, 100);
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
st.set_page_config(page_title="PDF Reader V21 (Fix)", layout="wide")

with st.sidebar:
    st.header("📂 Cài đặt")
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file:
    if 'current_page' not in st.session_state: st.session_state.current_page = 1
    if 'is_auto' not in st.session_state: st.session_state.is_auto = False

    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    total_pages = doc.page_count
    uploaded_file.seek(0)
    bytes_data = uploaded_file.read()

    col_vis, col_ctrl = st.columns([1.3, 1])

    # Cột Phải: Điều khiển
    with col_ctrl:
        st.subheader("🎛️ Bảng Điều Khiển")
        
        # Chọn trang
        col_input, col_total = st.columns([2, 1])
        with col_input:
            selected_page = st.number_input("Trang số:", 1, total_pages, st.session_state.current_page)
        with col_total:
            st.write(f" / {total_pages}")

        if selected_page != st.session_state.current_page:
            st.session_state.current_page = selected_page
            st.rerun()

        st.markdown("---")

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.session_state.is_auto:
                if st.button("⛔ DỪNG", type="primary", use_container_width=True):
                    components.html("<script>window.speechSynthesis.cancel(); clearInterval(window.speechInterval);</script>", height=0)
                    st.session_state.is_auto = False
                    st.rerun()
            else:
                if st.button("▶️ BẮT ĐẦU", use_container_width=True):
                    st.session_state.is_auto = True
                    st.rerun()
        
        with c2:
            if st.button("⏭️ Auto Next", use_container_width=True):
                if st.session_state.current_page < total_pages:
                    st.session_state.current_page += 1
                    st.session_state.is_auto = True
                    st.rerun()

    # Cột Trái: Ảnh
    img_show, text_content = get_page_content(bytes_data, st.session_state.current_page)
    with col_vis:
        if img_show: st.image(img_show, caption=f"Trang {st.session_state.current_page}", use_container_width=True)

    # Logic Đọc
    if st.session_state.is_auto:
        with col_ctrl:
            if text_content:
                st.toast(f"🔊 Đang đọc trang {st.session_state.current_page}...")
                speak_client_side(text_content, st.session_state.current_page)
                
                with st.expander("Văn bản"):
                    st.write(text_content)
            else:
                st.warning("Trang trắng. Chuyển tiếp...")
                time.sleep(1)
                if st.session_state.current_page < total_pages:
                    st.session_state.current_page += 1
                    st.rerun()
