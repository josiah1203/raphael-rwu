"""API routes for raphael-rwu."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["raphael-rwu"])


@router.get("")
def list_root() -> dict[str, str]:
  return {"service": "raphael-rwu", "status": "stub"}
