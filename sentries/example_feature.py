"""
Example feature module to demonstrate CodeSentry functionality.

This module contains functions that:
1. Lack comprehensive tests
2. Need better documentation
3. Have varying complexity levels
"""
import json


from typing import Dict, List, Optional

def process_user_data(user_input: str) -> Dict[str, any]:
    """Process user input and return structured data."""
    # This function has medium complexity and needs tests
    if not user_input:
        return {"error": "No input provided"}

    try:
        # Parse JSON input
        data = json.loads(user_input)

        # Validate required fields
        if "name" not in data:
            return {"error": "Name is required"}

        if "age" not in data:
            return {"error": "Age is required"}

        # Process and validate age
        age = int(data["age"])
        if age < 0 or age > 150:
            return {"error": "Invalid age range"}

        # Return processed data
        return {
            "name": data["name"],
            "age": age,
            "status": "valid",
            "processed": True
        }

    except json.JSONDecodeError:
        return {"error": "Invalid JSON format"}
    except ValueError:
        return {"error": "Invalid age value"}

def calculate_statistics(numbers: List[float]) -> Dict[str, float]:
    """Calculate basic statistics for a list of numbers."""
    # This function has high complexity and definitely needs tests
    if not numbers:
        return {"error": "No numbers provided"}

    # Calculate mean
    total = sum(numbers)
    count = len(numbers)
    mean = total / count

    # Calculate variance and standard deviation
    variance = sum((x - mean) ** 2 for x in numbers) / count
    std_dev = variance ** 0.5

    # Find min and max
    min_val = min(numbers)
    max_val = max(numbers)

    # Calculate median
    sorted_numbers = sorted(numbers)
    if count % 2 == 0:
        median = (sorted_numbers[count // 2 - 1] + sorted_numbers[count // 2]) / 2
    else:
        median = sorted_numbers[count // 2]

    return {
        "count": count,
        "mean": mean,
        "median": median,
        "std_dev": std_dev,
        "variance": variance,
        "min": min_val,
        "max": max_val,
        "range": max_val - min_val
    }

def validate_email(email: str) -> bool:
    """Validate email address format."""
    # Simple function with low complexity
    if not email or "@" not in email:
        return False

    parts = email.split("@")
    if len(parts) != 2:
        return False

    local, domain = parts

    if not local or not domain:
        return False

    if "." not in domain:
        return False

    return True

def generate_report(data: Dict[str, any], format_type: str = "text") -> str:
    """Generate a report in the specified format."""
    # This function has medium complexity and needs tests
    if not data:
        return "No data to report"

    if format_type == "json":
        return json.dumps(data, indent=2)
    elif format_type == "text":
        lines = []
        lines.append("Report")
        lines.append("=" * 20)

        for key, value in data.items():
            if isinstance(value, (int, float)):
                lines.append(f"{key}: {value}")
            elif isinstance(value, str):
                lines.append(f"{key}: {value}")
            elif isinstance(value, list):
                lines.append(f"{key}: {len(value)} items")
            elif isinstance(value, dict):
                lines.append(f"{key}: {len(value)} fields")
            else:
                lines.append(f"{key}: {type(value).__name__}")

        return "\n".join(lines)
    else:
        return f"Unsupported format: {format_type}"

# This function has no docstring and will be flagged by CodeSentry
def undocumented_function(x: int, y: int) -> int:


    result = x + y
    if result > 100:
        result = result * 2
    return result

# This function has high complexity and will need comprehensive testing
def complex_business_logic(user_data: Dict[str, any], business_rules: List[Dict[str, any]]) -> Dict[str, any]:
    """Apply business rules to user data."""
    if not user_data or not business_rules:
        return {"error": "Missing data or rules"}

    result = {"processed": False, "rules_applied": 0, "warnings": []}

    try:
        # Apply each business rule
        for rule in business_rules:
            if rule.get("enabled", True):
                # Check rule conditions
                conditions_met = True
                for condition in rule.get("conditions", []):
                    field = condition.get("field")
                    operator = condition.get("operator")
                    value = condition.get("value")

                    if field not in user_data:
                        conditions_met = False
                        break

                    user_value = user_data[field]

                    if operator == "equals" and user_value != value:
                        conditions_met = False
                    elif operator == "greater_than" and user_value <= value:
                        conditions_met = False
                    elif operator == "less_than" and user_value >= value:
                        conditions_met = False
                    elif operator == "contains" and value not in str(user_value):
                        conditions_met = False

                # Apply rule if conditions are met
                if conditions_met:
                    action = rule.get("action")
                    if action == "approve":
                        result["approved"] = True
                    elif action == "reject":
                        result["rejected"] = True
                    elif action == "flag":
                        result["flagged"] = True
                        result["warnings"].append(rule.get("message", "Rule violation"))

                    result["rules_applied"] += 1

        result["processed"] = True

    except Exception as e:
        result["error"] = str(e)

    return result

# Example feature module for testing sentries
# This file is intentionally simple to demonstrate CodeSentry's capabilities

def example_function():
    """A simple function that returns a greeting."""
    return "Hello, World!"

def calculate_sum(a, b):
    """Calculate the sum of two numbers.

    Args:
        a: First number
        b: Second number

    Returns:
        Sum of a and b
    """
    return a + b

def process_data(data_list):
    """Process a list of data items.

    This function demonstrates more complex logic that might need testing.

    Args:
        data_list: List of data items to process

    Returns:
        Processed data with additional metadata
    """
    if not data_list:
        return {"items": [], "count": 0, "processed": False}

    processed_items = []
    for item in data_list:
        if isinstance(item, (int, float)):
            processed_items.append(item * 2)
        elif isinstance(item, str):
            processed_items.append(item.upper())
        else:
            processed_items.append(str(item))

    return {
        "items": processed_items,
        "count": len(processed_items),
        "processed": True,
        "original_count": len(data_list)
    }

def new_feature_for_testing():
    """This is a new function added to trigger TestSentry and DocSentry.

    This function has no tests and minimal documentation, making it a perfect
    candidate for both TestSentry to create tests and DocSentry to improve docs.

    Returns:
        A dictionary with feature information
    """
    return {
        "name": "Enhanced Workflow Testing",
        "status": "active",
        "version": "2.0.0",
        "features": ["smart detection", "resource optimization", "stable automation"]
    }
