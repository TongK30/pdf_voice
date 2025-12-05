import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
import edge_tts
import asyncio
import tempfile
import fitz  # PyMuPDF
from PIL import Image, ImageOps, ImageEnhance
import numpy as np

# --- ⚠️ CẤU HÌNH ĐƯỜNG DẪN CỦA BẠN (QUAN TRỌNG NHẤT) ---
# Hãy thay đúng đường dẫn trên máy bạn vào 2 dòng dưới đây
PATH_TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe' 
PATH_POPPLER = r'C:\Program Files\poppler\poppler-25.12.0\Library\bin' 

# Cấu hình hệ thống
pytesseract.pytesseract.tesseract_cmd = PATH_TESSERACT

# --- CẤU HÌNH GIỌNG ĐỌC ---
VOICES = {
    "Nữ - Hoài My": "vi-VN-HoaiMyNeural",
    "Nam - Nam Minh": "vi-VN-NamMinhNeural"
}

# --- HÀM XỬ LÝ ẢNH CAO CẤP ---
def preprocess_image(image):
    """
    Biến ảnh mờ/xám thành ảnh trắng đen siêu nét để AI dễ đọc
    """
    # 1. Chuyển sang ảnh xám (Grayscale)
    img_gray = image.convert('L')
    
    # 2. Tăng độ tương phản lên 2 lần
    enhancer = ImageEnhance.Contrast(img_gray)
    img_contrast = enhancer.enhance(2.0)
    
    # 3. Làm sạch nhiễu (Thresholding) - Biến những điểm mờ thành trắng hẳn, chữ thành đen hẳn
    # Ngưỡng 180: Ai sáng hơn 180 -> Trắng, Tối hơn -> Đen
    img_binary = img_contrast.point(lambda x: 0 if x < 160 else 255, '1')
    
    return img_binary

def process_pdf_v5(pdf_file_bytes, psm_mode):
    pages_data = []
    
    # Chế độ cấu hình Tesseract
    # --psm 3: Tự động (Mặc định)
    # --psm 6: Coi như một khối văn bản duy nhất (Rất tốt cho trang sách)
    # --psm 4: Coi như một cột văn bản
    custom_config = f'--oem 3 --psm {psm_mode}'
    
    st.toast("Đang chuyển đổi PDF sang Ảnh...", icon="🔄")
    try:
        # Tăng DPI lên 300 để ảnh nét căng
        images = convert_from_bytes(pdf_file_bytes, poppler_path=PATH_POPPLER, dpi=300)
    except Exception as e:
        st.error(f"Lỗi Poppler: {e}")
        return []

    total = len(images)
    my_bar = st.progress(0)

    for i, image in enumerate(images):
        # Bước 1: Xử lý ảnh (Làm nét)
        processed_img = preprocess_image(image)
        
        # Bước 2: Đọc chữ
        try:
            text = pytesseract.image_to_string(processed_img, lang='vie', config=custom_config)
        except Exception as e:
            text = f"Lỗi OCR: {e}"

        pages_data.append({
            'id': i+1, 
            'text': text, 
            'image_original': image,
            'image_processed': processed_img
        })
        my_bar.progress((i + 1) / total)
            
    return pages_data

async def generate_audio_chunk(text, voice_key, output_file):
    if not text or len(text.strip()) < 2:
        return False
    communicate = edge_tts.Communicate(text, VOICES[voice_key])
    await communicate.save(output_file)
    return True

# --- GIAO DIỆN NGƯỜI DÙNG ---
st.set_page_config(page_title="Super OCR Reader", layout="wide")
st.title("👁️ Đọc PDF Scan (Chế độ xử lý ảnh)")

with st.sidebar:
    st.header("🔧 Cấu hình nâng cao")
    
    # Cho phép người dùng chỉnh chế độ đọc nếu máy đọc sai
    psm_mode = st.selectbox(
        "Chế độ đọc (PSM):", 
        options=[3, 6, 4], 
        format_func=lambda x: f"Mode {x} - {'Tự động' if x==3 else 'Khối văn bản (Nên dùng cho sách)' if x==6 else 'Cột đơn'}",
        index=1 # Mặc định chọn Mode 6 vì tốt cho sách của bạn
    )
    
    st.info("Mẹo: Nếu đọc ra trang trống, hãy thử đổi Mode sang 3 hoặc 4.")
    
    selected_voice = st.selectbox("Giọng đọc:", list(VOICES.keys()))
    uploaded_file = st.file_uploader("Upload PDF", type="pdf")

if uploaded_file:
    # Logic chạy lại khi đổi file hoặc đổi chế độ
    if 'data_v5' not in st.session_state or \
       st.session_state.get('fname') != uploaded_file.name or \
       st.session_state.get('psm') != psm_mode:
           
        with st.spinner('Đang xử lý hình ảnh...'):
            bytes_data = uploaded_file.read()
            # Reset pointer
            uploaded_file.seek(0) 
            data = process_pdf_v5(bytes_data, psm_mode)
            st.session_state['data_v5'] = data
            st.session_state['fname'] = uploaded_file.name
            st.session_state['psm'] = psm_mode

    if 'data_v5' in st.session_state:
        data = st.session_state['data_v5']
        
        # Chọn trang
        col_sel, col_info = st.columns([1, 4])
        with col_sel:
            page_idx = st.number_input("Chọn trang:", min_value=1, max_value=len(data), value=1) - 1
        
        current_page = data[page_idx]

        # Hiển thị 3 cột: Ảnh gốc - Ảnh máy nhìn - Kết quả chữ
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.caption("Ảnh gốc")
            st.image(current_page['image_original'], use_container_width=True)
            
        with c2:
            st.caption("Ảnh máy nhìn thấy (Đã xử lý)")
            # Đây là ảnh quan trọng, nếu ảnh này đen sì là lỗi
            st.image(current_page['image_processed'], use_container_width=True) 

        with c3:
            st.caption("Kết quả chữ")
            txt_val = st.text_area("Chữ đọc được:", current_page['text'], height=300)
            
            if st.button("📢 Đọc ngay", type="primary"):
                if not txt_val.strip():
                    st.error("Chưa đọc được chữ nào!")
                else:
                    with st.spinner('Đang tạo âm thanh...'):
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                        asyncio.run(generate_audio_chunk(txt_val, selected_voice, tmp.name))
                        st.audio(tmp.name)