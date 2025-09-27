"""Deterministic PII masking with class-preserving HMAC."""

import hashlib
import hmac
from typing import Dict, List, Literal, Tuple


def mask_span(
    text: str, char_span: Tuple[int, int], pii_type: str, key: str = "default_key"
) -> str:
    """
    Mask a span of text with deterministic HMAC.

    Args:
        text: Original text
        char_span: (start_char, end_char) character span
        pii_type: Type of PII being masked
        key: HMAC key for deterministic masking

    Returns:
        Text with the span masked
    """
    start_char, end_char = char_span
    original_span = text[start_char:end_char]

    # Generate deterministic mask
    mask = generate_deterministic_mask(original_span, pii_type, key)

    # Replace the span
    masked_text = text[:start_char] + mask + text[end_char:]

    return masked_text


def mask_text_with_spans(
    text: str, spans: List[Tuple[int, int, str]], key: str = "default_key"
) -> str:
    """
    Mask multiple spans in text.

    Args:
        text: Original text
        spans: List of (start_char, end_char, pii_type) tuples
        key: HMAC key for deterministic masking

    Returns:
        Text with all spans masked
    """
    # Sort spans by start position (descending) to avoid offset issues
    sorted_spans = sorted(spans, key=lambda x: x[0], reverse=True)

    masked_text = text

    for start_char, end_char, pii_type in sorted_spans:
        masked_text = mask_span(masked_text, (start_char, end_char), pii_type, key)

    return masked_text


def generate_deterministic_mask(original_text: str, pii_type: str, key: str) -> str:
    """
    Generate a deterministic mask for PII text.

    Args:
        original_text: Original PII text
        pii_type: Type of PII
        key: HMAC key

    Returns:
        Masked text in format: {pii_type}:{hmac_hash}
    """
    # Create HMAC of the original text
    hmac_hash = hmac.new(
        key.encode("utf-8"), original_text.encode("utf-8"), hashlib.sha256
    ).hexdigest()[
        :8
    ]  # Use first 8 characters

    return f"{pii_type}:{hmac_hash}"


def mask_with_token_spans(
    text: str,
    token_spans: List[Tuple[int, int, str]],
    tokenizer,
    algorithm: Literal["bpe", "sp"],
    key: str = "default_key",
) -> str:
    """
    Mask text using token spans instead of character spans.

    Args:
        text: Original text
        token_spans: List of (start_token, end_token, pii_type) tuples
        tokenizer: BPE or SentencePiece tokenizer
        algorithm: Tokenization algorithm
        key: HMAC key

    Returns:
        Masked text
    """
    # Get token boundaries
    token_boundaries = get_token_boundaries(text, tokenizer, algorithm)

    # Convert token spans to character spans
    char_spans = []
    for start_token, end_token, pii_type in token_spans:
        if start_token in token_boundaries and end_token in token_boundaries:
            start_char = token_boundaries[start_token][0]
            end_char = token_boundaries[end_token][1]
            char_spans.append((start_char, end_char, pii_type))

    # Mask using character spans
    return mask_text_with_spans(text, char_spans, key)


def get_token_boundaries(
    text: str, tokenizer, algorithm: Literal["bpe", "sp"]
) -> Dict[int, Tuple[int, int]]:
    """Get token boundaries for masking."""
    from .token_boundary import get_token_boundaries as _get_token_boundaries

    return _get_token_boundaries(text, tokenizer, algorithm)


def validate_masking(
    original_text: str, masked_text: str, expected_spans: List[Tuple[int, int, str]]
) -> Dict[str, any]:
    """
    Validate that masking was applied correctly.

    Args:
        original_text: Original text
        masked_text: Masked text
        expected_spans: Expected masked spans

    Returns:
        Validation metrics
    """
    # Check that text length is preserved
    length_preserved = len(original_text) == len(masked_text)

    # Check that non-masked parts are unchanged
    unchanged_chars = 0
    for i, (orig_char, masked_char) in enumerate(zip(original_text, masked_text)):
        if orig_char == masked_char:
            unchanged_chars += 1

    # Check that masked spans contain the expected format
    masked_spans_found = 0
    for start_char, end_char, pii_type in expected_spans:
        masked_span = masked_text[start_char:end_char]
        if masked_span.startswith(f"{pii_type}:"):
            masked_spans_found += 1

    return {
        "length_preserved": length_preserved,
        "unchanged_chars": unchanged_chars,
        "total_chars": len(original_text),
        "unchanged_ratio": unchanged_chars / len(original_text) if original_text else 0,
        "expected_spans": len(expected_spans),
        "masked_spans_found": masked_spans_found,
        "masking_accuracy": masked_spans_found / len(expected_spans) if expected_spans else 1.0,
    }


def extract_masked_spans(masked_text: str) -> List[Tuple[int, int, str, str]]:
    """
    Extract information about masked spans from masked text.

    Args:
        masked_text: Text that has been masked

    Returns:
        List of (start_char, end_char, pii_type, mask_hash) tuples
    """
    import re

    # Pattern to match masked spans: {pii_type}:{hash}
    pattern = re.compile(r"(\w+):([a-f0-9]{8})")

    spans = []
    for match in pattern.finditer(masked_text):
        start_char = match.start()
        end_char = match.end()
        pii_type = match.group(1)
        mask_hash = match.group(2)

        spans.append((start_char, end_char, pii_type, mask_hash))

    return spans
