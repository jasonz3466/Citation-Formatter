"""Run QuickCite's Python and JavaScript checks from one command."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'src' / 'citation_formatter'


def run(*command):
    environment = os.environ.copy()
    source_path = str(ROOT / 'src')
    environment['PYTHONPATH'] = os.pathsep.join(
        item for item in (source_path, environment.get('PYTHONPATH', '')) if item
    )
    subprocess.run(command, cwd=ROOT, check=True, env=environment)


if __name__ == '__main__':
    try:
        print('Running Python tests and doctests...', flush=True)
        run(
            sys.executable,
            '-m',
            'unittest',
            'discover',
            '-s',
            'tests/python',
            '-v',
        )
        run(sys.executable, '-m', 'citation_formatter.citations')
        node = shutil.which('node')
        if node:
            run(node, '--check', str(PACKAGE / 'static' / 'script.js'))
            run(node, '--check', str(PACKAGE / 'static' / 'state.js'))
            if (ROOT / 'node_modules/jsdom/package.json').exists():
                run(node, '--test', 'tests/js/state.test.cjs', 'tests/js/ui.test.cjs')
            else:
                run(node, '--test', 'tests/js/state.test.cjs')
                print('Optional DOM tests skipped. Run npm ci to install their test dependency.')
        else:
            print('JavaScript checks skipped because Node is not installed. The app does not need Node to run.')
        print('All available checks passed.')
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode)
