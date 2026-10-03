import builtins
from unittest.mock import MagicMock

import pytest

import action
from action import KoreaderAction, OperationStatus

PERCENT = '#percent_read'


@pytest.fixture(autouse=True)
def plain_config(monkeypatch):
    """Use a plain dict for CONFIG so the sync options are all off."""
    monkeypatch.setattr(action, 'CONFIG', {
        'column_percent_read': PERCENT,
        'column_percent_read_int': '',
        'column_status': '',
        'checkbox_sync_if_more_recent': False,
        'checkbox_no_sync_if_finished': False,
        'checkbox_enable_scheduled_progressync': False,
        'checkbox_enable_automatic_sync': False,
    })


@pytest.fixture
def debug_log(monkeypatch):
    log = MagicMock()
    monkeypatch.setattr(action, 'module_debug_print', log)
    return lambda: ' '.join(str(arg) for c in log.call_args_list for arg in c.args)


def run_update(callback, current=10, new=50):
    """Run update_metadata for one book with the given extension callback."""
    koreader_action = KoreaderAction(MagicMock(), MagicMock())
    koreader_action.extension_callback = callback
    metadata = MagicMock()
    metadata.get.side_effect = {PERCENT: current}.get
    db = MagicMock()
    db.lookup_by_uuid.return_value = 1
    db.get_metadata.return_value = metadata
    status, details = koreader_action.update_metadata('uuid', db, {PERCENT: new})
    return status, details, db


@pytest.mark.parametrize('current, debug', [
    (10, False),  # changed field
    (50, True),   # unchanged field, debug mode
    (50, False),  # nothing to update
], ids=['changed', 'unchanged-debug', 'no-updates'])
def test_callback_returning_none_keeps_update_log(monkeypatch, current, debug):
    monkeypatch.setattr(action, 'DEBUG', debug)

    def onItemUpdate(updateLog, **kwargs):
        updateLog['extension'] = 'changed in place'

    status, details, _ = run_update(onItemUpdate, current=current)

    assert status == OperationStatus.PASS
    assert details['extension'] == 'changed in place'


def test_callback_returning_non_dict_is_ignored(debug_log):
    def onItemUpdate(updateLog, **kwargs):
        updateLog['extension'] = 'changed in place'
        return 'not a dict'

    status, details, db = run_update(onItemUpdate)

    assert status == OperationStatus.PASS
    assert details['extension'] == 'changed in place'
    assert details[PERCENT] == '10 >> 50'
    db.set_metadata.assert_called_once()
    assert 'returned str, expected dict or None' in debug_log()


def test_callback_returning_dict_replaces_update_log():
    calls = []

    def onItemUpdate(**kwargs):
        calls.append(kwargs)
        kwargs['keys_values_to_update'][PERCENT] = 75
        return {'extension': 'new log'}

    status, details, db = run_update(onItemUpdate)

    assert status == OperationStatus.PASS
    assert set(calls[0]) == {
        'self', 'metadata', 'keys_values_to_update', 'updateLog', 'CONFIG', 'book_id'}
    assert calls[0]['book_id'] == 1
    assert details['extension'] == 'new log'
    assert details[PERCENT] == '10 >> 75'
    db.set_metadata.assert_called_once()


def test_callback_raising_is_caught(debug_log):
    def onItemUpdate(**kwargs):
        raise RuntimeError('boom')

    status, details, db = run_update(onItemUpdate)

    assert status == OperationStatus.PASS
    assert details[PERCENT] == '10 >> 50'
    db.set_metadata.assert_called_once()
    assert 'Error in extension onItemUpdate: boom' in debug_log()


def test_genesis_skips_non_callable_onItemUpdate(monkeypatch, tmp_path):
    (tmp_path / 'KOSync_extension_a.py').write_text('onItemUpdate = "not callable"\n')
    (tmp_path / 'KOSync_extension_b.py').write_text(
        'def onItemUpdate(**kwargs):\n    return "from b"\n')
    # os.listdir order is unspecified, so put the non-callable one first
    real_listdir = action.os.listdir
    monkeypatch.setattr(action.os, 'listdir', lambda path: [
        'KOSync_extension_a.py', 'KOSync_extension_b.py'
    ] if path == str(tmp_path) else real_listdir(path))
    monkeypatch.setattr(builtins, 'get_icons', MagicMock(), raising=False)

    site_customization = MagicMock()
    site_customization.plugin_path = str(tmp_path / 'KOReader Sync.zip')
    koreader_action = KoreaderAction(MagicMock(), site_customization)
    koreader_action.qaction = MagicMock()
    koreader_action.create_menu_action = MagicMock()
    koreader_action.genesis()

    assert koreader_action.extension_callback() == 'from b'
