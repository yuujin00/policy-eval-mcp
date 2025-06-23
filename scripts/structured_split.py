# structured_split.py
# pdf 파일에서 추출한 텍스트를 구조화된 JSONL 형식으로 분할 저장
# 2번
import os
import re
import json

# ✅ 경로 설정
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
input_dir = os.path.join(ROOT_DIR, "data", "evaluation")
output_dir = os.path.join(ROOT_DIR, "data", "evaluation_structured")
os.makedirs(output_dir, exist_ok=True)

def process_file(input_path: str, output_path: str):
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    lines = text.splitlines()
    chunks = []

    # ✅ 00. 제목/서론
    toc_start = next((i for i, line in enumerate(lines) if "목차" in line), None)
    if toc_start:
        head_text = "\n".join(lines[:toc_start]).strip()
        if head_text:
            chunks.append({
                "id": "00",
                "title": "제목",
                "text": head_text
            })
    else:
        toc_start = 0

    # ✅ 01. 목차 추출 (두 줄 이상도 포함)
    toc_lines = []
    i = toc_start + 1
    while i < len(lines):
        line = lines[i].strip()
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""

        if re.match(r"^\d{1,2}\.\s", line):
            # 다음 줄도 제목처럼 보이면 합침
            if (not re.match(r"^\d{1,2}\.\s", next_line)) and next_line and len(next_line) < 60 and not re.search(r'[.가-힣]{3,}', next_line):
                toc_lines.append(f"{line} {next_line}")
                i += 2
                continue
            else:
                toc_lines.append(line)
        elif re.match(r"^\d{1,2}\.\s", next_line):
            pass
        else:
            break
        i += 1

    toc_end_pos = i

    if toc_lines:
        chunks.append({
            "id": "01",
            "title": "목차",
            "text": "\n".join(toc_lines)
        })

    # ✅ 본문 항목 추출
    main_text = "\n".join(lines[toc_end_pos:])
    main_pattern = re.compile(r'(?m)^(\d{1,2})\.\s+(.+)')
    main_matches = list(main_pattern.finditer(main_text))

    for idx, match in enumerate(main_matches):
        start = match.start()
        end = main_matches[idx + 1].start() if idx + 1 < len(main_matches) else len(main_text)
        chunk_text = main_text[start:end].strip()
        title_text = match.group(2).strip().splitlines()[0]
        chunks.append({
            "id": match.group(1).zfill(2),
            "title": title_text,
            "text": chunk_text
        })

    # ✅ 저장
    with open(output_path, "w", encoding="utf-8") as f_out:
        for item in chunks:
            json.dump(item, f_out, ensure_ascii=False)
            f_out.write("\n")

    print(f"✅ 저장 완료: {output_path}")
    print(f"📄 총 {len(chunks)}개의 항목을 저장했습니다.")

# ✅ 폴더 내 모든 txt 처리
if __name__ == "__main__":
    for filename in os.listdir(input_dir):
        if filename.endswith(".txt"):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename.replace(".txt", "_structured.jsonl"))
            process_file(input_path, output_path)
            print(f"📄 처리 완료: {filename} → {output_path}")
