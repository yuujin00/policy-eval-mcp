import streamlit as st, subprocess, sys, time, json, os
from pathlib import Path
from utils.report_docx import generate_report as make_report 
import io
import pandas as pd 

st.set_page_config(page_title="개인정보처리방침 결과", layout="wide")
st.title("🔍 개인정보처리방침 자동 평가 시스템")

UPLOAD_PATH = Path("data/evaluation/uploaded_policy.pdf")
RESULT_DIR   = Path("results")

# ────────────────────────────────────────────────
# PDF 업로드
# ────────────────────────────────────────────────
pdf_file = st.file_uploader("📄 개인정보 처리방침 PDF 업로드", type="pdf")

if pdf_file is not None:
    UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_PATH.write_bytes(pdf_file.read())
    st.success("✅ PDF 업로드 완료 – [평가 실행] 버튼을 눌러 주세요!")

# ────────────────────────────────────────────────
# 파이프라인 실행
# ────────────────────────────────────────────────

run_btn = st.button("🚀 평가 실행", disabled=(pdf_file is None))

if run_btn:
    # 실시간 로그 스트리밍 영역
    with st.status("🧠 파이프라인 동작 중… (몇 분 걸릴 수 있습니다)", expanded=True) as status:
        log_box = st.empty()        # log 한 줄씩 업데이트할 placeholder

        # **현재 파이썬**으로 run_pipeline.py 호출!
        proc = subprocess.Popen(
            [sys.executable, "scripts/run_pipeline.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        # 표준출력 실시간 표시
        for line in proc.stdout:
            log_box.text(line.rstrip())

        proc.wait()

        if proc.returncode == 0:
            status.update(state="complete", expanded=False)
            st.success("🎉 파이프라인이 정상 종료되었습니다!")
        else:
            status.update(state="error", expanded=True)
            st.error("❌ 파이프라인 실행 중 오류가 발생했습니다.")
            st.stop()               # 이후 UI 렌더링 중단

    # 로그 flush & 결과파일 생성 대기
    time.sleep(1)
    st.rerun()         # 새로고침

# ────────────────────────────────────────────────
# 결과 표시
# ────────────────────────────────────────────────
run_id = st.session_state.get("run_id")
if run_id:
    result_path = RESULT_DIR / f"eval_{run_id}.jsonl"
else:                               # 페이지 새로 열린 상태라면 가장 최근 결과
    candidates = sorted(RESULT_DIR.glob("eval_*.jsonl"), reverse=True)
    result_path = candidates[0] if candidates else None

if result_path and result_path.exists():
    st.info(f"결과 파일: {result_path.name}")

    with result_path.open(encoding="utf-8") as f:
        records = [json.loads(l) for l in f if l.strip()]

    st.success(f"총 {len(records)}개 문장 평가")
    
    for rec in records:
        with st.expander(f"📝 ID {rec['eval_id']} – {'✅분석 성공' if rec['status']=='ok' else '❌분석 실패'}"):
            st.markdown(f"**문장**\n\n{rec['sentence']}")
            if rec['status']=="ok":
                st.json(rec['result'])
            else:
                st.error(rec.get('error',''))
    
    # ── 항목별 요약 테이블 생성 ─────────────────
    crit_path = Path("data/evaluation_criteria.json")

    with crit_path.open(encoding="utf-8") as f:
        raw = json.load(f)

    # 파일 최상단이 dict이면 "criteria" 키 안의 리스트를 사용
    criteria_list = raw["criteria"] if isinstance(raw, dict) else raw
    # dict 요소만 남기기
    criteria_list = [c for c in criteria_list if isinstance(c, dict) and "id" in c]

    # ── id ↔ (표시제목, level) 매핑 ─────────────────
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

    # ③ 요약표 생성
    summary = {
        "항목": [],
        "level": [],
        "기재여부": [],
        "문장ID": [],
        "비고": [],               # ← 새 컬럼
    }

    for _id in sorted(id_map):          # 1 → 24 순서
        name, lvl = id_map[_id]
        hits = bucket.get(_id, [])
        compliances = ",".join(c for c, _ in hits)
        ids         = ",".join(str(i) for _, i in hits)

        # 필수 항목인데 문장ID가 없으면 위반 표시
        if lvl.strip().startswith("필수") and not ids:
            remark = "필수기재위반"
        else:
            remark = ""                 # 나머지는 공란

        summary["항목"].append(name)
        summary["level"].append(lvl)
        summary["기재여부"].append(compliances)
        summary["문장ID"].append(ids)
        summary["비고"].append(remark)   # ← 추가

    
    df_summary = pd.DataFrame(summary)
    st.subheader("📊 처리방침 기재항목별 요약")
    st.dataframe(df_summary, use_container_width=True)

    # ───────── Word 보고서 다운로드
    tmp_doc = Path("_tmp_report.docx")
    make_report(records, UPLOAD_PATH.name, tmp_doc)   # ← 인자 3개
    with tmp_doc.open("rb") as f:
        st.download_button(
            "📥 Word 보고서 다운로드",
            data=f.read(),
            file_name=f"{result_path.stem}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    tmp_doc.unlink(missing_ok=True)
else:
    st.info("아직 결과가 없습니다. 먼저 평가를 실행하세요.")

