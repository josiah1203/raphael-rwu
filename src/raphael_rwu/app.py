"""Raphael service: raphael-rwu."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from raphael_contracts.errors import ErrorResponse
from raphael_rwu.routes import router

app = FastAPI(
    title="raphael-rwu",
    description="Raphael Work Unit execution accounting, banking, allocation",
    version="0.1.0",
    openapi_url="/v1/rwu/openapi.json" if "/v1/rwu" else "/openapi.json",
)

app.include_router(router, prefix="/v1/rwu" if "/v1/rwu" else "")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "raphael-rwu"}


@app.exception_handler(Exception)
async def unhandled(_request, exc: Exception) -> JSONResponse:
    err = ErrorResponse(code="internal_error", message=str(exc))
    return JSONResponse(status_code=500, content=err.model_dump())
