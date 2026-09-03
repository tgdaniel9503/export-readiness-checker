"""규칙 기반 매칭·우선순위 엔진 + 수출준비도 점수 산정.

ML/AI 없이 if-then 규칙 + 가중치 점수표로 구현한다 (원본 policy-fund-matcher와 동일한 설계 원칙).

절차:
1차: 지원목적 적합도로 후보를 넓게 잡는다 (완전 배제하지 않고 감점 처리 —
     "자격요건 통과 = 선정 확정 아님" 원칙을 지키기 위해 하드 필터링을 최소화).
2차: 업력·지역·자가진단 체크리스트(강점신호)로 가중치 점수를 더한다.
3차: 점수순으로 정렬한다.

별도로 자가진단 체크리스트만으로 "수출준비도 점수"(카테고리별 충족률의 평균)도 계산한다 —
이 점수는 특정 지원사업 적합도가 아니라, 기업의 수출 준비 수준 자체를 보여주기 위한 것이다.

주의: 점수는 어디까지나 참고용 우선순위이며, 실제 승인·선정 가능성을 보장하지 않는다.
"""
from datetime import date
from typing import Dict, List, Optional

from utils.scoring import category_ratio, clip_score

PURPOSE_MISMATCH_PENALTY = 15
EXPIRED_ANNOUNCEMENT_PENALTY = 10
INDUSTRY_MATCH_BONUS = 10

# 기업마당 API가 실제로 쓰는 지역 해시태그 16개 (data/regions.json의 시도 키와 동일하게 맞춤).
REGION_TAGS = [
    "서울", "부산", "대구", "인천", "전남광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "경북", "경남", "제주",
]
# 해시태그에 이 개수 이상의 지역이 걸려있으면 "특정 지역 전용"이 아니라 "전국 대상"으로 본다.
NATIONWIDE_TAG_THRESHOLD = len(REGION_TAGS) // 2


def _hashtag_regions(hashtags: str) -> set:
    tags = {t.strip() for t in (hashtags or "").split(",") if t.strip()}
    return tags & set(REGION_TAGS)


def filter_by_region(funds_data: Dict, sido: Optional[str]) -> Dict:
    """지원공고를 기업의 시/도(sido)에 맞는 것 + 전국 대상 공고만 남긴다.

    핵심 지원사업(kind="core_program")은 원래 지역 무관하게 항상 통과시킨다 — 지자체 자금은
    이미 {region} 템플릿과 region_required 가중치로 자체 처리되고 있어 여기서 또 거르면
    이중필터링이 된다.
    sido가 비어있으면 필터링하지 않고 그대로 반환한다 (기업정보 미입력 등 예외 상황 대비).
    """
    if not sido:
        return funds_data

    kept = []
    for item in funds_data.get("funds", []):
        if item.get("kind") != "announcement":
            kept.append(item)
            continue
        found = _hashtag_regions(item.get("hashtags", ""))
        is_nationwide = not found or len(found) >= NATIONWIDE_TAG_THRESHOLD
        if is_nationwide or sido in found:
            kept.append(item)
    return {"funds": kept}


def _industry_keywords(industry_name: str) -> List[str]:
    """'금속가공제품 제조업' 같은 업종명에서 매칭에 쓸만한 핵심 단어를 뽑는다.

    '제조업'/'서비스업'처럼 너무 흔한 접미어만 있는 조각은 뭘 걸러도 의미가 없어 제외한다.
    """
    generic = {"제조업", "서비스업", "및", "업"}
    words = [w for w in industry_name.replace(";", " ").split() if len(w) >= 2 and w not in generic]
    return words


def merge_active_sources(
    funds_data: Dict,
    announcements_data: Dict,
    today: Optional[date] = None,
    include_expired: bool = False,
) -> Dict:
    """핵심 수출지원사업(funds_master.json) + 기업마당 공고(announcements.json)를 하나의 후보 목록으로 합친다.

    include_expired=False(기본값): 접수기간이 지난 공고는 제외한다 (당장 신청 가능한 것만).
    include_expired=True: 지난 공고도 포함한다 — 지원정책은 보통 매년 유사한 내용으로
    재공고되고, 기업이 서류를 준비하는 데 시간이 걸리므로 "올해는 마감됐지만
    내년 재공고에 미리 대비"하는 용도로 참고할 수 있게 하기 위함.

    포함된 각 항목에는 is_expired(bool)가 추가로 표시된다 (핵심 지원사업은 항상 False).
    application_end가 없거나 날짜 형식이 잘못된 경우는 상시 공고로 보고 항상 포함한다.
    """
    today = today or date.today()
    combined = list(funds_data.get("funds", []))

    for item in announcements_data.get("announcements", []):
        end = item.get("application_end")
        expired = False
        if end:
            try:
                expired = date.fromisoformat(end) < today
            except ValueError:
                expired = False

        if expired and not include_expired:
            continue

        item = dict(item)
        item["is_expired"] = expired
        combined.append(item)

    return {"funds": combined}


def _checklist_category_counts(checklist_answers: Dict[str, bool], checklist_data: Dict) -> Dict[str, Dict]:
    """카테고리별 (checked, total, ratio)를 미리 계산."""
    result = {}
    for cat in checklist_data["categories"]:
        checked, total, ratio = category_ratio(checklist_answers, cat["items"])
        result[cat["key"]] = {"checked": checked, "total": total, "ratio": ratio, "label": cat["label"]}
    return result


