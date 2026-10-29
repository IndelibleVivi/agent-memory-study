#!/usr/bin/env python3
"""Local reader checks; synthetic classifier fitting, no pretrained models or remote services."""
import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true", help="Build a fresh artifact and run public/local browser acceptance")
    parser.add_argument("--site-root", type=Path, default=ROOT / "dist/site")
    parser.add_argument("--evidence-root", type=Path, default=ROOT / "dist/verification")
    args = parser.parse_args()
    python = sys.executable
    run([python, '-B', 'tools/content.py', '--check'])
    run([python, '-B', '-m', 'unittest', 'tools.test_content', 'tools.test_author', 'tools.test_public_corpus'])
    run([python, '-B', '-m', 'unittest', 'tools.test_build', 'tools.test_evidence',
         'tools.test_practice_data'])
    run([python, '-B', '-m', 'unittest', 'discover', '-s', 'schemas', '-p', 'test_*.py'])
    run([python, '-B', '-m', 'unittest', 'discover', '-s', 'services/local', '-t', '.', '-p', 'test_*.py'])
    run(['npm', '--prefix', 'apps/reader', 'run', 'typecheck'])
    run(['npm', '--prefix', 'apps/reader', 'test'])
    run(['node', '--test', 'packages/research-core/test/core.test.js'])
    run([python, '-B', '-m', 'unittest', 'discover', '-s',
         'research/multilingual-use-policy', '-p', 'test_casebook.py'])
    run([python, '-B', '-m', 'unittest', 'discover', '-s',
         'research/representation-use-study', '-p', 'test_*.py'])
    run([python, '-B', '-m', 'unittest', 'discover', '-s',
         'research/revision-propagation-study', '-p', 'test_*.py'])
    run([python, '-B', 'research/revision-propagation-study/study.py', 'check-sample'])
    run(['node', '--test', 'tools/test_research_map.cjs', 'tools/test_research_sculpture.cjs', 'tools/test_study_packets.cjs', 'tools/test_study_desk.cjs', 'tools/test_index_study.cjs', 'tools/test_export_study.cjs', 'tools/test_revision_study.cjs',
         'tools/test_reading_search.cjs', 'tools/test_practice.cjs', 'tools/test_seo.cjs'])
    for study, runner in [('trustmem-transition-study', 'audit.py'),
                          ('experience-reuse-retrieval-study', 'study.py'),
                          ('proactive-prefix-study', 'study.py'),
                          ('mosaic-score-dependency-study', 'study.py'),
                          ('task-relative-sufficiency', 'study.py'),
                          ('observation-contract-study', 'study.py'),
                          ('conditional-contribution-study', 'study.py'),
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
    if args.browser:
        # An unselected file beside an approved research owner is not public.
        # This synthetic probe rejects broad directory copies in the actual build.
        with tempfile.NamedTemporaryFile(mode='w', prefix='unselected-', suffix='.json', dir=ROOT / 'research/observation-contract-study') as probe:
            probe.write('{"synthetic":"AMS_UNSELECTED_BUILD_PROBE"}'); probe.flush()
            run([python, '-B', 'tools/seo_build.py', '--output', str(args.site_root)])
            if (args.site_root / Path(probe.name).relative_to(ROOT)).exists():
                raise SystemExit('The public artifact contains unselected research data.')
        for script, folder in [('test_reader_browser.py', 'public'), ('test_static_reader.py', 'static'), ('test_local_reader.py', 'local')]:
            run([python, '-B', 'tools/' + script, '--site-root', str(args.site_root), '--output-dir', str(args.evidence_root / folder)])
        run([python, '-B', 'tools/test_casebook_browser.py', '--output-dir', str(args.evidence_root / 'casebook')])
    print('PASS: reader contracts, generated data, source-aware workspaces/public collections, shared references/author drafts, bound reviews, offline representation/revision controls, native finite/retrieval studies, synthetic classifier refits and checked AgeMem/C2C/Jev receipts')


if __name__ == '__main__':
    main()
