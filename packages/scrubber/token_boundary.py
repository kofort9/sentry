"""Map character spans to token spans for different tokenization algorithms."""

from typing import Dict, List, Literal, Tuple

from .detectors import PIISpan


def expand_char_spans_to_token_spans(
    text: str, char_spans: List[PIISpan], tokenizer, algorithm: Literal["bpe", "sp"]
) -> List[Tuple[int, int, str]]:
    """
    Expand character spans to token spans.

    Args:
        text: Original text
        char_spans: List of PII character spans
        tokenizer: BPE or SentencePiece tokenizer
        algorithm: Tokenization algorithm

    Returns:
        List of (start_token, end_token, pii_type) tuples
    """
    token_spans = []

    if algorithm == "bpe":
        token_spans = _expand_bpe_spans(text, char_spans, tokenizer)
    elif algorithm == "sp":
        token_spans = _expand_sp_spans(text, char_spans, tokenizer)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")

    return token_spans


def _expand_bpe_spans(
    text: str, char_spans: List[PIISpan], tokenizer
) -> List[Tuple[int, int, str]]:
    """Expand character spans to BPE token spans."""
    # Get tokenization with offsets
    encoding = tokenizer.encode(text)
    token_offsets = encoding.offsets

    token_spans = []

    for char_span in char_spans:
        start_token = None
        end_token = None

        # Find tokens that overlap with character span
        for i, (token_start, token_end) in enumerate(token_offsets):
            # Token overlaps with character span
            if token_start < char_span.end and token_end > char_span.start:
                if start_token is None:
                    start_token = i
                end_token = i

        if start_token is not None and end_token is not None:
            token_spans.append((start_token, end_token, char_span.pii_type))

    return token_spans


def _expand_sp_spans(text: str, char_spans: List[PIISpan], tokenizer) -> List[Tuple[int, int, str]]:
    """Expand character spans to SentencePiece token spans."""
    # For SentencePiece, we need to work with the subword tokens
    tokens = tokenizer.encode(text, out_type=str)

    token_spans = []

    for char_span in char_spans:
        start_token = None
        end_token = None
        char_pos = 0

        for i, token in enumerate(tokens):
            # Calculate character position for this token
            token_start = char_pos

            # Handle SentencePiece subword markers
            if token.startswith("▁"):
                # This is a word boundary
                char_pos += 1
                token_char_length = len(token) - 1
            else:
                # Regular subword token
                token_char_length = len(token)

            char_pos += token_char_length
            token_end = char_pos

            # Check if this token overlaps with the character span
            if token_start < char_span.end and token_end > char_span.start:
                if start_token is None:
                    start_token = i
                end_token = i

        if start_token is not None and end_token is not None:
            token_spans.append((start_token, end_token, char_span.pii_type))

    return token_spans


def get_token_boundaries(
    text: str, tokenizer, algorithm: Literal["bpe", "sp"]
) -> Dict[int, Tuple[int, int]]:
    """
    Get character boundaries for each token.

    Args:
        text: Input text
        tokenizer: BPE or SentencePiece tokenizer
        algorithm: Tokenization algorithm

    Returns:
        Dict mapping token_index -> (start_char, end_char)
    """
    if algorithm == "bpe":
        return _get_bpe_boundaries(text, tokenizer)
    elif algorithm == "sp":
        return _get_sp_boundaries(text, tokenizer)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}")


def _get_bpe_boundaries(text: str, tokenizer) -> Dict[int, Tuple[int, int]]:
    """Get BPE token boundaries."""
    encoding = tokenizer.encode(text)
    return {i: offset for i, offset in enumerate(encoding.offsets)}


def _get_sp_boundaries(text: str, tokenizer) -> Dict[int, Tuple[int, int]]:
    """Get SentencePiece token boundaries."""
    tokens = tokenizer.encode(text, out_type=str)
    boundaries = {}
    char_pos = 0

    for i, token in enumerate(tokens):
        start_pos = char_pos

        if token.startswith("▁"):
            # Word boundary marker
            char_pos += 1
            char_pos += len(token) - 1
        else:
            # Regular subword token
            char_pos += len(token)

        boundaries[i] = (start_pos, char_pos)

    return boundaries


def find_token_span_for_char_span(
    char_start: int, char_end: int, token_boundaries: Dict[int, Tuple[int, int]]
) -> Tuple[int, int]:
    """
    Find the token span that covers a character span.

    Args:
        char_start: Start character position
        char_end: End character position
        token_boundaries: Token boundary mapping

    Returns:
        (start_token, end_token) inclusive token span
    """
    start_token = None
    end_token = None

    for token_idx, (token_start, token_end) in token_boundaries.items():
        # Token overlaps with character span
        if token_start < char_end and token_end > char_start:
            if start_token is None:
                start_token = token_idx
            end_token = token_idx

    if start_token is None:
        start_token = 0
    if end_token is None:
        end_token = len(token_boundaries) - 1

    return start_token, end_token
