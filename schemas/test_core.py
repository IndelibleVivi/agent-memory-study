"""Contract-level checks independent of the current public corpus projection."""

from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from schemas import validate

ROOT = Path(__file__).resolve().parents[1]


def work_record() -> dict:
    record = {
        "schema": "ams-core/2", "kind": "source_work", "id": "work:fixture",
        "revision": "rev:work-1", "state_revision": "rev:work-1",
        "title": "Synthetic work", "work_type": "mathematics",
        "authors": ["Fixture Author"], "year": 2026, "short_author": "Fixture",
        "identifiers": [], "manifestations": [], "aliases": ["fixture"],
        "visibility": "public",
    }
    record["content_digest"] = validate.content_digest(
        record, validate.content_fields(record)
    )
    return record


def revision_record() -> dict:
    record = {
        "schema": "ams-core/2", "kind": "source_revision", "id": "work:fixture",
        "revision": "rev:source-1", "state_revision": "rev:source-1",
        "work_ref": {"kind": "source_work", "id": "work:fixture", "revision": "rev:work-1"},
        "identity": {
            "mode": "observed-snapshot", "observed_at": None,
            "source_locator": "https://example.org/fixture",
            "observation_basis": "Original synthetic public fixture.",
            "publisher_version_known": False, "snapshot_captured": False,
        },
    }
    record["content_digest"] = validate.content_digest(
        record, validate.content_fields(record)
    )
    return record


def note_record() -> dict:
    record = {
        "schema": "ams-core/2", "kind": "source_note", "id": "note:fixture",
        "revision": "rev:note-1", "state_revision": "rev:note-1",
        "alias": "fixture", "title": "Fixture reading",
        "work_ref": {"kind": "source_work", "id": "work:fixture", "revision": "rev:work-1"},
        "source_revision_ref": {"kind": "source_revision", "id": "work:fixture", "revision": "rev:source-1"},
        "byline": "Fixture reader", "date": "2026-10-29",
        "intro": "A note about the synthetic work.", "note_depth": "skim",
        "reading_scope": "Abstract only.", "navigation": {}, "payload": {},
    }
    record["content_digest"] = validate.content_digest(
        record, validate.content_fields(record)
    )
    return record


