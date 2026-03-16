import sys
import os
import builtins
import types
import importlib.util
from unittest.mock import MagicMock

# 1. Mock gettext '_' function which Calibre injects into builtins
if not hasattr(builtins, '_'):
    builtins._ = lambda x: x

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 2. Mock 'calibre' package and submodules
calibre = types.ModuleType("calibre")
calibre.constants = MagicMock()
calibre.constants.numeric_version = (6, 0, 0)
calibre.customize = MagicMock()
class MockInterfaceActionBase:
    pass
calibre.customize.InterfaceActionBase = MockInterfaceActionBase

calibre.devices = MagicMock()
calibre.devices.usbms = MagicMock()
calibre.devices.usbms.driver = MagicMock()

# Setup calibre.utils as a package
calibre_utils = types.ModuleType("calibre.utils")
calibre_utils.__path__ = []
calibre.utils = calibre_utils

calibre_utils.config = MagicMock()
calibre_utils.iso8601 = MagicMock()
# Mock timezone objects
from datetime import timezone
calibre_utils.iso8601.utc_tz = timezone.utc
calibre_utils.iso8601.local_tz = timezone.utc # Good enough for mocks

# Setup calibre.gui2
calibre_gui2 = types.ModuleType("calibre.gui2")
calibre_gui2.__path__ = []
calibre.gui2 = calibre_gui2

calibre_gui2.actions = MagicMock()
class MockInterfaceAction:
    def __init__(self, parent, site_customization):
        self.gui = parent
        self.interface_action_base_plugin = site_customization
calibre_gui2.actions.InterfaceAction = MockInterfaceAction

calibre_gui2.device = MagicMock()
calibre_gui2.show_restart_warning = MagicMock()
calibre_gui2.error_dialog = MagicMock()
calibre_gui2.warning_dialog = MagicMock()
calibre_gui2.open_url = MagicMock()

# Setup calibre.gui2.dialogs as a package
calibre_gui2_dialogs = types.ModuleType("calibre.gui2.dialogs")
calibre_gui2_dialogs.__path__ = []
calibre_gui2.dialogs = calibre_gui2_dialogs
sys.modules["calibre.gui2.dialogs"] = calibre_gui2_dialogs

calibre_gui2_dialogs.message_box = MagicMock()
calibre_gui2_dialogs.message_box.MessageBox = MagicMock()

# Assign to sys.modules
sys.modules["calibre"] = calibre
sys.modules["calibre.constants"] = calibre.constants
sys.modules["calibre.customize"] = calibre.customize
sys.modules["calibre.devices"] = calibre.devices
sys.modules["calibre.devices.usbms"] = calibre.devices.usbms
sys.modules["calibre.devices.usbms.driver"] = calibre.devices.usbms.driver
sys.modules["calibre.utils"] = calibre.utils
sys.modules["calibre.utils.config"] = calibre.utils.config
sys.modules["calibre.utils.iso8601"] = calibre.utils.iso8601
sys.modules["calibre.gui2"] = calibre.gui2
sys.modules["calibre.gui2.actions"] = calibre_gui2.actions
sys.modules["calibre.gui2.dialogs"] = calibre_gui2.dialogs
sys.modules["calibre.gui2.dialogs.message_box"] = calibre_gui2_dialogs.message_box
sys.modules["calibre.gui2.device"] = calibre_gui2.device

# 3. Create 'calibre_plugins' package
calibre_plugins = types.ModuleType("calibre_plugins")
sys.modules["calibre_plugins"] = calibre_plugins

# 4. Create 'koreader' package
koreader_pkg = types.ModuleType("calibre_plugins.koreader")
koreader_pkg.__path__ = []
calibre_plugins.koreader = koreader_pkg
sys.modules["calibre_plugins.koreader"] = koreader_pkg

# 5. Import local modules
# Load __init__.py manually
init_path = os.path.join(os.path.dirname(__file__), '..', '__init__.py')
spec = importlib.util.spec_from_file_location("__init__", init_path)
__init__ = importlib.util.module_from_spec(spec)
sys.modules["__init__"] = __init__
spec.loader.exec_module(__init__)

import slpp

# 6. Assign submodules to the package
koreader_pkg.slpp = slpp
sys.modules["calibre_plugins.koreader.slpp"] = slpp

# __init__ exports
koreader_pkg.clean_bookmarks = __init__.clean_bookmarks
koreader_pkg.DEBUG = __init__.DEBUG
koreader_pkg.DRY_RUN = __init__.DRY_RUN
koreader_pkg.PYDEVD = __init__.PYDEVD
koreader_pkg.KoreaderSync = __init__.KoreaderSync

# 7. Import config (depends on setup)
import config
koreader_pkg.config = config
sys.modules["calibre_plugins.koreader.config"] = config
