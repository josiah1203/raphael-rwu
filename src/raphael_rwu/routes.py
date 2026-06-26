"""RWU metering API."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["rwu"])

_db = Path(os.environ.get("RAPHAEL_RWU_DB", "/tmp/raphael-rwu.db"))
_conn = sqlite3.connect(_db, check_same_thread=False)
_conn.execute(
    """CREATE TABLE IF NOT EXISTS balances (
        org_id TEXT PRIMARY KEY,
        balance REAL NOT NULL DEFAULT 1000,
        reserved REAL NOT NULL DEFAULT 0
    )"""
)
_conn.execute(
    """CREATE TABLE IF NOT EXISTS ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        org_id TEXT NOT NULL,
        amount REAL NOT NULL,
        reason TEXT,
        created_at TEXT NOT NULL
    )"""
)
_conn.commit()
_conn.execute("INSERT OR IGNORE INTO balances (org_id, balance) VALUES ('org_default', 1000)")
_conn.commit()


def _balance(org_id: str) -> dict[str, float]:
    row = _conn.execute("SELECT balance, reserved FROM balances WHERE org_id = ?", (org_id,)).fetchone()
    if not row:
        _conn.execute("INSERT INTO balances (org_id) VALUES (?)", (org_id,))
        _conn.commit()
        return {"balance": 1000.0, "reserved": 0.0}
    return {"balance": row[0], "reserved": row[1]}


@router.get("/balance")
def get_balance(x_raphael_org_id: str = "org_default") -> dict[str, Any]:
    b = _balance(x_raphael_org_id)
    return {"org_id": x_raphael_org_id, **b, "available": b["balance"] - b["reserved"]}


@router.post("/reserve")
def reserve(body: dict[str, Any], x_raphael_org_id: str = "org_default") -> dict[str, Any]:
    amount = float(body.get("amount", 0))
    b = _balance(x_raphael_org_id)
    if b["balance"] - b["reserved"] < amount:
        raise HTTPException(402, detail="insufficient_rwu")
    _conn.execute("UPDATE balances SET reserved = reserved + ? WHERE org_id = ?", (amount, x_raphael_org_id))
    _conn.commit()
    return {"org_id": x_raphael_org_id, "reserved": amount, "status": "reserved"}


@router.post("/consume")
def consume(body: dict[str, Any], x_raphael_org_id: str = "org_default") -> dict[str, Any]:
    amount = float(body.get("amount", 0))
    reason = body.get("reason", "usage")
    _conn.execute(
        "UPDATE balances SET balance = balance - ?, reserved = MAX(0, reserved - ?) WHERE org_id = ?",
        (amount, amount, x_raphael_org_id),
    )
    _conn.execute(
        "INSERT INTO ledger (org_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
        (x_raphael_org_id, -amount, reason, datetime.now(timezone.utc).isoformat()),
    )
    _conn.commit()
    return {"org_id": x_raphael_org_id, "consumed": amount, "balance": _balance(x_raphael_org_id)["balance"]}
