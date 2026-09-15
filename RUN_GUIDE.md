# QuickCite run guide

This guide covers the new `src` layout, local setup, testing, saved data, and common startup problems.

## Open the right folder

The project root is the folder containing `pyproject.toml`. The Python application itself is now under `src/citation_formatter/`, so you should not `cd` into that package folder to run the server.

For the usual QuickCite location:

```bash
cd ~/Documents/CS_Projects/Personal_Projects/QuickCite/citation-formatter
```

Confirm the folder is correct:

```bash
pwd
ls pyproject.toml
ls src/citation_formatter/app.py
```

## macOS or Linux with uv

Install the locked dependencies and start the app:

```bash
uv sync --frozen
uv run quickcite
```

Open <http://127.0.0.1:5000>. Keep the terminal open and press `Control+C` to stop the server.

Other supported start commands are:

```bash
uv run python -m citation_formatter
uv run citation-formatter
```

`uv run app.py` is not the right command now. uv interprets the first argument as a program name. `uv run quickcite` starts the console entry point declared in `pyproject.toml`.

You normally do not need to activate `.venv`. If you prefer an activated shell:

```bash
source .venv/bin/activate
python -m citation_formatter
```

## Standard Python setup

The recommended project workflow is uv because it reads the dependency metadata and lockfile. If you use ordinary Python, install the project itself from the root:

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m citation_formatter
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m citation_formatter
```

Python 3.11 or newer is required. Node.js is not needed to run the website.

## Choose another port

```bash
uv run quickcite --port 5001
```

Then open <http://127.0.0.1:5001>.

Environment variables work too:

```bash
PORT=5001 uv run quickcite
```

For a local debugging session only:

```bash
uv run quickcite --debug
```

Do not expose the Flask debugger to the public internet.

## Try the main features

1. Choose **Book**, **Journal article**, **Book chapter**, or **Web page**.
2. Enter the source information and compare APA, MLA, and Chicago.
3. Paste a DOI or ISBN and choose **Look up** if you want metadata.
4. Review the lookup dialog before choosing **Use as new source** or **Fill empty fields**.
5. Save the source. `Command+Enter` works on macOS; `Control+Enter` works elsewhere.
6. Select a saved source to edit it, or remove it and use **Undo**.
7. Filter the saved list by title, contributor, publication, year, DOI, or ISBN.
8. Copy a citation, download the selected bibliography as HTML, or print it.

## Run the checks

From the project root:

```bash
uv run python scripts/check.py
```

The same checks can be started with:

```bash
sh scripts/check.sh
```

For the full JavaScript DOM suite:

```bash
npm ci
npm test
```

The application does not need npm. The JavaScript test dependency is kept separate from the runtime.

Build the package:

```bash
uv build
```

## Check a running server

In a second terminal:

```bash
curl http://127.0.0.1:5000/api/health
curl http://127.0.0.1:5000/api/library
```

The health response should be:

```json
{"service":"quickcite","status":"ok"}
```

## Restore an existing library

The new layout keeps the database at the repository root under `data/`, not inside the Python package. Stop QuickCite before copying a database:

```bash
cp /path/to/quickcite-library-backup.sqlite3 data/library.sqlite3
uv run quickcite
```

The supplied backup is separate from the clean project archive so you can decide whether to restore your personal sources.

You can keep data outside the repository:

```bash
mkdir -p "$HOME/.quickcite"
CITATION_DATA_DIR="$HOME/.quickcite" uv run quickcite
```

Older `data/library.json` and `data/overrides.json` files are imported once when SQLite is first opened. They are not deleted or rewritten.

## DOI and ISBN lookup troubleshooting

The lookup module uses `certifi` instead of relying on a possibly incomplete system certificate path. Update the environment if needed:

```bash
uv sync --upgrade-package certifi
```

Then restart QuickCite. Do not disable HTTPS certificate verification.

To test the two services directly, use plain URLs, not Markdown link syntax:

```bash
uv run python - <<'PY'
import ssl
import urllib.request

import certifi

context = ssl.create_default_context(cafile=certifi.where())
urls = {
    "Crossref DOI": "https://api.crossref.org/works/10.1002/j.1538-7305.1948.tb01338.x",
    "Open Library ISBN": "https://openlibrary.org/api/books?bibkeys=ISBN%3A9780321973610&format=json&jscmd=data",
}

for name, url in urls.items():
    try:
        with urllib.request.urlopen(url, timeout=10, context=context) as response:
            print(name, "OK:", response.status)
    except Exception as error:
        print(name, "FAILED:", type(error).__name__, repr(error))
PY
```

If both services fail, check VPN, proxy, school or work network restrictions, firewall rules, and system time. Formatting, saving, and exporting work offline.

## Common startup problems

### `uv: command not found`

Install uv using its official instructions, reopen the terminal, and run `uv sync --frozen` again. The standard Python setup above is a fallback.

### `Failed to spawn: app.py`

Use the package command from the repository root:

```bash
uv run quickcite
```

### `No module named citation_formatter`

Run `uv sync --frozen` from the folder containing `pyproject.toml`. If you use ordinary Python, run `python -m pip install -e .` first.

### `No module named flask`

Run `uv sync --frozen`, or install the project into the active virtual environment.

### The interface looks unchanged

Hard-refresh with `Command+Shift+R` on macOS or `Control+F5` on Windows. Confirm that the server is running the new project folder, then restart it.

### The saved list is empty

Confirm that `data/library.sqlite3` exists in the project root or that `CITATION_DATA_DIR` points to the directory containing it. Copy the database somewhere safe before replacing it.
