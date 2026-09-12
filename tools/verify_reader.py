#!/usr/bin/env python3
"""Model-free reader checks; no private data, models, remote sources or deployment."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    print('+', ' '.join(map(str, args)), flush=True)
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def main():
    python = sys.executable
    with tempfile.TemporaryDirectory() as temp:
        payload = Path(temp) / 'materials-data.js'
        run([python, '-B', 'tools/build.py', '--js-output', str(payload)])
        if payload.read_bytes() != (ROOT / 'assets/materials-data.js').read_bytes():
            raise SystemExit('Generated browser data drift: run python3 tools/build.py and commit the projection.')
    run([python, '-B', '-m', 'unittest', 'tools.test_build', 'tools.test_evidence'])
    run(['node', '--test', 'tools/test_revision_study.cjs', 'tools/test_reading_search.cjs'])
    for study, runner in [('trustmem-transition-study', 'audit.py'),
                          ('experience-reuse-retrieval-study', 'study.py'),
                          ('proactive-prefix-study', 'study.py'),
                          ('mosaic-score-dependency-study', 'study.py')]:
        directory = f'research/{study}'
        run([python, '-B', f'{directory}/{runner}', '--check'])
        run([python, '-B', '-m', 'unittest', 'discover', '-s', directory, '-p', 'test_*.py'])
    result = run(['node', 'research/correction-scope-study/run.js'], capture_output=True, text=True)
    if json.loads(result.stdout) != json.loads((ROOT / 'research/correction-scope-study/results.json').read_text()):
        raise SystemExit('Correction study outputs differ from the checked results.')
    print('PASS: reader contracts, generated data and five fresh deterministic studies')


if __name__ == '__main__':
    main()
