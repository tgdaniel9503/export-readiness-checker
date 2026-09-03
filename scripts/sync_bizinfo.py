"""기업마당(bizinfo.go.kr) 지원사업정보 오픈API를 호출해 data/announcements.json을 최신 상태로 갱신한다.

사용법:
    python scripts/sync_bizinfo.py

필요조건:
    프로젝트 루트의 .env 파일에 BIZINFO_API_KEY=발급받은인증키 가 있어야 한다.
    (발급: https://www.bizinfo.go.kr/apiList.do → 지원사업정보 API → 사용신청)

동작:
    1. 기업마당 API를 페이지 단위로 호출해 현재 등록된 지원사업 공고를 모두 받아온다.
    2. 분야(pldirSportRealmLclasCodeNm)가 "수출"이거나, 공고명에 "수출"이 포함된 공고만 골라
       우리 announcements.json 스키마(core/matching_engine.py가 기대하는 필드)로 매핑한다.
       (기업마당 자체는 전체 업종의 공고를 다루므로, 이 스크립트는 수출 관련 공고만 추려낸다.)
    3. data/announcements.json을 통째로 교체한다 (기업마당 공고 전용 — 손으로 추가한
       핵심 지원사업은 funds_master.json에 있으므로 영향받지 않는다).

주의:
    이 스크립트는 "지금 이 순간 API가 반환하는 공고 스냅샷"으로 파일을 덮어쓴다.
    실행 후 반드시 앱을 재시작(또는 새로고침)해서 반영해야 한다.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
OUTPUT_PATH = ROOT / "data" / "announcements.json"

API_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
PAGE_UNIT = 100
MAX_PAGES = 30  # 안전장치: 최대 3,000건까지만 조회 (수출 관련 공고만 추려내므로 넉넉히 잡음)

# "수출" 분야 공고를 우리 앱의 지원목적(purpose) / 자가진단 카테고리로 매핑.
# 완벽한 대응은 아니고, 매칭엔진이 이미 "부합도 낮음" 감점을 두고 있어 틀려도 후보에서
# 완전히 빠지지는 않는다 (하드 필터링 최소화 원칙과 일치).
KEYWORD_PURPOSE_MAP = [
    (["바우처", "바이어", "마케팅", "전시회", "유통망", "지사화"], ["바이어발굴", "해외거점"], ["mkt"]),
    (["인증", "규격", "CE", "FDA"], ["해외인증"], ["cert"]),
    (["보험", "보증", "금융", "환율", "환헤지"], ["보험/자금"], ["fin"]),
    (["통관", "물류", "AEO", "관세"], ["물류/통관"], ["trade"]),
    (["인큐베이터", "사무소", "거점"], ["해외거점"], ["hr_org"]),
]
DEFAULT_MAPPING = (["신규수출준비"], ["mkt"])


def load_env():
    """.env 파일을 읽어 os.environ에 없는 값만 채워넣는다 (외부 패키지 의존 없이 최소 구현)."""
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def fetch_page(api_key: str, page_index: int) -> dict:
    params = {
        "crtfcKey": api_key,
        "dataType": "json",
        "pageUnit": PAGE_UNIT,
        "pageIndex": page_index,
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def fetch_all(api_key: str) -> list:
    """페이지를 넘겨가며 전체 공고를 받아온다 (totCnt만큼, MAX_PAGES 안전장치 적용)."""
    items = []
    total = None
    for page in range(1, MAX_PAGES + 1):
        data = fetch_page(api_key, page)
        page_items = data.get("jsonArray", [])
        if not page_items:
            break
        items.extend(page_items)
        total = page_items[0].get("totCnt")
        if total and len(items) >= int(total):
            break
    return items


def is_export_related(item: dict) -> bool:
    field = item.get("pldirSportRealmLclasCodeNm", "")
    name = item.get("pblancNm", "")
    return field == "수출" or "수출" in name


def guess_purposes_and_categories(item: dict):
    name = item.get("pblancNm", "")
    for keywords, purposes, categories in KEYWORD_PURPOSE_MAP:
        if any(kw in name for kw in keywords):
            return purposes, categories
    return DEFAULT_MAPPING


def parse_period(reqst_begin_end: str):
    """'2026-08-24 ~ 2026-09-11' 형태를 (start, end)로 분리. 형식이 다르면 (None, None)."""
    if not reqst_begin_end:
        return None, None
    m = re.match(r"\s*(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})\s*", reqst_begin_end)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"\s*(\d{8})\s*~\s*(\d{8})\s*", reqst_begin_end)
    if m:
        def fmt(d):
            return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
        return fmt(m.group(1)), fmt(m.group(2))
    return None, None  # '상시접수' 등 -> 상시 공고로 취급 (마감일 없음)


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def map_item(item: dict) -> dict:
    field = item.get("pldirSportRealmLclasCodeNm", "")
    purposes, categories = guess_purposes_and_categories(item)

    jrsd = item.get("jrsdInsttNm", "").strip()
    exc = item.get("excInsttNm", "").strip()
    institution = f"{jrsd} · {exc}" if exc and exc != jrsd else (jrsd or exc or "-")

    start, end = parse_period(item.get("reqstBeginEndDe", ""))
    contact = item.get("refrncNm", "").strip()
    summary = strip_html(item.get("bsnsSumryCn", ""))[:200]

    mapped = {
        "id": item.get("pblancId"),
        "name": item.get("pblancNm", "").strip(),
        "institution": institution,
        "type": f"지원사업 공고 ({field})" if field else "지원사업 공고 (수출)",
        "kind": "announcement",
        "eligible_purposes": purposes,
        "min_years": 0,
        "region_required": False,
        "relevant_categories": categories,
        "base_score": 20,
        "purpose_bonus": 20,
        "years_bonus": 0,
        "category_weight": 20,
        "limit_text": summary or "공고 원문 참고",
        "receive_text": item.get("reqstMthPapersCn", "").strip() or "공고 원문 참고",
        "note_text": f"문의처: {contact}" if contact else "",
        "application_start": start,
        "application_end": end,
        "source_url": item.get("rceptEngnHmpgUrl") or item.get("pblancUrl") or "",
        "target": item.get("trgetNm", ""),
        # 지역 필터링용 원본 해시태그 보존 (core.matching_engine.filter_by_region이 사용).
        # 지역 관련 해시태그가 하나도 없으면 전국 대상 공고로 취급한다.
        "hashtags": item.get("hashtags", ""),
    }
    if not mapped["application_start"]:
        mapped.pop("application_start")
    if not mapped["application_end"]:
        mapped.pop("application_end")
    return mapped


def main():
    load_env()
    api_key = os.environ.get("BIZINFO_API_KEY", "")
    if not api_key or api_key in ("여기에_새_키_붙여넣기", ""):
        print(".env에 BIZINFO_API_KEY가 설정되어 있지 않습니다.", file=sys.stderr)
        sys.exit(1)

    print("기업마당 API에서 공고 목록을 가져오는 중...")
    raw_items = fetch_all(api_key)
    print(f"  -> {len(raw_items)}건 수신")

    export_items = [it for it in raw_items if is_export_related(it)]
    print(f"  -> 수출 관련 공고 {len(export_items)}건 선별")

    mapped = [map_item(it) for it in export_items if it.get("pblancId") and it.get("pblancNm")]

    by_id = {m["id"]: m for m in mapped}
    result = {
        "note": (
            "기업마당(bizinfo.go.kr) 오픈API로 자동 수집된 '수출' 분야 공고입니다 "
            "(scripts/sync_bizinfo.py). 수동으로 고친 항목은 이 스크립트를 다시 실행하면 "
            "덮어써지니 주의하세요."
        ),
        "schema_note": (
            "funds_master.json과 동일한 점수 필드를 쓰되, kind: 'announcement', "
            "application_start/application_end(YYYY-MM-DD, 없으면 상시), source_url이 추가됩니다."
        ),
        "synced_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "announcements": list(by_id.values()),
    }

    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"완료: {len(by_id)}건을 {OUTPUT_PATH} 에 저장했습니다.")


if __name__ == "__main__":
    main()
