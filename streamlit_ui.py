"""
개인정보처리방침 자동 평가 시스템 – Streamlit UI
두 가지 파이프라인(원본 / LLM) 중 원하는 것을 실행‧비교할 수 있다.

※ 파일 구조(기존 그대로 사용)
├─ scripts/run_pipeline.py          (원본 : pdf→rule‑based split)
├─ scripts/run_pipeline_llm.py      (새   : pdf→llm_structured_extract)
└─ results/eval_20250101_120000[_llm].jsonl
"""

from __future__ import annotations
import streamlit as st
import subprocess, sys, time, json, os
from pathlib import Path
from collections import defaultdict
import pandas as pd
from utils.report_docx import generate_report as make_report

# ────────────────── 기본 설정 ──────────────────
st.set_page_config(page_title="개인정보처리방침 결과", layout="wide")
st.title("🔍 개인정보처리방침 자동 평가 시스템")

UPLOAD_PATH  = Path("data/evaluation/uploaded_policy.pdf")
RESULT_DIR   = Path("results")
CRITERIA_PATH= Path("data/evaluation_criteria.json")

# ────────────────── 1. PDF 업로드 ──────────────────
pdf_file = st.file_uploader("📄 개인정보 처리방침 PDF 업로드", type="pdf")
if pdf_file:
    UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_PATH.write_bytes(pdf_file.read())
    st.success("✅ PDF 업로드 완료 – 파이프라인을 선택해 실행하세요!")

# ────────────────── 2. 파이프라인 실행 ──────────────────
col1, col2 = st.columns(2)
with col1:
    btn_orig = st.button("🚀 원본 파이프라인 실행", disabled=pdf_file is None)
with col2:
    btn_llm  = st.button("🤖 LLM 파이프라인 실행",  disabled=pdf_file is None)

# 공통 실행 함수 --------------------------------------------------------------

def run_pipeline(script: str, tag: str):
    """script 를 서브 프로세스로 실행하며 로그를 실시간 표시한다."""
    with st.status(f"🧠 **{tag}** 파이프라인 동작 중…", expanded=True) as status:
        log_box = st.empty()
        proc = subprocess.Popen(
            [sys.executable, script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for ln in proc.stdout:
            log_box.text(ln.rstrip())
        proc.wait()

        if proc.returncode==0:
            status.update(state="complete", expanded=False)
            st.success("🎉 파이프라인이 정상 종료되었습니다!")
            # 최근 실행 모드 기억 → 새로고침 후 바로 결과 표시
            st.session_state["last_mode"] = tag
        else:
            status.update(state="error", expanded=True)
            st.error("❌ 파이프라인 실행 중 오류가 발생했습니다.")
            st.stop()
    time.sleep(1); st.rerun()

if btn_orig:
    run_pipeline("scripts/run_pipeline.py", "orig")
if btn_llm:
    run_pipeline("scripts/run_pipeline_llm.py", "llm")

# ────────────────── 3. 결과 표시 ──────────────────
# 3‑1  결과 파일 탐색 함수 -----------------------------------------------------

def latest_result(tag: str) -> Path|None:
    pattern = f"eval_*{'_llm' if tag=='llm' else ''}.jsonl"
    files   = sorted(RESULT_DIR.glob(pattern), reverse=True)
    return files[0] if files else None

# 3‑2  선택 UI / 기본 선택 ------------------------------------------------------
mode = st.radio("🔎 확인할 결과", ("orig","llm"), format_func=lambda m: "원본" if m=="orig" else "LLM", index=(0 if st.session_state.get("last_mode","orig")=="orig" else 1))
result_path = latest_result(mode)

if not result_path:
    st.info("아직 실행된 결과가 없습니다.")
    st.stop()

st.info(f"결과 파일: {result_path.name}")

records: list[dict]
with result_path.open(encoding="utf-8") as f:
    records = [json.loads(l) for l in f if l.strip()]

st.success(f"총 {len(records)}개 문장 평가 (mode = {mode})")

for rec in records:
    ok = rec.get("status") == "ok"
    header = f"📝 ID {rec['eval_id']} – {'✅ 분석 성공' if ok else '❌ 분석 실패'}"
    with st.expander(header):
        st.markdown(f"**문장**\n\n{rec['sentence']}")
        if ok:
            st.json(rec.get("result", {}))
        else:
            st.error(rec.get("error", ""))

# ────────────────── 4. 항목별 요약 테이블 ──────────────────
crit_raw = json.loads(CRITERIA_PATH.read_text(encoding="utf-8"))
criteria = crit_raw["criteria"] if isinstance(crit_raw, dict) else crit_raw
criteria_list  = [c for c in criteria if isinstance(c, dict) and "id" in c]

id_map = {}
for c in criteria_list:
    try:
        cid = int(c["id"])          # "01" → 1
    except (ValueError, TypeError):
        continue                    # 숫자가 아니면 건너뜀
    title = c["title"].strip()      # 앞뒤 공백 제거
    id_map[cid] = (f"{cid:02d}. {title}", c.get("level", ""))

title_to_id = {title: cid for cid, (title, _) in id_map.items()}

# ① records 에 dict 아닌 요소 제거
records = [r for r in records if isinstance(r, dict)]

# ② 항목별 결과 집계 (id 기준)
from collections import defaultdict
bucket = defaultdict(list)
for r in records:
    res = r.get("result", {})
    raw_key = res.get("항목")               # '01. …' 또는 정수 id
    key_id  = raw_key if isinstance(raw_key, int) else title_to_id.get(raw_key)
    if key_id is None:                      # 기준표에 없는 값이면 건너뜀
        continue
    bucket[key_id].append((res.get("준수"), r.get("eval_id")))

summary = {"항목": [], "level": [], "준수": [], "문장ID": [], "비고": []}

for cid in sorted(id_map):
    title, lvl = id_map[cid]
    hits = bucket.get(cid, [])

    # ① 준수 값 • eval_id 모두 공백 제거
    clean_hits = [((h or "").strip(), str(i or "").strip()) for h, i in hits]

    # ② 중복 제거 후 정렬 → "O,X" / "X" …
    statuses = sorted({h for h, _ in clean_hits if h})
    comp     = ",".join(statuses)

    # ③ 문장 ID (공백·None 제외)
    ids = ",".join(i for _, i in clean_hits if i)

    has_x = "X" in statuses

    r1 = "필수기재위반"     if lvl.startswith("필수") and not ids else ""
    r2 = "해당여부판단필요" if lvl.startswith("해당시") and not ids else ""
    r3 = "처리방침변경필요" if has_x else ""
    remark = ",".join(t for t in (r1, r2, r3) if t)

    summary["항목"].append(title)
    summary["level"].append(lvl)
    summary["준수"].append(comp)      # ← 이제 X 도 정확히 보임
    summary["문장ID"].append(ids)     # ← 문장 ID 도 사라지지 않음
    summary["비고"].append(remark)
    
df = pd.DataFrame(summary)
st.subheader("📊 처리방침 기재항목별 요약")
st.dataframe(df, use_container_width=True)

# ────────────────── 5. Word 보고서 다운로드 ──────────────────
_tmp = Path("_tmp_report.docx")
make_report(records, UPLOAD_PATH.name if UPLOAD_PATH.exists() else "uploaded_policy.pdf", _tmp)
with _tmp.open("rb") as f:
    st.download_button(
        "📥 Word 보고서 다운로드",
        data=f.read(),
        file_name=f"{result_path.stem}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
_tmp.unlink(missing_ok=True)
