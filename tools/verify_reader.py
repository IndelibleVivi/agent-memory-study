#!/usr/bin/env python3
"""Local reader checks; synthetic classifier fitting, no pretrained models or remote services."""
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
    run([python, '-B', 'tools/content.py', '--check'])
    run([python, '-B', '-m', 'unittest', 'tools.test_content', 'tools.test_author'])
    run([python, '-B', '-m', 'unittest', 'tools.test_build', 'tools.test_evidence',
         'tools.test_practice_data'])
    run([python, '-B', '-m', 'unittest', 'discover', '-s',
         'research/multilingual-use-policy', '-p', 'test_casebook.py'])
    run([python, '-B', '-m', 'unittest', 'discover', '-s',
         'research/representation-use-study', '-p', 'test_*.py'])
    run(['node', '--test', 'tools/test_research_map.cjs', 'tools/test_research_sculpture.cjs', 'tools/test_study_packets.cjs', 'tools/test_study_desk.cjs', 'tools/test_revision_study.cjs',
         'tools/test_reading_search.cjs', 'tools/test_practice.cjs', 'tools/test_seo.cjs'])
    for study, runner in [('trustmem-transition-study', 'audit.py'),
                          ('experience-reuse-retrieval-study', 'study.py'),
                          ('proactive-prefix-study', 'study.py'),
                          ('mosaic-score-dependency-study', 'study.py'),
                          ('decision-learning-study', 'study.py')]:
        directory = f'research/{study}'
        run([python, '-B', f'{directory}/{runner}', '--check'])
        run([python, '-B', '-m', 'unittest', 'discover', '-s', directory, '-p', 'test_*.py'])
    result = run(['node', 'research/correction-scope-study/run.js'], capture_output=True, text=True)
    if json.loads(result.stdout) != json.loads((ROOT / 'research/correction-scope-study/results.json').read_text()):
        raise SystemExit('Correction study outputs differ from the checked results.')
    run([python, '-B', 'research/agemem-reward-observation-audit/audit.py', '--verify-checked'])
    run([python, '-B', 'research/c2c-cache-retraction-study/study.py', '--verify-checked'])
    run([python, '-B', '-m', 'unittest', 'discover', '-s', 'research/c2c-cache-retraction-study', '-p', 'test_*.py'])
    run([python, '-B', 'research/jev-memory-contract-study/study.py', '--verify-checked'])
    run([python, '-B', '-m', 'unittest', 'discover', '-s', 'research/jev-memory-contract-study', '-p', 'test_*.py'])
    print('PASS: reader contracts, generated data, bound reviews, offline representation controls, five deterministic studies, synthetic classifier refits and checked AgeMem/C2C/Jev receipts')


if __name__ == '__main__':
    main()