class CoreContractTests(unittest.TestCase):
    def test_historical_observations_and_analyses_need_fixed_evidence_not_a_fabricated_run(self):
        from services.local.records import record, ref
        artifact = record('artifact', {'media_type':'application/json', 'byte_length':1,
            'artifact_digest':'sha256:'+'0'*64, 'storage':{'kind':'blob','locator':'sha256:'+'0'*64},
            'role':'receipt', 'visibility':'private', 'obtained_at':'2026-10-30T00:00:00Z'})
        observation = record('observation', {'scope':'historical receipt only', 'statement':'Early tensors were not saved.', 'basis_refs':[ref(artifact)]})
        analysis = record('analysis', {'run_refs':[], 'observation_refs':[ref(observation)], 'method':'Inspect saved receipt fields', 'scope':'No new execution', 'result':'Missing raw remains unresolved.'})
        validate.validate_graph([artifact, observation, analysis])
        for kind, fields in [('observation', {'scope':'none','statement':'unbound','basis_refs':[]}),
                      ('analysis', {'run_refs':[],'method':'none','scope':'none','result':'unbound'}),
                      ('analysis', {'run_refs':[],'observation_refs':[ref(artifact)],'method':'wrong kind','scope':'none','result':'unbound'}),
                      ('observation', {'run_ref':ref(artifact),'basis_refs':[],'scope':'wrong kind','statement':'not a run'})]:
            with self.assertRaises(validate.ContractError): record(kind, fields)
        with self.assertRaisesRegex(validate.ContractError, 'dangling'):
            validate.validate_graph([observation, analysis])

    def test_all_record_types_are_structurally_covered(self):
        expected = {
            "capture", "source_work", "source_revision", "source_note", "artifact",
            "extraction", "read_activity", "excerpt", "entry", "claim_revision",
            "thread", "session", "relation_proposal", "evidence_relation",
            "support_bundle", "observation", "design", "run", "analysis", "changeset",
            "publication_manifest",
        }
        definitions = validate.SCHEMA["$defs"]
        definition_names = {
            "claim_revision": "ClaimRevision", "changeset": "ChangeSet",
            "evidence_relation": "EvidenceRelation", "publication_manifest": "PublicationManifest",
            "read_activity": "ReadActivity", "relation_proposal": "RelationProposal",
            "source_note": "SourceNote", "source_revision": "SourceRevision",
            "source_work": "SourceWork", "support_bundle": "SupportBundle",
        }
        for kind in expected:
            definition = definition_names.get(kind, kind.title().replace("_", ""))
            self.assertIn(definition, definitions)
            self.assertEqual(definitions[definition]["properties"]["kind"]["const"], kind)

    def test_canonical_vectors_match_node_implementation(self):
        vectors = json.loads((ROOT / "schemas" / "canonical-vectors.json").read_text())
        script = (
            "import fs from 'node:fs';"
            "import {canonicalValue} from './packages/research-core/canonical.js';"
            "import {createHash} from 'node:crypto';"
            "const v=JSON.parse(fs.readFileSync('schemas/canonical-vectors.json','utf8'));"
            "process.stdout.write(JSON.stringify(v.vectors.map(x=>{"
            "const bytes=canonicalValue(x.value);"
            "return {name:x.name,bytes,sha256:createHash('sha256').update(bytes).digest('hex')};})));"
        )
        node = json.loads(subprocess.check_output(["node", "--input-type=module", "-e", script], cwd=ROOT))
        self.assertEqual(node, [
            {key: vector[key] for key in ("name", "bytes", "sha256")}
            for vector in vectors["vectors"]
        ])

    def test_work_revision_and_note_are_distinct_pinned_identities(self):
        work, revision, note = work_record(), revision_record(), note_record()
        for record in (work, revision, note):
            validate.validate_entity(record)
        self.assertNotEqual(work["revision"], revision["revision"])
        self.assertNotEqual(note["work_ref"], note["source_revision_ref"])
        with self.assertRaisesRegex(validate.ContractError, "canonical fields"):
            validate.check_digest({**work, "content_digest": {
                **work["content_digest"], "fields": ["title", "private_note"]}})

    def test_same_revision_changed_payload_is_checked_by_semantic_index(self):
        first = work_record()
        second = copy.deepcopy(first)
        second["title"] = "Changed without a revision"
        first_digest = validate.content_digest(first, validate.content_fields(first))
        second_digest = validate.content_digest(second, validate.content_fields(second))
        self.assertNotEqual(first_digest, second_digest)

    def test_command_create_cannot_have_base_and_update_requires_one(self):
        record = work_record()
        command = {
            "schema": "ams-command/1", "kind": "command",
            "command_id": "command:fixture", "idempotency_key": "fixture/create",
            "operation": "create", "target": {"kind": "source_work", "id": "work:fixture"},
            "actor": {"kind": "human", "id": "actor:fixture"}, "record": record,
        }
        validate.validate_command(command)
        invalid = copy.deepcopy(command)
        invalid["expected_revision"] = "rev:prior"
        with self.assertRaisesRegex(validate.ContractError, "schema:Command"):
            validate.validate_command(invalid)
        update = copy.deepcopy(command)
        update["operation"] = "update"
        update["expected_revision"] = "rev:prior"
        update["record"]["revision"] = "rev:work-2"
        update["record"]["state_revision"] = "rev:work-2"
        update["record"]["content_digest"] = validate.content_digest(
            update["record"], validate.content_fields(update["record"])
        )
        validate.validate_command(update)

    def test_draft_changes_have_base(self):
        record = work_record()
        changeset = {
            "schema": "ams-core/2", "kind": "changeset", "id": "change:fixture",
            "revision": "rev:change-1", "state_revision": "rev:change-1",
            "review_state": "reviewing", "application_state": "not-applied",
            "items": [{
                "id": "item:one", "target": "canonical-draft",
                "base_ref": validate.record_ref(record), "change": "Draft correction.",
                "review_state": "proposed", "application_state": "not-applied",
            }],
            "publication_refs": [],
        }
        changeset["content_digest"] = validate.content_digest(
            changeset, validate.content_fields(changeset)
        )
        validate.validate_entity(changeset)
        invalid = copy.deepcopy(changeset)
        invalid["items"][0].pop("base_ref")
        with self.assertRaisesRegex(validate.ContractError, "schema:ChangeSet"):
            validate.validate_entity(invalid)

    def test_unnamed_private_thread_is_valid_and_digestable(self):
        thread = {
            "schema": "ams-core/2", "kind": "thread", "id": "thread:unnamed",
            "revision": "rev:thread-1", "state_revision": "rev:thread-1",
            "title": "", "byline": "Local researcher", "status": "open",
            "payload": {"question": "An unfinished direction."},
        }
        thread["content_digest"] = validate.content_digest(thread)
        validate.validate_entity(thread)
        self.assertIn("title", validate.content_fields(thread))

    def test_python_and_generated_js_field_maps_are_identical(self):
        validate.assert_generated_field_parity()

    def test_command_rejects_revision_identity_digest_and_base_mutations(self):
        item = work_record()
        command = {
            "schema": "ams-command/1", "kind": "command",
            "command_id": "command:create", "idempotency_key": "create",
            "operation": "create", "target": {"kind": item["kind"], "id": item["id"]},
            "actor": {"kind": "human", "id": "actor:fixture"}, "record": item,
        }
        validate.validate_command(command)
        for mutation in (
            lambda value: value["record"].update(state_revision="rev:other"),
            lambda value: value["record"].update(content_digest={
                **value["record"]["content_digest"], "value": "0" * 64}),
            lambda value: value.update(target={"kind": "source_work", "id": "work:other"}),
        ):
            invalid = copy.deepcopy(command)
            mutation(invalid)
            with self.subTest(mutation=mutation), self.assertRaises(validate.ContractError):
                validate.validate_command(invalid)

    def test_graph_rejects_cross_kind_revision_payload_reuse(self):
        work = work_record()
        repeated = {
            "schema": "ams-core/2", "kind": "entry", "id": "entry:reused",
            "revision": work["revision"], "state_revision": work["revision"],
            "entry_type": "learning-note", "title": "Reused revision",
            "byline": "Fixture", "date": "2026-10-29", "intro": "Fixture body",
            "body_file": "entries/fixture.md", "payload": {},
        }
        repeated["content_digest"] = validate.content_digest(repeated)
        with self.assertRaisesRegex(validate.ContractError, "same revision"):
            validate.validate_graph([work, repeated])

    def test_graph_rejects_unbound_representation_and_selector_mismatch(self):
        source_work = work_record()
        source_revision = revision_record()
        source_work["content_digest"] = validate.content_digest(source_work)
        source_revision["content_digest"] = validate.content_digest(source_revision)
        artifact = {
            "schema": "ams-core/2", "kind": "artifact", "id": "artifact:representation",
            "revision": "rev:artifact-1", "state_revision": "rev:artifact-1",
            "media_type": "text/plain", "byte_length": 4,
            "artifact_digest": "sha256:" + "0" * 64,
            "storage": {"kind": "blob", "locator": "sha256:" + "0" * 64},
            "role": "extracted-text", "visibility": "private",
            "source_revision_ref": validate.record_ref(source_revision),
            "obtained_at": "2026-10-29T00:00:00Z",
        }
        artifact["content_digest"] = validate.content_digest(artifact)
        other = copy.deepcopy(source_revision)
        other.update({"id": "work:other", "revision": "rev:other-1",
                      "state_revision": "rev:other-1"})
        other_work = copy.deepcopy(source_work)
        other_work.update({"id": "work:other", "revision": "rev:other-work",
                           "state_revision": "rev:other-work"})
        other["work_ref"] = validate.record_ref(other_work)
        other_work["content_digest"] = validate.content_digest(other_work)
        other["content_digest"] = validate.content_digest(other)
        excerpt = {
            "schema": "ams-core/2", "kind": "excerpt", "id": "excerpt:wrong",
            "revision": "rev:excerpt-1", "state_revision": "rev:excerpt-1",
            "target_ref": validate.record_ref(other),
            "representation_ref": validate.record_ref(artifact),
            "selector": "TextQuoteSelector(exact=fixture)",
        }
        excerpt["content_digest"] = validate.content_digest(excerpt)
        with self.assertRaisesRegex(validate.ContractError, "not bound"):
            validate.validate_graph([source_work, source_revision, other_work, other, artifact, excerpt])

    def test_graph_rejects_scope_and_proposal_drift(self):
        item = work_record()
        target = copy.deepcopy(item)
        target.update({"id": "work:target", "revision": "rev:target",
                       "state_revision": "rev:target"})
        target["content_digest"] = validate.content_digest(target)
        proposal = {
            "schema": "ams-core/2", "kind": "relation_proposal",
            "id": "proposal:one", "revision": "rev:proposal-1",
            "state_revision": "rev:proposal-1",
            "from_ref": validate.record_ref(item), "to_ref": validate.record_ref(target),
            "relation": "supports", "scope": "fixture scope",
            "scope_binding": "Both statements refer to the same synthetic fixture.",
            "locator": "fixture", "rationale": "Synthetic relation.",
            "generated_by": {"kind": "agent", "id": "actor:fixture"},
            "method_version": "test/1", "status": "proposal",
        }
        proposal["content_digest"] = validate.content_digest(proposal)
        accepted = copy.deepcopy(proposal)
        accepted.update({"kind": "evidence_relation", "id": "relation:one",
                         "revision": "rev:relation-1", "state_revision": "rev:relation-1",
                         "proposal_ref": validate.record_ref(proposal),
                         "status": "accepted",
                         "review": {"actor": {"kind": "human", "id": "actor:fixture"},
                                    "at": "2026-10-29T00:00:00Z",
                                    "rationale": "Synthetic review."}})
        accepted.pop("generated_by"); accepted.pop("method_version")
        accepted["content_digest"] = validate.content_digest(accepted)
        validate.validate_graph([item, target, proposal, accepted])
        changed = copy.deepcopy(accepted)
        changed["scope"] = "broader scope"
        changed["content_digest"] = validate.content_digest(changed)
        with self.assertRaisesRegex(validate.ContractError, "scope differs"):
            validate.validate_graph([item, target, proposal, changed])


