"""Generate synthetic events for testing and benchmarking."""

import random
import string
from datetime import datetime, timedelta
from typing import List

import pandas as pd


def generate_synthetic_events(
    num_events: int = 1000,
    services: List[str] = None,
    releases: List[str] = None,
    pii_density: float = 0.1,
    start_date: datetime = None,
) -> pd.DataFrame:
    """
    Generate synthetic events with controllable PII density.

    Args:
        num_events: Number of events to generate
        services: List of service names
        releases: List of release versions
        pii_density: Fraction of events that should contain PII
        start_date: Start date for event timestamps

    Returns:
        DataFrame with synthetic events
    """
    if services is None:
        services = ["testsentry", "docsentry", "patch-engine", "git-utils"]

    if releases is None:
        releases = ["v0.1.0", "v0.1.1", "v0.2.0", "dev", "main"]

    if start_date is None:
        start_date = datetime.now() - timedelta(days=30)

    events = []

    for i in range(num_events):
        # Generate base event
        service = random.choice(services)
        release = random.choice(releases)
        ts = start_date + timedelta(seconds=random.randint(0, 30 * 24 * 60 * 60))  # 30 days

        # Generate message with or without PII
        if random.random() < pii_density:
            message = generate_message_with_pii()
        else:
            message = generate_clean_message()

        event = {
            "message": message,
            "service": service,
            "release": release,
            "ts": ts,
            "event_type": "llm_interaction",
            "metadata": {
                "token_count": len(message.split()),
                "char_count": len(message),
                "has_pii": random.random() < pii_density,
            },
        }

        events.append(event)

    return pd.DataFrame(events)


def generate_clean_message() -> str:
    """Generate a clean message without PII."""
    templates = [
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
        "Error: test failed",
        "Warning: deprecated function used",
        "Info: test completed successfully",
        "Debug: entering function",
        "Trace: function call stack",
        "Exception: division by zero",
        "TypeError: unsupported operand type",
        "ValueError: invalid input",
        "KeyError: key not found",
        "AttributeError: object has no attribute",
    ]

    return random.choice(templates)


def generate_message_with_pii() -> str:
    """Generate a message containing PII."""
    base_message = generate_clean_message()

    # Add various types of PII
    pii_types = [
        generate_email,
        generate_ip_address,
        generate_phone_number,
        generate_credit_card,
        generate_aws_key,
        generate_api_token,
    ]

    # Add 1-3 PII items to the message
    num_pii = random.randint(1, 3)
    pii_items = [random.choice(pii_types)() for _ in range(num_pii)]

    # Insert PII into the message
    words = base_message.split()
    for pii in pii_items:
        insert_pos = random.randint(0, len(words))
        words.insert(insert_pos, pii)

    return " ".join(words)


def generate_email() -> str:
    """Generate a fake email address."""
    domains = ["example.com", "test.org", "demo.net", "sample.io"]
    username = "".join(random.choices(string.ascii_lowercase, k=random.randint(5, 10)))
    domain = random.choice(domains)
    return f"{username}@{domain}"


def generate_ip_address() -> str:
    """Generate a fake IP address."""
    if random.choice([True, False]):
        # IPv4
        return ".".join(str(random.randint(1, 254)) for _ in range(4))
    else:
        # IPv6 (simplified)
        return ":".join(f"{random.randint(0, 65535):x}" for _ in range(8))


def generate_phone_number() -> str:
    """Generate a fake phone number."""
    formats = [
        "({}{}{}) {}{}{}-{}{}{}{}",
        "{}{}{}-{}{}{}-{}{}{}{}",
        "+1-{}{}{}-{}{}{}-{}{}{}{}",
    ]
    template = random.choice(formats)
    digits = [str(random.randint(0, 9)) for _ in range(10)]
    return template.format(*digits)


def generate_credit_card() -> str:
    """Generate a fake credit card number."""
    # Generate a number that passes Luhn algorithm
    prefix = random.choice(["4", "5", "3"])
    number = prefix + "".join(str(random.randint(0, 9)) for _ in range(14))

    # Calculate check digit using Luhn algorithm
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

    check_digit = (10 - luhn_checksum(number)) % 10
    return number + str(check_digit)


def generate_aws_key() -> str:
    """Generate a fake AWS access key."""
    return f"AKIA{''.join(random.choices(string.ascii_uppercase + string.digits, k=16))}"


def generate_api_token() -> str:
    """Generate a fake API token."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=32))


def add_unicode_confusables(text: str, density: float = 0.05) -> str:
    """
    Add unicode confusables to make PII detection more challenging.

    Args:
        text: Input text
        density: Fraction of characters to replace with confusables

    Returns:
        Text with unicode confusables
    """
    # Common unicode confusables
    confusables = {
        "a": ["а", "ɑ", "α"],
        "e": ["е", "ε", "є"],
        "o": ["о", "ο", "σ"],
        "p": ["р", "ρ"],
        "c": ["с", "ϲ"],
        "x": ["х", "χ"],
        "y": ["у", "γ"],
        "i": ["і", "ι", "і"],
        "j": ["ј", "ϳ"],
        "l": ["ⅼ", "ι"],
        "1": ["l", "I", "|"],
        "0": ["O", "ο", "о"],
    }

    result = []
    for char in text:
        if char.lower() in confusables and random.random() < density:
            result.append(random.choice(confusables[char.lower()]))
        else:
            result.append(char)

    return "".join(result)
