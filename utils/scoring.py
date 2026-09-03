"""점수 가중치 계산 헬퍼. matching_engine에서 사용."""
from typing import Dict, Tuple


def category_ratio(checklist_answers: Dict[str, bool], category_items: list) -> Tuple[int, int, float]:
    """카테고리에 속한 항목들의 (체크개수, 전체개수, 비율)을 반환."""
    total = len(category_items)
    if total == 0:
        return 0, 0, 0.0
    checked = sum(1 for item in category_items if checklist_answers.get(item["id"], False))
    return checked, total, checked / total


def clip_score(score: float, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, round(score)))
