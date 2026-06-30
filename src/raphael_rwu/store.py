"""RWU balance ledger — Postgres when RAPHAEL_DATABASE_URL is set."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RWUStore:
    def __init__(self, db_path: Path | str) -> None:
        from raphael_contracts import db as rdb

        self._postgres = rdb.is_postgres()
        if self._postgres:
            rdb.ensure_migrations()
            self.db_path = Path("postgres")
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS balances (
                org_id TEXT PRIMARY KEY,
                balance REAL NOT NULL DEFAULT 1000,
                reserved REAL NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id TEXT NOT NULL,
                amount REAL NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        self._conn.execute("INSERT OR IGNORE INTO balances (org_id, balance) VALUES ('org_default', 1000)")
        self._conn.commit()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        if self._postgres:
            from raphael_contracts.db import pg_execute

            return pg_execute(self._adapt_table(sql), params)
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return cur

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Any | None:
        if self._postgres:
            from raphael_contracts.db import pg_fetchone

            return pg_fetchone(self._adapt_table(sql), params)
        return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        if self._postgres:
            from raphael_contracts.db import pg_fetchall

            return pg_fetchall(self._adapt_table(sql), params)
        return self._conn.execute(sql, params).fetchall()

    @staticmethod
    def _adapt_table(sql: str) -> str:
        return sql.replace("balances", "rwu_balances").replace("ledger", "rwu_ledger")

    def balance(self, org_id: str) -> dict[str, float]:
        row = self.fetchone("SELECT balance, reserved FROM balances WHERE org_id = ?", (org_id,))
        if not row:
            self.execute("INSERT OR IGNORE INTO balances (org_id, balance) VALUES (?, 1000)", (org_id,))
            return {"balance": 1000.0, "reserved": 0.0}
        return {"balance": float(row["balance"]), "reserved": float(row["reserved"])}

    def reserve(self, org_id: str, amount: float) -> None:
        b = self.balance(org_id)
        if b["balance"] - b["reserved"] < amount:
            raise ValueError("insufficient_rwu")
        self.execute("UPDATE balances SET reserved = reserved + ? WHERE org_id = ?", (amount, org_id))

    def consume(self, org_id: str, amount: float, reason: str) -> float:
        if self._postgres:
            self.execute(
                "UPDATE balances SET balance = balance - ?, reserved = GREATEST(0, reserved - ?) WHERE org_id = ?",
                (amount, amount, org_id),
            )
        else:
            self.execute(
                "UPDATE balances SET balance = balance - ?, reserved = MAX(0, reserved - ?) WHERE org_id = ?",
                (amount, amount, org_id),
            )
        self.execute(
            "INSERT INTO ledger (org_id, amount, reason, created_at) VALUES (?, ?, ?, ?)",
            (org_id, -amount, reason, datetime.now(timezone.utc).isoformat()),
        )
        return self.balance(org_id)["balance"]

    def ledger_entries(self, org_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.fetchall(
            "SELECT amount, reason, created_at FROM ledger WHERE org_id = ? ORDER BY id DESC LIMIT ?",
            (org_id, limit),
        )
        if not rows:
            return []
        result = []
        running = self.balance(org_id)["balance"]
        for row in rows:
            amount = float(row["amount"] if isinstance(row, dict) else row[0])
            reason = row["reason"] if isinstance(row, dict) else row[1]
            created = row["created_at"] if isinstance(row, dict) else row[2]
            entry_type = "Credit" if amount > 0 else "Debit"
            result.append({
                "date": str(created)[:10],
                "type": entry_type,
                "amount": f"{amount:+.0f}",
                "balance": f"{running:.0f}",
                "description": reason or "RWU adjustment",
            })
            running -= amount
        return result
