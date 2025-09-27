"""Tokenization utilities for BPE and SentencePiece."""

from typing import Dict, List, Literal, Tuple

import sentencepiece as spm
from tokenizers import Tokenizer
from tokenizers.models import BPE
from tokenizers.pre_tokenizers import ByteLevelPreTokenizer
from tokenizers.processors import ByteLevelProcessing
from tokenizers.trainers import BpeTrainer


def build_bpe_tokenizer(vocab_size: int = 32000) -> Tokenizer:
    """
    Build a byte-level BPE tokenizer.

    Args:
        vocab_size: Target vocabulary size

    Returns:
        Trained BPE tokenizer
    """
    # Create BPE model
    tokenizer = Tokenizer(BPE(unk_token="<unk>"))

    # Add pre-tokenizer
    tokenizer.pre_tokenizer = ByteLevelPreTokenizer(add_prefix_space=True)

    # Add post-processor
    tokenizer.post_processor = ByteLevelProcessing(trim_offsets=True)

    # Create trainer
    trainer = BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=["<unk>", "<s>", "</s>", "<pad>"],
        min_frequency=2,
        show_progress=True,
    )

    # Train on a basic corpus (we'll use synthetic data)
    corpus = [
        "def test_function():",
        "    assert 1 == 1",
        "    return True",
        "def test_another():",
        "    assert 2 == 2",
        "    return False",
        "class TestClass:",
        "    def test_method(self):",
        "        assert self.value > 0",
        "        return self.value",
    ]

    tokenizer.train_from_iterator(corpus, trainer)

    return tokenizer


def build_sentencepiece_unigram(
    vocab_size: int = 32000, domain_preserve: List[str] = None
) -> spm.SentencePieceProcessor:
    """
    Build a SentencePiece Unigram tokenizer.

    Args:
        vocab_size: Target vocabulary size
        domain_preserve: List of domain-specific strings to preserve

    Returns:
        Trained SentencePiece processor
    """
    if domain_preserve is None:
        domain_preserve = ["Error[E0277]", "NullReferenceException", "assert", "def", "class"]

    # Create training data with domain-specific terms
    corpus = [
        "def test_function():",
        "    assert 1 == 1",
        "    return True",
        "def test_another():",
        "    assert 2 == 2",
        "    return False",
        "class TestClass:",
        "    def test_method(self):",
        "        assert self.value > 0",
        "        return self.value",
    ]

    # Add domain-specific terms
    for term in domain_preserve:
        corpus.append(f" {term} ")

    # Write corpus to temporary file
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("\n".join(corpus))
        corpus_file = f.name

    try:
        # Train SentencePiece model
        spm.SentencePieceTrainer.train(
            input=corpus_file,
            model_prefix="sp_model",
            vocab_size=vocab_size,
            character_coverage=0.9995,
            model_type="unigram",
            user_defined_symbols=domain_preserve,
        )

        # Load the trained model
        processor = spm.SentencePieceProcessor()
        processor.load("sp_model.model")

        return processor

    finally:
        # Clean up
        os.unlink(corpus_file)
        if os.path.exists("sp_model.model"):
            os.unlink("sp_model.model")
        if os.path.exists("sp_model.vocab"):
            os.unlink("sp_model.vocab")


def tokenize_text(text: str, tokenizer, algo: Literal["bpe", "sp"]) -> List[int]:
    """
    Tokenize text and return token IDs.

    Args:
        text: Input text to tokenize
        tokenizer: BPE or SentencePiece tokenizer
        algo: Algorithm type ("bpe" or "sp")

    Returns:
        List of token IDs
    """
    if algo == "bpe":
        encoding = tokenizer.encode(text)
        return encoding.ids
    elif algo == "sp":
        return tokenizer.encode(text, out_type=int)
    else:
        raise ValueError(f"Unknown algorithm: {algo}")


def span_to_token_indices(
    text: str, char_span: Tuple[int, int], tokenizer, algo: Literal["bpe", "sp"]
) -> Tuple[int, int]:
    """
    Convert character span to token span indices.

    Args:
        text: Original text
        char_span: (start_char, end_char) character span
        tokenizer: BPE or SentencePiece tokenizer
        algo: Algorithm type

    Returns:
        (start_token, end_token) inclusive token span
    """
    start_char, end_char = char_span

    if algo == "bpe":
        encoding = tokenizer.encode(text)
        offsets = encoding.offsets

        # Find tokens that overlap with character span
        start_token = None
        end_token = None

        for i, (token_start, token_end) in enumerate(offsets):
            if token_start <= start_char < token_end:
                start_token = i
            if token_start < end_char <= token_end:
                end_token = i
                break

        if start_token is None:
            start_token = 0
        if end_token is None:
            end_token = len(offsets) - 1

        return start_token, end_token

    elif algo == "sp":
        # For SentencePiece, we need to decode and re-encode to get offsets
        # This is a simplified approach - in practice you'd want more robust offset tracking
        tokens = tokenizer.encode(text, out_type=str)
        char_pos = 0
        start_token = 0
        end_token = len(tokens) - 1

        for i, token in enumerate(tokens):
            # Skip special tokens for position calculation
            if token.startswith("▁"):
                char_pos += 1
            elif not token.startswith("<"):
                char_pos += len(token)

            if char_pos >= start_char and start_token == 0:
                start_token = i
            if char_pos >= end_char:
                end_token = i
                break

        return start_token, end_token
    else:
        raise ValueError(f"Unknown algorithm: {algo}")


def get_token_boundaries(
    text: str, tokenizer, algo: Literal["bpe", "sp"]
) -> Dict[int, Tuple[int, int]]:
    """
    Get character boundaries for each token.

    Args:
        text: Input text
        tokenizer: BPE or SentencePiece tokenizer
        algo: Algorithm type

    Returns:
        Dict mapping token_index -> (start_char, end_char)
    """
    if algo == "bpe":
        encoding = tokenizer.encode(text)
        return {i: offset for i, offset in enumerate(encoding.offsets)}
    elif algo == "sp":
        # For SentencePiece, this is more complex due to subword nature
        # This is a simplified implementation
        tokens = tokenizer.encode(text, out_type=str)
        boundaries = {}
        char_pos = 0

        for i, token in enumerate(tokens):
            start_pos = char_pos
            if token.startswith("▁"):
                char_pos += 1
            elif not token.startswith("<"):
                char_pos += len(token)
            else:
                # Special token, don't advance position
                pass
            boundaries[i] = (start_pos, char_pos)

        return boundaries
    else:
        raise ValueError(f"Unknown algorithm: {algo}")
