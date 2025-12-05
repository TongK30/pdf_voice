import sys
import os
import pytesseract
from pytesseract import get_languages

# --- CẤU HÌNH LẠI ĐƯỜNG DẪN CỦA BẠN VÀO ĐÂY ĐỂ TEST ---
tess_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
poppler_path = r'C:\Program Files\poppler\poppler-25.12.0\Library\bin'
# ------------------------------------------------------

print("--- BẮT ĐẦU KIỂM TRA HỆ THỐNG ---")

# 1. Kiểm tra file tesseract.exe
if os.path.exists(tess_path):
    print(f"✅ Đã tìm thấy Tesseract tại: {tess_path}")
    pytesseract.pytesseract.tesseract_cmd = tess_path
    
    # Kiểm tra ngôn ngữ
    try:
        langs = get_languages(config='')
        print(f"   Các ngôn ngữ đã cài: {langs}")
        if 'vie' in langs:
            print("   ✅ Đã có tiếng Việt (vie)!")
        else:
            print("   ❌ CHƯA CÓ TIẾNG VIỆT! (Lỗi là do đây)")
            print("   -> Hãy cài lại Tesseract và tích chọn Vietnamese.")
    except Exception as e:
        print(f"   ❌ Lỗi khi gọi Tesseract: {e}")
else:
    print(f"❌ Không tìm thấy file Tesseract tại: {tess_path}")
    print("   -> Hãy kiểm tra lại đường dẫn.")

# 2. Kiểm tra Poppler
if os.path.exists(poppler_path):
    print(f"✅ Đã tìm thấy thư mục Poppler tại: {poppler_path}")
    pdftoppm = os.path.join(poppler_path, 'pdftoppm.exe')
    if os.path.exists(pdftoppm):
        print("   ✅ Đã tìm thấy file pdftoppm.exe (Poppler ngon lành).")
    else:
        print("   ❌ Thư mục đúng nhưng không thấy file exe. Bạn có giải nén đúng không?")
else:
    print(f"❌ Không tìm thấy thư mục Poppler tại: {poppler_path}")

print("--- KẾT THÚC ---")