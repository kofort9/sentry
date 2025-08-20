"""
Module to trigger sentry jobs for testing the enhanced workflow system.
This file contains functions that will cause TestSentry and DocSentry to run.
"""

def trigger_test_sentry():
    """This function has no tests and will trigger TestSentry to create tests.

    TestSentry should detect this function and create appropriate test cases.

    Returns:
        A message indicating the function was called
    """
    return "TestSentry should create tests for this function!"

def trigger_doc_sentry(name, times):
    """This function has minimal documentation and will trigger DocSentry.

    DocSentry should detect this function and improve its documentation.

    Args:
        name: The name to greet
        times: Number of times to repeat the greeting

    Returns:
        A formatted greeting string
    """
    greeting = f"Hello, {name}!"
    return " ".join([greeting] * times)

def complex_logic_function(items, threshold, transform):
    """This function has complex logic that needs both tests and documentation.

    It performs multiple operations and has edge cases that should be tested.

    Args:
        items: List of items to process
        threshold: Minimum value threshold
        transform: Whether to transform the data

    Returns:
        Dictionary with processing results and statistics
    """
    if not items:
        return {"error": "No items provided", "count": 0}

    valid_items = [item for item in items if item >= threshold]

    if transform:
        processed_items = [item * 2 for item in valid_items]
    else:
        processed_items = valid_items

    return {
        "total_items": len(items),
        "valid_items": len(valid_items),
        "processed_items": len(processed_items),
        "average": sum(processed_items) / len(processed_items) if processed_items else 0,
        "transformed": transform
    }
