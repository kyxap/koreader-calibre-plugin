
import os
import sqlite3
import pytest
from unittest.mock import MagicMock
from action import KoreaderAction

def test_dummy_data_consistency():
    # Verify dummy_library metadata.db
    conn = sqlite3.connect('dummy_library/metadata.db')
    cursor = conn.cursor()
    cursor.execute('SELECT title, uuid FROM books')
    db_books = {title: uuid for title, uuid in cursor.fetchall()}
    conn.close()

    assert "Alice's Adventures in Wonderland" in db_books
    assert "Walden, and On The Duty Of Civil Disobedience" in db_books

    # Verify dummy_device paths
    alice_path = "Carroll, Lewis/Alice's Adventures in Wonderland - Lewis Carroll.epub"
    thoreau_path = "Thoreau, Henry David/Walden, and On The Duty Of Civil Disobedience - Henry David Thoreau.epub"
    
    assert os.path.exists(os.path.join('dummy_device', alice_path))
    assert os.path.exists(os.path.join('dummy_device', thoreau_path))

def test_get_paths_with_dummy_device():
    # Mock book objects as they would come from a real device driver
    class MockBook:
        def __init__(self, uuid, path):
            self.uuid = uuid
            self.path = path

    alice_book = MockBook(
        uuid='43bd8264-96fa-461a-a05e-1d1cb245d34f',
        path="Carroll, Lewis/Alice's Adventures in Wonderland - Lewis Carroll.epub"
    )
    thoreau_book = MockBook(
        uuid='3393747a-f0d8-44e1-bfaf-5fad857da3eb',
        path="Thoreau, Henry David/Walden, and On The Duty Of Civil Disobedience - Henry David Thoreau.epub"
    )

    mock_device = MagicMock()
    mock_device.books.return_value = [alice_book, thoreau_book]

    # Instantiate action with mocks for parent and site_customization
    mock_parent = MagicMock()
    mock_site_customization = MagicMock()
    mock_site_customization.name = 'KOReader Sync'
    mock_site_customization.version = (0, 8, 0)

    action = KoreaderAction(mock_parent, mock_site_customization)
    paths = action.get_paths(mock_device)

    assert len(paths) == 2
    # Verify Alice's sidecar path generation
    alice_sidecar = next(p for u, p in paths if u == alice_book.uuid)
    assert alice_sidecar == "Carroll, Lewis/Alice's Adventures in Wonderland - Lewis Carroll.sdr/metadata.epub.lua"