def calculate_readiness_breakdown(checklist_answers: Dict[str, bool], checklist_data: Dict) -> List[Dict]:
    """카테고리별 수출준비도 충족률을 리스트로 반환 (화면 표시용)."""
    counts = _checklist_category_counts(checklist_answers, checklist_data)
    return [
        {"key": key, "label": info["label"], "checked": info["checked"], "total": info["total"], "ratio": info["ratio"]}
        for key, info in counts.items()
    ]


def overall_readiness_score(breakdown: List[Dict]) -> int:
    """카테고리별 충족률의 단순평균 * 100 을 전체 수출준비도 점수(0~100)로 사용.

    카테고리 항목 수가 서로 달라도 "분야별 균형"을 반영하기 위해 항목 수가 아닌
    카테고리 단위로 평균을 낸다 (특정 분야만 항목이 많다고 그 분야가 점수를 좌우하지 않도록).
    """
    if not breakdown:
        return 0
    avg_ratio = sum(b["ratio"] for b in breakdown) / len(breakdown)
    return clip_score(avg_ratio * 100)


def calculate_matches(
    company: Dict,
    checklist_answers: Dict[str, bool],
    funds_data: Dict,
    checklist_data: Dict,
) -> List[Dict]:
    """기업정보 + 자가진단 체크리스트를 기준으로 수출지원사업 후보를 점수순으로 정렬한다.

    Returns: [{fund, score, reasons: [str, ...]}, ...] score 내림차순
    """
    cat_counts = _checklist_category_counts(checklist_answers, checklist_data)
    purpose = company.get("purpose", "")
    years = float(company.get("years") or 0)
    region = company.get("region", "")
    export_amount = float(company.get("export_amount_usd_10k") or 0)
    industry_keywords = _industry_keywords(company.get("industry", ""))

    results = []

    for fund in funds_data["funds"]:
        score = fund.get("base_score", 0)
        reasons: List[str] = []

        # 1차: 지원목적 적합도
        if purpose in fund.get("eligible_purposes", []):
            score += fund.get("purpose_bonus", 0)
            reasons.append(f"지원목적 부합: {purpose}")
        else:
            score -= PURPOSE_MISMATCH_PENALTY
            reasons.append("지원목적 부합도 낮음 — 별도 확인 필요")

        # 2차: 업력
        min_years = fund.get("min_years", 0)
        if min_years:
            if years >= min_years:
                score += fund.get("years_bonus", 0)
                reasons.append(f"업력 {years:g}년 (요건 {min_years}년 이상 충족)")
            else:
                reasons.append(f"업력요건({min_years}년 이상) 미충족 가능성 — 공고 확인 필요")

        # 2차: 지역 (지자체 협약사업 등)
        if fund.get("region_required"):
            if region:
                score += fund.get("region_bonus", 0)
                reasons.append(f"{region} 지역 소재 — 지자체 협약사업 대상")
            else:
                reasons.append("사업장 소재지 미입력 — 지역 매칭 불가")

        # 2차: 자가진단 체크리스트 강점신호
        for cat_key in fund.get("relevant_categories", []):
            info = cat_counts.get(cat_key)
            if not info or info["total"] == 0:
                continue
            score += fund.get("category_weight", 0) * info["ratio"]
            if info["checked"] > 0:
                reasons.append(f"'{info['label']}' 자가진단 {info['checked']}/{info['total']} 항목 해당")

        # 2차: 업종 키워드 관련성 (지원공고 대상, 참고용 가점 — 정확한 업종코드 매칭 데이터가
        # 없어 하드 필터링은 하지 않는다. "잠재후보를 넓게 찾는" 이 앱의 목적과도 맞다.)
        if fund.get("kind") == "announcement" and industry_keywords:
            hay = f"{fund.get('name', '')} {fund.get('hashtags', '')}"
            if any(kw in hay for kw in industry_keywords):
                score += INDUSTRY_MATCH_BONUS
                reasons.append(f"업종({company.get('industry', '')}) 관련 키워드 매칭")

        # 2차: 수출 미경험(첫 수출 준비 단계) 보완 신호 — 보험/바우처류는 초보 수출기업에도 유효
        if fund.get("first_timer_bonus") and export_amount <= 0:
            score += fund["first_timer_bonus"]
            reasons.append("수출 초기/준비 단계 기업도 신청 가능")

        # 지원공고는 핵심 지원사업과 달리 접수기간이 있으므로 마감일을 항상 눈에 띄게 표시
        if fund.get("kind") == "announcement" and fund.get("application_end"):
            if fund.get("is_expired"):
                score -= EXPIRED_ANNOUNCEMENT_PENALTY
                reasons.append(
                    f"⏰ 접수 마감됨 (~{fund['application_end']}) — 내년도 유사 공고 재공고 가능성이 있어 "
                    "사전 서류 준비용으로 참고 가능"
                )
            else:
                reasons.append(f"접수기간: ~{fund['application_end']} (마감일 확인 필수)")

        results.append(
            {
                "fund": fund,
                "score": clip_score(score),
                "reasons": reasons,
            }
        )

    # 마감된 공고가 점수만으로 진행중인 후보보다 위로 올라오지 않도록,
    # 마감 여부를 1차 기준으로 먼저 정렬하고 그 안에서 점수 내림차순으로 정렬한다.
    results.sort(key=lambda r: (r["fund"].get("is_expired", False), -r["score"]))
    for i, r in enumerate(results, start=1):
        r["rank"] = i

    return results
