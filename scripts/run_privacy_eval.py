"""
run_privacy_eval.py
───────────────────
① 지침 PDF 업로드 (최초 1회)
② Assistant 없으면 생성 → .cache/assistant.json 저장
③ results/cross_reference.json  평가 → results/eval_result.jsonl
"""

import os, json, time
from pathlib import Path
from openai import OpenAI

### 경로 설정 ###############################################################
PDF_PATH     = "data/policies/개인정보_처리방침_작성지침_2025.4..pdf"
CROSS_FILE   = "results/cross_reference.json"
OUT_FILE     = "results/eval_result.jsonl"
CACHE_FILE   = Path("scripts/.cache/assistant.json")      # ID 보관
MODEL        = "gpt-4o-mini"                              # 필요시 변경
#############################################################################

client = OpenAI()

# ───────────────────────────────────────────────────────────────────────────
# 1) 캐시(어시스턴트 ID) 있나 확인
# ───────────────────────────────────────────────────────────────────────────
if CACHE_FILE.exists():
    cache = json.loads(CACHE_FILE.read_text())
    assistant_id = cache["assistant_id"]
    file_id      = cache["file_id"]
    print(f"♻️  기존 Assistant 재사용: {assistant_id}")
else:
    CACHE_FILE.parent.mkdir(exist_ok=True)        # scripts/.cache 생성
    # 1-A. PDF 업로드
    print("⬆️  PDF 업로드 중 …")
    f = client.files.create(file=open(PDF_PATH, "rb"), purpose="assistants")
    file_id = f.id
    # 1-B. 어시스턴트 생성
    system_prompt = """
    당신은 「개인정보 처리방침 작성지침(2025.4.)」을 가이드라인을 참고하여
    cross_reference.json에 있는 평가 문장을 심사하는 전문가입니다.
    − ‘similar_laws’ 필드를 최우선 근거로, PDF는 Retrieval 로 찾아 인용하세요.
    − 반드시 JSON 한 줄만 출력합니다.
    """.strip()
    ast = client.beta.assistants.create(
        name         ="Privacy-Policy Evaluator (KR-2025)",
        model        = MODEL,
        instructions = system_prompt,
        tools        =[{"type":"retrieval"}],
        file_ids     =[file_id],
    )
    assistant_id = ast.id
    # 캐시 저장
    CACHE_FILE.write_text(json.dumps({
        "assistant_id": assistant_id,
        "file_id"     : file_id
    }))
    print(f"✅ Assistant 생성: {assistant_id}")

# ───────────────────────────────────────────────────────────────────────────
# 2) 헬퍼 – Assistant 실행
# ───────────────────────────────────────────────────────────────────────────
def ask_assistant(content: str) -> str:
    thread = client.beta.threads.create(
        messages=[{"role":"user","content":content}]
    )
    run = client.beta.threads.runs.create(
        thread_id   =thread.id,
        assistant_id=assistant_id,
        model       =MODEL
    )
    while run.status not in ("completed","failed","cancelled"):
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(thread.id, run.id)
    if run.status!="completed":
        raise RuntimeError(f"Run {run.status}")
    msg = client.beta.threads.messages.list(thread.id).data[0]
    return msg.content[0].text.value.strip()

# ───────────────────────────────────────────────────────────────────────────
# 3) cross_reference.json → 평가 루프
# ───────────────────────────────────────────────────────────────────────────
Path("results").mkdir(exist_ok=True)

with open(CROSS_FILE, encoding="utf-8") as fin, \
     open(OUT_FILE , "w",         encoding="utf-8") as fout:

    for line in fin:
        r = json.loads(line)
        eid  = r["eval_id"]
        sent = r["eval_sentence"]
        laws = r.get("similar_laws", [])

        prompt = f"""
평가 문장
---------
{sent}

유사_법령
---------
{json.dumps(laws, ensure_ascii=False, indent=2)}

평가 양식
---------
1. 필수 항목 여부 (Y / N / 판단불가)
2. 형식 적절성     (적절 / 부적절 / 판단불가)
3. 내용 적절성     (적절 / 과도함 / 판단불가)
4. 1–3번 근거      (간단+인용)
JSON 한 줄로만 답하라.
""".strip()

        try:
            res = ask_assistant(prompt)
        except Exception as e:
            res = json.dumps({"error": str(e)}, ensure_ascii=False)

        fout.write(json.dumps({
            "eval_id"   : eid,
            "evaluation": res
        }, ensure_ascii=False) + "\n")
        print(f"📝 {eid} 완료")

print(f"\n🎉  결과 파일 → {OUT_FILE}")
