# pdf_to_text.py
# PDF 파일에서 표와 줄바꿈을 보존하여 텍스트 추출

import os
import pdfplumber

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # 프로젝트 루트
input_dir = os.path.join(BASE_DIR, "data", "evaluation")

def extract_text_preserve_all(pdf_path: str, output_path: str = None):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"📂 파일이 존재하지 않습니다: {pdf_path}")

    full_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)

    result = "\n\n".join(full_text)

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"✅ 저장 완료: {output_path}")
    else:
        return result

if __name__ == "__main__":
    for filename in os.listdir(input_dir):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(input_dir, filename)
            txt_filename = filename.replace(".pdf", ".txt")
            txt_path = os.path.join(input_dir, txt_filename)
            extract_text_preserve_all(pdf_path, txt_path)
            print(f"📄 처리 완료: {filename} → {txt_filename}")
