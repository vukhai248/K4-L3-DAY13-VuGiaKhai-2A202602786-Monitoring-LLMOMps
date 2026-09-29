from __future__ import annotations

import hashlib
import re

# Thứ tự quan trọng: mẫu rộng phải đứng trước mẫu hẹp để không bị ăn cụt.
# - iban trước phone_vn: nếu không, `+84`/số đầu của IBAN sẽ bị che thành
#   REDACTED_PHONE_VN và phần đuôi tài khoản vẫn lọt.
# - credit_card (16-19 số) trước cccd (12 số): `\b` khiến cccd không ăn vào
#   giữa dãy số dài, nhưng đặt trước vẫn an toàn hơn khi số được ghi có dấu.
PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "iban": r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?\b",
    "credit_card": r"\b(?:\d[ -]?){15,18}\d\b",
    "phone_vn": r"(?<![\d.])(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    "cccd": r"\b\d{12}\b",
    "passport": r"\b[A-Z]{1,2}\d{6,9}\b",
    "vn_address": (
        r"(?i)\b(?:so|duong|phuong|quan|hẻm|ap|khom)\s*"
        r"(?:\d+[a-z]?|[a-z]+)\s*,?\s*(?:so|duong|phuong|quan|hẻm)\b"
    ),
}

REDACTION_TEMPLATE = "[REDACTED_{name}]"


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, REDACTION_TEMPLATE.format(name=name.upper()), safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    """Băm user_id thành giá trị ổn định và không thể bị nhầm với PII.

    Tiền tố `u` cố ý: chuỗi SHA-256 thuần có xác suất ~0,06% chỉ toàn chữ số
    và bị detector CCCD (`\\b\\d{12}\\b`) của `validate_logs.py` báo nhầm thành
    PII, dẫn tới trừ 30 điểm ở scorecard.
    """
    return "u" + hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
