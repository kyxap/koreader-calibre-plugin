
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

def test_usb_device_uses_local_filesystem():
    """
    Verifies that USB devices STILL use the local filesystem for speed.
    """
    from calibre.devices.usbms.driver import USBMS
    
    class MyUSBDevice(USBMS):
        def exists(self, path):
            return False

    mock_device = MyUSBDevice()
    
    mock_parent = MagicMock()
    mock_site_customization = MagicMock()
    action = KoreaderAction(mock_parent, mock_site_customization)
    
    device_path = "D:/Books/Test.sdr/metadata.epub.lua"

    with patch('os.path.exists') as mock_exists:
        mock_exists.return_value = True
        
        exists = action.device_path_exists(mock_device, device_path)
        
        assert exists is True
        mock_exists.assert_called_with(device_path)
