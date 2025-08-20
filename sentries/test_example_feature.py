"""
Tests for example_feature module.

This file contains tests that will fail to demonstrate TestSentry functionality.
"""

import pytest
from sentries.example_feature import (
    process_user_data, calculate_statistics, validate_email,
    generate_report, undocumented_function, complex_business_logic
)


def test_process_user_data_valid_input():
    """Test process_user_data with valid input."""
    input_data = '{"name": "John Doe", "age": 30}'
    result = process_user_data(input_data)

    assert result["name"] == "John Doe"
    assert result["age"] == 30
    assert result["status"] == "valid"
    assert result["processed"] is True


def test_process_user_data_missing_name():
    """Test process_user_data with missing name."""
    input_data = '{"age": 30}'
    result = process_user_data(input_data)

    assert "error" in result
    assert "Name is required" in result["error"]


def test_process_user_data_missing_age():
    """Test process_user_data with missing age."""
    input_data = '{"name": "John Doe"}'
    result = process_user_data(input_data)

    assert "error" in result
    assert "Age is required" in result["error"]


def test_process_user_data_invalid_age():
    """Test process_user_data with invalid age."""
    input_data = '{"name": "John Doe", "age": -5}'
    result = process_user_data(input_data)

    assert "error" in result
    assert "Invalid age range" in result["error"]


def test_process_user_data_invalid_json():
    """Test process_user_data with invalid JSON."""
    input_data = '{"name": "John Doe", "age": 30'  # Missing closing brace
    result = process_user_data(input_data)

    assert "error" in result
    assert "Invalid JSON format" in result["error"]


def test_calculate_statistics_empty_list():
    """Test calculate_statistics with empty list."""
    result = calculate_statistics([])

    assert "error" in result
    assert "No numbers provided" in result["error"]


def test_calculate_statistics_single_number():
    """Test calculate_statistics with single number."""
    result = calculate_statistics([42.0])

    assert result["count"] == 1
    assert result["mean"] == 42.0
    assert result["median"] == 42.0
    assert result["std_dev"] == 0.0
    assert result["variance"] == 0.0
    assert result["min"] == 42.0
    assert result["max"] == 42.0
    assert result["range"] == 0.0


def test_calculate_statistics_multiple_numbers():
    """Test calculate_statistics with multiple numbers."""
    numbers = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = calculate_statistics(numbers)

    assert result["count"] == 5
    assert result["mean"] == 3.0
    assert result["median"] == 3.0
    assert result["min"] == 1.0
    assert result["max"] == 5.0
    assert result["range"] == 4.0


def test_validate_email_valid():
    """Test validate_email with valid email."""
    assert validate_email("user@example.com") is True
    assert validate_email("test.user@domain.co.uk") is True
    assert validate_email("simple@test.org") is True


def test_validate_email_invalid():
    """Test validate_email with invalid email."""
    assert validate_email("") is False
    assert validate_email("invalid-email") is False
    assert validate_email("@domain.com") is False
    assert validate_email("user@") is False
    assert validate_email("user@domain") is False


def test_generate_report_text_format():
    """Test generate_report with text format."""
    data = {"name": "Test", "count": 42, "items": [1, 2, 3]}
    result = generate_report(data, "text")

    assert "Report" in result
    assert "name: Test" in result
    assert "count: 42" in result
    assert "items: 3 items" in result


def test_generate_report_json_format():
    """Test generate_report with JSON format."""
    data = {"name": "Test", "count": 42}
    result = generate_report(data, "json")

    assert "name" in result
    assert "Test" in result
    assert "count" in result
    assert "42" in result


def test_generate_report_unsupported_format():
    """Test generate_report with unsupported format."""
    data = {"name": "Test"}
    result = generate_report(data, "xml")

    assert "Unsupported format: xml" in result


def test_generate_report_empty_data():
    """Test generate_report with empty data."""
    result = generate_report({}, "text")

    assert "No data to report" in result


def test_undocumented_function():
    """Test undocumented_function."""
    assert undocumented_function(5, 3) == 8
    assert undocumented_function(50, 60) == 220  # (50+60)*2 > 100


def test_complex_business_logic_basic():
    """Test complex_business_logic with basic rules."""
    user_data = {"age": 25, "income": 50000}
    business_rules = [
        {
            "enabled": True,
            "conditions": [
                {"field": "age", "operator": "greater_than", "value": 18}
            ],
            "action": "approve"
        }
    ]

    result = complex_business_logic(user_data, business_rules)

    assert result["processed"] is True
    assert result["approved"] is True
    assert result["rules_applied"] == 1


def test_complex_business_logic_rejection():
    """Test complex_business_logic with rejection rules."""
    user_data = {"age": 16, "income": 50000}
    business_rules = [
        {
            "enabled": True,
            "conditions": [
                {"field": "age", "operator": "greater_than", "value": 18}
            ],
            "action": "reject"
        }
    ]

    result = complex_business_logic(user_data, business_rules)

    assert result["processed"] is True
    assert result["rules_applied"] == 0  # No rules applied due to age condition


def test_complex_business_logic_flagging():
    """Test complex_business_logic with flagging rules."""
    user_data = {"age": 25, "income": 50000}
    business_rules = [
        {
            "enabled": True,
            "conditions": [
                {"field": "income", "operator": "less_than", "value": 100000}
            ],
            "action": "flag",
            "message": "Low income warning"
        }
    ]

    result = complex_business_logic(user_data, business_rules)

    assert result["processed"] is True
    assert result["flagged"] is True
    assert "Low income warning" in result["warnings"]
    assert result["rules_applied"] == 1


def test_complex_business_logic_missing_data():
    """Test complex_business_logic with missing data."""
    result = complex_business_logic({}, [])

    assert "error" in result
    assert "Missing data or rules" in result["error"]


def test_complex_business_logic_disabled_rule():
    """Test complex_business_logic with disabled rule."""
    user_data = {"age": 25}
    business_rules = [
        {
            "enabled": False,
            "conditions": [
                {"field": "age", "operator": "greater_than", "value": 18}
            ],
            "action": "approve"
        }
    ]

    result = complex_business_logic(user_data, business_rules)

    assert result["processed"] is True
    assert result["rules_applied"] == 0  # Rule is disabled

# This test will fail to demonstrate TestSentry functionality


def test_failing_function():
    """This test will fail and should be fixed by TestSentry."""
    assert 1 == 2, "This assertion will fail"


def test_another_failing_test():
    """Another failing test for variety."""
    result = 2 + 2
    assert result == 5, f"Expected 5, got {result}"


if __name__ == "__main__":
    pytest.main([__file__])
