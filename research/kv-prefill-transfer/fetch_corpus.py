#!/usr/bin/env python3
"""Freeze a small public FineWeb-Edu rows snapshot outside the Git checkout."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

DATASET = 'HuggingFaceFW/fineweb-edu'
CONFIG = 'sample-10BT'
REVISION = '87f09149ef4734204d70ed1d046ddc9ca3f2b8f9'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    dest = args.out_dir.resolve()
    checkout = Path(__file__).resolve().parents[2]
    if dest.is_relative_to(checkout):
        parser.error('Raw corpus belongs outside the Git checkout.')
    if dest.exists() and any(dest.iterdir()):
        parser.error('Use an empty snapshot directory; preserve prior raw inputs.')
    dest.mkdir(parents=True, exist_ok=True)
    records, pages = [], []
    for offset in (0, 100):
        url = 'https://datasets-server.huggingface.co/rows?' + urlencode(
            dict(dataset=DATASET, config=CONFIG, split='train', offset=offset, length=100))
        with urlopen(url, timeout=60) as response:
            raw = response.read()
            revision = response.headers.get('x-revision')
            fetched_at = datetime.now(timezone.utc).isoformat()
        filename = f'rows-{offset:05}.json'
        (dest / filename).write_bytes(raw)
        if revision != REVISION:
            raise RuntimeError(f'Rows API revision {revision!r} differs from pinned {REVISION}; raw response retained.')
        payload = json.loads(raw)
        rows = payload['rows']
        if payload.get('partial') or len(rows) != 100:
            raise RuntimeError('Expected a complete 100-row response; raw response retained.')
        if any(row['truncated_cells'] for row in rows):
            raise RuntimeError('Rows API truncated cells; do not treat these as complete documents.')
        for item in rows:
            row = item['row']
            records.append(dict(id=row['id'], text=row['text'], source_url=row['url'],
                                row_index=item['row_idx'], dataset=DATASET,
                                dataset_config=CONFIG, dataset_revision=REVISION))
        pages.append(dict(file=filename, url=url, revision=revision, fetched_at=fetched_at,
                          sha256=hashlib.sha256(raw).hexdigest(), rows=len(rows)))
    content = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in records).encode('utf-8')
    (dest / 'documents.jsonl').write_bytes(content)
    manifest = dict(schema_version=1, dataset=DATASET, config=CONFIG, revision=REVISION,
                    snapshot_method='official rows API; x-revision checked; no truncated cells',
                    document_candidates=len(records), pages=pages,
                    jsonl_sha256=hashlib.sha256(content).hexdigest(),
                    split_status='unassigned; runner.prepare filters length and splits whole documents',
                    dataset_card='https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu',
                    license='ODC-By-1.0; also subject to upstream CommonCrawl terms')
    (dest / 'corpus-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k:manifest[k] for k in ['dataset','revision','document_candidates','jsonl_sha256']}, indent=2))


if __name__ == '__main__':
    main()
