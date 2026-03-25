
import io
import pytest
from unittest.mock import MagicMock
from action import KoreaderAction

def test_reproduce_issue_143():
    """
    Reproduces Issue #143: '_io.BytesIO' object has no attribute 'startswith'
    This happens when a driver's put_file implementation expects a string 
    (likely a file path) but receives a BytesIO object.
    """
    mock_parent = MagicMock()
    mock_site_customization = MagicMock()
    action = KoreaderAction(mock_parent, mock_site_customization)
    
    # Simulate a driver that might do 'stream.startswith'
    class CrashingDriver:
        def put_file(self, path, stream):
            # This simulates the internal Calibre driver logic that might be crashing
            if stream.startswith('some_path'):
                pass

    mock_device = CrashingDriver()
    
    # Mock DB etc to reach the put_file call
    action.gui.current_db.new_api.lookup_by_uuid.return_value = 1
    mock_metadata = MagicMock()
    mock_metadata.get.return_value = '{"test": 1}'
    action.gui.current_db.new_api.get_metadata.return_value = mock_metadata
    
    # This should return a failure result containing the error message
    result, details = action.push_metadata_to_koreader_sidecar(mock_device, "uuid", "some/path.lua")
    
    assert result == "failure"
    assert "'_io.BytesIO' object has no attribute 'startswith'" in details['result']
