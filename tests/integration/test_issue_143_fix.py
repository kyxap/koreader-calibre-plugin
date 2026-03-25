
import os
import io
import pytest
from unittest.mock import MagicMock, patch
from action import KoreaderAction

def test_fix_issue_143_usb_direct_write():
    """
    Verifies fix for Issue #143: USB/Folder devices use direct open()
    instead of put_file() to avoid driver crashes.
    """
    from calibre.devices.usbms.driver import USBMS
    class MyUSBDevice(USBMS):
        def put_file(self, path, stream):
            raise Exception("Should not be called for USB")

    mock_device = MyUSBDevice()
    mock_parent = MagicMock()
    mock_site_customization = MagicMock()
    action = KoreaderAction(mock_parent, mock_site_customization)
    
    # Mock DB etc
    action.gui.current_db.new_api.lookup_by_uuid.return_value = 1
    mock_metadata = MagicMock()
    mock_metadata.get.return_value = '{"test": 1}'
    action.gui.current_db.new_api.get_metadata.return_value = mock_metadata
    
    with patch('builtins.open', MagicMock()) as mock_open, \
         patch('os.makedirs') as mock_makedirs, \
         patch('os.path.exists') as mock_exists:
        
        mock_exists.return_value = True
        
        result, details = action.push_metadata_to_koreader_sidecar(mock_device, "uuid", "E:/path.lua")
        
        assert result == "success"
        # Verify open was used
        mock_open.assert_called()
        # Verify put_file was NOT used
        # (Already handled by the exception in MyUSBDevice.put_file)

def test_wireless_still_uses_put_file():
    """
    Ensures wireless devices STILL use put_file().
    """
    class WirelessDevice:
        def put_file(self, path, stream):
            self.called = True
    
    mock_device = WirelessDevice()
    mock_device.called = False
    
    mock_parent = MagicMock()
    mock_site_customization = MagicMock()
    action = KoreaderAction(mock_parent, mock_site_customization)
    
    action.gui.current_db.new_api.lookup_by_uuid.return_value = 1
    mock_metadata = MagicMock()
    mock_metadata.get.return_value = '{"test": 1}'
    action.gui.current_db.new_api.get_metadata.return_value = mock_metadata
    
    result, details = action.push_metadata_to_koreader_sidecar(mock_device, "uuid", "/mnt/path.lua")
    
    assert result == "success"
    assert mock_device.called is True
