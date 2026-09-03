"""기능 ② 수출준비도 점수 + 규칙기반 매칭·우선순위 결과."""
import json
from pathlib import Path

import streamlit as st

from core.matching_engine import (
    calculate_matches,
    calculate_readiness_breakdown,
    filter_by_region,
    merge_active_sources,
    overall_readiness_score,
)

st.set_page_config(page_title="준비도·매칭 결과 · 수출 준비도 점검 어시스턴트", page_icon="🚢", layout="wide")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
with open(DATA_DIR / "funds_master.json", "r", encoding="utf-8") as f:
    FUNDS = json.load(f)
with open(DATA_DIR / "announcements.json", "r", encoding="utf-8") as f:
    ANNOUNCEMENTS = json.load(f)
with open(DATA_DIR / "checklist.json", "r", encoding="utf-8") as f:
    CHECKLIST = json.load(f)

company = st.session_state.get("company")

st.caption("STEP 2 / 3")
st.title("준비도·매칭 결과")

if not company:
    st.warning("먼저 기업정보를 입력해주세요.")
    if st.button("← 기업정보 입력으로 이동"):
        st.switch_page("pages/1_기업정보입력.py")
    st.stop()

st.title(f"준비도·매칭 결과 — {company['name']}")

checklist_answers = st.session_state.get("checklist_answers", {})
total_checked = sum(1 for v in checklist_answers.values() if v)

breakdown = calculate_readiness_breakdown(checklist_answers, CHECKLIST)
readiness_score = overall_readiness_score(breakdown)
st.session_state["readiness_score"] = readiness_score

# ── ① 수출준비도 점수 (지원사업과 무관하게, 자가진단만으로 계산) ─────────────
st.subheader("📊 수출준비도 점수")
col_score, col_bars = st.columns([1, 3])
with col_score:
    st.metric("종합 준비도", f"{readiness_score} / 100")
    st.caption(f"자가진단 {total_checked} / 54 항목 체크됨")
with col_bars:
    for b in breakdown:
        st.write(f"{b['label']} — {b['checked']}/{b['total']}")
        st.progress(b["ratio"])

st.caption("종합 준비도 점수는 9개 분야 충족률의 평균이며, 특정 지원사업의 선정 가능성을 의미하지 않습니다.")

st.divider()

# ── ② 지원사업 매칭 ──────────────────────────────────────────────
st.subheader("🎯 수출지원사업 매칭 후보")
st.write(
    "핵심 수출지원사업과 기업마당 지원공고 중 **잠재적으로 관련 있는 후보를 넓게 찾아드리는 초기 탐색 결과**입니다. "
    "점수순으로 정렬되어 있으니, 관심 가는 항목을 눌러 서류·절차까지 더 살펴보시고 판단해주세요."
)

scope = st.radio(
    "지원공고 표시범위",
    ["진행중인 공고만", "마감된 공고도 포함 (내년도 재공고 대비)"],
    horizontal=True,
    help=(
        "지원정책은 보통 매년 유사한 내용으로 다시 공고됩니다. '마감된 공고도 포함'을 선택하면 "
        "이미 접수가 끝난 공고도 함께 보여드려, 내년 재공고 시점에 맞춰 서류를 미리 준비하실 수 있습니다."
    ),
)
include_expired = scope.startswith("마감된 공고도")

CANDIDATES = merge_active_sources(FUNDS, ANNOUNCEMENTS, include_expired=include_expired)

# 지역이 명시된 지원공고는 사업장 소재지(시/도)와 일치하거나 전국 대상인 것만 남긴다.
# 핵심 지원사업(core_program)은 지역 무관 항상 유지됨 (filter_by_region 참고).
_n_before_region = len(CANDIDATES["funds"])
CANDIDATES = filter_by_region(CANDIDATES, company.get("region_sido"))
_n_excluded_by_region = _n_before_region - len(CANDIDATES["funds"])

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("업종", company["industry"])
c2.metric("소재지", company.get("region", "-"))
c3.metric("업력", f"{company['years']:g}년")
c4.metric("필요 지원유형", company["purpose"])
c5.metric("최근 수출실적", f"{company['export_amount_usd_10k']:g}만$" if company["export_amount_usd_10k"] else "미경험")
c6.metric("준비도 점수", f"{readiness_score} / 100")

