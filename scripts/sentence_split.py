# 텍스트 파일 문장 단위 분해

import os
import json

def split_sentences(text: str) -> list[str]:
    # 줄 단위로 분해 (표·개조식 포함)
    lines = text.strip().splitlines()
    return [line.strip() for line in lines if line.strip()]

def convert_txt_to_jsonl(txt_path: str, jsonl_path: str):
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()

    sentences = split_sentences(text)
    os.makedirs(os.path.dirname(jsonl_path), exist_ok=True)

    with open(jsonl_path, "w", encoding="utf-8") as out:
        for i, sentence in enumerate(sentences):
            json.dump({"id": i, "text": sentence}, out, ensure_ascii=False)
            out.write("\n")
    print(f"✅ 저장 완료: {jsonl_path}")

if __name__ == "__main__":
    input_dir = "data/evaluation"
    output_dir = "data/evaluation_split"
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if filename.endswith(".txt"):
            txt_path = os.path.join(input_dir, filename)
            jsonl_path = os.path.join(output_dir, filename.replace(".txt", ".jsonl"))
            convert_txt_to_jsonl(txt_path, jsonl_path)
            print(f"📄 처리 완료: {filename} → {jsonl_path}")