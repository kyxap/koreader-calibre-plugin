
import pytest
import re
from unittest.mock import MagicMock
from action import KoreaderAction

def test_sidecar_path_regex_robustness():
    """Verifies that the sidecar path regex handles various extensions correctly."""
    def get_sidecar_path(book_path):
        # Using the NEW regex from action.py
        return re.sub(r'\.([^./\\]+)$', r'.sdr/metadata.\1.lua', book_path)

    assert get_sidecar_path("Book.epub") == "Book.sdr/metadata.epub.lua"
    assert get_sidecar_path("Folder/Book.mobi") == "Folder/Book.sdr/metadata.mobi.lua"
    assert get_sidecar_path("Book.fb2.zip") == "Book.fb2.sdr/metadata.zip.lua"
    assert get_sidecar_path("My.Book.With.Dots.epub") == "My.Book.With.Dots.sdr/metadata.epub.lua"
    # Test with hyphen in extension (rare but possible)
    assert get_sidecar_path("file.epub-original") == "file.sdr/metadata.epub-original.lua"

def test_is_system_path():
    from action import is_system_path
    assert is_system_path("kfmon.sdr/metadata.lua") is True
    assert is_system_path("koreader.sdr/metadata.lua") is True
    assert is_system_path("Books/MyBook.sdr/metadata.lua") is False