st.warning(
    "**점수가 높다고 자동 선정이 아닙니다.** 아래 순위는 자격요건·지원목적·강점신호를 기준으로 한 "
    "참고용 우선순위이며, 최종 선정은 각 기관의 심사 결과에 따릅니다."
)

results = calculate_matches(company, checklist_answers, CANDIDATES, CHECKLIST)
st.session_state["match_results"] = results

n_announcements = sum(1 for r in results if r["fund"].get("kind") == "announcement")
n_expired = sum(1 for r in results if r["fund"].get("is_expired"))
subtitle = f"추천 후보 {len(results)}건 (핵심 지원사업 {len(results) - n_announcements}건 · 지원공고 {n_announcements}건"
subtitle += f", 그중 마감됨 {n_expired}건)" if n_expired else ")"
st.subheader(subtitle)
region_note = (
    f" · {company.get('region_sido', '')} 지역과 무관한 공고 {_n_excluded_by_region}건은 제외(전국 대상 공고는 포함)"
    if _n_excluded_by_region
    else ""
)
st.caption(f"점수 = 자격요건 충족 여부 + 지원목적 부합도 + 업종/강점신호 가중합 (참고용){region_note}")

# 기업마당 연동 이후 지원공고가 수천 건 단위라, 한 번에 다 그리면 화면이 매우 무거워진다.
# 점수순 상위 일부만 먼저 보여주고 "더 보기"로 늘려나간다. 회사/표시범위가 바뀌면 처음부터 다시.
DISPLAY_STEP = 20
reset_key = (company.get("name"), scope)
if st.session_state.get("_match_reset_key") != reset_key:
    st.session_state["match_display_count"] = DISPLAY_STEP
    st.session_state["_match_reset_key"] = reset_key

display_count = st.session_state["match_display_count"]

KIND_LABEL = {"core_program": "🎯 핵심 지원사업", "announcement": "📢 지원공고(기업마당)"}

for r in results[:display_count]:
    fund = r["fund"]
    institution = fund["institution"].replace("{region}", company["region"])
    badge = KIND_LABEL.get(fund.get("kind"), "")
    if fund.get("is_expired"):
        badge += " · 🔒 마감됨(참고용)"
    with st.container(border=True):
        col_rank, col_main, col_score, col_action = st.columns([0.5, 4, 1.5, 1.5])
        with col_rank:
            st.markdown(f"### {r['rank']}")
        with col_main:
            st.caption(badge)
            st.markdown(
                f"**{fund['name']}** \n<span style='color:#8590a0;font-size:0.85em'>{institution}</span>",
                unsafe_allow_html=True,
            )
            st.caption(" · ".join(r["reasons"][:3]))
        with col_score:
            st.metric("점수", f"{r['score']} / 100")
            st.progress(r["score"] / 100)
        with col_action:
            if st.button("서류 보기", key=f"select_{fund['id']}"):
                st.session_state["selected_fund_id"] = fund["id"]
                st.switch_page("pages/3_서류_절차안내.py")

if display_count < len(results):
    remaining = len(results) - display_count
    if st.button(f"더 보기 (다음 {min(DISPLAY_STEP, remaining)}건, 남은 {remaining}건)"):
        st.session_state["match_display_count"] += DISPLAY_STEP
        st.rerun()
st.caption(f"{min(display_count, len(results))} / {len(results)}건 표시 중 — 점수 낮은 후보까지 다 보실 필요는 보통 없습니다.")

st.divider()
st.caption("* 최신 지원율·한도·접수기간은 각 기관 공식 공고에서 다시 확인하세요.")
