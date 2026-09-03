"""SQLite 연결/초기화.

MVP 단계에서는 암호화 없이 로컬 파일로 저장한다.
실제 서비스 전환 시 사업자등록번호·재무제표 등 민감 컬럼은 반드시
암호화 저장(예: SQLCipher, 애플리케이션 레벨 암호화)으로 교체할 것.
"""
import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("EXPORT_READINESS_DB_PATH", str(BASE_DIR / "database" / "export_readiness.db"))
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def save_consultation(
    company: dict,
    readiness_score: int,
    checklist_checked_count: int,
    selected_fund: dict | None,
) -> int:
    """상담 결과(기업정보 + 수출준비도 점수 + 선택한 지원사업)를 저장하고 consultation id를 반환.

    Streamlit의 pages/ 다중페이지 구조에서는 사용자가 앱 진입점(app.py)을 거치지 않고
    특정 페이지 URL로 바로 들어올 수도 있어, 여기서도 init_db()를 한 번 더 보장한다
    (CREATE TABLE IF NOT EXISTS라 반복 호출해도 안전).
    """
    init_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO companies (name, industry, region, years, employees, revenue_eok, export_amount_usd_10k)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company.get("name"),
                company.get("industry"),
                company.get("region"),
                company.get("years"),
                company.get("employees"),
                company.get("revenue_eok"),
                company.get("export_amount_usd_10k"),
            ),
        )
        company_id = cur.lastrowid

        cur = conn.execute(
            """
            INSERT INTO consultations (
                company_id, purpose, readiness_score, checklist_checked_count,
                selected_fund_id, selected_fund_name, selected_fund_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_id,
                company.get("purpose"),
                readiness_score,
                checklist_checked_count,
                (selected_fund or {}).get("id"),
                (selected_fund or {}).get("name"),
                (selected_fund or {}).get("score"),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
