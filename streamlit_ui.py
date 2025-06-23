import streamlit as st
import json
from pathlib import Path
import subprocess
import time

st.set_page_config(page_title="개인정보처리방침 평가 결과", layout="wide")
st.title("🔍 개인정보처리방침 자동 평가 시스템")

# 경로 설정
UPLOAD_PATH = Path("data/policies/uploaded_policy.pdf")
TXT_PATH = Path("data/evaluation/uploaded_policy.txt")
STRUCTURED_PATH = Path("data/evaluation_structured/uploaded_policy_structured.jsonl")
RESULT_PATH = Path("results/naver_eval_result.jsonl")

# 평가 결과 로딩 함수
def load_results(path):
    results = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results

# PDF 파일 업로드
pdf_file = st.file_uploader("📄 개인정보 처리방침 PDF 파일을 업로드하세요.", type="pdf")

if pdf_file is not None:
    UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(UPLOAD_PATH, "wb") as f:
        f.write(pdf_file.read())
    st.success("✅ PDF 업로드 성공! 평가 버튼을 눌러 진행하세요.")

# 평가 실행 버튼
eval_trigger = st.button("🚀 평가 실행")

if eval_trigger:
    with st.status("🧠 평가 중... 잠시만 기다려주세요", expanded=True):
        # 1단계: PDF → TXT 변환
        result = subprocess.run(["python", "scripts/pdf_to_text.py"], capture_output=True, text=True)
        st.write("📄 텍스트 변환 완료")
        st.text(result.stdout)

        # 2단계: TXT → JSONL 구조화
        result = subprocess.run(["python", "scripts/structured_split.py"], capture_output=True, text=True)
        st.write("📑 구조화 완료")
        st.text(result.stdout)

        # 3단계: Cross-reference 생성
        result = subprocess.run(["python", "scripts/query_cross_reference.py"], capture_output=True, text=True)
        st.write("🔗 교차 참조 완료")
        st.text(result.stdout)

        # 4단계: 유사 문장 평가 실행
        result = subprocess.run(["python", "scripts/run_privacy_eval.py"], capture_output=True, text=True)
        st.write("🔍 평가 완료")
        st.text(result.stdout)

        # 일시 대기 후 새로고침 유도
        time.sleep(1)
        st.rerun()

# UI: 평가 결과 존재 시 출력
if not RESULT_PATH.exists():
    st.warning("`results/naver_eval_result.jsonl` 파일이 없습니다. 먼저 평가를 수행해주세요.")
else:
    results = load_results(RESULT_PATH)
    st.success(f"총 평가 문장 수: {len(results)}개")

    for r in results:
        eid = r.get("eval_id")
        sent = r.get("sentence")
        status = r.get("status")
        result = r.get("result")
        err = r.get("error")

        with st.expander(f"📝 평가 ID {eid} - 상태: {'✅ 성공' if status == 'ok' else '❌ 실패'}"):
            st.markdown(f"**📌 평가 문장:**\n\n{sent}")
            if status == "ok" and result:
                st.json(result, expanded=False)
            else:
                st.error(f"에러: {err}")
