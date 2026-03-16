import os

def test_version_match():
    """Check if version in .version matches version in __init__.py"""
    with open(".version", "r") as f:
        version = f.read().strip()

    with open("__init__.py", "r") as f:
        content = f.read()
        # Look for version_string = '0.8.0'
        expected = f"version_string = '{version}'"
        assert expected in content, f"Expected {expected} not found in __init__.py"

def test_version_tuple_match():
    """Check if version in .version matches version tuple in __init__.py"""
    with open(".version", "r") as f:
        version = f.read().strip()

    parts = version.split(".")
    # format (0, 8, 0)
    version_tuple = f"({', '.join(parts)})"

    with open("__init__.py", "r") as f:
        content = f.read()
        expected = f"version = {version_tuple}"
        assert expected in content, f"Expected {expected} not found in __init__.py"
