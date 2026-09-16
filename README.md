# QuickCite

QuickCite is a focused citation workspace for building, checking, saving, and exporting APA, MLA, and Chicago citations. It is a small Flask application with a plain HTML, CSS, and JavaScript interface, so there is no frontend build step.

The project is designed to make routine citation work faster while keeping the final review in the writer's hands.

## What it does

- Formats books, journal articles, edited-book chapters, and web pages.
- Shows APA 7, MLA 9, and Chicago 17 results together.
- Generates reference entries, in-text citations, and Chicago notes.
- Looks up DOI metadata through Crossref and ISBN metadata through Open Library.
- Saves sources to a local SQLite library with editing, duplicate detection, removal, and undo.
- Filters the saved list by title, contributor, publisher, year, DOI, or ISBN.
- Copies rich text or plain text, downloads an HTML bibliography, and prints it.
- Follows the system light or dark theme, with a manual theme control.
- Adapts to phones, tablets, laptops, and wide desktop screens.

QuickCite handles common academic cases, but it is not a replacement for checking the relevant style manual. Unusual names, uncommon source types, title capitalization, and same-author/same-year citations still deserve a final review.

## Project layout

```text
citation-formatter/
├── pyproject.toml              Project metadata, dependencies, and commands
├── uv.lock                     Locked Python dependency versions
├── package.json                Optional JavaScript test commands
├── package-lock.json           Locked JavaScript test dependency
├── Procfile                    Gunicorn command for hosting platforms
├── scripts/
│   ├── check.py                Runs the complete local check suite
│   └── check.sh                Shell wrapper that works from any directory
├── src/citation_formatter/
│   ├── app.py                  Flask routes and API error handling
│   ├── cli.py                  `quickcite` command-line entry point
│   ├── citations.py            APA, MLA, Chicago, and capitalization rules
│   ├── validation.py           Request validation and normalization
│   ├── lookup.py               Crossref and Open Library requests
│   ├── library.py              SQLite storage, duplicates, and undo
│   ├── output.py               Safe HTML and plain-text output
│   ├── templates/index.html    Page structure and accessible controls
│   ├── static/                 Browser behavior, state, and responsive CSS
│   └── resources/              Bundled vocabulary for title capitalization
├── data/.gitkeep               Keeps the local-data folder in Git
├── tests/python/               Python unit tests and template checks
├── tests/js/                   JavaScript state and DOM tests
├── .github/workflows/          Continuous integration
├── RUN_GUIDE.md                Setup and troubleshooting walkthrough
├── PROJECT_REVIEW.md           Code, UI, and product assessment
├── ROADMAP.md                  Prioritized future work
└── CHANGELOG.md                Release history
```

The `src` layout prevents the application from accidentally importing loose files from the repository root. Runtime modules stay together, while tests, scripts, documentation, and local data have clear homes.

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) for the recommended setup
- Node.js 20 or newer only for the optional JavaScript DOM tests

The application itself does not need Node.js, npm, a database server, or a frontend build tool. SQLite is included with Python.

## Quick start with uv

From the project root, the folder containing `pyproject.toml`:

```bash
uv sync --frozen
uv run quickcite
```

Open <http://127.0.0.1:5000>. Leave the terminal running while using QuickCite and press `Control+C` to stop it.

The equivalent module command is:

```bash
uv run python -m citation_formatter
```

The older `citation-formatter` console command remains available as an alias:

```bash
uv run citation-formatter
```

If port 5000 is busy:

```bash
uv run quickcite --port 5001
```

You normally do not need to activate `.venv` when using uv. An activated shell also works:

```bash
source .venv/bin/activate
python -m citation_formatter
```

## Dependencies

The dependencies declared in `pyproject.toml` are:

| Package | Role |
|---|---|
| Flask | Web server, routes, templates, and JSON responses |
| certifi | Certificate-authority bundle for DOI and ISBN HTTPS requests |
| Gunicorn | Production WSGI server on Linux hosts |

Flask installs its normal support packages: Werkzeug, Jinja2, MarkupSafe, Click, ItsDangerous, and Blinker. Gunicorn uses Packaging. uv resolves and records these versions in `uv.lock`.

JavaScript tests use `jsdom` 26.1.0 as an npm development dependency. It is not loaded by the website.

## Typical workflow

1. Choose Book, Journal article, Book chapter, or Web page.
2. Enter the details you know and compare the three live previews.
3. Optionally enter a DOI or ISBN, choose **Look up**, and review the imported metadata.
4. Choose **Save to list**, or press `Command+Enter` on macOS and `Control+Enter` elsewhere.
5. Filter, edit, copy, download, or print the saved bibliography.

Lookup results are reviewed before they touch the form. Imported metadata is never silently saved.

## Development commands

Run Python tests, citation doctests, JavaScript syntax checks, and available JavaScript tests:

```bash
uv run python scripts/check.py
```

The shell wrapper is useful when you are not already in the project folder:

```bash
sh scripts/check.sh
```

Install the optional DOM-test dependency and run the full JavaScript suite:

```bash
npm ci
npm test
```

Build the Python wheel and source archive:

```bash
uv build
```

## Data and privacy

When started from the project root, QuickCite stores saved sources in `data/library.sqlite3`. The database is ignored by Git and is not included in release archives. If an installed copy is started outside a project containing `pyproject.toml`, it falls back to `~/.quickcite`.

Formatting happens locally. DOI and ISBN lookup sends only the entered identifier to Crossref or Open Library. The current draft stays in the browser's session storage.

Older `data/library.json` and `data/overrides.json` files are imported once when a new SQLite database is created. The original JSON files remain untouched.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `HOST` | `127.0.0.1` | Development-server bind address |
| `PORT` | `5000` | Development-server port |
| `CITATION_DATA_DIR` | Project `data/` when run from its root, otherwise `~/.quickcite` | SQLite location |
| `CITATION_USER_AGENT` | `QuickCite/0.4.1 (personal citation tool)` | Optional contact-aware lookup user agent |

Example:

```bash
CITATION_DATA_DIR="$HOME/.quickcite" uv run quickcite
```

## Deployment notes

The included `Procfile` runs:

```text
gunicorn --bind 0.0.0.0:$PORT citation_formatter.app:app
```

For a personal deployment, attach persistent storage and set `CITATION_DATA_DIR` to that location. Use `/api/health` for a health check.

The current application is suitable for a private personal deployment, not an open multi-user service. It does not yet provide accounts, per-user data isolation, rate limiting, or administrative controls.

## Publishing checklist

Before pushing the repository publicly:

1. Run `uv sync --frozen`, `npm ci`, `uv run python scripts/check.py`, and `uv build`.
2. Confirm that no `data/library.sqlite3` file is staged.
3. Review the two inherited vocabulary files in `src/citation_formatter/resources/`. Their original source and license were not included in the supplied project.
4. Choose a project license only after confirming that every bundled data file can be redistributed under it.

No license is granted by this repository as currently packaged. That is intentional until the vocabulary-file provenance is resolved.

## Further reading

- [RUN_GUIDE.md](RUN_GUIDE.md) for exact setup, migration, lookup troubleshooting, and saved-data backup steps.
- [CHANGELOG.md](CHANGELOG.md) for completed work.
