# PDF 파일에서 표와 줄바꿈을 보존하여 텍스트 추출

import os
import pdfplumber

def extract_text_preserve_all(pdf_path: str, output_path: str = None):
    """
    표·줄바꿈 보존 포함 전체 텍스트 추출
    """
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
    # 📌 자동화 경로: evaluation/ 폴더 안의 모든 PDF 파일을 텍스트로 변환
    input_dir = "data/evaluation"
    for filename in os.listdir(input_dir):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(input_dir, filename)
            txt_filename = filename.replace(".pdf", ".txt")
            txt_path = os.path.join(input_dir, txt_filename)
            extract_text_preserve_all(pdf_path, txt_path)
            print(f"📄 처리 완료: {filename} → {txt_filename}")