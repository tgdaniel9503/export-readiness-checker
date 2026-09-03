-- 수출 준비도 점검 어시스턴트 — SQLite 스키마
-- 주의: 사업자등록번호·재무제표 등 민감정보 컬럼은 운영 전환 시 암호화 저장을 전제로 설계할 것.

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    industry TEXT,
    region TEXT,
    years REAL,
    employees INTEGER,
    revenue_eok REAL,
    export_amount_usd_10k REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS consultations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    purpose TEXT,
    readiness_score INTEGER,
    checklist_checked_count INTEGER,
    selected_fund_id TEXT,
    selected_fund_name TEXT,
    selected_fund_score INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (company_id) REFERENCES companies (id)
);
