# scripts/llm_structured_extract.py
# 파일을 LLM을 이용해 구조화된 JSON Lines로 추출하는 스크립트

import os, json, logging, pdfplumber, re, textwrap, time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# ── 설정값 ────────────────────────────────────────
PDF_PATH   = Path("data/evaluation/uploaded_policy.pdf")
OUT_FILE   = Path("results/policy_structured_llm.jsonl")
MODEL      = "gpt-4o-mini"
MAX_CHARS  = 15_000          # 한 번에 보내는 원문 길이(≈ 토큰 5k)
OVERLAP    = 2_000           # 윈도우 겹침(문단 잘림 방지)
# ────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# ① PDF 전체를 텍스트로
with pdfplumber.open(PDF_PATH) as pdf:
    plain = "\n".join(p.extract_text() or "" for p in pdf.pages)

# ② 긴 문서를 슬라이딩 윈도우로 분할
chunks = []
start = 0
while start < len(plain):
    end = start + MAX_CHARS
    chunk = plain[start:end]
    chunks.append(chunk)
    start = end - OVERLAP                # 조금 겹치게 이동

logging.info(f"PDF 분할: {len(chunks)}개 청크")

OUT_FILE.parent.mkdir(exist_ok=True)
OUT_FILE.write_text("", encoding="utf-8")   # 결과 초기화

def build_prompt(doc_txt:str) -> str:
    """규칙 + 원문 합친 프롬프트 생성"""
    return textwrap.dedent(f"""
    다음 문서는 한 회사의 개인정보 처리방침 전문/일부분입니다.

    =========
    {doc_txt}
    =========

    LM-용 프롬프트 ―
    <원본 문서>를 ‘항목’(=대제목 1개 + 그에 속한 본문) 단위로 잘라
    id·title·text 3개 필드를 갖는 **JSON Lines** 형태(줄마다 1 JSON)로만 출력하십시오.

    꼴 JSON 한 줄만 항목 수 만큼 연속 출력하십시오.  
    그 외 설명·주석·코드블록·빈 줄 등 부가 텍스트는 절대 작성하지 마십시오.

    [규칙]
    id  : 두 자리 연속번호(01, 02, …)  
    title: 항목 제목(띄어쓰기·번호 등 원문 그대로 보존)  
    text : 해당 제목 아래 본문 전체(줄바꿈 포함)  

    [출력예시]  ※ 따옴표는 전부 ASCII " 사용
    {{"id":"01","title":"개인정보의 처리 목적","text":"…"}}
    """)

# ③ 각 청크별로 LLM 호출 & JSONL 저장
for idx, chunk in enumerate(chunks, 1):
    logging.info(f"청크 {idx}/{len(chunks)} 처리 중…")
    prompt = build_prompt(chunk)

    resp = client.chat.completions.create(
        model       = MODEL,
        temperature = 0,
        messages    = [{"role":"user","content":prompt}],
    )
    answer = resp.choices[0].message.content.strip()

    # 후처리: LLM 이 규칙 위반한 줄 제거 → id,title,text 들어간 행만 남김
    valid_lines = [ln for ln in answer.splitlines()
                   if re.fullmatch(r'\{.*"id".*"title".*"text".*\}', ln)]
    with OUT_FILE.open("a", encoding="utf-8") as f:
        for line in valid_lines:
            f.write(line.rstrip() + "\n")

logging.info(f"✅ 추출 완료 → {OUT_FILE}")
