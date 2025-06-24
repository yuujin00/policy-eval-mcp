# scripts/run_privacy_eval.py
# LLM을 이용한 평가 수행

import os
import json
import time
import logging
import datetime as dt
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import argparse   

load_dotenv()


ts = dt.datetime.now().strftime("%y%m%d_%H%M%S")
default_out = f"results/eval_result_{ts}.jsonl"

# ---------------- CLI 인자 파싱 ----------------
parser = argparse.ArgumentParser()
parser.add_argument("--pdf",
    default="data/policies/개인정보 처리방침 작성지침(2025.4.).pdf")
parser.add_argument("--criteria",
    default="data/evaluation_criteria.json")
parser.add_argument("--cross",
    default="results/policy_structured_cross_reference.jsonl")
parser.add_argument("--out", default=default_out)
parser.add_argument("--model",
    default="gpt-4o-mini")
args = parser.parse_args()
# ----------------------------------------------

#############################################################################
# 경로 및 상수 (오직 *한 번*만 선언)
#############################################################################
PDF_PATH      = args.pdf
CRITERIA_FILE = args.criteria
CROSS_FILE    = args.cross
OUT_FILE      = args.out
MODEL         = args.model
CACHE_FILE    = Path("scripts/.cache/assistant.json")
#############################################################################


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("scripts/privacy_eval.log", encoding="utf-8"),
              logging.StreamHandler()]
)

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

#############################################################################
# 1) Assistant 캐시 확인 및 생성
#############################################################################
if CACHE_FILE.exists():
    cache = json.loads(CACHE_FILE.read_text())
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
    client.vector_stores.file_batches.create(vector_store_id=vs_id, file_ids=[file_id])

    system_prompt = Path("scripts/system_prompt_ko.txt").read_text(encoding="utf-8")
    ast = client.beta.assistants.create(
        name="Privacy-Policy Evaluator (KR-2025)",
        model=MODEL,
        instructions=system_prompt,
        tools=[{"type": "file_search"}],
        tool_resources={"file_search": {"vector_store_ids": [vs_id]}}
    )
    assistant_id = ast.id
    CACHE_FILE.write_text(json.dumps({"assistant_id": assistant_id}))
    logging.info(f"✅ Assistant 생성: {assistant_id}")

#############################################################################
# 2) 평가 실행 함수
#############################################################################
REF_MAP = {
    "privacy-act": "법",
    "privacy-law": "법",
    "privacy-decree": "영",
    "privacy-notification": "고시",
}

def _map_sources(obj):
    for item in obj.get("근거", []):
        item["출처"] = REF_MAP.get(item.get("출처", ""), item.get("출처", ""))
    return obj

def ask_assistant(content, retries=2):
    for attempt in range(retries + 1):
        thread = client.beta.threads.create(messages=[{"role": "user", "content": content}])
        run = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant_id)

        while run.status not in {"completed", "failed", "cancelled"}:
            time.sleep(0.4)
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

        if run.status != "completed":
            raise RuntimeError(f"Run {run.status}")

        msg = client.beta.threads.messages.list(thread.id).data[0]
        raw = msg.content[0].text.value.strip()

        try:
            obj = json.loads(raw)
            obj = _map_sources(obj)
            required = {"항목", "level", "준수", "법령_적합성","지침_적합성", "판단_사유", "근거"}
            if not required.issubset(obj):
                raise ValueError("키 누락")
            return raw
        except Exception as e:
            logging.warning(f"JSON 파싱 실패 attempt={attempt}: {e}")
            if attempt == retries:
                sanitized = raw.replace("\n", " ")
                raise RuntimeError(f"assistant output parse failed: {sanitized}")
            content = "형식 오류가 있었습니다. 이전 지침을 준수하여 JSON 한 줄로만 재출력하세요.\n\n" + content

#############################################################################
# 3) 평가 루프 실행
#############################################################################
criteria_data = json.loads(Path(CRITERIA_FILE).read_text(encoding="utf-8"))
criteria_json = json.dumps(criteria_data, ensure_ascii=False, indent=2)
Path("results").mkdir(exist_ok=True)

with open(CROSS_FILE, encoding="utf-8") as fin, open(OUT_FILE, "w", encoding="utf-8") as fout:
    for line in fin:
        if not line.strip():
            continue
        r = json.loads(line)
        eid = r["eval_id"]
        title = r["eval_title"]
        sent = r["eval_sentence"]
        laws = r.get("similar_laws", [])

        prompt = f"""【평가 문장】\n{sent}\n\n【similar_laws】\n{json.dumps(laws, ensure_ascii=False, indent=2)}\n\n【evaluation_criteria.json】\n{criteria_json}\n\n위 정보를 참고하여 system_prompt 규격대로 JSON 한 줄로만 출력."""

        try:
            res = ask_assistant(prompt)
            obj = json.loads(res)
            status = "ok"
            err = ""
        except Exception as e:
            obj = {}
            status = "error"
            err = str(e)
            res = ""
            logging.error(f"【평가 문장】{eid} 실패: {e}")

        fout.write(json.dumps({
            "eval_id": eid,
            "sentence": sent,
            "status": status,
            "result": obj,
            "raw": res,
            "error": err
        }, ensure_ascii=False) + "\n")
        logging.info(f"【평가 문장】 {eid} → {status}")

logging.info("평가 완료: 결과 저장됨")