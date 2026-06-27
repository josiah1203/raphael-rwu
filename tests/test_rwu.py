"""RWU domain tests."""

import tempfile
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from raphael_rwu.app import app


def test_health() -> None:
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "raphael-rwu"


def test_balance_and_consume() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "rwu-test.db"
        import raphael_rwu.routes as routes
        from raphael_rwu.store import RWUStore

        routes._store = RWUStore(db)
        client = TestClient(app)

        res = client.get("/v1/rwu/balance", headers={"X-Raphael-Org-Id": "org_test"})
        assert res.status_code == 200
        assert res.json()["balance"] == 1000.0

        res = client.post(
            "/v1/rwu/consume",
            json={"amount": 5, "reason": "test"},
            headers={"X-Raphael-Org-Id": "org_test"},
        )
        assert res.status_code == 200
        assert res.json()["balance"] == 995.0

        res = client.post(
            "/v1/rwu/reserve",
            json={"amount": 10},
            headers={"X-Raphael-Org-Id": "org_test"},
        )
        assert res.status_code == 200
        assert res.json()["status"] == "reserved"

        res = client.get("/v1/rwu/balance", headers={"X-Raphael-Org-Id": "org_test"})
        assert res.json()["reserved"] == 10.0
        assert res.json()["available"] == 985.0


def test_new_org_default_balance() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "rwu-empty.db"
        import raphael_rwu.routes as routes
        from raphael_rwu.store import RWUStore

        routes._store = RWUStore(db)
        client = TestClient(app)
        org_id = f"org-new-{uuid.uuid4().hex[:8]}"

        res = client.get("/v1/rwu/balance", headers={"X-Raphael-Org-Id": org_id})
        assert res.status_code == 200
        assert res.json()["balance"] == 1000.0
        assert res.json()["reserved"] == 0.0


def test_reserve_insufficient_funds() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "rwu-reserve.db"
        import raphael_rwu.routes as routes
        from raphael_rwu.store import RWUStore

        routes._store = RWUStore(db)
        client = TestClient(app)
        org_id = "org_reserve_test"
        headers = {"X-Raphael-Org-Id": org_id}

        client.post("/v1/rwu/reserve", json={"amount": 990}, headers=headers)
        res = client.post("/v1/rwu/reserve", json={"amount": 50}, headers=headers)
        assert res.status_code == 402


def test_consume_updates_balance() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "rwu-consume.db"
        import raphael_rwu.routes as routes
        from raphael_rwu.store import RWUStore

        routes._store = RWUStore(db)
        client = TestClient(app)
        org_id = f"org-consume-{uuid.uuid4().hex[:8]}"
        headers = {"X-Raphael-Org-Id": org_id}

        before = client.get("/v1/rwu/balance", headers=headers).json()["balance"]
        consumed = client.post("/v1/rwu/consume", json={"amount": 25, "reason": "smoke"}, headers=headers)
        assert consumed.status_code == 200
        assert consumed.json()["balance"] == before - 25


def test_reserve_reduces_available_balance() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "rwu-available.db"
        import raphael_rwu.routes as routes
        from raphael_rwu.store import RWUStore

        routes._store = RWUStore(db)
        client = TestClient(app)
        org_id = f"org-avail-{uuid.uuid4().hex[:8]}"
        headers = {"X-Raphael-Org-Id": org_id}

        client.post("/v1/rwu/reserve", json={"amount": 100}, headers=headers)
        balance = client.get("/v1/rwu/balance", headers=headers).json()
        assert balance["reserved"] == 100.0
        assert balance["available"] == 900.0
