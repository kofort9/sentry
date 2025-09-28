"""PII detection using regex patterns."""

import re
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PIISpan:
    """A detected PII span with metadata."""

    start: int
    end: int
    pii_type: str
    confidence: float = 1.0
    reason_code: str = ""


@dataclass
class PIIDetectionResult:
    """Result of PII detection analysis."""
    
    pii_spans: List[PIISpan]
    total_pii_chars: int
    leakage_rate: float = 0.0
    
    def __post_init__(self):
        """Calculate derived metrics."""
        if not hasattr(self, 'total_pii_chars') or self.total_pii_chars is None:
            self.total_pii_chars = sum(span.end - span.start for span in self.pii_spans)


# Regex patterns for PII detection
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")

IPV4_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)

IPV6_PATTERN = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b")

PHONE_PATTERN = re.compile(
    r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b"
)

CREDIT_CARD_PATTERN = re.compile(
    r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|"
    r"3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
)

AWS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

API_TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9]{32,}\b")

# Combined pattern for all PII types
ALL_PII_PATTERNS = {
    "email": EMAIL_PATTERN,
    "ipv4": IPV4_PATTERN,
    "ipv6": IPV6_PATTERN,
    "phone": PHONE_PATTERN,
    "credit_card": CREDIT_CARD_PATTERN,
    "aws_key": AWS_KEY_PATTERN,
    "api_token": API_TOKEN_PATTERN,
}


def detect_email(text: str) -> List[PIISpan]:
    """Detect email addresses in text."""
    spans = []
    for match in EMAIL_PATTERN.finditer(text):
        spans.append(
            PIISpan(
                start=match.start(), end=match.end(), pii_type="email", reason_code="email_regex"
            )
        )
    return spans


def detect_ip_address(text: str) -> List[PIISpan]:
    """Detect IP addresses (IPv4 and IPv6) in text."""
    spans = []

    # IPv4
    for match in IPV4_PATTERN.finditer(text):
        spans.append(
            PIISpan(start=match.start(), end=match.end(), pii_type="ipv4", reason_code="ipv4_regex")
        )

    # IPv6
    for match in IPV6_PATTERN.finditer(text):
        spans.append(
            PIISpan(start=match.start(), end=match.end(), pii_type="ipv6", reason_code="ipv6_regex")
        )

    return spans


def detect_phone_number(text: str) -> List[PIISpan]:
    """Detect phone numbers in text."""
    spans = []
    for match in PHONE_PATTERN.finditer(text):
        spans.append(
            PIISpan(
                start=match.start(), end=match.end(), pii_type="phone", reason_code="phone_regex"
            )
        )
    return spans


def detect_credit_card(text: str) -> List[PIISpan]:
    """Detect credit card numbers in text."""
    spans = []
    for match in CREDIT_CARD_PATTERN.finditer(text):
        # Additional validation using Luhn algorithm
        card_number = match.group().replace(" ", "").replace("-", "")
        if is_valid_credit_card(card_number):
            spans.append(
                PIISpan(
                    start=match.start(),
                    end=match.end(),
                    pii_type="credit_card",
                    reason_code="credit_card_regex_luhn",
                )
            )
    return spans


def detect_aws_key(text: str) -> List[PIISpan]:
    """Detect AWS access keys in text."""
    spans = []
    for match in AWS_KEY_PATTERN.finditer(text):
        spans.append(
            PIISpan(
                start=match.start(),
                end=match.end(),
                pii_type="aws_key",
                reason_code="aws_key_regex",
            )
        )
    return spans


def detect_api_token(text: str) -> List[PIISpan]:
    """Detect API tokens in text."""
    spans = []
    for match in API_TOKEN_PATTERN.finditer(text):
        # Filter out common false positives
        token = match.group()
        if not is_likely_false_positive(token):
            spans.append(
                PIISpan(
                    start=match.start(),
                    end=match.end(),
                    pii_type="api_token",
                    reason_code="api_token_regex",
                )
            )
    return spans


def detect_all_pii(text: str) -> List[PIISpan]:
    """Detect all types of PII in text."""
    all_spans = []

    # Run all detectors
    all_spans.extend(detect_email(text))
    all_spans.extend(detect_ip_address(text))
    all_spans.extend(detect_phone_number(text))
    all_spans.extend(detect_credit_card(text))
    all_spans.extend(detect_aws_key(text))
    all_spans.extend(detect_api_token(text))

    # Remove overlapping spans (keep the longest)
    all_spans = remove_overlapping_spans(all_spans)

    return all_spans


def is_valid_credit_card(card_number: str) -> bool:
    """Validate credit card number using Luhn algorithm."""

    def luhn_checksum(card_num):
        def digits_of(n):
            return [int(d) for d in str(n)]

        digits = digits_of(card_num)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10

    return luhn_checksum(card_number) == 0


def is_likely_false_positive(token: str) -> bool:
    """Check if a token is likely a false positive for API token detection."""
    # Common false positives
    false_positives = {
        "def",
        "class",
        "import",
        "from",
        "return",
        "assert",
        "test",
        "function",
        "method",
        "variable",
        "constant",
        "string",
        "integer",
        "boolean",
        "array",
        "object",
        "null",
        "undefined",
        "true",
        "false",
    }

    return token.lower() in false_positives or len(token) < 16


def remove_overlapping_spans(spans: List[PIISpan]) -> List[PIISpan]:
    """Remove overlapping spans, keeping the longest ones."""
    if not spans:
        return spans

    # Sort by start position
    sorted_spans = sorted(spans, key=lambda x: x.start)

    result = []
    current_span = sorted_spans[0]

    for span in sorted_spans[1:]:
        if span.start < current_span.end:
            # Overlapping spans - keep the longer one
            if (span.end - span.start) > (current_span.end - current_span.start):
                current_span = span
        else:
            # No overlap - add current span and move to next
            result.append(current_span)
            current_span = span

    result.append(current_span)
    return result


def get_pii_statistics(spans: List[PIISpan], text: str) -> Dict[str, any]:
    """Get statistics about detected PII spans."""
    if not spans:
        return {
            "total_spans": 0,
            "total_chars": 0,
            "pii_density": 0.0,
            "pii_types": {},
            "char_coverage": 0.0,
        }

    total_chars = sum(span.end - span.start for span in spans)
    text_length = len(text)

    pii_types = {}
    for span in spans:
        pii_types[span.pii_type] = pii_types.get(span.pii_type, 0) + 1

    return {
        "total_spans": len(spans),
        "total_chars": total_chars,
        "pii_density": total_chars / text_length if text_length > 0 else 0.0,
        "pii_types": pii_types,
        "char_coverage": total_chars / text_length if text_length > 0 else 0.0,
    }


def detect_all_pii(text: str) -> PIIDetectionResult:
    """Detect all types of PII in the given text."""
    all_spans = []
    
    # Detect each type of PII
    all_spans.extend(detect_email(text))
    all_spans.extend(detect_ip_address(text))
    all_spans.extend(detect_phone_number(text))
    all_spans.extend(detect_credit_card(text))
    all_spans.extend(detect_aws_key(text))
    all_spans.extend(detect_api_token(text))
    
    # Sort spans by start position
    all_spans.sort(key=lambda span: span.start)
    
    # Calculate total PII characters
    total_pii_chars = sum(span.end - span.start for span in all_spans)
    
    return PIIDetectionResult(
        pii_spans=all_spans,
        total_pii_chars=total_pii_chars,
        leakage_rate=0.0  # Will be calculated later if needed
    )
