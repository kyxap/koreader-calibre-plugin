
import pytest
from __init__ import clean_bookmarks

def test_clean_bookmarks_large_payload():
    # Simulate a 1.8MB metadata file scenario:
    # 900 annotations, each with ~2KB of text/notes.
    num_annotations = 900
    large_text = "A" * 1000  # 1KB of text
    large_note = "B" * 1000  # 1KB of note
    
    bookmarks = {}
    for i in range(1, num_annotations + 1):
        bookmarks[i] = {
            'chapter': f'Chapter {i // 10}',
            'note': f'Note {i}: {large_note}',
            'text': f'Highlight {i}: {large_text}',
            'datetime': '2023-01-01 12:00:00'
        }
    
    result = clean_bookmarks(bookmarks)
    
    # Check that the result is a string
    assert isinstance(result, str)
    
    # With the fix (O(N) complexity):
    # Total size should be roughly (2KB per highlight * 900) + HTML overhead
    # 2000 * 900 = 1.8 MB. 
    # We allow some headroom for HTML and hidden attributes.
    # Calibre's SQLite limit for a single cell (Long Text) is technically 1GB, 
    # but practical performance issues start much earlier (usually around 10-20MB).
    # 5MB is a very safe upper bound for 900 highlights of this size.
    assert len(result) < 5 * 1024 * 1024 
    
    # Verify content
    assert 'Chapter 0' in result
    assert 'Note 1:' in result
    assert '900. Highlight' in result

def test_clean_bookmarks_empty():
    assert 'Book Highlights and Notes' in clean_bookmarks({})
