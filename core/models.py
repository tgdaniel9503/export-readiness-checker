"""기업정보 / 수출지원사업 데이터 구조 정의.

Streamlit 화면과 무관한 순수 데이터 구조만 담는다.
"""
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CompanyProfile:
    """기업 기본정보 (① 기업정보입력 화면에서 수집)."""

    name: str = ""
    industry: str = ""
    region: str = ""
    years: float = 0.0
    employees: int = 0
    revenue_eok: float = 0.0  # 억원 단위
    export_amount_usd_10k: float = 0.0  # 최근 1년 수출실적, 만달러 단위 (0이면 수출 미경험)
    purpose: str = "신규수출준비"  # 신규수출준비 / 해외인증 / 바이어발굴 / 물류/통관 / 보험/자금 / 해외거점
    target_countries: str = ""

    @property
    def is_first_time_exporter(self) -> bool:
        return self.export_amount_usd_10k <= 0


@dataclass
class ChecklistState:
    """수출준비도 자가진단 항목 체크 상태. item_id -> bool."""

    answers: Dict[str, bool] = field(default_factory=dict)

    def checked_count(self) -> int:
        return sum(1 for v in self.answers.values() if v)
