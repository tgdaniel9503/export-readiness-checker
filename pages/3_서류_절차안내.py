"""기능 ③ 추천 지원사업의 필요서류·접수처·유의사항 안내 + 상담 결과 저장."""
import json
from pathlib import Path

import streamlit as st

from database.db import save_consultation

st.set_page_config(page_title="서류·절차 안내 · 수출 준비도 점검 어시스턴트", page_icon="🚢", layout="wide")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
with open(DATA_DIR / "funds_master.json", "r", encoding="utf-8") as f:
    FUNDS = json.load(f)
with open(DATA_DIR / "announcements.json", "r", encoding="utf-8") as f:
    ANNOUNCEMENTS = json.load(f)
with open(DATA_DIR / "documents_by_fund.json", "r", encoding="utf-8") as f:
    DOCUMENTS = json.load(f)["documents"]

ALL_CANDIDATES = FUNDS["funds"] + ANNOUNCEMENTS["announcements"]

st.caption("STEP 3 / 3")
st.title("서류·절차 안내")

company = st.session_state.get("company")
if not company:
    st.warning("먼저 기업정보를 입력해주세요.")
    if st.button("← 기업정보 입력으로 이동"):
        st.switch_page("pages/1_기업정보입력.py")
    st.stop()

selected_fund_id = st.session_state.get("selected_fund_id")
if not selected_fund_id:
    st.warning("준비도·매칭 결과에서 안내받을 지원사업을 먼저 선택해주세요.")
    if st.button("← 준비도·매칭 결과로 이동"):
        st.switch_page("pages/2_매칭결과.py")
    st.stop()

match_results = st.session_state.get("match_results", [])
selected_result = next((r for r in match_results if r["fund"]["id"] == selected_fund_id), None)
score = selected_result["score"] if selected_result else None

# match_results의 fund에는 매칭결과 화면에서 계산된 is_expired 표시가 이미 들어있으니
# 있으면 그걸 우선 쓰고, 없을 때만(예: 세션 만료 후 직접 재선택) 원본 데이터에서 찾는다.
fund = selected_result["fund"] if selected_result else next(
    (f for f in ALL_CANDIDATES if f["id"] == selected_fund_id), None
)
if fund is None:
    st.error("선택한 지원사업 정보를 찾을 수 없습니다. 준비도·매칭 결과에서 다시 선택해주세요.")
    if st.button("← 준비도·매칭 결과로 이동"):
        st.switch_page("pages/2_매칭결과.py")
    st.stop()

institution = fund["institution"].replace("{region}", company.get("region", ""))

st.title(fund["name"])
st.caption(institution)

c1, c2, c3 = st.columns(3)
c1.metric("지원유형", fund.get("type", "-"))
c2.metric("지원한도", fund.get("limit_text", "-"))
if score is not None:
    c3.metric("참고 점수", f"{score} / 100")

st.markdown(f"**접수처** \n{fund.get('receive_text', '-')}")
if fund.get("note_text"):
    st.info(f"📌 유의사항: {fund['note_text']}")
if fund.get("source_url"):
    st.markdown(f"🔗 [공식 안내 바로가기]({fund['source_url']})")

if fund.get("kind") == "announcement":
    start = fund.get("application_start", "-")
    end = fund.get("application_end", "-")
    if fund.get("is_expired"):
        st.error(
            f"🔒 **이 공고는 접수가 마감되었습니다 (접수기간: {start} ~ {end}).** "
            "지금 신청할 수는 없지만, 지원정책은 보통 매년 유사한 내용으로 재공고됩니다. "
            "아래 필요서류를 미리 준비해두시면 다음 공고 때 빠르게 신청하실 수 있습니다."
        )
    else:
        st.warning(f"📅 **접수기간: {start} ~ {end}** — 지원사업 공고는 예산 소진 시 조기 마감될 수 있으니 서두르세요.")

if selected_result and selected_result.get("reasons"):
    with st.expander("이 지원사업이 추천된 이유"):
        for reason in selected_result["reasons"]:
            st.write(f"- {reason}")

st.divider()
st.subheader("필요서류 체크리스트")

docs = DOCUMENTS.get(selected_fund_id, [])
if not docs:
    st.write("등록된 서류 정보가 없습니다. 접수처에 직접 문의해주세요.")
else:
    prepared_count = 0
    for doc in docs:
        checked = st.checkbox(
            f"**{doc['name']}**" + (f" — {doc['memo']}" if doc.get("memo") else ""),
            key=f"doc_{selected_fund_id}_{doc['name']}",
        )
        if checked:
            prepared_count += 1
        st.caption(f"발급처: {doc.get('source', '-')}")
    st.caption(f"준비 완료 {prepared_count} / {len(docs)}건")

st.divider()
st.warning(
    "⚠️ **면책 안내**\n\n"
    "- 지원율·한도·접수기간은 변경될 수 있으므로 신청 시점 공식공고를 반드시 최종 확인하세요.\n"
    "- 본 서비스는 선정을 보장하지 않습니다. 최종 결정은 각 기관의 심사 결과에 따릅니다."
)

st.divider()
col_back, col_save = st.columns([1, 1])
with col_back:
    if st.button("← 준비도·매칭 결과로 돌아가기"):
        st.switch_page("pages/2_매칭결과.py")

with col_save:
    if st.button("상담 결과 저장", type="primary"):
        checklist_answers = st.session_state.get("checklist_answers", {})
        checked_count = sum(1 for v in checklist_answers.values() if v)
        readiness_score = st.session_state.get("readiness_score", 0)
        consultation_id = save_consultation(
            company,
            readiness_score,
            checked_count,
            {"id": fund["id"], "name": fund["name"], "score": score},
        )
        st.success(f"상담 결과가 저장되었습니다. (상담 ID: {consultation_id})")
