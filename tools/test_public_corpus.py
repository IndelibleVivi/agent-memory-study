"""Public identity is content-bound and old reference snapshots remain available."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools import content, content_public
from schemas.validate import canonical_object_bytes, validate_graph


class PublicCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = content.compile_content()

    def test_every_manifest_address_resolves_to_a_valid_core_snapshot(self):
        manifest = copy.deepcopy(self.data['public_manifest'])
        files = content_public.material_entity_files(self.data, manifest)
        records = [files[path] for path in manifest['record_shards']]
        validate_graph(records)
        for item in manifest['objects']:
            self.assertEqual({k: files[item['revision_shard']][k] for k in ('kind','id','revision')},
                             {k: item[k] for k in ('kind','id','revision')})
        self.assertNotIn('bodyMarkdown', json.dumps(manifest))
        self.assertTrue(any(r['to'].startswith('material/') for r in manifest['graphs']['references']))

    def test_body_edit_changes_identity_but_rendering_does_not(self):
        item = copy.deepcopy(self.data['studies'][0])
        old = content_public._current_ref(item, 'study')
        item['bodyHtml'] += '<p>renderer decoration</p>'
        self.assertEqual(content_public._current_ref(item, 'study'), old)
        item['bodyMarkdown'] += '\nA revised authored statement.\n'
        self.assertNotEqual(content_public._current_ref(item, 'study'), old)

    def test_build_retains_old_snapshots_and_refuses_revision_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content.write_public_corpus(self.data, root)
            old = json.loads((root/'data/public-corpus.manifest.json').read_text())
            changed = copy.deepcopy(self.data)
            changed['studies'][0]['bodyMarkdown'] += '\nRevised after the first reading.\n'
            changed['public_manifest'] = content_public.build(changed)
            content.write_public_corpus(changed, root)
            new = json.loads((root/'data/public-corpus.manifest.json').read_text())
            self.assertEqual(len(new['record_shards']), len(old['record_shards']) + 1)
            target = root/new['record_shards'][0]
            target.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'immutable public revision changed'):
                content.write_public_corpus(changed, root)

    def test_history_does_not_publish_an_unlisted_private_file(self):
        from services.local.records import record
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content.write_public_corpus(self.data, root)
            private = record('thread', {'title':'PRIVATE_HISTORY_CANARY','byline':'Synthetic','status':'open','payload':{}})
            relative = 'data/corpus/revisions/thread/private/unselected.json'
            target = root/relative; target.parent.mkdir(parents=True); target.write_text(json.dumps(private))
            content.write_public_corpus(self.data, root)
            manifest_path = root/'data/public-corpus.manifest.json'
            manifest = json.loads(manifest_path.read_text())
            self.assertNotIn(relative, manifest['record_shards'])
            manifest['record_shards'].append(relative); manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'private or unsupported'):
                content.write_public_corpus(self.data, root)

    def test_numeric_and_unicode_canonical_contract(self):
        import subprocess
        value = {'\U0001f331': '🌱', '\ue000': -0.0, 'number': 1.0}
        observed = subprocess.check_output(['node','--input-type=module','-e',
            "import {canonicalValue} from './packages/research-core/canonical.js';process.stdout.write(canonicalValue(JSON.parse(process.argv[1])))", json.dumps(value)],cwd=content.ROOT)
        self.assertEqual(canonical_object_bytes(value), observed)
        with self.assertRaisesRegex(ValueError, 'safe integers'):
            canonical_object_bytes({'number':2**53})


if __name__ == '__main__': unittest.main()
