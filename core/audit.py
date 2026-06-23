"""감사 로그 - 운영자 의사결정의 영속 추적 (SQLite)

실 fab 도입의 전제조건. 품질시스템(IATF 16949 등)은 '누가 언제 무슨 근거로
무엇을 결정했는가'의 추적성을 요구한다. 세션 메모리는 휘발되므로 결정을 SQLite에
영속 기록해 감사 가능하게 한다

테이블 decisions:
  id, ts, surface, target_id, target_title, decision, operator,
  confidence, reason, payload(json)
decision: approved | held | rejected
surface: analysis(4-Tier) | triage | maintenance
"""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "audit.db"


def make_work_order(target_id: str, date: datetime | None = None) -> str:
    """대상 ID로 작업지시서 번호 생성 (알람·incident 모두 안전)

    A1 -> W-YYYYMMDD-A1, TRIAGE-0001 -> W-YYYYMMDD-TRIAGE0001
    """
    d = (date or datetime.now()).strftime("%Y%m%d")
    suffix = re.sub(r"[^A-Za-z0-9]", "", target_id) or "NA"
    return f"W-{d}-{suffix}"


def surface_for(target_id: str) -> str:
    """대상 ID로 결정 surface 추론 (incident면 triage 출처)"""
    return "triage" if target_id.startswith("TRIAGE-") else "analysis"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    surface TEXT,
    target_id TEXT,
    target_title TEXT,
    decision TEXT NOT NULL,
    operator TEXT,
    confidence REAL,
    reason TEXT,
    payload TEXT
);
"""


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def record_decision(
    decision: str,
    target_id: str = "",
    target_title: str = "",
    surface: str = "analysis",
    operator: str = "운영자",
    confidence: float | None = None,
    reason: str = "",
    payload: dict | None = None,
    ts: str | None = None,
) -> int:
    """운영자 결정을 감사 로그에 기록, row id 반환

    ts 미지정 시 현재 시각 (테스트 재현 위해 주입 가능)
    """
    stamp = ts or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO decisions (ts, surface, target_id, target_title, decision, "
            "operator, confidence, reason, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (stamp, surface, target_id, target_title, decision, operator,
             confidence, reason, json.dumps(payload or {}, ensure_ascii=False)),
        )
        return cur.lastrowid


def recent(limit: int = 20) -> list[dict]:
    """최근 결정 목록 (최신순)"""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def stats() -> dict:
    """결정 통계 - 총건수, 유형별 카운트, 승인율"""
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM decisions").fetchone()["c"]
        by = {r["decision"]: r["c"] for r in conn.execute(
            "SELECT decision, COUNT(*) AS c FROM decisions GROUP BY decision"
        ).fetchall()}
    approved = by.get("approved", 0)
    return {
        "total": total,
        "approved": approved,
        "held": by.get("held", 0),
        "rejected": by.get("rejected", 0),
        "approval_rate": round(approved / total, 3) if total else 0.0,
    }
