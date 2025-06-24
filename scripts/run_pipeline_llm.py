# scripts/run_pipeline_llm.py
"""
LLM 기반 구조화 스텝을 사용하는 파이프라인
(pdf→llm_structured_extract→cross_reference→eval)
"""
import subprocess, sys, pathlib, datetime, os
PY = sys.executable
ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULT_DIR = ROOT / "results"

run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_llm"
os.environ["RUN_ID"] = run_id
result_path = RESULT_DIR / f"eval_{run_id}.jsonl"

STEPS = [
    ["scripts/llm_structured_extract.py"],          # ✅ 유일한 차이점
    ["scripts/query_cross_reference.py"],
    ["scripts/run_privacy_eval.py", "--out", str(result_path)],
]

def run(cmd):
    subprocess.check_call([PY, *cmd])

if __name__ == "__main__":
    for c in STEPS:
        run(c)
    print(f"파이프라인 완료: {result_path}")
    print(f"결과 파일 경로: {result_path}")