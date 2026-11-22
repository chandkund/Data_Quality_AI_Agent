"""API tests using a stub agent so they do not require an LLM API key."""

from itertools import count
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main


DATA_DIR = Path(__file__).parent / "data"
_client_ips = count(1)
EXPECTED_REPORT = {"score": 90, "issues": [], "tools_used": []}


@pytest.fixture
def client(monkeypatch):
    # Isolate per-IP rate limits between tests; the rate-limit test uses one client.
    address = next(_client_ips)
    monkeypatch.setattr(main, "run_agent", lambda dataframe: EXPECTED_REPORT.copy())
    with TestClient(main.app, client=(f"198.18.0.{address}", 50000)) as test_client:
        yield test_client


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_sample_returns_report(client):
    response = client.get("/sample")

    assert response.status_code == 200
    report = response.json()
    assert {"score", "issues", "rows", "columns", "summary"}.issubset(report)
    assert report["rows"] == 5050
    assert report["columns"] == 16


def test_analyze_dirty_csv_returns_json(client):
    with (DATA_DIR / "dirty.csv").open("rb") as csv_file:
        response = client.post(
            "/analyze",
            files={"file": ("dirty.csv", csv_file, "text/csv")},
        )

    assert response.status_code == 200
    report = response.json()
    assert report["score"] == EXPECTED_REPORT["score"]
    assert report["issues"] == EXPECTED_REPORT["issues"]
    assert report["tools_used"] == EXPECTED_REPORT["tools_used"]
    assert report["rows"] == 5050
    assert report["columns"] == 16
    assert isinstance(report["summary"], str) and report["summary"]


def test_analyze_rejects_file_over_5_mb(client):
    response = client.post(
        "/analyze",
        files={"file": ("large.csv", b"x" * (6 * 1024 * 1024), "text/csv")},
    )

    assert response.status_code == 400
    assert "5 MB" in response.json()["detail"]


def test_analyze_rejects_more_than_50000_rows(client):
    csv_data = "value\n" + "1\n" * 50_001
    response = client.post(
        "/analyze",
        files={"file": ("too_many.csv", csv_data, "text/csv")},
    )

    assert response.status_code == 400
    assert "50,000" in response.json()["detail"]


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [("notes.txt", "text/plain"), ("image.png", "image/png")],
)
def test_analyze_rejects_non_csv_files(client, filename, content_type):
    response = client.post(
        "/analyze",
        files={"file": (filename, b"not a csv upload", content_type)},
    )

    assert response.status_code == 400


def test_analyze_rejects_empty_file(client):
    response = client.post(
        "/analyze",
        files={"file": ("empty.csv", b"", "text/csv")},
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_analyze_rejects_csv_with_headers_only(client):
    response = client.post(
        "/analyze",
        files={"file": ("headers.csv", b"name,age\n", "text/csv")},
    )

    assert response.status_code == 400
    assert "no data rows" in response.json()["detail"].lower()


def test_sixth_request_within_a_minute_is_rate_limited(client):
    results = [client.get("/sample") for _ in range(6)]

    assert [response.status_code for response in results[:5]] == [200] * 5
    assert results[5].status_code == 429


def test_uploaded_csv_is_not_saved_to_disk(client):
    before = {
        path.resolve()
        for path in Path(__file__).parent.rglob("*")
        if path.is_file()
    }
    response = client.post(
        "/analyze",
        files={"file": ("memory_only.csv", b"name\nAda\n", "text/csv")},
    )
    after = {
        path.resolve()
        for path in Path(__file__).parent.rglob("*")
        if path.is_file()
    }

    assert response.status_code == 200
    assert after == before
