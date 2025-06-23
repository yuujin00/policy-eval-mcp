import os, json, time, logging
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from difflib import SequenceMatcher

load_dotenv()          # .env 읽어서 os.environ 에 주입

"""Privacy‑policy cross‑reference evaluator ‑ 2025‑KR
-----------------------------------------------------
🔧 2025‑06 수정 (OpenAI SDK ≥ 1.18)
  • Retrieval → file_search + vector‑store 구조 반영
  • eval_title → mapped_title → 항목 고정 평가 구조로 변경
"""

#############################################################################
# 경로 및 상수
#############################################################################
PDF_PATH      = "data/policies/개인정보 처리방침 작성지침(2025.4.).pdf"
CRITERIA_FILE = "data/evaluation_criteria.json"
CROSS_FILE    = "results/KISA_structured_cross_reference.jsonl"
OUT_FILE      = "results/eval_result.jsonl"
CACHE_FILE    = Path("scripts/.cache/assistant.json")
MODEL         = "gpt-4o-mini"
#############################################################################

# 로깅 ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("privacy_eval.log", encoding="utf-8"),
              logging.StreamHandler()]
)

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

#############################################################################
# 1) 캐시 확인 ‑ Assistant / Vector‑store 재사용
#############################################################################
if CACHE_FILE.exists():
    cache        = json.loads(CACHE_FILE.read_text())
    assistant_id = cache["assistant_id"]
    logging.info(f"♻️  기존 Assistant 재사용: {assistant_id}")
else:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    logging.info("⬆️  PDF 업로드 중 …")
    uploaded = client.files.create(file=open(PDF_PATH, "rb"), purpose="assistants")
    file_id = uploaded.id

    logging.info("🗂️  Vector-store 생성 …")
    vs = client.vector_stores.create(name="privacy-guide-2025")
    vs_id = vs.id

    client.vector_stores.file_batches.create(
        vector_store_id=vs_id,
        file_ids=[file_id],
    )

    system_prompt = Path("scripts/system_prompt_ko.txt").read_text(encoding="utf-8")

    ast = client.beta.assistants.create(
        name="Privacy-Policy Evaluator (KR-2025)",
        model=MODEL,
        instructions=system_prompt,
        tools=[{"type": "file_search"}],
        tool_resources={
            "file_search": {
                "vector_store_ids": [vs_id]
            }
        }
    )
    assistant_id = ast.id

    CACHE_FILE.write_text(json.dumps({
        "assistant_id": assistant_id
    }))
    logging.info(f"✅ Assistant 생성: {assistant_id}")

#############################################################################
# 2) 유사한 항목 매핑
#############################################################################
def find_closest_title(title: str, criteria_list: list[str]) -> str:
    def similarity(a, b):
        return SequenceMatcher(None, a, b).ratio()
    return max(criteria_list, key=lambda x: similarity(title, x))

criteria_data = json.loads(Path(CRITERIA_FILE).read_text(encoding="utf-8"))
criteria_map = {c["title"]: c["description"] for c in criteria_data}
criteria_titles = list(criteria_map.keys())

#############################################################################
# 3) Assistant 호출 함수
#############################################################################
def ask_assistant(prompt: str, retries: int = 2) -> str:
    for attempt in range(retries + 1):
        thread = client.beta.threads.create(messages=[{"role": "user", "content": prompt}])
        run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant_id)

        while run.status not in {"completed", "failed", "cancelled"}:
            time.sleep(0.4)
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

        if run.status != "completed":
            raise RuntimeError(f"Run {run.status}")

        msg = client.beta.threads.messages.list(thread.id).data[0]
        raw = msg.content[0].text.value.strip()
        try:
            return json.loads(raw)
        except Exception as e:
            logging.warning(f"⚠️ JSON 파싱 실패 attempt={attempt}: {e}")
            if attempt == retries:
                raise RuntimeError(f"Output parse failed: {raw.replace('\n', ' ')}")
            prompt = "형식 오류가 있었습니다. JSON 한 줄로 재출력하세요.\n\n" + prompt

#############################################################################
# 4) 평가 루프
#############################################################################
Path("results").mkdir(exist_ok=True)

with open(CROSS_FILE, encoding="utf-8") as fin, open(OUT_FILE, "w", encoding="utf-8") as fout:
    for line in fin:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        eid = r["eval_id"]
        title = r["eval_title"]
        sent = r["eval_sentence"]

        mapped_title = find_closest_title(title, criteria_titles)
        description = criteria_map[mapped_title]

        prompt = f"""다음 문장을 기준으로 아래 항목의 기준에 따라 평가하세요.

【항목】{mapped_title}
【기준 설명】{description}
【문장】{sent}

결과는 다음 항목으로 JSON 한 줄로 출력하세요:
- level: 적절 / 미흡 / 없음
- 판단_사유: 평가 근거
- 기재: O / △ / X
"""

        try:
            obj = ask_assistant(prompt)
            status = "ok"
            err = ""
        except Exception as e:
            obj = {}
            status = "error"
            err = str(e)
            logging.error(f"❌ {eid} 실패: {e}")

        fout.write(json.dumps({
            "eval_id": eid,
            "title": mapped_title,
            "status": status,
            "result": obj,
            "error": err
        }, ensure_ascii=False) + "\n")
        logging.info(f"📝 {eid} → {status}")
