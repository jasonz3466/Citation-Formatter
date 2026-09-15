# Changelog

## 0.4.1

### Interface refresh

- Increased type sizes, control heights, spacing, and tap targets for easier reading on larger screens and touch devices.
- Replaced the green palette with warm paper, indigo actions, coral accents, and amber guidance that stay legible in light and dark themes.
- Rebalanced the source editor, citation preview, saved list, and lookup review dialog so each area has clearer hierarchy without adding visual clutter.
- Added a single-column source-type layout on phones and kept the DOI / ISBN entry area flat and free of a heavy outside outline.

## 0.4.0

### Project structure

- Adopted a standard `src/citation_formatter/` Python package layout.
- Moved tests to `tests/python/` and `tests/js/`.
- Moved maintenance commands to `scripts/` and made the shell wrapper project-root aware.
- Separated shipped capitalization resources from user-owned SQLite data.
- Added `quickcite` and `python -m citation_formatter` entry points, while keeping the old console name as an alias.
- Added a real build backend and verified wheel and source-archive creation.
- Removed the duplicate `requirements.txt`; `pyproject.toml` is now the canonical dependency file.

### Documentation

- Rewrote the README and run guide for the `src` layout, uv commands, package installation, testing, data backup, and deployment.
- Added a structure-focused project review and kept the prioritized roadmap.

## 0.3.0

### Interface

- Reworked the page into a quieter, more focused editor instead of a stack of decorative cards.
- Removed the forced 125% page zoom and the heavy outline around DOI/ISBN lookup.
- Added purpose-built phone, tablet, laptop, and wide-desktop layouts.
- Simplified headings, labels, navigation, buttons, spacing, radii, shadows, and status text.
- Added balanced light and dark themes that follow the system by default.
- Improved touch targets, keyboard focus, reduced-motion support, print styles, and forced-color behavior.
- Added saved-source filtering and a `Command+Enter` / `Control+Enter` save shortcut.

### Reliability and security

- Added `certifi` to fix Python installations that cannot find a usable HTTPS certificate bundle for DOI and ISBN lookup.
- Added a health endpoint at `/api/health`.
- Added browser security headers and disabled caching on API responses.
- Added upstream-aware lookup status codes for unavailable, rate-limited, and timed-out services.
- Built saved-source controls with DOM APIs so quote characters in source titles cannot break button attributes.
- Added an SQLite fingerprint index for faster duplicate checks as the library grows.
- Corrected the exported bibliography document structure.

### Validation

- Added responsive-layout, theme, lookup, CLI, API, persistence, and DOM regressions.

## 0.2.0

### Citation accuracy

- Added partial publication dates and organization or unknown-author modes.
- Improved personal suffixes, edited books, APA locators, MLA page ranges, and Chicago notes.
- Added safer output handling for literal punctuation and internal formatting markup.
- Added automatic and preserve-as-entered capitalization modes.

### Saving and export

- Replaced direct JSON writes with transactional SQLite storage.
- Added one-time JSON migration, editing, duplicate detection, removal, and undo.
- Added formatted and plain-text copy modes, HTML bibliography download, and printing.
- Added a metadata review dialog before applying DOI or ISBN results.

## Versioning note

QuickCite does not yet promise a stable public API. Minor releases may adjust request or response details while the local web interface remains the primary supported workflow.
