from urllib.error import URLError
from unittest.mock import MagicMock

import pytest

import action
import config
from action import KoreaderAction, OperationStatus

FLOAT = '#ko_progfloat'
INT = '#ko_progint'
STATUS = '#ko_status'


class FakeMetadata(dict):
    def set(self, key, value):
        self[key] = value


@pytest.fixture
def set_config(monkeypatch):
    """Replace the plugin CONFIG with a plain dict for the duration of a test."""
    def _set(**overrides):
        cfg = {
            'column_percent_read': FLOAT,
            'column_percent_read_int': '',
            'column_status': STATUS,
            'column_status_bool': '',
            'column_date_sidecar_modified': '',
            'checkbox_percent_read_100': False,
            'checkbox_sync_if_more_recent': False,
            'checkbox_no_sync_if_finished': False,
        }
        cfg.update(overrides)
        monkeypatch.setattr(config, 'CONFIG', cfg)
        monkeypatch.setattr(action, 'CONFIG', cfg)
        return cfg
    return _set


def run_update(stored, new):
    koreader_action = KoreaderAction(MagicMock(), MagicMock())
    koreader_action.extension_callback = None
    db = MagicMock()
    db.lookup_by_uuid.return_value = 1
    db.get_metadata.return_value = FakeMetadata(stored)
    status, result = koreader_action.update_metadata('uuid', db, dict(new))
    return status, result, db.get_metadata.return_value


@pytest.mark.parametrize('percent_read_100, expected', [(False, 0.46), (True, 46.0)])
def test_sidecar_float_transform_honours_range_option(set_config, percent_read_100, expected):
    set_config(checkbox_percent_read_100=percent_read_100)
    transform = config.CUSTOM_COLUMN_DEFAULTS['column_percent_read']['transform']
    assert transform(0.46) == pytest.approx(expected)
    # The int column is always 0-100
    assert config.CUSTOM_COLUMN_DEFAULTS['column_percent_read_int']['transform'](0.46) == 46


@pytest.mark.parametrize('overrides, stored', [
    ({}, 1.0),                                               # float, 0-1 range
    ({'checkbox_percent_read_100': True}, 100.0),            # float, 0-100 range
    ({'column_percent_read': '', 'column_percent_read_int': INT}, 100),  # int
])
def test_no_sync_if_finished_skips_finished_book(set_config, overrides, stored):
    set_config(checkbox_no_sync_if_finished=True, **overrides)
    key = INT if overrides.get('column_percent_read_int') else FLOAT
    status, result, _ = run_update({key: stored, STATUS: 'reading'}, {key: stored / 5})
    assert status == OperationStatus.SKIP
    assert result['result'] == 'skipped, book already finished'


@pytest.mark.parametrize('overrides, stored', [
    ({}, 0.99),
    ({'checkbox_percent_read_100': True}, 99.0),
    ({'column_percent_read': '', 'column_percent_read_int': INT}, 99),
    # Int 1 is 1%, only the float column can be on the 0-1 scale
    ({'column_percent_read': '', 'column_percent_read_int': INT}, 1),
    # Stored while the 0-100 option was on, then the option was turned off: 45%, not 4500%
    ({}, 45.0),
    # Option on, legacy sidecar value on the 0-1 scale: read as 1%, never a wrong skip
    ({'checkbox_percent_read_100': True}, 1.0),
])
def test_no_sync_if_finished_syncs_unfinished_book(set_config, overrides, stored):
    set_config(checkbox_no_sync_if_finished=True, **overrides)
    key = INT if overrides.get('column_percent_read_int') else FLOAT
    status, _, metadata = run_update({key: stored, STATUS: 'reading'}, {key: 0})
    assert status == OperationStatus.PASS
    assert metadata[key] == 0


@pytest.mark.parametrize('overrides, stored, new, synced', [
    # Float, 0-1 range, value stored while the 0-100 option was on
    ({}, 45.0, 0.5, True),
    ({}, 45.0, 0.4, False),
    # Float, 0-100 range, legacy sidecar value on the 0-1 scale is read as 0.46%
    ({'checkbox_percent_read_100': True}, 0.46, 20.0, True),
    ({'checkbox_percent_read_100': True}, 46.0, 46.0, False),
    # Int column is always 0-100
    ({'column_percent_read': '', 'column_percent_read_int': INT}, 46, 47, True),
    ({'column_percent_read': '', 'column_percent_read_int': INT}, 46, 45, False),
])
def test_sync_if_more_recent_percent_fallback(set_config, overrides, stored, new, synced):
    set_config(checkbox_sync_if_more_recent=True, **overrides)
    key = INT if overrides.get('column_percent_read_int') else FLOAT
    status, result, metadata = run_update({key: stored}, {key: new})
    if synced:
        assert status == OperationStatus.PASS
        assert metadata[key] == new
    else:
        assert status == OperationStatus.SKIP
        assert metadata[key] == stored


@pytest.mark.parametrize('overrides, new, expected_status', [
    ({}, 1.0, 'complete'),
    ({}, 0.5, 'reading'),
    ({'checkbox_percent_read_100': True}, 100.0, 'complete'),
    ({'checkbox_percent_read_100': True}, 50.0, 'reading'),
    ({'column_percent_read': '', 'column_percent_read_int': INT}, 100, 'complete'),
])
def test_status_inferred_from_percent(set_config, overrides, new, expected_status):
    set_config(**overrides)
    key = INT if overrides.get('column_percent_read_int') else FLOAT
    _, _, metadata = run_update({STATUS: None}, {key: new})
    assert metadata[STATUS] == expected_status


def test_status_inferred_with_both_columns_mapped(set_config):
    set_config(column_percent_read_int=INT)
    _, _, metadata = run_update({STATUS: None}, {FLOAT: 1.0, INT: 100})
    assert metadata[STATUS] == 'complete'


@pytest.mark.parametrize('percent_read_100', [False, True])
@pytest.mark.parametrize('stored, integer, fetched', [
    (1.0, None, False),
    (0.5, None, True),
    (0.995, 100, True),  # Rounded int must not hide unfinished float progress
    (1.0, 100, False),
    (None, 100, False),  # A newly mapped float column may still be empty
    (None, 50, True),
])
def test_progresssync_skips_finished_float_book(set_config, monkeypatch, percent_read_100, stored, integer, fetched):
    set_config(checkbox_percent_read_100=percent_read_100,
               column_percent_read_int=INT if integer is not None else '',
               column_md5='#ko_md5', progress_sync_url='https://sync.example',
               progress_sync_username='user', progress_sync_password='pass',
               checkbox_skip_ssl_verification=False)
    koreader_action = KoreaderAction(MagicMock(), MagicMock())
    koreader_action.version = 'test'
    db = koreader_action.gui.current_db.new_api
    db.search.return_value = [1]
    db.get_metadata.return_value = FakeMetadata(
        {'#ko_md5': 'abc', 'uuid': 'uuid', 'title': 'Title', STATUS: 'reading',
         FLOAT: stored * 100 if percent_read_100 and stored is not None else stored, INT: integer})
    urlopen = MagicMock(side_effect=URLError('offline'))
    monkeypatch.setattr(action, 'urlopen', urlopen)

    koreader_action.sync_progress_from_progresssync(silent=True)

    assert urlopen.called is fetched
