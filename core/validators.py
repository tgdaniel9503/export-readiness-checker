"""입력값 검증. 필수항목 누락, 숫자범위 오류 등을 미리 걸러낸다."""
from typing import Dict, List

REQUIRED_FIELDS = ["name", "industry", "region", "purpose"]


def validate_company_form(data: Dict) -> List[str]:
    """기본정보 폼 입력값을 검증하고, 문제가 있으면 에러 메시지 목록을 반환한다.

    빈 리스트를 반환하면 통과.
    """
    errors: List[str] = []

    for f in REQUIRED_FIELDS:
        if not data.get(f):
            errors.append(f"'{f}' 항목은 필수입니다.")

    for f in ["years", "employees", "revenue_eok", "export_amount_usd_10k"]:
        v = data.get(f)
        if v is None:
            continue
        try:
            num = float(v)
        except (TypeError, ValueError):
            errors.append(f"'{f}' 값은 숫자여야 합니다.")
            continue
        if num < 0:
            errors.append(f"'{f}' 값은 0 이상이어야 합니다.")

    return errors
