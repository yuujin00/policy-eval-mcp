# run_pipeline.py
"""
전체 파이프라인을 순차 실행하는 스크립트
(터미널에서도, Streamlit sub-process에서도 동일하게 동작)
"""
import subprocess, sys, pathlib, datetime, os, textwrap, traceback

PY = sys.executable
ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULT_DIR = ROOT / "results"

# 오늘-시각을 이용해 고유 run_id 생성
run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
os.environ["RUN_ID"] = run_id          # 자식 프로세스도 읽도록
RESULT_PATH = RESULT_DIR / f"eval_{run_id}.jsonl"

# 실행 단계 – 필요하면 순서만 바꿔 주세요
STEPS = [
    ["scripts/pdf_to_text.py"],
    ["scripts/structured_split.py"],
    ["scripts/query_cross_reference.py"],
    ["scripts/run_privacy_eval.py", "--out", str(RESULT_PATH)],
]

LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"pipeline_{datetime.datetime.now():%Y%m%d_%H%M%S}.log"

def append_log(line: str) -> None:
    """로그 파일에 한 줄 추가(파일 없으면 자동 생성, UTF-8)"""
    with LOG_FILE.open("a", encoding="utf-8") as lf:
        lf.write(line + "\n")

def banner(msg: str) -> None:
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)          # 터미널·Streamlit 즉시 출력
    append_log(line)     # ↙︎ 파일 append (존재 여부와 무관)

# run_step 안에서도 LOG_FILE.read_text(...) 대신 append_log 사용
def run_step(cmd: list[str]):
    step_name = pathlib.Path(cmd[0]).stem
    banner(f"[STEP] 시작: {step_name}")
    completed = subprocess.run(
        [sys.executable, *cmd],
        text=True, capture_output=True
    )
    # ───────── 결과 정리 ─────────
    append_log(f">>> stdout({step_name})\n{completed.stdout}")
    append_log(f">>> stderr({step_name})\n{completed.stderr}")

    if completed.returncode == 0:
        banner(f"[STEP] 완료: {step_name}")
    else:
        banner(f"[STEP] 실패: {step_name}")
        raise subprocess.CalledProcessError(
            completed.returncode, cmd,
            output=completed.stdout, stderr=completed.stderr
        )

    
def main() -> None:
    banner("=== 파이프라인 시작 ===")
    print(f"RUN_ID={run_id}")  
    for cmd in STEPS:
        run_step(cmd)
    banner("=== 파이프라인 전체 완료 ===")

if __name__ == "__main__":          # ← 반드시 필요!
    main()
