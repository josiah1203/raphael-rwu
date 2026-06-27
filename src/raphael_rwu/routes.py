"""RWU metering API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Header

from raphael_rwu.store import RWUStore

router = APIRouter(tags=["rwu"])

_db = Path(os.environ.get("RAPHAEL_RWU_DB", "/tmp/raphael-rwu.db"))
_store = RWUStore(_db)


@router.get("/balance")
def get_balance(x_raphael_org_id: str = Header(default="org_default", alias="X-Raphael-Org-Id")) -> dict[str, Any]:
    b = _store.balance(x_raphael_org_id)
    return {"org_id": x_raphael_org_id, **b, "available": b["balance"] - b["reserved"]}


@router.post("/reserve")
def reserve(
    body: dict[str, Any],
    x_raphael_org_id: str = Header(default="org_default", alias="X-Raphael-Org-Id"),
) -> dict[str, Any]:
    amount = float(body.get("amount", 0))
    try:
        _store.reserve(x_raphael_org_id, amount)
    except ValueError as exc:
        raise HTTPException(402, detail=str(exc)) from exc
    return {"org_id": x_raphael_org_id, "reserved": amount, "status": "reserved"}


@router.post("/consume")
def consume(
    body: dict[str, Any],
    x_raphael_org_id: str = Header(default="org_default", alias="X-Raphael-Org-Id"),
) -> dict[str, Any]:
    amount = float(body.get("amount", 0))
    reason = body.get("reason", "usage")
    balance = _store.consume(x_raphael_org_id, amount, reason)
    return {"org_id": x_raphael_org_id, "consumed": amount, "balance": balance}
