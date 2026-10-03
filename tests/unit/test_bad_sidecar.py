import pytest
from unittest.mock import MagicMock

import action as action_module
from action import (
    KoreaderAction,
    GetSidecarStatus,
    OperationStatus,
    parse_sidecar_lua,
)

VALID_SIDECAR = (
    '-- we can read Lua syntax here!\n'
    'return {\n'
    '    ["summary"] = {\n'
    '        ["status"] = "reading",\n'
    '    },\n'
    '}\n'
)
# Same file cut off in the middle, e.g. by an unsafe unplug (issue #167)
TRUNCATED_SIDECAR = VALID_SIDECAR[:VALID_SIDECAR.index('reading')]
DECODE_FAILED_MSG = 'decoding is failed see debug for more details'


def make_device(sidecars):
    """A device whose get_file() serves the given {path: bytes} sidecars."""
    device = MagicMock()

    def get_file(path, outfile):
        outfile.write(sidecars[path])
    device.get_file.side_effect = get_file
    return device


@pytest.mark.parametrize('contents', [
    '',
    ' \n',
    '-- we can read Lua syntax here!\n',
    TRUNCATED_SIDECAR,
], ids=['empty', 'whitespace', 'comment-only', 'truncated'])
def test_parse_sidecar_lua_returns_none_when_unparsable(contents):
    assert parse_sidecar_lua(contents) is None


def test_parse_sidecar_lua_accepts_empty_table():
    assert parse_sidecar_lua('-- we can read Lua syntax here!\nreturn {}\n') == {}


@pytest.mark.parametrize('contents', [
    b'',
    b' \n',
    TRUNCATED_SIDECAR.encode(),
], ids=['empty', 'whitespace', 'truncated'])
def test_get_sidecar_reports_decode_failed_for_empty_or_truncated(contents):
    path = 'Book.sdr/metadata.epub.lua'
    action = KoreaderAction(MagicMock(), MagicMock())

    result = action.get_sidecar(make_device({path: contents}), path)

    assert result is GetSidecarStatus.DECODE_FAILED


def test_get_sidecar_accepts_empty_table():
    path = 'Book.sdr/metadata.epub.lua'
    action = KoreaderAction(MagicMock(), MagicMock())

    result = action.get_sidecar(make_device({path: b'return {}\n'}), path)

    assert isinstance(result, dict)
    assert 'summary' in result
    assert 'calculated' in result


def setup_sync_to_calibre(monkeypatch, sidecar_paths, sidecars):
    """Prepare a KoreaderAction whose sync_to_calibre() runs the worker
    synchronously against fake device/library data and records the dialogs.
    """
    action = KoreaderAction(MagicMock(), MagicMock())
    device = make_device(sidecars)
    monkeypatch.setattr(action, 'get_connected_device', lambda: device)
    monkeypatch.setattr(action, 'check_device', lambda device: True)
    monkeypatch.setattr(action, 'get_paths', lambda device: sidecar_paths)

    def update_metadata(uuid, db, keys_values_to_update):
        if uuid == 'uuid-4':
            raise RuntimeError('database is locked')
        return OperationStatus.PASS, {'result': 'success'}
    monkeypatch.setattr(action, 'update_metadata', update_metadata)

    db = action.gui.current_db.new_api
    db.lookup_by_uuid.side_effect = lambda uuid: int(uuid.split('-')[1]) + 1
    db.get_metadata.side_effect = lambda book_id: {'title': f'Book {book_id - 1}'}

    monkeypatch.setattr(action_module, 'DEBUG', False)
    monkeypatch.setattr(action_module, 'CONFIG',
                        {name: '' for name in action_module.COLUMNS})
    monkeypatch.setattr(action_module, 'ProgressDialog', MagicMock())
    monkeypatch.setattr(action_module, 'SyncCompletionDialog', MagicMock())
    # Run the worker in this thread so its signals are delivered directly
    monkeypatch.setattr(action_module.QThread, 'start', lambda self: self.run())
    return action


def test_sync_to_calibre_continues_past_bad_sidecars(monkeypatch):
    # More than 10 books, so the progress dialog is shown (issue #167)
    sidecar_paths = [(f'uuid-{i}', f'Book {i}.sdr/metadata.epub.lua')
                     for i in range(11)]
    sidecars = {path: VALID_SIDECAR.encode() for _, path in sidecar_paths}
    sidecars['Book 2.sdr/metadata.epub.lua'] = b''
    sidecars['Book 3.sdr/metadata.epub.lua'] = TRUNCATED_SIDECAR.encode()
    # Book 4 fails in update_metadata() with an unexpected error
    action = setup_sync_to_calibre(monkeypatch, sidecar_paths, sidecars)

    action.sync_to_calibre()

    action_module.ProgressDialog.return_value.close.assert_called_once()
    action_module.SyncCompletionDialog.assert_called_once()
    _, _, message, results, dialog_type = \
        action_module.SyncCompletionDialog.call_args.args
    assert dialog_type == 'error'
    assert 'Metadata sync succeeded for: 8\n' in message
    assert 'Metadata sync failed for: 3\n' in message

    row_by_title = {row['title']: row for row in results}
    assert len(row_by_title) == 11
    assert row_by_title['Book 2']['result'] == DECODE_FAILED_MSG
    assert row_by_title['Book 3']['result'] == DECODE_FAILED_MSG
    assert row_by_title['Book 4']['result'] == 'failed, unexpected error'
    assert row_by_title['Book 4']['error'] == 'RuntimeError: database is locked'
    assert row_by_title['Book 10']['result'] == 'success'
    # Rows with an error are listed first in the results dialog
    assert results[0]['title'] == 'Book 4'


def test_sync_to_calibre_failed_row_does_not_reuse_previous_title(monkeypatch):
    sidecar_paths = [(f'uuid-{i}', f'Book {i}.sdr/metadata.epub.lua')
                     for i in range(3)]
    sidecars = {path: VALID_SIDECAR.encode() for _, path in sidecar_paths}
    action = setup_sync_to_calibre(monkeypatch, sidecar_paths, sidecars)
    # Fails before the book's title has been looked up
    real_get_sidecar = action.get_sidecar

    def get_sidecar(device, path):
        if path == 'Book 1.sdr/metadata.epub.lua':
            raise RuntimeError('unexpected sidecar error')
        return real_get_sidecar(device, path)
    monkeypatch.setattr(action, 'get_sidecar', get_sidecar)

    action.sync_to_calibre()

    _, _, message, results, _ = action_module.SyncCompletionDialog.call_args.args
    assert 'Metadata sync succeeded for: 2\n' in message
    assert 'Metadata sync failed for: 1\n' in message
    failed = [row for row in results if 'error' in row]
    assert len(failed) == 1
    assert failed[0]['title'] == 'Unknown'
    assert failed[0]['book_uuid'] == 'uuid-1'
    assert failed[0]['error'] == 'RuntimeError: unexpected sidecar error'
    assert [row['title'] for row in results].count('Book 0') == 1


def test_sync_to_calibre_reports_results_if_the_loop_aborts(monkeypatch):
    # A malformed entry fails outside the per-book error handling
    sidecar_paths = [('uuid-0', 'Book 0.sdr/metadata.epub.lua'), None]
    sidecars = {'Book 0.sdr/metadata.epub.lua': VALID_SIDECAR.encode()}
    action = setup_sync_to_calibre(monkeypatch, sidecar_paths, sidecars)

    with pytest.raises(TypeError):
        action.sync_to_calibre()

    action_module.SyncCompletionDialog.assert_called_once()
