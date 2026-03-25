# TODO

## 🚀 High Priority (0.8.x Release)
- [x] Fix `apsw.TooBigError` for books with 900+ highlights [#114](https://github.com/kyxap/koreader-calibre-plugin/issues/114)
- [x] Implement robust UUID matching: Parse `calibre:` prefix in sidecar identifiers to fix mismatches [#115](https://github.com/kyxap/koreader-calibre-plugin/issues/115), [#99](https://github.com/kyxap/koreader-calibre-plugin/issues/99)
- [x] Add support for `POCKETBOOK_IMPROVED` driver [#63](https://github.com/kyxap/koreader-calibre-plugin/issues/63)
- [x] Fix sidecar write regression for USB/Folder devices (`_io.BytesIO` error) [#143](https://github.com/kyxap/koreader-calibre-plugin/issues/143)

## 🐛 Bug Fixes
- [x] Fix MD5 computation for Kobo devices using custom folders [#98](https://github.com/kyxap/koreader-calibre-plugin/issues/98)
- [x] Fix sidecar directory resolution in Docker (linuxserver/calibre) environments [#73](https://github.com/kyxap/koreader-calibre-plugin/issues/73)
- [x] Resolve Windows "Access Denied" error for Kobo sidecar folder creation [#68](https://github.com/kyxap/koreader-calibre-plugin/issues/68)

## ✨ Enhancements & Features
- [ ] Add support for highlights and bookmarks into the native `annotations` table in calibre's `metadata.db` [#95](https://github.com/kyxap/koreader-calibre-plugin/issues/95)
- [ ] **Architectural Change**: Stop converting Lua to JSON for storage. Store raw Lua in the "Raw Sidecar" column to prevent lossy conversions and fix sync-back bugs [#65](https://github.com/kyxap/koreader-calibre-plugin/issues/65), [#58](https://github.com/kyxap/koreader-calibre-plugin/issues/58).
- [ ] Implement metadata merging (union) instead of overwriting for multi-device sync [#76](https://github.com/kyxap/koreader-calibre-plugin/issues/76)
- [ ] Support custom sidecar locations (global .sdr folder) [#57](https://github.com/kyxap/koreader-calibre-plugin/issues/57)
- [ ] Implement 2-way wireless sidecar modification [#100](https://github.com/kyxap/koreader-calibre-plugin/issues/100)
- [ ] Add template support for customizing the appearance of imported highlights [#1](https://github.com/kyxap/koreader-calibre-plugin/issues/1)

## 🛠 Project Health & Maintenance
- [ ] Fix remaining pylint errors and warnings (currently 9.59/10)
- [ ] Standardize Python code style with Black/Ruff [#81](https://github.com/kyxap/koreader-calibre-plugin/issues/81)
- [ ] Add `last_page` support for PDFs
- [ ] Investigate `calibre.devices.usbms.cli.CLI.list()` for better sidecar discovery

## ✅ Completed
- [x] Add an `.editorconfig` and `.pylintrc` to define code layout
- [x] Add support for highlights and bookmarks into a metadata field
- [x] Make the warning about synced metadata more informative
- [x] Add support for `KINDLE2` devices
- [x] ~~Add support for `MTP_DEVICE` devices~~
- [x] ~~Add support for multiple storages (i.e. SD cards) for `MTP_DEVICES`~~
