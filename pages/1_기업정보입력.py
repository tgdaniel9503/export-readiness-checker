"""기능 ① 기업정보 입력 폼 (수출준비도 자가진단 체크리스트).

기본정보 + 54개 자가진단 항목을 입력받아 session_state에 저장하고,
② 준비도·매칭 결과 화면으로 넘어가기 위한 입력값을 만든다.

업종·소재지 검색이 입력할 때마다 즉시 필터링되어야 해서(폼 안에서는 제출 전까지
입력이 반영되지 않음) 기본정보 위젯들은 st.form 밖에 둔다. 54개 체크박스만
st.form으로 묶어서, 하나씩 체크할 때마다 전체 페이지가 다시 그려지는 걸 막는다.
"""
import json
from pathlib import Path

import streamlit as st

from core.validators import validate_company_form

st.set_page_config(page_title="기업정보 입력 · 수출 준비도 점검 어시스턴트", page_icon="🚢", layout="wide")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
with open(DATA_DIR / "checklist.json", "r", encoding="utf-8") as f:
    CHECKLIST = json.load(f)
with open(DATA_DIR / "ksic_codes.json", "r", encoding="utf-8") as f:
    KSIC_ITEMS = json.load(f)["items"]
with open(DATA_DIR / "regions.json", "r", encoding="utf-8") as f:
    REGIONS = json.load(f)["sido"]

PURPOSE_OPTIONS = ["신규수출준비", "해외인증", "바이어발굴", "물류/통관", "보험/자금", "해외거점"]

st.caption("STEP 1 / 3")
st.title("기업정보 입력")
st.write("기본정보와 54개 자가진단 항목을 입력하면, 다음 단계에서 분야별 수출준비도 점수와 가능성이 높은 수출지원사업 후보를 보여드립니다.")

company_prev = st.session_state.get("company", {})
checklist_prev = st.session_state.get("checklist_answers", {})

st.subheader("기본정보")

c1, c2 = st.columns(2)
with c1:
    name = st.text_input("기업명 *", value=company_prev.get("name", ""))
with c2:
    target_countries = st.text_input(
        "목표 수출국가 (선택)", value=company_prev.get("target_countries", ""), placeholder="예: 미국, 베트남, EU"
    )

# ── 업종: 키워드로 검색 -> 왼쪽에 선택, 오른쪽에 해당 산업분류코드 표시 ─────────
st.markdown("**업종 \\***")
col_industry, col_code = st.columns([3, 1])
with col_industry:
    industry_query = st.text_input(
        "업종 검색 (키워드 입력 후 목록에서 선택)",
        value="",
        placeholder="예: 금속, 소프트웨어, 화장품, 식품",
        label_visibility="collapsed",
    )
    query = industry_query.strip()
    matches = [it for it in KSIC_ITEMS if query in it["name"]] if query else KSIC_ITEMS

    if not matches:
        st.warning("검색 결과가 없습니다. 다른 키워드로 검색해보세요 (예: '금속', '식품').")
        industry_name, industry_code = "", ""
    else:
        options = [f"[{it['code']}] {it['name']} ({it['level']})" for it in matches]
        prev_name = company_prev.get("industry", "")
        default_index = next((i for i, it in enumerate(matches) if it["name"] == prev_name), 0)
        selected_label = st.selectbox(
            "업종 선택", options, index=min(default_index, len(options) - 1), label_visibility="collapsed"
        )
        selected_item = matches[options.index(selected_label)]
        industry_name, industry_code = selected_item["name"], selected_item["code"]
with col_code:
    st.text_input("산업분류코드", value=industry_code, disabled=True)

st.caption(
    "한국표준산업분류(KSIC) 대분류·중분류 기준입니다. 세세분류까지는 아직 없어 "
    "정확한 업종코드는 사업자등록증을 함께 확인하세요."
)

# ── 사업장 소재지: 시/도 -> 시/군/구 2단 선택 (자유입력으로 인한 오탈자 방지) ──
st.markdown("**사업장 소재지 \\***")
col_sido, col_sigungu = st.columns(2)
with col_sido:
    sido_options = list(REGIONS.keys())
    prev_sido = company_prev.get("region_sido", "")
    sido_index = sido_options.index(prev_sido) if prev_sido in sido_options else 0
    sido = st.selectbox("시/도", sido_options, index=sido_index)
with col_sigungu:
    sigungu_options = REGIONS.get(sido, [])
    prev_sigungu = company_prev.get("region_sigungu", "")
    sigungu_index = sigungu_options.index(prev_sigungu) if prev_sigungu in sigungu_options else 0
    sigungu = st.selectbox("시/군/구", sigungu_options, index=sigungu_index)
region = f"{sido} {sigungu}"

c4, c5, c6 = st.columns(3)
with c4:
    years = st.number_input(
        "업력(년)", min_value=0.0, step=0.5, value=float(company_prev.get("years", 0.0))
    )
with c5:
    employees = st.number_input(
        "상시근로자 수(명)", min_value=0, step=1, value=int(company_prev.get("employees", 0))
    )
with c6:
    revenue_eok = st.number_input(
        "최근 연매출(억원)", min_value=0.0, step=0.5, value=float(company_prev.get("revenue_eok", 0.0))
    )

c7, c8 = st.columns(2)
with c7:
    export_amount_usd_10k = st.number_input(
        "최근 1년 수출실적(만달러, 없으면 0)",
        min_value=0.0,
        step=10.0,
        value=float(company_prev.get("export_amount_usd_10k", 0.0)),
        help="아직 수출 실적이 없는 '수출 준비 단계' 기업은 0으로 두세요.",
    )
with c8:
    purpose_default = company_prev.get("purpose", PURPOSE_OPTIONS[0])
    purpose = st.selectbox(
        "지금 가장 필요한 지원 유형 *",
        PURPOSE_OPTIONS,
        index=PURPOSE_OPTIONS.index(purpose_default) if purpose_default in PURPOSE_OPTIONS else 0,
    )

st.divider()

with st.form("checklist_form"):
    st.subheader("수출준비도 자가진단 (54개 항목)")
    st.caption(
        "해당하는 항목만 체크하세요. 체크 항목이 많다고 자동으로 선정되는 것은 아니며, "
        "다음 단계의 준비도 점수·추천 순위 산정에 참고 신호로만 활용됩니다."
    )

    checklist_answers = {}
    for cat in CHECKLIST["categories"]:
        with st.expander(f"{cat['label']} ({len(cat['items'])}개 항목)"):
            for item in cat["items"]:
                checklist_answers[item["id"]] = st.checkbox(
                    item["label"],
                    value=bool(checklist_prev.get(item["id"], False)),
                    key=f"chk_{item['id']}",
                )

    submitted = st.form_submit_button("준비도·매칭 결과 보기 →", type="primary")

if submitted:
    company = {
        "name": name.strip(),
        "industry": industry_name,
        "industry_code": industry_code,
        "region": region.strip(),
        "region_sido": sido,
        "region_sigungu": sigungu,
        "years": years,
        "employees": employees,
        "revenue_eok": revenue_eok,
        "export_amount_usd_10k": export_amount_usd_10k,
        "purpose": purpose,
        "target_countries": target_countries.strip(),
    }

    errors = validate_company_form(company)
    if errors:
        for e in errors:
            st.error(e)
    else:
        st.session_state["company"] = company
        st.session_state["checklist_answers"] = checklist_answers
        st.switch_page("pages/2_매칭결과.py")
