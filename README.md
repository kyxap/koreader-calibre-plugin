# KOReader calibre plugin

| Release | Build Status | Version |
| :--- | :--- | :--- |
| **Stable** (`main`) | [![CI Status](https://github.com/kyxap/koreader-calibre-plugin/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/kyxap/koreader-calibre-plugin/actions/workflows/ci.yml) | [![Latest Release](https://img.shields.io/github/v/release/kyxap/koreader-calibre-plugin?label=latest&color=green)](https://github.com/kyxap/koreader-calibre-plugin/releases) |
| **Development** (`develop`) | [![CI Status](https://github.com/kyxap/koreader-calibre-plugin/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/kyxap/koreader-calibre-plugin/actions/workflows/ci.yml) | [![Dev Build](https://github.com/kyxap/koreader-calibre-plugin/actions/workflows/dev-release.yml/badge.svg?branch=develop)](https://github.com/kyxap/koreader-calibre-plugin/releases/tag/dev-build) |

[![License](https://img.shields.io/github/license/kyxap/koreader-calibre-plugin?color=blue)](https://github.com/kyxap/koreader-calibre-plugin/blob/main/LICENSE)

A calibre plugin to synchronize metadata from KOReader to calibre.

[KOReader](https://koreader.rocks/) creates sidecar files that hold read
progress and annotations.
This plugin reads the data from those sidecar files and updates calibre's
metadata based on them. It is inspired
by [the Kobo Utilities plugin](https://www.mobileread.com/forums/showthread.php?t=215339),
that synchronizes reading progress between the original Kobo firmware ("Nickel")
and custom columns in calibre.

Note that at the moment the sync is primarily one-way—from the KOReader device
to calibre, and only works for USB
and [wireless](https://github.com/koreader/koreader/wiki/Calibre-wireless-connection)
devices. For best experience please use the latest
KOReader [release](https://github.com/koreader/koreader/releases)

Releases will also be uploaded
to [plugin thread](https://www.mobileread.com/forums/showthread.php?t=362706) on
the MobileRead Forums.
If you are on there as well, please let me know what you think of the plugin in
that thread.

## Using this plugin

### Download and install

1. Go to your calibre's _Preferences_ > _Plugins_ > _Get new plugins_ and search
   for _KOReader Sync_
2. Click _Install_
3. Restart calibre

#### Alternatively

1. Download the latest release
   from [here](https://github.com/kyxap/koreader-calibre-plugin/releases).
2. Go to your calibre's _Preferences_ > _Plugins_ > _Load plugin from file_ and
   point it to the downloaded ZIP file
3. Restart calibre

### Setup

1. Pick and choose the metadata you would like to sync and create the
   appropriate columns in calibre. The plugin makes this easy, simply select
   the **create new columns** option in the config dropdowns.

   These are your options:
   - A _Floating point numbers_ column to store the **current percent read**,
     with _Format for numbers_ set to `{:.0%}`.
   - An _Integers_ column to store the **current percent read**.
   - A regular _Text_ column to store the **location you last stopped reading at**
   - A _Rating_ column to store your **rating** of the book, as entered on the
     book's status page.
   - A _Long text_ column to store your **review** of the book, as entered on
     the book's status page.
   - A regular _Text_ column to store the **reading status** of the book, as
     entered on the book status page (_Finished_, _Reading_, _On hold_).
     Translates to complete, reading, and abandoned respectively in calibre.
   - A _Yes/No_ column to store the **reading status** of the book, as a
     boolean (_Yes_ = _Finished_, _No_ = everything else).
   - A _Long text_ column to store your **bookmarks and highlights** of the
     book, with _Interpret this column as_ set to _Plain text formatted using
     markdown_. (Highlights are an unordered list with their metadata in an
     HTML comment.)
   - A regular _Text_ column to store the **MD5 hash** KOReader uses to sync
     progress to a [KOReader Sync
     Server](https://github.com/koreader/koreader-sync-server#koreader-sync-server)
     (_Progress sync_ in the KOReader app). This allows for syncing
     progress and location to calibre without having to connect your KOReader device.
   - A _Date_ column to store **when the last sync was performed**.
   - A _Date_ column to store **when the sidecar file was last modified**. Works
     for wired connection only, wireless will be always empty.
   - A _Date_ column to store **when the book status was first marked reading**.
   - A _Date_ column to store **when the book status was first marked finished**.
   - A _Long text_ column to store the **contents of the metadata sidecar** as
     HTML, with _Interpret this column as_ set to _HTML_.

   There are additional settings for:
   - Sync only if changes are more recent: Checks retrieved **Last Sync Date** against date on file.
   - No sync if book has already been finished: If **percent read** is _100_ or if **reading status** is _finished_ don't update data.
   - Automatic Sync on device connection: Silently sync's from KOReader when device is connected

1.  Add _KOReader Sync_ to _main toolbar when a device is connected_, if it
    isn't there already.
2.  Right-click the _KOReader Sync_ icon and _Configure_.
3.  Map the metadata you want to sync to the newly created calibre columns.
4.  Click _OK_ to save your mapping.
5.  From now on just click the _KOReader Sync_ icon to sync all mapped metadata
    for all books on the connected device to calibre.

**Note:** Some field are depreciated and removed from plugin since they are
changed/removed from `sidecar_contents` data structure:

- `first_bookmark` removed
- `last_bookmark` removed
- `bookmarks` renamed to `annotations`
- `rating` KOreader uses 5-point but calibre 10-point scale (whole starts, not half stars)
- `date_sidecar_modified` seems to be present in `calculated` only if connected via
  cable (not wireless)

### ProgressSync

  This plugin supports use of a [KOReader Sync
  Server](https://github.com/koreader/koreader-sync-server#koreader-sync-server)
  (_Progress sync_ in the KOReader app) in order to update **current percent read**
  (both float and int) and **location you last stopped reading at** wirelessly.\
  You must also have the **MD5 hash** column enabled.\
  Add the server and user credentials in the plugin config to use this function.
  The user password is stored as a hash, not plain text.\
  You can have calibre fetch updated data on a daily schedule.

### Things to consider

- The plugin overwrites existing metadata in Calibre without asking. That
  usually isn’t a problem, because you will probably only add to KOReader’s
  metadata. But be aware that you might lose data in calibre if you’re not
  careful.
- Pushing sidecars back to KOReader currently only happens for sidecars which
  are missing. For now, manually delete the `<bookname>.sdr` folder from the
  device before attempting to push the sidecars back to KOReader for any books
  you would like to overwrite the current metadata with Calibre's metadata.
- When pushing missing sidecars to the device, no attempt is made to convert
  Calibre's metadata to account for changes in KOReader's sidecar format. Old
  metadata may work unpredictably if it's from a different version of KOReader.

### Supported devices

This plugin has been tested successfully with:

- Kobo Clara BW/Colour connected over USB or KOreader wireless driver
- Kobo Aura/Touch connected over USB (`KOBO` and `KOBOTOUCH` drivers)
- Kobo Aura H2O over USB (`KOBOTOUCHEXTENDED` driver)
- All devices connected wirelessly via the `SMART_DEVICE_APP` driver (e.g., KOReader wireless connection)
- PocketBook devices using `POCKETBOOK_IMPROVED`, `POCKETBOOK632`, `POCKETBOOK626`, or `POCKETBOOK622` drivers
- Kindle Keyboard (`KINDLE2`)
- Tolino Vision 4 HD (`TOLINO`)
- A connected folder (`FOLDER_DEVICE`)
- Manually defined devices using the `USER_DEFINED` driver

This plugin is not compatible with:

- `MTP_DEVICE` (Android devices connected via MTP)

### Star History

[![Star History Chart](https://api.star-history.com/svg?repos=kyxap/koreader-calibre-plugin&type=Date)](https://star-history.com/#kyxap/koreader-calibre-plugin&Date)

### Issues

If you encounter any issues with the plugin, please submit
them [here](https://github.com/kyxap/koreader-calibre-plugin/issues).

## Acknowledgements

- Multiple tweaks and bug fixes by [Glen Sawyer](https://git.sr.ht/~snelg)
- Additional functionality by [Charles Taylor](https://github.com/charlesangus/)
- Contains [SirAnthony's SLPP](https://github.com/SirAnthony/slpp) to parse Lua
  in Python.
- Some code borrowed from--and heavily inspired by--the
  great [Kobo Utilities](https://www.mobileread.com/forums/showthread.php?t=215339)
  calibre plugin.
- Some code borrowed from--and heavily inspired by--the
  great [Goodreads Sync](https://www.mobileread.com/forums/showthread.php?t=123281)
  calibre plugin.

## Contributing to this plugin

### Notes & Tips

- My first attempt was actually to sync calibre with KOReader's read progress
  through the progress sync plugin and
  a [sync server](https://github.com/koreader/koreader-sync-server).
  Read [here](https://github.com/koreader/koreader/issues/6399#issuecomment-721826362)
  why that did not work. This plugin might actually make that possible now by
  allowing you to store KOReader's MD5 hash in calibre...
- calibre allows you to auto-connect to a folder device on boot, which greatly
  speeds up your workflow when testing. You can find this under "
  Preferences" > "Tweaks", search for `auto_connect_to_folder`. Point that to
  the `dummy_device` folder in this repository. (I have included royalty free
  EPUBs for your and my convenience.)
- If you're testing and don't actually want to update any metadata,
  set `DRY_RUN` to `True` in `__init__.py`.
- I work in PyCharm, which offers a remote debugging server. To enable that in
  this plugin, set `PYDEVD` to `True` in `__init__.py`.You might need to
  change `sys.path.append` in `action.py`.
- The supported device drivers can be found
  in [the `SUPPORTED_DEVICES` list in `config.py`](https://github.com/kyxap/koreader-calibre-plugin/blob/main/config.py).
  Adding a new type here is the first step to adding support, but make sure all
  features are tested thoroughly before releasing a version with an added device

### Testing in calibre

Use make to load the plugin into calibre and launch it:

```shell
make dev
```

For Linux users with a Flatpak installation of Calibre, use the `FLATPAK=1`
flag. This is necessary because Flatpak runs Calibre in a
[sandboxed environment](https://docs.flatpak.org/en/latest/sandbox-permissions.html),
requiring specific commands to interact with it:

```shell
make dev FLATPAK=1
```

> **Note:** `FLATPAK=1` is only supported on Linux. On Windows and macOS,
> please install Calibre natively and run `make` without this flag.

### Makefile Targets

#### Main


| Target         | Description                                                                                                      |
|----------------|------------------------------------------------------------------------------------------------------------------|
| `test`         | Run unit and integration tests using `pytest` (includes Calibre environment mocks)                               |
| `lint`         | Run static analysis using `pylint` (enforces 9.5/10 score and zero Errors)                      |
| `dev`          | Load plugin source directly into Calibre and launch in debug mode                               |
| `pre`          | Patch internal version with `-pre` and build a community pre-release ZIP                        |
| `bump-patch`   | Increment the patch version in `.version` (e.g., 0.8.0 -> 0.8.1)                                |

| `bump-minor`   | Increment the minor version in `.version` (e.g., 0.8.0 -> 0.9.0)                                                 |
| `bump-major`   | Increment the major version in `.version` (e.g., 0.8.0 -> 1.0.0)                                                 |
| `prep-release` | Create a `release-prep-<version>` branch, update files, and commit                                               |
| `release`      | Tag the current version and push to trigger GitHub Release, do this after updated version already pushed to main |
| `md_to_bb`     | Convert input.md to output.forumbb (BBCode) for MobileRead forum posts                                           |

#### Extra

| Target        | Description                                                         |
|---------------|---------------------------------------------------------------------|
| `install`     | Install ZIP into Calibre without launching the GUI                  |
| `zip`         | Create plugin ZIP file in `dist/` directory                         |
| `load`        | Install ZIP from `dist/` and launch Calibre in debug mode           |
| `build`       | Full build workflow: update versions from `.version` and create ZIP |
| `dev_version` | Update all code files with the current version from `.version`      |
| `clean`       | Remove all build artifacts and temporary files                      |
| `clean_dev`   | Clean up development-specific temporary files                       |
| `tag`         | Create and push git tag for current version                         |

### Development & Release Cycle

The project uses a structured workflow to ensure both rapid updates and stable releases:

1.  **Develop Branch (`develop`)**: This is the primary work-in-progress branch.
    -   Experimental fixes and new features are merged here first.
    -   Every push to this branch triggers an automated **Pre-release build**.
    -   Users can download the latest community pre-release from the [Upcoming Release](https://github.com/kyxap/koreader-calibre-plugin/releases/tag/dev-build) page.
2.  **Main Branch (`main`)**: This branch contains the stable, production-ready code.
    -   Only merge `develop` into `main` when a milestone is reached.
    -   Running `make release` on this branch automatically cleans the version string, tags the commit, and triggers the official GitHub Release.

### Quality Assurance

The project enforces high code quality standards through automated checks:

- **Unit Testing:** Run `make test`. We use `pytest` along with a mocking layer (`tests/conftest.py`) that simulates the Calibre environment. This allows you to test plugin logic without having Calibre installed.
- **Linting:** Run `make lint`. We use `pylint` with a custom configuration (`.pylintrc`).
  - **Threshold:** The project requires a minimum score of **9.5/10**.
  - **Strictness:** The build will **instantly fail** if any **Fatal (F)** or **Error (E)** messages are found, regardless of the total score.

These checks run automatically on every Pull Request via GitHub Actions.

The project uses GitHub Actions to automate releases. When a tag `v*` is pushed, a GitHub Release is created automatically with the built plugin ZIP.

1.  **Prepare the version:**
    -   Manually edit `.version` OR run `make bump-patch` / `make bump-minor`.
2.  **Run preparation:**
    -   Run `make prep-release`. This creates a new branch (e.g., `release-prep-x.x.x`), updates all version strings in the code, and commits them.
3.  **Review and Merge:**
    -   Review the changes in the new branch, then merge it into `main`.
4.  **Publish:**
    -   On the `main` branch, run `make release`. This will tag the commit and push it.
    -   The GitHub Action will pick up the tag, build the plugin, and create a GitHub Release with the ZIP attached.

### Debugging a release

1. Download the required release
   from [here](https://github.com/kyxap/koreader-calibre-plugin/releases)
1. Add it to calibre by running this in your
   terminal: `calibre-customize -a "KOReader_Sync_vX.X.X.zip"`, where `X.X.X`
   refers to the version you downloaded
1. Start calibre in debug mode with `calibre-debug -g`
1. Configure the KOReader plugin as
   described [here](https://github.com/kyxap/koreader-calibre-plugin#setup)
1. Connect your device
1. Run the sync by clicking the KOReader icon in your toolbar
1. Check the details of the message when it's done if any/all books have been
   synced correctly
1. Check your (custom) columns for one of those books to see if their contents
   are what they should be
1. Check the output in your terminal for lines containing `koreader` to see what
   it did
