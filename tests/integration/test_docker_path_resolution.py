
import os
from unittest.mock import MagicMock, patch
from action import KoreaderAction

def test_wireless_device_avoids_local_filesystem():
    """
    Reproduces Issue #73: Ensure that for non-USB devices (Wireless/Docker),
    the plugin does NOT use os.path.exists which would look at the local 
    container filesystem.
    """
    # 1. Setup a mock device that is NOT a USBMS instance
    # In conftest.py, we mocked MockUSBMS. 
    # Here we create a device that does NOT inherit from it.
    class WirelessDevice:
        def exists(self, path):
            return True
        def get_file(self, path, outfile):
            pass

    mock_device = WirelessDevice()
    
    # 2. Setup Action
    mock_parent = MagicMock()
    mock_site_customization = MagicMock()
    mock_site_customization.name = 'KOReader Sync'
    mock_site_customization.version = (0, 8, 0)
    action = KoreaderAction(mock_parent, mock_site_customization)

    # Path that looks like a Linux/KOReader path but definitely doesn't exist locally
    device_path = "/mnt/onboard/Books/Test.sdr/metadata.epub.lua"

    # 3. Patch os.path.exists to track calls
    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = False # Doesn't exist on host
        
        # Trigger the check
        exists = action.device_path_exists(mock_device, device_path)
        
        # ASSERTIONS
        assert exists is True, "Should have used driver.exists"
        
        # CRITICAL REPRODUCTION CHECK:
        # Before the fix, this would have been called with the device_path.
        # After the fix, it should NOT be called for non-USB devices.
        mock_exists.assert_not_called()

def test_usb_device_triggers_makedirs():
    """
    Verifies that for USB devices, the plugin attempts to create the 
    sidecar directory if it doesn't exist.
    """
    from calibre.devices.usbms.driver import USBMS
    class MyUSBDevice(USBMS):
        def put_file(self, path, stream): pass

    mock_device = MyUSBDevice()
    mock_parent = MagicMock()
    mock_site_customization = MagicMock()
    action = KoreaderAction(mock_parent, mock_site_customization)
    
    device_path = "E:/Books/NewBook.sdr/metadata.epub.lua"
    
    # Mock DB lookup to return metadata
    action.gui.current_db.new_api.lookup_by_uuid.return_value = 1
    mock_metadata = MagicMock()
    mock_metadata.get.return_value = '{"test": 1}' # dummy sidecar json
    action.gui.current_db.new_api.get_metadata.return_value = mock_metadata

    with patch('os.makedirs') as mock_makedirs, \
         patch('os.path.exists') as mock_exists:
        mock_exists.return_value = False
        
        action.push_metadata_to_koreader_sidecar(mock_device, "some-uuid", device_path)
        
        # This will currently FAIL because I removed makedirs
        mock_makedirs.assert_called_with(os.path.dirname(device_path), exist_ok=True)

def test_wireless_device_skips_makedirs():
    """
    Verifies that for wireless devices, the plugin does NOT call os.makedirs.
    """
    class WirelessDevice:
        def put_file(self, path, stream): pass

    mock_device = WirelessDevice()
    mock_parent = MagicMock()
    mock_site_customization = MagicMock()
    action = KoreaderAction(mock_parent, mock_site_customization)
    
    device_path = "/mnt/onboard/Books/NewBook.sdr/metadata.epub.lua"
    
    action.gui.current_db.new_api.lookup_by_uuid.return_value = 1
    mock_metadata = MagicMock()
    mock_metadata.get.return_value = '{"test": 1}'
    action.gui.current_db.new_api.get_metadata.return_value = mock_metadata

    with patch('os.makedirs') as mock_makedirs:
        action.push_metadata_to_koreader_sidecar(mock_device, "some-uuid", device_path)
        mock_makedirs.assert_not_called()
