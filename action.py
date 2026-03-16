#!/usr/bin/env python3

"""KOReader Sync Plugin for Calibre."""

from datetime import datetime
from functools import partial
import io
import json
import os
import re
import sys
import importlib.util
import time

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl

from PyQt5.Qt import (
    QUrl,
    QTimer,
    QTime,
    QTableWidget,
    QTableWidgetItem,
    QHBoxLayout,
    QVBoxLayout,
    QDialog,
    QLabel,
    QIcon,
    QPushButton,
    QScrollArea,
    QProgressBar,
    QApplication,
    Qt,
    QThread,
    pyqtSignal,
)

from calibre_plugins.koreader.slpp import slpp as lua
from calibre_plugins.koreader.config import (
    SUPPORTED_DEVICES,
    UNSUPPORTED_DEVICES,
    CUSTOM_COLUMN_DEFAULTS as COLUMNS,
    CONFIG,
)
from calibre_plugins.koreader import (
    DEBUG,
    DRY_RUN,
    PYDEVD,
    KoreaderSync,
)

from calibre.utils.iso8601 import utc_tz, local_tz
from calibre.gui2.dialogs.message_box import MessageBox
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.device import device_signals
from calibre.gui2 import (
    error_dialog,
    warning_dialog,
    open_url,
)
from calibre.devices.usbms.driver import debug_print as root_debug_print, USBMS
from calibre.constants import numeric_version
from enum import Enum, auto

__license__ = 'GNU GPLv3'
__copyright__ = '2021, harmtemolder <mail at harmtemolder.com>'
__modified_by__ = 'kyxap kyxappp@gmail.com'
__modification_date__ = '2024'
__docformat__ = 'restructuredtext en'

if numeric_version >= (5, 5, 0):
    module_debug_print = partial(root_debug_print, ' koreader:action:', sep='')
else:
    module_debug_print = partial(root_debug_print, 'koreader:action:')

if DEBUG and PYDEVD:
    try:
        sys.path.append(
            # '/Applications/PyCharm.app/Contents/debug-eggs/pydevd-pycharm.egg'  # macOS
            '/opt/pycharm-professional/debug-eggs/pydevd-pycharm.egg'
            # Manjaro Linux
        )
        import pydevd_pycharm

        pydevd_pycharm.settrace(
            'localhost', stdoutToServer=True, stderrToServer=True,
            suspend=False
        )
    except Exception as e:
        module_debug_print('could not start pydevd_pycharm, e = ', e)
        PYDEVD = False


class GetSidecarStatus(Enum):
    PATH_NOT_FOUND = auto()
    DECODE_FAILED = auto()


class OperationStatus(Enum):
    PASS = auto()
    FAIL = auto()
    SKIP = auto()


def is_system_path(path):
    """
    KOreader user may have some files in the root which we want to skip to
    avoid showing warning message

    :param path: path to sidecar file (*.lua)
    :return: true/false if partial match found
    """
    to_ignore = ['kfmon.sdr', 'koreader.sdr']
    return any(substring in path for substring in to_ignore)


def append_results(results, title, status_msg, book_uuid, sidecar_path):
    debug_print = partial(
        module_debug_print,
        'KoreaderAction:append_results:'
    )
    debug_print(f'{sidecar_path} - {status_msg}')
    return results.append(
        {
            'title': title,
            'result': status_msg,
            'book_uuid': book_uuid,
            'sidecar_path': sidecar_path,
        }
    )


def parse_sidecar_lua(sidecar_lua):
    """Parses a sidecar Lua file into a Python dict

    :param sidecar_lua: the contents of a sidecar Lua as a str
    :return: a dict of those contents
    """
    debug_print = partial(
        module_debug_print,
        'KoreaderAction:parse_sidecar_lua:'
    )

    try:
        clean_lua = re.sub(r'^[^{]*', '', sidecar_lua).strip()
        decoded_lua = lua.decode(clean_lua)
    except:
        debug_print('could not decode sidecar_lua')
        decoded_lua = None

    if 'bookmarks' in decoded_lua:
        if type(decoded_lua['bookmarks']) is list:
            decoded_lua['bookmarks'] = {
                # Starts from 1
                i+1: bookmark for i, bookmark in enumerate(decoded_lua['bookmarks'])}

        debug_print('calculating first and last bookmark dates')
        bookmark_dates = [
            datetime.strptime(
                bookmark['datetime'],
                '%Y-%m-%d %H:%M:%S'
            ).replace(tzinfo=utc_tz)
            for bookmark in decoded_lua['bookmarks'].values()
        ]

        if len(bookmark_dates) > 0:
            decoded_lua['calculated'] = {
                'first_bookmark': min(bookmark_dates),
                'last_bookmark': max(bookmark_dates),
            }

    return decoded_lua


