import os
from collections import defaultdict
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import action as action_module
import config as config_module
from action import KoreaderAction, local_tz

SIDECAR_LUA = '''-- we can read Lua syntax here!
return {
    ["percent_finished"] = 0.2,
    ["summary"] = {
        ["modified"] = "2026-10-01",
        ["status"] = "reading",
    },
}
'''

TEST_CONFIG = {
    'checkbox_sync_if_more_recent': True,
    'checkbox_percent_read_100': False,
    'column_date_sidecar_modified': '#ko_lastmod',
    'column_percent_read': '#ko_percent',
}


class WirelessDevice:
    """Not a USBMS device, like SMART_DEVICE_APP"""
    def get_file(self, path, outfile):
        outfile.write(SIDECAR_LUA.encode())


def make_action():
    action = KoreaderAction(MagicMock(), MagicMock())
    action.extension_callback = None
    return action


def run_sync(device, sidecar_path, stored):
    """Runs the real sync worker for one book against the stored calibre
    values and returns the worker's results, metadata and db mocks"""
    action = make_action()
    db = action.gui.current_db.new_api
    db.lookup_by_uuid.return_value = 1
    metadata = MagicMock()
    metadata.get.side_effect = {'title': 'Book', **stored}.get
    db.get_metadata.return_value = metadata

    finished = []
    def start(worker):
        worker.finished_signal.connect(finished.append)
        worker.run()

    test_config = defaultdict(str, TEST_CONFIG)
    with patch.object(action_module, 'CONFIG', test_config), \
         patch.object(config_module, 'CONFIG', test_config), \
         patch.object(action_module, 'DEBUG', False), \
         patch.object(action, 'get_connected_device', return_value=device), \
         patch.object(action, 'check_device', return_value=True), \
         patch.object(action, 'get_paths', return_value=[('uuid', sidecar_path)]), \
         patch.object(action_module.QThread, 'start', start):
        action.sync_to_calibre(silent=True)

    return finished[0], metadata, db


def test_wireless_sidecar_has_no_date_modified():
    """
    Issue #168: the sidecar's mtime cannot be read over wireless, so
    date_sidecar_modified must be left unset instead of using the sync time.
    """
    action = make_action()
    with patch('os.path.getmtime') as mock_getmtime:
        sidecar_contents = action.get_sidecar(
            WirelessDevice(), '/mnt/us/Book.sdr/metadata.epub.lua')

    assert 'date_synced' in sidecar_contents['calculated']
    assert 'date_sidecar_modified' not in sidecar_contents['calculated']
    mock_getmtime.assert_not_called()


def test_usb_sync_date_modified_uses_mtime(tmp_path):
    """USB devices still get the sidecar's real modification time."""
    from calibre.devices.usbms.driver import USBMS
    class USBDevice(USBMS):
        def get_file(self, path, outfile):
            with open(path, 'rb') as f:
                outfile.write(f.read())

    sidecar_path = tmp_path / 'Book.sdr' / 'metadata.epub.lua'
    sidecar_path.parent.mkdir()
    sidecar_path.write_text(SIDECAR_LUA)
    mtime = datetime(2026, 1, 2, 3, 4, 5).timestamp()
    os.utime(sidecar_path, (mtime, mtime))

    res, metadata, db = run_sync(
        USBDevice(), str(sidecar_path), {'#ko_percent': 0.1})

    assert res['num_success'] == 1
    metadata.set.assert_any_call(
        '#ko_lastmod', datetime.fromtimestamp(mtime).replace(tzinfo=local_tz))
    db.set_metadata.assert_called_once()


def test_wireless_sync_if_more_recent_rejects_lower_progress():
    """
    Issue #168: over wireless, "Sync only if changes are more recent" falls
    back to percent read, so 20% from the device does not overwrite 60%.
    """
    stored = {
        '#ko_percent': 0.6,
        '#ko_lastmod': datetime.now(local_tz) - timedelta(days=1),
    }
    res, metadata, db = run_sync(
        WirelessDevice(), '/mnt/us/Book.sdr/metadata.epub.lua', stored)

    assert res['num_skip'] == 1
    assert 'read Percent is lower' in res['results'][0]['result']
    metadata.set.assert_not_called()
    db.set_metadata.assert_not_called()


def test_wireless_sync_keeps_stored_date_modified():
    """Higher progress syncs over wireless without clearing Date Modified."""
    stored = {
        '#ko_percent': 0.1,
        '#ko_lastmod': datetime.now(local_tz) - timedelta(days=1),
    }
    res, metadata, db = run_sync(
        WirelessDevice(), '/mnt/us/Book.sdr/metadata.epub.lua', stored)

    assert res['num_success'] == 1
    metadata.set.assert_called_once_with('#ko_percent', 0.2)
    db.set_metadata.assert_called_once()