class OperationalContractTests(unittest.TestCase):
    def test_operational_unit_receipt_and_delegated_review_are_structural(self):
        pointer={'kind':'thread','id':'thread:fixture','revision':'rev:base'}
        human={'kind':'human','id':'actor:fixture'}
        unit={'schema':'ams-operational-apply-unit/1','id':'unit:fixture','idempotency_key':'unit-fixture','request':{'changeset_id':'changeset:fixture','item_ids':['a'],'expected_revision':'rev:base','owner':'db','actor':human},'changeset_ref':{'kind':'changeset','id':'changeset:fixture','revision':'rev:base'},'base_refs':[pointer],'created_at':'2026-10-29T00:00:00Z'}
        validate.check_structure(unit,'OperationalApplyUnit')
        bad=copy.deepcopy(unit);bad['request']['actor']={'kind':'agent','id':'actor:delegated'}
        with self.assertRaises(validate.ContractError):validate.check_structure(bad,'OperationalApplyUnit')
        bad['request']['delegation_ref']=pointer;validate.check_structure(bad,'OperationalApplyUnit')
        receipt={'schema':'ams-operational-apply-receipt/1','id':'unit:fixture','changeset_id':'changeset:fixture','owner':'db','state':'checked-unchanged','conflicts':[],'applied_refs':[],'changeset_ref':unit['changeset_ref'],'item_results':[{'item_id':'a','state':'checked-unchanged'}],'authorization':{'actor':human,'at':'2026-10-29T00:00:00Z','rationale':'checked exact unchanged fields'},'recorded_at':'2026-10-29T00:00:00Z'}
        validate.check_structure(receipt,'OperationalApplyReceipt')
        wrong=copy.deepcopy(receipt);wrong['item_results'][0]['result_ref']=pointer
        with self.assertRaises(validate.ContractError):validate.check_structure(wrong,'OperationalApplyReceipt')
        wrong=copy.deepcopy(receipt);wrong.update(owner='git',state='applied',applied_refs=[pointer]);wrong['item_results'][0]={'item_id':'a','state':'applied','result_ref':pointer}
        with self.assertRaises(validate.ContractError):validate.check_structure(wrong,'OperationalApplyReceipt')
    def test_publication_delivery_needs_independent_concrete_states(self):
        commit='a'*40;digest='sha256:'+'b'*64
        value={'schema':'ams-publication-delivery/1','id':'delivery:fixture','manifest_ref':{'kind':'publication_manifest','id':'publication_manifest:fixture','revision':'rev:manifest'},'delivery':{'repository':{'state':'visible','commit':commit,'url':'https://example.invalid/repo','observed_at':'2026-10-29T00:00:00Z'},'build':{'state':'failed','source_commit':commit},'site':{'state':'failed'}},'recorded_at':'2026-10-29T00:00:00Z','authorization':{'actor':{'kind':'human','id':'actor:fixture'},'at':'2026-10-29T00:00:00Z','rationale':'synthetic observed failure'},'evidence_status':'operator-supplied-observation; not independently network-verified'}
        validate.check_structure(value,'PublicationDelivery')
        invalid=copy.deepcopy(value);invalid['delivery']['site']={'state':'active','source_commit':commit,'artifact_digest':digest,'deployment_id':'fixture','url':'https://example.invalid/','verified_at':'2026-10-29T00:00:00Z'}
        with self.assertRaises(validate.ContractError):validate.check_structure(invalid,'PublicationDelivery')
        invalid['delivery']['build']={'state':'succeeded','source_commit':commit,'artifact_digest':digest};validate.check_structure(invalid,'PublicationDelivery')
        invalid['delivery']['site']['artifact_digest']='unbound-label'
        with self.assertRaises(validate.ContractError):validate.check_structure(invalid,'PublicationDelivery')

if __name__ == "__main__":
    unittest.main()
