# KOReader Calibre Plugin - AI Context & Architecture

This file provides critical architectural context and known limitations for AI assistants working on this codebase.

## 🏗 Core Architecture

The plugin facilitates metadata synchronization between **KOReader** (on E-ink devices) and **Calibre**.

### Connection Methods & Capabilities

| Method | Reading Metadata | Writing Sidecars (`.sdr`) | Notes |
| :--- | :--- | :--- | :--- |
| **USB Cable** | ✅ Supported | ✅ Supported | Device mounted as a local filesystem. |
| **Calibre WiFi** | ✅ Supported | ❌ Not Supported | Uses `SMART_DEVICE_APP` driver. `put_file()` is not available for arbitrary sidecars. |
| **Sync Server** | ✅ Supported | ✅ Supported | Communicates via REST API. Identifies books by MD5 hash instead of UUID. |

### Metadata Schema & Mapping
The plugin maps KOReader's Lua sidecar data to Calibre custom columns. Key fields include:
- **Percent Read:** Supported as both Floating Point (`{:.0%}`) and Integer.
- **Status:** Maps KOReader statuses (*Finished, Reading, On hold*) to Calibre (*complete, reading, abandoned*).
- **Annotations/Highlights:** Stored as Markdown in a Long Text column.
- **MD5 Hash:** **Critical** for ProgressSync server functionality.
- **Date Sidecar Modified:** Only available via wired (USB) connections.

## 🛠 Key Implementation Details

### Wireless "Sync Missing" Logic
- Because Calibre's Wireless driver cannot write sidecar files, the "Sync Missing to KOReader" feature is gracefully disabled for wireless connections to prevent `AttributeError`.
- **Existence Probing:** The method `device_path_exists` uses `device.get_file()` as a probe. On wireless connections, this is fast (~0.05s per book) and much more reliable than `os.path.exists()`.

### Metadata Extraction
- **Sidecar Parsing:** Sidecar files (`.lua`) are parsed into Python dicts using the internal `slpp.py` (Lua-in-Python parser).
- **Robustness:** Always use `.get()` or check for the existence of the `summary` key. Older or corrupted KOReader files may lack this key, which previously caused crashes.
- **Large Annotations:** To avoid `apsw.TooBigError` (Issue #114), the metadata extraction loop for hidden attributes must be O(N) relative to the number of highlights. Never iterate over the entire bookmark collection inside an individual annotation loop.
- **Renamed Fields:** Be aware that `bookmarks` was renamed to `annotations` in newer sidecar formats.

### Book Identification
- **UUID vs. MD5:** Direct device sync uses Calibre's internal UUID. Server-based sync relies on an MD5 hash stored in a custom column.
- **Sync Loop:** The internal sync loop (in `sync_to_calibre`) uses a list of `(uuid, path)` tuples. This allows handling multiple books that might be missing UUIDs without overwriting data in a dictionary.

## ⚠️ Known Limitations & Constraints

- **Hidden Folders:** The plugin is configured to ignore any book paths containing hidden directories (e.g., `.stfolder`, `.stversions`) to avoid "None Book" entries in the UI.
- **Python Versioning:** The plugin aims for compatibility with Python 3.12+. All regex patterns MUST use raw strings (`r"..."`) to avoid `SyntaxWarning` for invalid escape sequences.

## 🧪 Development & Debugging
- Use `make dev` to build and install the development version.
- Timing logs for device operations are prefixed with `KoreaderAction:device_path_exists:` in the debug output.
