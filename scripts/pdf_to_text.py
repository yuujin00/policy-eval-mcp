# scripts/pdf_to_text.py
# Streamlit 평가 흐름에 맞춰 PDF → TXT 텍스트 추출 (함수형)
import os
import pdfplumber

def extract_text_preserve_all(pdf_path: str, output_path: str):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"파일이 존재하지 않습니다: {pdf_path}")

    full_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text.append(text)

    result = "\n\n".join(full_text)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"저장 완료: {output_path}")

if __name__ == "__main__":
    input_pdf = "data/evaluation/uploaded_policy.pdf"
    output_txt = "data/evaluation/uploaded_policy.txt"
    extract_text_preserve_all(input_pdf, output_txt)