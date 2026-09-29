from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx
import pytest

from app import logging_config
from app.main import app
from app.middleware import CORRELATION_ID_PATTERN, new_correlation_id

CHAT_BODY = {
    "user_id": "student-01",
    "session_id": "session-01",
    "feature": "qa",
    "message": "Explain observability",
}


def post(headers: dict[str, str] | None = None, body: dict | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/chat", json=body or CHAT_BODY, headers=headers or {}
            )

    return asyncio.run(send())


def records(log_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@pytest.fixture()
def log_path(monkeypatch, tmp_path: Path) -> Path:
    path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", path)
    return path


def test_valid_x_request_id_is_reused(log_path: Path) -> None:
    response = post(headers={"x-request-id": "req-ab12cd34"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-ab12cd34"
    assert response.json()["correlation_id"] == "req-ab12cd34"
    assert all(rec["correlation_id"] == "req-ab12cd34" for rec in records(log_path))


def test_malformed_x_request_id_is_replaced_by_a_generated_id(log_path: Path) -> None:
    response = post(headers={"x-request-id": "student@vinuni.edu.vn"})

    correlation_id = response.headers["x-request-id"]
    assert correlation_id != "student@vinuni.edu.vn"
    assert CORRELATION_ID_PATTERN.match(correlation_id)


def test_generated_id_matches_the_required_format(log_path: Path) -> None:
    response = post()

    assert response.json()["correlation_id"] == response.headers["x-request-id"]
    assert CORRELATION_ID_PATTERN.match(response.json()["correlation_id"])


def test_response_time_header_is_present_and_numeric(log_path: Path) -> None:
    response = post()

    assert float(response.headers["x-response-time-ms"]) > 0


def test_each_request_gets_its_own_correlation_id(log_path: Path) -> None:
    first = post()
    second = post()

    assert first.headers["x-request-id"] != second.headers["x-request-id"]


def test_structlog_context_does_not_leak_between_requests(log_path: Path) -> None:
    """Mỗi request mang ID của chính nó ở mọi dòng log, không dùng lại ID cũ."""
    first = post(
        headers={"x-request-id": "req-11111111"},
        body={**CHAT_BODY, "session_id": "session-first"},
    )
    second = post(
        headers={"x-request-id": "req-22222222"},
        body={**CHAT_BODY, "session_id": "session-second"},
    )
    assert first.headers["x-request-id"] == "req-11111111"
    assert second.headers["x-request-id"] == "req-22222222"

    by_session: dict[str, set[str]] = {}
    for record in records(log_path):
        by_session.setdefault(record["session_id"], set()).add(record["correlation_id"])

    assert by_session["session-first"] == {"req-11111111"}
    assert by_session["session-second"] == {"req-22222222"}


def test_new_correlation_id_is_unique() -> None:
    ids = {new_correlation_id() for _ in range(500)}
    assert len(ids) == 500


def test_api_logs_carry_the_required_enrichment_fields(log_path: Path) -> None:
    post()

    api_records = [rec for rec in records(log_path) if rec["service"] == "api"]
    assert api_records
    for record in api_records:
        assert re.match(r"^req-[0-9a-f]{8}$", record["correlation_id"])
        for field in ("user_id_hash", "session_id", "feature", "model", "env"):
            assert record.get(field), f"thieu {field} trong {record['event']}"
        assert record["model"] == "claude-sonnet-4-5"
        assert record["user_id_hash"] != "student-01"


def test_failed_request_also_carries_enrichment(log_path: Path) -> None:
    from app import incidents

    incidents.STATE["tool_fail"] = True
    try:
        response = post()
    finally:
        incidents.STATE["tool_fail"] = False

    assert response.status_code == 500
    failed = [rec for rec in records(log_path) if rec["event"] == "request_failed"]
    assert failed
    record = failed[-1]
    assert record["error_type"] == "RuntimeError"
    assert record["tool_success"] is False
    for field in ("user_id_hash", "session_id", "feature", "model", "env"):
        assert record.get(field)


def test_raw_pii_never_reaches_the_log_file(log_path: Path) -> None:
    """Caller quên gọi summarize_text thì pipeline scrub vẫn phải chặn PII."""
    post(
        body={
            **CHAT_BODY,
            "message": "Email a@vinuni.edu.vn, CCCD 001202012345, card 4111111111111111",
        }
    )

    raw = log_path.read_text(encoding="utf-8")
    for pii in ("a@vinuni.edu.vn", "001202012345", "4111111111111111"):
        assert pii not in raw
    assert "[REDACTED_EMAIL]" in raw
    assert "[REDACTED_CCCD]" in raw
    assert "[REDACTED_CREDIT_CARD]" in raw


def test_vietnamese_phone_is_redacted_in_a_real_request(log_path: Path) -> None:
    post(body={**CHAT_BODY, "message": "So goi 0901234567 hoac 090 123 4567 nhe"})

    raw = log_path.read_text(encoding="utf-8")
    assert "0901234567" not in raw
    assert "090 123 4567" not in raw
    assert "[REDACTED_PHONE_VN]" in raw


def test_user_id_is_never_written_in_plain_text(log_path: Path) -> None:
    post(body={**CHAT_BODY, "user_id": "student@vinuni.edu.vn"})

    raw = log_path.read_text(encoding="utf-8")
    assert "student@vinuni.edu.vn" not in raw
    assert '"user_id"' not in raw


def test_log_lines_are_valid_json_with_the_schema_fields(log_path: Path) -> None:
    post()

    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "config" / "logging_schema.json").read_text(
            encoding="utf-8"
        )
    )
    required = set(schema["required"])
    for record in records(log_path):
        assert required.issubset(record.keys())
        assert set(record).issubset(set(schema["properties"]))
