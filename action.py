#!/usr/bin/env python3

__license__   = 'GNU GPLv3'
__copyright__ = '2020, harmtemolder <mail at harmtemolder.com>'
__docformat__ = 'restructuredtext en'

from functools import partial
import io
import re
import sys

from calibre.devices.usbms.driver import debug_print as root_debug_print
from calibre.gui2 import error_dialog, info_dialog
from calibre.gui2.actions import InterfaceAction
from calibre_plugins.koreader import KoreaderSync
from calibre_plugins.koreader.config import COLUMNS, CONFIG
from calibre_plugins.koreader.slpp import slpp as lua


sys.path.append('/Applications/PyCharm.app/Contents/debug-eggs/pydevd-pycharm.egg')
import pydevd_pycharm
pydevd_pycharm.settrace('localhost', stdoutToServer=True, stderrToServer=True,
                        suspend=False)

module_debug_print = partial(root_debug_print, ' koreader:action:', sep='')


class KoreaderAction(InterfaceAction):
    name = KoreaderSync.name
    action_spec = (name, 'copy-to-library.png', KoreaderSync.description, None)
    action_add_menu = True
    action_menu_clone_qaction = 'Sync from KOReader'
    dont_add_to = frozenset([
        'context-menu', 'context-menu-device', 'toolbar-child', 'menubar',
        'menubar-device', 'context-menu-cover-browser', 'context-menu-split'])
    dont_remove_from = InterfaceAction.all_locations - dont_add_to
    action_type = 'current'

    def genesis(self):
        debug_print = partial(module_debug_print, 'KoreaderAction:genesis:')
        debug_print('start')

        base = self.interface_action_base_plugin
        self.version = '{} {}.{}.{}'.format(base.name, *base.version)

        # Overwrite icon with actual KOReader logo
        icon = get_icons('images/icon.png')
        self.qaction.setIcon(icon)

        # Left-click action
        self.qaction.triggered.connect(self.sync_to_calibre)

        # Right-click menu (already includes left-click action)
        self.create_menu_action(
            self.qaction.menu(),
            'Configure KOReader Sync',
            'Configure',
            icon='config.png',
            description=None,
            triggered=self.show_config
        )

    def show_config(self):
        self.interface_action_base_plugin.do_user_config(self.gui)

    def apply_settings(self):
        debug_print = partial(module_debug_print, 'KoreaderAction:apply_settings:')
        debug_print('start')
        pass

    def get_connected_device(self):
        """Tries to get the connected device, if any

        :return: the connected device object or None
        """
        debug_print = partial(module_debug_print,
                              'KoreaderAction:get_connected_device:')

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

    def get_paths(self, device):
        """Retrieves paths to sidecars of all books in calibre's library
        on the device

        :param device: a device object
        :return: a dict of uuids with corresponding paths to sidecars
        """
        debug_print = partial(module_debug_print,
                              'KoreaderAction:get_paths:')

        paths = {
            book.uuid: device._main_prefix + book.lpath.replace(
                '.epub', '.sdr/metadata.epub.lua')
            for book in device.books()
        }

        debug_print('found {} path(s) to sidecar Lua files'.format(
            len(paths)))

        return paths

    def get_sidecar(self, device, path):
        """Requests the given path from the given device and returns the
        contents of a sidecar Lua as Python dict

        :param device: a device object
        :param path: a path to a sidecar Lua on the device
        :return: dict or None
        """
        debug_print = partial(module_debug_print,
                              'KoreaderAction:get_sidecar:')

        with io.BytesIO() as outfile:
            try:
                device.get_file(path, outfile)
            except:
                debug_print('could not get ', path)
                return None

            contents = outfile.getvalue()
            parsed_contents = self.parse_sidecar_lua(contents.decode())

        return parsed_contents

    def parse_sidecar_lua(self, sidecar_lua):
        """Parses a sidecar Lua file into a Python dict

        :param sidecar_lua: the contents of a sidecar Lua as a str
        :return: a dict of those contents
        """
        debug_print = partial(module_debug_print,
                              'KoreaderAction:parse_sidecar_lua:')

        try:
            decoded_lua = lua.decode(re.sub('^[^{]*', '', sidecar_lua))
        except:
            debug_print('could not decode sidecar_lua')
            decoded_lua = None

        return decoded_lua

    def update_metadata(self, uuid, keys_values_to_update):
        """Update multiple metadata columns for the given book.

        :param uuid: identifier for the book
        :param keys_values_to_update: a dict of keys to update with values
        :return: None
        """
        debug_print = partial(module_debug_print,
                              'KoreaderAction:update_metadata:')

        try:
            db = self.gui.current_db.new_api
            book_id = db.lookup_by_uuid(uuid)
        except:
            book_id = None

        if not book_id:
            debug_print('could not find {} in calibre’s library'.format(uuid))
            return None

        # Get the current metadata for the book from the library
        metadata = db.get_metadata(book_id)

        # Update that metadata locally
        for key, value in keys_values_to_update.items():
            metadata.set(key, value)

        # Write the updated metadata back to the library
        db.set_metadata(book_id, metadata, set_title=False, set_authors=False)
        debug_print('updated metadata for uuid = ', uuid, ', id = ', book_id)

    def sync_to_calibre(self):
        """This plugin’s main purpose. It syncs the contents of
        KOReader’s metadata sidecar files into calibre’s metadata.

        :return:
        """
        debug_print = partial(module_debug_print,
                              'KoreaderAction:sync_to_calibre:')

        supported_devices = ['FOLDER_DEVICE']
        device = self.get_connected_device()

        if not device:
            return None

        device_class = device.__class__.__name__

        if device_class not in supported_devices:
            debug_print('unsupported device, device_class = ', device_class)
            error_dialog(
                self.gui,
                'Unsupported device',
                'Devices of the type {} are not (yet) supported by this '
                'plugin. Please check if there already is a feature request '
                'for this <a href="https://todo.sr.ht/~harmtemolder/koreader'
                '-calibre-plugin">here</a>. If not, feel free to create '
                'one.'.format(device_class),
                det_msg='',
                show=True,
                show_copy_button=False)
            return None

        sidecar_paths = self.get_paths(device)

        for book_uuid, sidecar_path in sidecar_paths.items():
            sidecar_contents = self.get_sidecar(device, sidecar_path)
            keys_values_to_update = {}

            for column in COLUMNS:
                name = column['name']
                target = CONFIG[name]

                if target == '':
                    # No column mapped, so do not sync
                    continue

                property = column['sidecar_property']
                value = sidecar_contents

                for subproperty in property:
                    if subproperty in value:
                        value = value[subproperty]
                    else:
                        debug_print('{} not in {}'.format(
                            subproperty, value.keys()))
                        value = None
                        break

                if not value:
                    break

                # Transform value if required
                if 'transform' in column:
                    value = column['transform'](value)

                keys_values_to_update[target] = value

            self.update_metadata(book_uuid, keys_values_to_update)
            info_dialog(
                self.gui,
                'Successfully synced metadata from KOReader',
                'Successfully synced metadata from KOReader',
                det_msg='',
                show=True,
                show_copy_button=False
            )