class KoreaderAction(InterfaceAction):
    name = KoreaderSync.name
    action_spec = (name, 'edit-redo.png', KoreaderSync.description, None)
    action_add_menu = True
    action_menu_clone_qaction = 'Sync from KOReader'
    dont_add_to = frozenset(
        [
            'context-menu', 'context-menu-device', 'menubar',
            'menubar-device', 'context-menu-cover-browser',
            'context-menu-split']
    )
    dont_remove_from = frozenset()
    action_type = 'current'

    def genesis(self):
        debug_print = partial(module_debug_print, 'KoreaderAction:genesis:')
        debug_print('start')

        base = self.interface_action_base_plugin
        if hasattr(base, 'version_string') and base.version_string:
            self.version = f'{base.name} (v{base.version_string})'
        else:
            self.version = f'{base.name} (v{".".join(map(str, base.version))})'
        self.extension_callback = None

    def is_usb_device(self, device):
        """Returns True if the device is connected via USB Mass Storage."""
        return isinstance(device, USBMS)

        # Overwrite icon with actual KOReader logo
        icon = get_icons(
            'images/icon.png'
        )
        self.qaction.setIcon(icon)

        # Left-click action
        self.qaction.triggered.connect(self.exec_main_action)

        # Right-click menu (already includes left-click action)

        # TODO: Sync calibre to KOReader is disabled see more in #8
        self.create_menu_action(
            self.qaction.menu(),
            'Sync missing to KOReader',
            'Sync missing to KOReader',
            icon='edit-undo.png',
            description='If calibre has an entry in the "Raw sidecar column", '
                        'but KOReader does not have a sidecar file, push the '
                        'metadata from calibre to a new sidecar file.',
            triggered=self.sync_missing_sidecars_to_koreader
        )

        self.create_menu_action(
            self.qaction.menu(),
            'Sync from ProgressSync',
            'Sync from ProgressSync',
            icon='convert.png',
            description='Use KOReader''s built in ProgressSync Plugin '
                        'to update percentRead int or float.',
            triggered=self.sync_progress_from_progresssync
        )

        self.qaction.menu().addSeparator()

        self.create_menu_action(
            self.qaction.menu(),
            'Configure KOReader Sync',
            'Configure',
            icon='config.png',
            description='Configure KOReader Sync',
            triggered=self.show_config
        )

        self.qaction.menu().addSeparator()

        self.create_menu_action(
            self.qaction.menu(),
            'Readme for KOReader Sync',
            'Readme',
            icon='dialog_question.png',
            description='Readme for KOReader Sync',
            triggered=self.show_readme
        )

        self.create_menu_action(
            self.qaction.menu(),
            'About KOReader Sync',
            'About',
            icon='dialog_information.png',
            description='About KOReader Sync',
            triggered=self.show_about
        )

        # Start the scheduled progress sync if enabled
        if CONFIG["checkbox_enable_scheduled_progressync"]:
            self.scheduled_progress_sync()

        # Start the device connection watcher if enabled
        if CONFIG["checkbox_enable_automatic_sync"]:
            device_signals.device_metadata_available.connect(
                self._on_device_metadata_available)

        basedir = os.path.dirname(base.plugin_path)
        for filename in os.listdir(basedir):
            if filename.startswith("KOSync_extension") and filename.endswith(".py"):
                filepath = os.path.join(basedir, filename)
                try:
                    spec = importlib.util.spec_from_file_location(
                        "KOSync_extension", filepath)
                    extension = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(extension)
                    if hasattr(extension, "onItemUpdate"):
                        self.extension_callback = extension.onItemUpdate
                        print(f"Loaded onItemUpdate from {filename}")
                        return
                except Exception as e:
                    print(f"Failed to load extension: {e}")

    def exec_main_action(self) -> None:
        # Execute main action defined by user
        main_button = CONFIG['main_action']
        if main_button == 'KOReader Sync':
            self.sync_to_calibre()
        elif main_button == 'Progress Sync':
            self.sync_progress_from_progresssync()
        else:
            self.sync_to_calibre()

    def show_config(self):
        self.interface_action_base_plugin.do_user_config(self.gui)

    def show_readme(self):
        debug_print = partial(module_debug_print,
                              'KoreaderAction:show_readme:')
        debug_print('start')
        readme_url = QUrl(
            'https://github.com/harmtemolder/koreader-calibre-plugin#readme'
        )
        open_url(readme_url)

    def show_about(self):
        debug_print = partial(module_debug_print, 'KoreaderAction:show_about:')
        debug_print('start')
        text = get_resources('about.txt').decode(
            'utf-8'
        )
        if DEBUG:
            text += '\n\nRunning in debug mode'
        icon = get_icons(
            'images/icon.png'
        )

        about_dialog = MessageBox(
            MessageBox.INFO,
            f'About {self.version}',
            text,
            det_msg='',
            q_icon=icon,
            show_copy_button=False,
            parent=None,
        )

        return about_dialog.exec_()

    def apply_settings(self):
        debug_print = partial(
            module_debug_print,
            'KoreaderAction:apply_settings:'
        )
        debug_print('start')

    def get_connected_device(self):
        """Tries to get the connected device, if any

        :return: the connected device object or None
        """
        debug_print = partial(
            module_debug_print,
            'KoreaderAction:get_connected_device:'
        )

        try:
            is_device_present = self.gui.device_manager.is_device_present
        except:
            is_device_present = False

        if not is_device_present:
            debug_print('is_device_present = ', is_device_present)
            error_dialog(
                self.gui,
                'No device found',
                'No device found',
                det_msg='',
                show=True,
                show_copy_button=False
            )
            return None

        try:
            connected_device = self.gui.device_manager.connected_device
            connected_device_type = connected_device.__class__.__name__
        except:
            debug_print('could not get connected_device')
            error_dialog(
                self.gui,
                'Could not connect to device',
                'Could not connect to device',
                det_msg='',
                show=True,
                show_copy_button=False
            )
            return None

        debug_print('connected_device_type = ', connected_device_type)
        return connected_device

    def _on_device_metadata_available(self):
        self.sync_to_calibre(silent=True if not DEBUG else False)

    def get_paths(self, device):
        """Retrieves paths to sidecars of all books in calibre's library
        on the device

        :param device: a device object
        :return: a list of (uuid, path) tuples to sidecars
        """
        debug_print = partial(
            module_debug_print,
            'KoreaderAction:get_paths:'
        )

        debug_print(
            f'found {len(device.books())} paths to books:\n\t',
            '\n\t'.join([book.path for book in device.books()])
        )

        for book in device.books():
            debug_print(f'uuid to path: {book.uuid} - {book.path}')

        paths = []
        for book in device.books():
            # Ignore hidden folders (issue #101)
            if any(part.startswith('.') for part in book.path.replace('\\\\', '/').split('/')):
                debug_print(f'Ignoring book in hidden folder: {book.path}')
                continue

            sidecar_path = re.sub(
                r'\.(\w+)$', r'.sdr/metadata.\1.lua', book.path
            )
            paths.append((book.uuid, sidecar_path))


        debug_print(
            f'generated {len(paths)} path(s) to sidecar Lua files:\n\t',
            '\n\t'.join([p[1] for p in paths])
        )

        return paths

    def get_sidecar(self, device, path):
        """Requests the given path from the given device and returns the
        contents of a sidecar Lua as Python dict

        :param device: a device object
        :param path: a path to a sidecar Lua on the device
        :return: dict or None
        """
        debug_print = partial(
            module_debug_print,
            'KoreaderAction:get_sidecar:'
        )

        with io.BytesIO() as outfile:
            try:
                device.get_file(path, outfile)
            except:
                debug_print('could not get ', path)
                return GetSidecarStatus.PATH_NOT_FOUND

            contents = outfile.getvalue()

            try:
                decoded_contents = contents.decode()
            except UnicodeDecodeError:
                debug_print('could not decode ', contents)
                return GetSidecarStatus.DECODE_FAILED

            debug_print(f'Parsing: {path}')
            parsed_contents = parse_sidecar_lua(decoded_contents)
            parsed_contents['calculated'] = {}
            
            # Ensure 'summary' exists to avoid KeyError later (#117)
            if 'summary' not in parsed_contents:
                debug_print(f"Warning: 'summary' key missing in sidecar for {path}")
                parsed_contents['summary'] = {'status': 'unknown', 'modified': datetime.now().strftime("%Y-%m-%d")}

            # Define metadata extraction tasks
            is_usb = self.is_usb_device(device)
            metadata_tasks = [
                ('date_synced', lambda: datetime.now().replace(tzinfo=local_tz)),
                ('date_status_changed', lambda: datetime.strptime(
                    parsed_contents['summary'].get('modified', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d").replace(tzinfo=local_tz)),
                ('date_sidecar_modified', lambda: datetime.fromtimestamp(
                    os.path.getmtime(path) if is_usb and os.path.exists(path) else time.time()).replace(tzinfo=local_tz))
            ]

            for key, task in metadata_tasks:
                try:
                    parsed_contents['calculated'][key] = task()
                except Exception as error:
                    debug_print(f'Failed to set {key}: {error}')

        return parsed_contents

    def get_calibre_uuid_from_sidecar(self, sidecar_contents):
        """Extracts the calibre UUID from sidecar identifiers if present.
        (Issue #115)
        """
        if not isinstance(sidecar_contents, dict):
            return None
        stats = sidecar_contents.get('stats', {})
        identifiers_str = stats.get('identifiers', '')
        if not identifiers_str:
            return None

        # KOReader uses both space and \ as separators in some versions
        parts = re.split(r'[\s\\]+', identifiers_str)
        for part in parts:
            if part.startswith('calibre:'):
                return part.replace('calibre:', '').strip()
        return None

    def update_metadata(self, uuid, db, keys_values_to_update):
        """Update multiple metadata columns for the given book.

        :param uuid: identifier for the book
        :param keys_values_to_update: a dict of keys to update with values
        :return: a dict of values that can be used to report back to the user
        """
        debug_print = partial(
            module_debug_print,
            'KoreaderAction:update_metadata:'
        )

        try:
            debug_print('Looking for uuid in calibre db: ', uuid)
            book_id = db.lookup_by_uuid(uuid)
        except:
            book_id = None

        if not book_id:
            debug_print(f'could not find {uuid} in calibre\'s library')
            return OperationStatus.SKIP, {
                'result': 'could not find uuid in calibre\'s library, have you deleted this book from library?'}

        # Get the current metadata for the book from the library
        metadata = db.get_metadata(book_id)

        # Dict for use in logging
        updateLog = {}

        read_percent_key = CONFIG['column_percent_read'] or CONFIG['column_percent_read_int']

        # Check config to sync only if data is more recent
        if CONFIG['checkbox_sync_if_more_recent']:
            date_modified_key = CONFIG['column_date_sidecar_modified']
            current_date_modified = metadata.get(date_modified_key)
            new_date_modified = keys_values_to_update.get(date_modified_key)
            if current_date_modified is not None and new_date_modified is not None:
                if current_date_modified.timestamp() >= new_date_modified.timestamp():
                    debug_print(
                        f'book {book_id} date_modified {new_date_modified} older than current {current_date_modified}')
                    return OperationStatus.SKIP, {
                        'result': 'skipped, data in calibre is newer',
                    }
            # Fallback if no 'Date Modified Column' is set or not obtainable (wireless)
            elif new_date_modified is None:
                current_read_percent = metadata.get(read_percent_key)
                new_read_percent = keys_values_to_update.get(read_percent_key)
                if current_read_percent is not None and new_read_percent is not None:
                    if current_read_percent >= new_read_percent:
                        debug_print(
                            f'book {book_id} read_percent {new_read_percent} lower or equal than current {current_read_percent}')
                        return OperationStatus.SKIP, {
                            'result': 'skipped, read Percent is lower or equal to the one stored in calibre',
                            'book_id': book_id,
                        }
                elif current_read_percent is not None and new_read_percent is None:
                    debug_print(
                        f'book {book_id} read_percent is None but existing is {current_read_percent}')
                    return OperationStatus.SKIP, {
                        'result': 'skipped, no new read percent found',
                    }

        # Check config to sync only if the book is not yet finished
        status_key = CONFIG['column_status']
        if CONFIG['checkbox_no_sync_if_finished']:
            current_read_percent = metadata.get(read_percent_key)
            current_status = metadata.get(status_key)
            if current_read_percent is not None and current_read_percent >= 100 \
                    or current_status is not None and current_status == "complete":
                debug_print(f'book {book_id} was already finished')
                return OperationStatus.SKIP, {
                    'result': 'skipped, book already finished',
                }

        # Check and correct reading status if required
        if status_key:
            new_status = keys_values_to_update.get(status_key)
            if not new_status:
                new_read_percent = keys_values_to_update.get(read_percent_key)
                current_status = metadata.get(status_key)
                if new_read_percent and current_status != "abandoned":
                    if new_read_percent > 0 and new_read_percent < 100 and current_status != "reading":
                        debug_print(
                            f'book {book_id} set column_status to reading')
                        keys_values_to_update[status_key] = "reading"
                        status_bool_key = CONFIG['column_status_bool']
                        if status_bool_key:
                            keys_values_to_update[status_bool_key] = False
                    elif new_read_percent >= 100 and current_status != "complete":
                        debug_print(
                            f'book {book_id} set column_status to complete')
                        keys_values_to_update[status_key] = "complete"
                        status_bool_key = CONFIG['column_status_bool']
                        if status_bool_key:
                            keys_values_to_update[status_bool_key] = True

        # Call the extension callback if it exists
        if self.extension_callback:
            try:
                updateLog = self.extension_callback(
                    self=self,
                    metadata=metadata,
                    keys_values_to_update=keys_values_to_update,
                    updateLog=updateLog,
                    CONFIG=CONFIG,
                    book_id=book_id
                )
            except Exception as e:
                debug_print(f'Error in extension onItemUpdate: {e}')

        updates = []
        # Update that metadata locally
        for key, new_value in keys_values_to_update.items():
            old_value = metadata.get(key)

            if new_value != old_value:
                updates.append(key)
                metadata.set(key, new_value)
                updateLog[key] = f'{old_value} >> {new_value}'
            else:
                if DEBUG:
                    updateLog[key] = f'{old_value} -- {new_value}'

        # Write the updated metadata back to the library
        if len(updates) == 0:
            updateLog['result'] = 'no updates needed'
            debug_print(
                'no changed metadata for uuid = ', uuid,
                ', id = ', book_id
            )
        elif DEBUG and DRY_RUN:
            debug_print(
                'would have updated the following fields for uuid = ',
                uuid, ', id = ', book_id, ': ', updates
            )
        else:
            db.set_metadata(
                book_id, metadata, set_title=False,
                set_authors=False
            )
            debug_print(
                'updated the following fields for uuid = ', uuid,
                ', id = ', book_id, ': ', updates
            )

        return OperationStatus.PASS, {
            'result': 'success',
            **updateLog
        }

    def check_device(self, device):
        """Return .

        :param device: The connected device.
        :return: False if device is specifically not supported,
        otherwise True
        """

        debug_print = partial(
            module_debug_print,
            'KoreaderAction:check_device:'
        )

        if not device:
            return False

        device_class = device.__class__.__name__

        if device_class in UNSUPPORTED_DEVICES:
            debug_print('unsupported device, device_class = ', device_class)
            error_dialog(
                self.gui,
                'Device not supported',
                f'Devices of the type {device_class} are not supported by this plugin. I '
                f'have tried to get it working, but couldn’t. Sorry.',
                det_msg='',
                show=True,
                show_copy_button=False
            )
            return False
        elif device_class in SUPPORTED_DEVICES:
            return True
        else:
            debug_print(
                'not yet supported device, device_class = ',
                device_class
            )
            warning_dialog(
                self.gui,
                'Device not yet supported',
                f'Devices of the type {device_class} are not yet supported by this plugin. '
                f'Please check if there already is a feature request for this '
                f'<a href="https://github.com/harmtemolder/koreader-calibre-plugin/issues">'
                f'here</a>. If not, feel free to create one. I\'ll try to sync anyway.',
                det_msg='',
                show=True,
                show_copy_button=False
            )
            return True

    def device_path_exists(self, device, path):
        """Checks if a path exists on the device, with timing debug logs."""
        debug_print = partial(
            module_debug_print,
            'KoreaderAction:device_path_exists:'
        )
        start_time = time.time()
        exists = False
        method = "unknown"

        # 1. Try native driver exists() if available
        if hasattr(device, 'exists'):
            try:
                exists = device.exists(path)
                method = "driver.exists"
            except:
                pass

        # 2. Try local filesystem (for USB)
        if not exists and self.is_usb_device(device):
            try:
                if os.path.exists(path):
                    exists = True
                    method = "os.path.exists"
            except:
                pass

        # 3. Try get_file (for Wireless) - this is the "expensive" fallback
        if not exists and method == "unknown":
            try:
                with io.BytesIO() as dummy:
                    device.get_file(path, dummy)
                exists = True
                method = "device.get_file"
            except:
                exists = False
                method = "device.get_file (failed)"

        end_time = time.time()
        debug_print(f"Path: {path} | Exists: {exists} | Method: {method} | Time: {end_time - start_time:.4f}s")
        return exists

    def push_metadata_to_koreader_sidecar(self, device, book_uuid, path):
        """Create a sidecar file for the given book.

        :param device: The connected device object
        :param book_uuid: Calibre's uuid for the book
        :param path: path to sidecar file to create
        :return: tuple of bool and result dict
        """

        debug_print = partial(
            module_debug_print,
            'KoreaderAction:push_metadata_to_koreader_sidecar:'
        )

        try:
            db = self.gui.current_db.new_api
            book_id = db.lookup_by_uuid(book_uuid)
            debug_print(f"Book id is {book_id}")
        except:
            book_id = None

        if not book_id:
            debug_print(f'could not find {book_uuid} in calibre’s library')
            return "failure", {
                'result': f"Could not find uuid {book_uuid} in Calibre's "
                f"library."
            }

        # Get the current metadata for the book from the library
        metadata = db.get_metadata(book_id)
        sidecar_metadata = metadata.get(CONFIG["column_sidecar"])
        if not sidecar_metadata:
            return "no_metadata", {
                'result': f'No KOReader metadata for book_id {book_id}, no '
                f'need to push.'
            }
        sidecar_dict = json.loads(sidecar_metadata)
        sidecar_lua = lua.encode(sidecar_dict)
        # Lua -> JSON -> Lua conversion is lossy, because JSON does not support integer
        # keys. This means that a key like [1] will end up as ["1"] after the round
        # trip. The following regex strips the quotes from any Lua object key that consists of
        # only digits. This is not entirely correct because it now converts keys with
        # only digits that were originally string keys as well, but it doesn't seem that
        # KOReader uses those.
        sidecar_lua = re.sub(r'\["(\d+)"\]', r'[\1]', sidecar_lua)
        sidecar_lua_formatted = f"-- we can read Lua syntax here!\nreturn {sidecar_lua}\n"
        
        # Use device.put_file to support wireless devices (#122)
        # Check if driver supports writing arbitrary files
        if not hasattr(device, 'put_file'):
            debug_print(f"Device driver {device.__class__.__name__} does not support writing sidecar files wirelessly.")
            return "failure", {
                'result': 'Wireless write not supported by this device driver. Please use USB or Sync Server.',
            }

        try:
            with io.BytesIO(sidecar_lua_formatted.encode('utf-8')) as f:
                device.put_file(path, f)
        except Exception as e:
            debug_print(f"Failed to push metadata to {path}: {e}")
            return "failure", {
                'result': f'Failed to write to device: {e}',
            }

        return "success", {
            'result': 'success',
        }

    def sync_missing_sidecars_to_koreader(self, silent=False):
        """Push the content of Calibre's raw metadata column to KOReader
        for any files which are missing in KOReader. Does not touch existing
        metadata sidecars on KOReader.

        Intended for e.g. setting up a new device and syncing to it for the first
        time.

        :return:
        """
        debug_print = partial(
            module_debug_print,
            'KoreaderAction:sync_missing_sidecars_to_koreader:'
        )

        if CONFIG["column_sidecar"] == '':
            error_dialog(
                self.gui,
                'Failure',
                'Raw metadata column not mapped, impossible to push metadata to sidecars',
                show=True,
                show_copy_button=False
            )
            return None

        device = self.get_connected_device()

        if not self.check_device(device):
            return None

        sidecar_paths = self.get_paths(device)
        debug_print('sidecar_paths: ', sidecar_paths)
        
        results = []
        num_processed = 0
        num_success = 0
        num_no_metadata = 0
        num_fail = 0
        num_skipped_existing = 0
        
        for book_uuid, path in sidecar_paths:
            # Check if exists first (issue #122 revisited)
            if self.device_path_exists(device, path):
                debug_print(f"Skipping existing sidecar: {path}")
                num_skipped_existing += 1
                continue

            num_processed += 1
            result, details = self.push_metadata_to_koreader_sidecar(device, book_uuid,
                                                                     path)
            if result == "success":
                num_success += 1
                results.append(
                    {
                        **details,
                        'book_uuid': book_uuid,
                        'sidecar_path': path,
                    }
                )
            elif result == "failure":
                num_fail += 1
                results.append(
                    {
                        **details,
                        'book_uuid': book_uuid,
                        'sidecar_path': path,
                    }
                )
            elif result == "no_metadata":
                num_no_metadata += 1
                results.append(
                    {
                        **details,
                        'book_uuid': book_uuid,
                        'sidecar_path': path,
                    }
                )

        if not silent:
            results_message = (
                f'{len(sidecar_paths)} books on device.\n'
                f'{num_skipped_existing} books already have sidecars (skipped).\n'
                f'Sidecar creation succeeded for {num_success}.\n'
                f'Sidecar creation failed for {num_fail}.\n'
                f'No attempt made for {num_no_metadata} (no metadata in Calibre to push).\n'
                f'See below for details.'
            )

            if num_success > 0 and num_fail > 0:
                SyncCompletionDialog(
                    self.gui,
                    'Results',
                    results_message,
                    results,
                    'warn'
                )
            elif num_success > 0 or num_no_metadata > 0:  # and num_fail == 0
                SyncCompletionDialog(
                    self.gui,
                    'Success',
                    results_message,
                    results,
                    'info'
                )
            else:
                SyncCompletionDialog(
                    self.gui,
                    'Failure',
                    results_message,
                    results,
                    'error'
                )

    def sync_progress_from_progresssync(self, silent=False):
        """Use KOReader's ProgressSync Server to update Calibre metadata rather than a manual sync.

        Intended to easily update Calibre with the latest reading progress from KOReader.

        :return:
        """

        debug_print = partial(
            module_debug_print,
            'KoreaderAction:sync_progress_from_progresssync:'
        )

        md5_column = CONFIG["column_md5"]
        if md5_column == '':
            error_dialog(
                self.gui,
                'Failure',
                'MD5 column not mapped, impossible to get metadata from Progress Sync Server',
                show=True,
                show_copy_button=False
            )
            return None

        if CONFIG["progress_sync_password"] == '':
            error_dialog(
                self.gui,
                'Failure',
                'Progress Sync Account is not logged in, add credentials in plugin settings',
                show=True,
                show_copy_button=False
            )
            return None

        status_key = CONFIG['column_status']
        read_percent_key = CONFIG['column_percent_read_int'] or CONFIG['column_percent_read']
        if read_percent_key == '' or status_key == '':
            error_dialog(
                self.gui,
                'Failure',
                'This feature needs a KOReader Progress (int or float) and Status Text column.\n'
                'Add those in plugin settings and try again.',
                show=True,
                show_copy_button=False
            )
            return None

        'Get list of books with MD5 column'
        db = self.gui.current_db.new_api
        books_with_md5 = db.search(f'{md5_column}:!''')

        results = []
        num_success = 0
        num_skip = 0

        headers = {
            'x-auth-user': CONFIG["progress_sync_username"],
            'x-auth-key': CONFIG["progress_sync_password"],
            'Accept': 'application/vnd.koreader.v1+json',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'User-Agent': f'CalibreKOReaderSync/{self.version}'
        }

        # Create SSL context based on user preference
        ssl_context = ssl.create_default_context()
        if CONFIG['checkbox_skip_ssl_verification']:
            # Skip SSL verification for custom servers with self-signed certificates
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        for book_id in books_with_md5:
            metadata = db.get_metadata(book_id)
            md5_value = metadata.get(md5_column)
            book_uuid = metadata.get('uuid')
            title = metadata.get('title')

            # Only get sync status if curr progress < 100 and status = reading or if curr_progress/status is not set yet
            metadata_status = metadata.get(status_key)
            metadata_read_percent = metadata.get(read_percent_key)
            if (metadata_status is None or metadata_status == "reading") and (metadata_read_percent is None or metadata_read_percent < 100):
                try:
                    url = f'{CONFIG["progress_sync_url"]}/syncs/progress/{md5_value}'
                    request = Request(url, headers=headers)
                    with urlopen(request, timeout=20, context=ssl_context) as response:
                        response_data = response.read()
                        if response_data == b'{}':
                            results.append({
                                'md5_value': md5_value,
                                'error': 'No ProgressSync entry for md5 hash'
                            })
                            num_skip += 1
                            continue
                        progress_data = json.loads(response_data.decode('utf-8'))

                    # Kinda Janky edge case handling
                    if len(str(progress_data)) < 8:
                        continue

                    # List of keys to check
                    ProgressSync_Columns = [
                        'column_percent_read', 'column_percent_read_int', 'column_last_read_location', 'column_date_synced', 'column_device_name', 'column_device_id']

                    # Map of progress_data keys to match each config key
                    progress_mapping = {
                        'column_percent_read': progress_data['percentage'] if not CONFIG["checkbox_percent_read_100"] else progress_data['percentage']*100,
                        'column_percent_read_int': round(progress_data['percentage']*100),
                        'column_last_read_location': progress_data['progress'],
                        'column_date_synced': datetime.fromtimestamp(progress_data['timestamp']/1000, tz=local_tz),
                        'column_device_name': progress_data['device'],
                        'column_device_id': progress_data['device_id']
                    }
                    # Change percentage to be human readable on summary screen
                    if CONFIG["checkbox_percent_read_100"]:
                        progress_data['percentage']*=100

                    # Dictionary to store values to be updated
                    keys_values_to_update = {}

                    # Set column_date_book_started if this is the first sync and column not already filled
                    date_book_started_key = CONFIG.get('column_date_book_started')
                    if date_book_started_key is not None:
                        if metadata.get(date_book_started_key) is None:
                            keys_values_to_update[date_book_started_key] = progress_mapping['column_date_synced']

                    # Set column_date_book_finished if this book is finished and column not already filled
                    if progress_mapping['column_percent_read_int'] >= 100:
                        date_book_finished_key = CONFIG.get('column_date_book_finished')
                        if date_book_finished_key is not None:
                            if metadata.get(date_book_finished_key) is None:
                                keys_values_to_update[date_book_finished_key] = progress_mapping['column_date_synced']

                    for key in ProgressSync_Columns:
                        # Get internal column name from CONFIG
                        internal_column = CONFIG.get(key, '')
                        if not internal_column:  # Skip if internal column name is blank
                            continue

                        # Get current value from metadata
                        current_value = metadata.get(internal_column)
                        remote_value = progress_mapping[key]

                        # Compare current and remote values
                        if current_value != remote_value:
                            keys_values_to_update[internal_column] = remote_value
                        # TODO This is redundant isn't it? I can remove a whole chunk of this ngl.

                    # Update only if there are differences
                    if keys_values_to_update:
                        operation_status, result = self.update_metadata(
                            book_uuid, db, keys_values_to_update)
                    else:
                        result = {}

                    results.append({
                        **result,
                        'title': title,
                        'book_uuid': book_uuid,
                        'md5_value': md5_value,
                        **progress_data
                    })
                    num_success += 1

                except (HTTPError, URLError) as e:
                    msg = f'Failed to make progress sync query: {url}, error: {str(e)}'
                    debug_print(msg)
                    results.append({
                        'title': title,
                        'book_uuid': book_uuid,
                        'md5_value': md5_value,
                        'error': 'No data received'
                    })
                    num_skip += 1

            else:
                results.append({
                    'title': title,
                    'book_uuid': book_uuid,
                    'md5_value': md5_value,
                    'error': 'Book has already been read'
                })
                num_skip += 1

        if not silent:
            results_message = (
                f'Total books with MD5 values: {len(books_with_md5)}\n\n'
                f'Successful syncs: {num_success}\n'
                f'Failed/Skipped syncs: {num_skip}\n\n'
            )

            if num_success > 0 and num_skip == 0:
                SyncCompletionDialog(
                    self.gui,
                    'Progress sync finished',
                    results_message + 'All looks good!\n\n',
                    results,
                    'info'
                )
            elif num_skip > 0:
                SyncCompletionDialog(
                    self.gui,
                    'Some syncs failed',
                    results_message + 'There were some errors during the sync process!\n'
                    'Please investigate and report if it looks like a bug\n\n',
                    results,
                    'warn'
                )
            else:
                SyncCompletionDialog(
                    self.gui,
                    'No successful syncs',
                    results_message + 'No successful syncs\n'
                    'Please investigate and report if it looks like a bug\n\n',
                    results,
                    'error'
                )

    def scheduled_progress_sync(self):
        def scheduledTask():
            # Set another timer for the next day and order sync
            QTimer.singleShot(24 * 3600 * 1000, scheduledTask)
            self.sync_progress_from_progresssync(
                silent=True if not DEBUG else False)

        def main():
            # Get current local time
            currentTime = QTime.currentTime()

            # Set target time to user inputted time
            targetTime = QTime(
                CONFIG["scheduleSyncHour"], CONFIG["scheduleSyncMinute"])

            # Calculate the time difference
            timeDiff = currentTime.msecsTo(targetTime)

            # If target time has already passed today, set the target time for tomorrow
            if timeDiff < 0:
                timeDiff = timeDiff + 86400000

            # Create a QTimer to trigger the task at the desired time
            QTimer.singleShot(timeDiff, scheduledTask)

        main()  # Runs scheduled_progress_sync

    def sync_to_calibre(self, silent=False):
        """This plugin’s main purpose. It syncs the contents of
        KOReader’s metadata sidecar files into calibre’s metadata.

        :return:
        """
        debug_print = partial(
            module_debug_print,
            'KoreaderAction:sync_to_calibre:'
        )

        device = self.get_connected_device()

        if not self.check_device(device):
            return None

        sidecar_paths = self.get_paths(device)
        debug_print('sidecar_paths:', sidecar_paths)

        class KOSyncWorker(QThread):
            progress_update = pyqtSignal(int, str)
            finished_signal = pyqtSignal(dict)

            def __init__(self, action, db, sidecar_paths):
                super().__init__()
                self.action = action
                self.db = db
                self.sidecar_paths = sidecar_paths

            def run(self):
                results = []
                num_success = 0
                num_fail = 0
                num_skip = 0

                for idx, (book_uuid, sidecar_path) in enumerate(self.sidecar_paths):
                    debug_print('Trying to get sidecar from ', device,
                                ', with sidecar_path: ', sidecar_path)

                    # pre-checks before parsing
                    if book_uuid is None:
                        status = 'skipped, no UUID'
                        append_results(results, None, status,
                                       book_uuid, sidecar_path)
                        num_skip += 1
                        continue

                    sidecar_contents = self.action.get_sidecar(
                        device, sidecar_path)
                    debug_print("sidecar_contents:", sidecar_contents)

                    try:
                        book_id = db.lookup_by_uuid(book_uuid)
                        if not book_id:
                            # Try to find a better UUID in the sidecar (Issue #115)
                            better_uuid = self.action.get_calibre_uuid_from_sidecar(sidecar_contents)
                            if better_uuid:
                                debug_print(f"Found alternative UUID in sidecar: {better_uuid}")
                                book_id = db.lookup_by_uuid(better_uuid)
                                if book_id:
                                    book_uuid = better_uuid # Use the one that worked

                        if not book_id:
                            raise Exception("Book not found")
                        metadata = db.get_metadata(book_id)
                        title = metadata.get('title')
                    except Exception as e:
                        debug_print(f"Failed to lookup book {book_uuid}: {e}")
                        status = f'skipped, could not find in library'
                        append_results(results, "Unknown", status,
                                       book_uuid, sidecar_path)
                        num_skip += 1
                        continue

                    self.progress_update.emit(idx + 1, title)
                    if DEBUG: # Add time delay when debugging
                        time.sleep(.4)

                    if sidecar_contents is GetSidecarStatus.PATH_NOT_FOUND:
                        status = ('skipped, sidecar does not exist '
                                  '(seems like book is never opened)')
                        append_results(results, title, status,
                                       book_uuid, sidecar_path)
                        num_skip += 1
                        continue

                    elif sidecar_contents is GetSidecarStatus.DECODE_FAILED:
                        status = 'decoding is failed see debug for more details'
                        append_results(results, title, status,
                                       book_uuid, sidecar_path)
                        num_fail += 1
                        continue

                    else:
                        debug_print('sidecar_contents is found!')

                    keys_values_to_update = {}

                    for config_name, column in COLUMNS.items():
                        target = CONFIG[config_name]

                        if target == '':
                            # No column mapped, so do not sync
                            continue

                        # Special handling for date started/finished
                        # Safety check for 'summary' key (#117)
                        summary = sidecar_contents.get('summary', {})
                        if config_name == 'column_date_book_started':
                            if metadata.get(target) is None and summary.get('status') == 'reading':
                                sidecar_contents['calculated']['date_book_started'] = sidecar_contents['calculated'].get('date_status_changed')
                        if config_name == 'column_date_book_finished':
                            if metadata.get(target) is None and summary.get('status') == 'complete':
                                sidecar_contents['calculated']['date_book_finished'] = sidecar_contents['calculated'].get('date_status_changed')

                        data_location = column['data_location']
                        value = sidecar_contents

                        for subproperty in data_location:
                            if value and subproperty in value:
                                value = value[subproperty]
                            else:
                                debug_print(
                                    f'subproperty "{subproperty}" not found in value')
                                value = None
                                break

                        if value is None:
                            continue

                        # Transform value if required
                        if 'transform' in column:
                            debug_print('transforming value for ', target)
                            value = column['transform'](value)

                        keys_values_to_update[target] = value

                    operation_status, result = self.action.update_metadata(
                        book_uuid, db, keys_values_to_update)


                    results.append(
                        {
                            **result,
                            'title': title,
                            'book_uuid': book_uuid,
                            'sidecar_path': sidecar_path,
                            **({'updated': json.dumps(keys_values_to_update, default=str)} if DEBUG else {})
                        }
                    )

                    if operation_status == OperationStatus.PASS:
                        num_success += 1
                    elif operation_status == OperationStatus.FAIL:
                        num_fail += 1
                    elif operation_status == OperationStatus.SKIP:
                        num_skip += 1
                self.finished_signal.emit(
                    {'results': results, 'num_success': num_success, 'num_fail': num_fail, 'num_skip': num_skip})

        db = self.gui.current_db.new_api
        startTime = time.perf_counter()
        self.koSyncWorker = KOSyncWorker(self, db, sidecar_paths)
        progress_dialog = None
        if not silent and len(sidecar_paths) > 10:
            progress_dialog = ProgressDialog(
                self.gui, "Syncing Sidecars...", len(sidecar_paths))
            progress_dialog.show()
            self.koSyncWorker.progress_update.connect(progress_dialog.setValue)

        def on_finished(res):
            if not silent:
                if progress_dialog:
                    progress_dialog.close()
                results_message = (
                    f"Total targets found: {len(sidecar_paths)}\n\n"
                    f"Metadata sync succeeded for: {res['num_success']}\n"
                    f"Metadata sync skipped for: {res['num_skip']}\n"
                    f"Metadata sync failed for: {res['num_fail']}\n"
                    f"Time taken: {time.perf_counter() - startTime:.4f} seconds.\n\n"
                )
                # Sort by if error, then # of changes
                res['results'].sort(key=lambda row: (
                    not row.get('error', False), -len(row)))
                if res['num_success'] > 0 and res['num_fail'] == 0:
                    SyncCompletionDialog(
                        self.gui,
                        'Metadata sync finished',
                        results_message + 'All looks good!\n\n',
                        res['results'],
                        'info'
                    )
                elif res['num_fail'] > 0:
                    SyncCompletionDialog(
                        self.gui,
                        'Some sync failed',
                        results_message + 'There was some error during sync process!\n'
                        'Please investigate and report if it looks '
                        'like a bug\n\n',
                        res['results'],
                        'error'
                    )
                elif res['num_success'] == 0 and res['num_fail'] == 0:
                    SyncCompletionDialog(
                        self.gui,
                        'No errors but not successful syncs',
                        results_message + 'No errors but no successful syncs\n'
                        'Do you have book(s) which are ready to be '
                        'sync?\n'
                        'Please investigate and report if it looks '
                        'like a bug\n\n',
                        res['results'],
                        'warn'
                    )
                else:
                    error_dialog(
                        self.gui,
                        'Edge case',
                        results_message + 'Seems like and bug, please report ASAP\n\n',
                        det_msg=json.dumps(res['results'], indent=2),
                        show=True,
                        show_copy_button=False
                    )
        self.koSyncWorker.finished_signal.connect(on_finished)
        self.koSyncWorker.start()


class ProgressDialog(QDialog):
    def __init__(self, parent, title: str, count: int):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModal)
        layout = QVBoxLayout(self)
        self.progressBar = QProgressBar(self)
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(count)
        self.progressBar.setFormat("%v of %m")
        layout.addWidget(self.progressBar)
        self.currBook = QLabel('Beginning Sync')
        layout.addWidget(self.currBook)

    def setValue(self, idx: int, bookTitle: str):
        self.progressBar.setValue(idx)
        self.currBook.setText(bookTitle)


class SyncCompletionDialog(QDialog):
    def __init__(self, parent=None, title="", msg="", results=None, type=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(800)
        self.setMinimumHeight(800)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Main Message Area
        mainMessageLayout = QHBoxLayout()
        type_icon = {
            'info': 'dialog_information',
            'error': 'dialog_error',
            'warn': 'dialog_warning',
        }.get(type)
        if type_icon is not None:
            icon = QIcon.ic(f'{type_icon}.png')
            self.setWindowIcon(icon)
            icon_widget = QLabel(self)
            icon_widget.setPixmap(icon.pixmap(64, 64))
            mainMessageLayout.addWidget(icon_widget)
        message_label = QLabel(msg)
        mainMessageLayout.addWidget(message_label)
        mainMessageLayout.addStretch()  # Left align the message/text
        layout.addLayout(mainMessageLayout)

        # Table in scrollable area if results are provided
        if results:
            self.table_area = QScrollArea(self)
            self.table_area.setWidgetResizable(True)
            table = self.create_results_table(results)
            self.table_area.setWidget(table)
            layout.addWidget(self.table_area)

        # Bottom Buttons
        bottomButtonLayout = QHBoxLayout()
        if results:
            copy_button = QPushButton("COPY", self)
            copy_button.setFixedWidth(200)
            copy_button.setIcon(QIcon.ic('edit-copy.png'))
            copy_button.clicked.connect(lambda: (
                QApplication.clipboard().setText(str(results)),
                copy_button.setText('Copied')
            ))
            bottomButtonLayout.addWidget(copy_button)
        bottomButtonLayout.addStretch()  # Right align the rest of this layout
        ok_button = QPushButton("OK", self)
        ok_button.setFixedWidth(200)
        ok_button.setIcon(QIcon.ic('ok.png'))
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        bottomButtonLayout.addWidget(ok_button)
        layout.addLayout(bottomButtonLayout)

        self.show()

    def create_results_table(self, results):
        # Get all possible headers from results and save as set
        all_headers = {key for result in results for key in result.keys()}

        headers = []
        custom_columns = sorted(h for h in all_headers
                                if h not in ('title', 'book_uuid', 'result', 'error'))

        if 'title' in all_headers:
            headers.append('title')
        if 'book_uuid' in all_headers:
            headers.append('book_uuid')
        if 'result' in all_headers:
            headers.append('result')
        if 'error' in all_headers:
            headers.append('error')
        if custom_columns:
            headers.extend(custom_columns)

        table = QTableWidget()
        table.setRowCount(len(results))
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        for row, result in enumerate(results):
            for col, header in enumerate(headers):
                item = QTableWidgetItem(str(result.get(header, "")))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                # Set the tooltip to the full text
                item.setToolTip(item.text())
                table.setItem(row, col, item)

        max_lines = 1
        for col, header in enumerate(headers):
            words, line, lines, col_len_limit = header.split(
            ), "", [], max(table.columnWidth(col) // 7, 10)
            for word in words:
                line = f"{line} {word}".strip()
                if len(line) > col_len_limit:
                    lines.append(line.rsplit(' ', 1)[0])
                    line = word if ' ' in line else ''
            lines.append(line)
            max_lines = max(len(lines), max_lines)
            wrapped = '\n'.join(lines)
            table.setHorizontalHeaderItem(col, QTableWidgetItem(wrapped))
        table.horizontalHeader().setFixedHeight(20 * max_lines)  # Default = 20

        return table
