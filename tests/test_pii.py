from __future__ import annotations

import re

from app.pii import PII_PATTERNS, hash_user_id, scrub_text, summarize_text

VALID_FORMATTED_PHONE = (
    "0901234567",
    "090 123 4567",
    "090.123.4567",
    "090-123-4567",
    "+84 90 123 4567",
)


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    for phone_number in VALID_FORMATTED_PHONE:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_national_id_keeps_surrounding_text() -> None:
    out = scrub_text("CCCD 001202012345 duoc cap nam 2020")
    assert "001202012345" not in out
    assert "REDACTED_CCCD" in out
    assert "duoc cap nam 2020" in out


def test_scrub_credit_card_in_both_formats() -> None:
    for card in ("4111 1111 1111 1111", "4111111111111111"):
        out = scrub_text(f"card {card}")
        assert card not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_scrub_iban_does_not_leave_trailing_account_digits() -> None:
    out = scrub_text("IBAN VN07 1234 5678 9012 3456 8901 234")
    assert "REDACTED_IBAN" in out
    # `1234 5678` nằm trong IBAN; nếu thiếu pattern iban thì mẫu phone_vn
    # chỉ che phần đầu và các nhóm số phía sau vẫn lọt.
    assert "5678 9012" not in out
    assert "8901 234" not in out


def test_scrub_passport() -> None:
    out = scrub_text("passport C1234567 issued in Ha Noi")
    assert "C1234567" not in out
    assert "REDACTED_PASSPORT" in out


def test_scrub_vietnamese_address() -> None:
    out = scrub_text("Dia chi: so 12, duong Le Loi")
    assert "REDACTED_VN_ADDRESS" in out


def test_scrubbing_never_invents_pii() -> None:
    clean = "refund policy applies within 7 days for every order"
    assert scrub_text(clean) == clean


def test_summarize_text_scrubs_and_truncates() -> None:
    summary = summarize_text("Email " + "a" * 200 + " student@vinuni.edu.vn")
    assert "student@" not in summary
    assert summary.endswith("...")
    assert len(summary) == 83


def test_hash_user_id_is_stable_and_never_looks_like_pii() -> None:
    hashed = hash_user_id("u01")
    assert hashed == hash_user_id("u01")
    assert hashed != hash_user_id("u02")
    # Tiền tố `u` ngăn chuỗi băm 12 ký tự toàn chữ số khớp detector CCCD.
    assert re.search(r"\b\d{12}\b", hashed) is None
    assert re.search(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", hashed) is None


def test_every_pattern_is_a_valid_regex() -> None:
    for name, pattern in PII_PATTERNS.items():
        try:
            re.compile(pattern)
        except re.error as exc:  # pragma: no cover
            raise AssertionError(f"pattern {name} khong bien dich duoc: {exc}") from exc
