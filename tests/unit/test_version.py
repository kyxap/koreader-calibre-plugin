import os
import re

def test_version_match():
    """Check if version in .version matches version in __init__.py"""
    with open(".version", "r") as f:
        version = f.read().strip()

    # Enforce no '-pre' on main branch releases
    # GITHUB_REF_NAME is provided by GitHub Actions
    is_main = os.environ.get('GITHUB_REF_NAME') == 'main'
    
    if is_main:
        assert "-pre" not in version, "Release error: .version file on 'main' branch must not contain '-pre'!"

    with open("__init__.py", "r") as f:
        content = f.read()
        
        # On main, we expect an exact match.
        # On other branches, we allow -pre or -dev suffixes (added by 'make pre' or 'make dev')
        if is_main:
            pattern = rf'version_string\s*=\s*[\'"]{re.escape(version)}[\'"]'
        else:
            pattern = rf'version_string\s*=\s*[\'"]{re.escape(version)}(-pre|-dev)?[\'"]'
            
        assert re.search(pattern, content), f"Version string matching '{version}' not found in __init__.py"

def test_version_tuple_match():
    """Check if version in .version matches version tuple in __init__.py"""
    with open(".version", "r") as f:
        version = f.read().strip()

    # Strip any suffix like -pre or -dev for the numeric tuple
    # This matches the logic in our Makefile
    numeric_version = version.split("-")[0]
    parts = numeric_version.split(".")
    
    # format (0, 8, 0)
    version_tuple = f"({', '.join(parts)})"

    with open("__init__.py", "r") as f:
        content = f.read()
        expected = f"version = {version_tuple}"
        assert expected in content, f"Expected {expected} not found in __init__.py"
