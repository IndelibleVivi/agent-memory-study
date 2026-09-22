#!/usr/bin/env python3
"""Source-bound contract experiment for Jev-Mem's memory write / consolidation decisions.

This runner imports and executes the *real* ``MemoryBuilder.build`` and
``MemoryBuilder.consolidate`` and their dependencies from a pinned checkout of
https://github.com/libingzheren/Jev-Mem, in front of a scripted system-one controller.
It needs no credentials and never calls an online model or downloads weights.

    python3 -B study.py --source-dir <upstream> --write
    python3 -B study.py --source-dir <upstream> --check
    python3 -B study.py --verify-checked

Boundaries (see protocol.md and README.md):
  * The controller is a scripted stand-in for model judgement. No row here is evidence
    about real Jev inference or model calibration.
  * The graph store, vector store and encoder are the real upstream classes
    (NetworkXGraphDB, NumpyVectorDB, MockEncoder). The mock encoder is upstream's own and
    is not a semantic-retrieval claim.
  * Fresh source execution needs numpy, networkx and tqdm (upstream's declared deps).
    Only the SDK carrier, the scripted controller, summary callback and LLM layer are
    substitutes. Runtime UUIDs are normalized in the receipt. No upstream function body is
    rewritten; relative imports resolve through a normal package spec with ``__path__``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS_PATH = HERE / "results.json"
FIXTURES_PATH = HERE / "fixtures.json"
SCHEMA = "ams-jev-contract-results/1"
PACKAGE = "jev_mem_upstream"

# Real upstream modules imported/executed directly for the receipt.
REAL_MODULES = [
    ("memory/memory_builder.py", "MemoryBuilder.build, MemoryBuilder.consolidate"),
    ("memory/jev_mem_policies.py", "WritePolicy, find_candidates, node_state"),
    ("memory/jev_mem_config.py", "JevMemConfig"),
    ("memory/keyword_enrichment.py", "KeywordEnricher"),
    ("memory/jev_questions.py", "Noul/Choice question definitions"),
    ("memory/mock_encoder.py", "MockEncoder"),
    ("memory/graph_db.py", "EventNode, Link, LinkType, NodeType, NetworkXGraphDB"),
    ("memory/vector_db.py", "NumpyVectorDB"),
    ("memory/trg_memory.py", "TemporalResonanceGraphMemory"),
    ("memory/temporal_parser.py", "TemporalParser"),
    ("memory/episode_segmenter.py", "Episode (imported by memory_builder)"),
    ("memory/answer_formatter.py", "AnswerFormatter"),
]

# Files whose bytes and symbol locators are bound into the receipt.
SOURCE_FILES = REAL_MODULES + [
    ("memory/jev_client.py", "JevClient, ProbabilityResult (inspected; carrier substituted)"),
]


def substitutes():
    """The isolated substitutes: the only non-upstream pieces on the executed path."""
    return [
        {
            "boundary": "typesafe_sdk carrier",
            "replaces": "typesafe_sdk Noul / Choice / ChoiceAnswer / error classes",
            "why": "The SDK is not installed and must not be installed; the model step is "
                   "scripted. Question payloads still come from the real jev_questions.py.",
        },
        {
            "boundary": "system-one controller",
            "replaces": "JevClient.probabilities / JevClient.evaluate live path",
            "why": "No online model, network or credentials. Scripted answers carry the same "
                   "Noul float / ChoiceAnswer shape the real jev_mock path produces.",
        },
        {
            "boundary": "deterministic node labels in the receipt",
            "replaces": "the runtime uuid4 node ids inside the receipt only",
            "why": "Upstream EventNode keeps its real uuid4 ids end-to-end; the runner maps "
                   "each runtime id to n1, n2 ... in creation order and reports those labels. "
                   "The mapping is applied to the snapshot output, never to the executed "
                   "source, so no upstream behaviour depends on it.",
        },
        {
            "boundary": "LLM layer",
            "replaces": "utils.memory_layer.LLMController",
            "why": "memory_builder / trg_memory import it at module scope; it is never used "
                   "because llm_enabled=False; its constructor raises if reached.",
        },
        {"boundary": "summary generation", "replaces": "System-Two summarizer",
         "why": "The callback joins the two source strings and records its inputs; it does not call a model."},
    ]


def install_sdk_carrier():
    """Register the typesafe_sdk stand-in that jev_questions.py imports."""
    import types

    sdk = types.ModuleType("typesafe_sdk")

    class Choice:
        def __init__(self, instructions="", criteria=None):
            self.instructions = instructions
            self.criteria = dict(criteria or {})

        def model_dump(self):
            return {"type": "choice", "instructions": self.instructions,
                    "criteria": self.criteria}

    class Noul:
        def __init__(self, instructions="", criteria=None):
            self.instructions = instructions
            self.criteria = dict(criteria or {})

        def model_dump(self):
            return {"type": "noul", "instructions": self.instructions,
                    "criteria": self.criteria}

    class ChoiceAnswer:
        def __init__(self, choice, probabilities, confidence):
            self.choice = choice
            self.probabilities = probabilities
            self.confidence = confidence

        def model_dump(self):
            return {"type": "choice", "choice": self.choice,
                    "probabilities": self.probabilities, "confidence": self.confidence}

    sdk.Choice = Choice
    sdk.Noul = Noul
    sdk.ChoiceAnswer = ChoiceAnswer
    sdk.RetryPolicy = object
    sdk.TypeSafeClient = object
    sdk.TypeSafeAPIConnectionError = RuntimeError
    sdk.TypeSafeAPIError = RuntimeError
    sdk.TypeSafeAPIResponseValidationError = RuntimeError
    sys.modules["typesafe_sdk"] = sdk
    return sdk


def install_llm_stub():
    """Register a raising LLMController so module-scope imports succeed; never called."""
    import types

    if "utils" not in sys.modules:
        utils = types.ModuleType("utils")
        utils.__path__ = []
        sys.modules["utils"] = utils
    if "utils.memory_layer" not in sys.modules:
        layer = types.ModuleType("utils.memory_layer")

        class LLMController:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("LLM layer is out of scope for this experiment")

        layer.LLMController = LLMController
        sys.modules["utils.memory_layer"] = layer
        sys.modules["utils"].memory_layer = layer


# --------------------------------------------------------------------------
# source binding / loading
# --------------------------------------------------------------------------

def git(source_dir, *args):
    import subprocess
    out = subprocess.run(["git", "-C", str(source_dir), *args], capture_output=True,
                         text=True, check=True)
    return out.stdout.strip()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bind_source(source_dir, fixtures):
    import ast

    expected = fixtures["source"]["commit"]
    commit = git(source_dir, "rev-parse", "HEAD")
    binding = {
        "repo": fixtures["source"]["repo"],
        "commit": commit,
        "expected_commit": expected,
        "commit_matches_pin": commit == expected,
        "commit_subject": git(source_dir, "log", "-1", "--format=%s"),
        "dirty": bool(git(source_dir, "status", "--porcelain")),
    }
    if not binding["commit_matches_pin"]:
        raise SystemExit("checkout HEAD %s does not match pinned commit %s" % (commit, expected))
    if binding["dirty"]:
        raise SystemExit("checkout has uncommitted changes; refusing to run against a dirty tree")
    files = []
    for rel, purpose in SOURCE_FILES:
        path = source_dir / rel
        if not path.is_file():
            raise SystemExit("source file missing: %s" % rel)
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        files.append({
            "path": rel,
            "purpose": purpose,
            "sha256": sha256_text(text),  # binds the executed bytes to the receipt
            "bytes": len(text.encode("utf-8")),
            "line_count": text.count("\n") + 1,
            "classes": {node.name: node.lineno for node in ast.walk(tree)
                        if isinstance(node, ast.ClassDef)},
            "functions": {node.name: node.lineno for node in ast.walk(tree)
                          if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))},
        })
    binding["files"] = files
    binding["executed"] = [{"path": path, "symbols": purpose} for path, purpose in REAL_MODULES]
    binding["substituted"] = substitutes()
    return binding


def load_package(source_dir, package):
    """Install a real package spec over the checkout's ``memory/`` directory so the modules'
    own relative imports resolve, then return module_of(name)."""
    import importlib
    import importlib.machinery
    import importlib.util

    for name in list(sys.modules):
        if name == package or name.startswith(package + "."):
            del sys.modules[name]
    pkg = importlib.util.module_from_spec(importlib.machinery.ModuleSpec(package, None))
    pkg.__path__ = [str(source_dir / "memory")]
    sys.modules[package] = pkg
    loaded = {}

    def module_of(name):
        if name in loaded:
            return loaded[name]
        real = source_dir / "memory" / (name + ".py")
        if not real.is_file():
            raise SystemExit("source module missing: %s" % real)
        loaded[name] = importlib.import_module(package + "." + name)
        return loaded[name]

    return module_of


# --------------------------------------------------------------------------
# deterministic node labels (receipt-side only; upstream ids stay real)
# --------------------------------------------------------------------------

class Labeler:
    """Maps runtime uuid node ids to stable n1, n2 ... labels in first-seen order.

    Upstream EventNode, links and hashing all use the real uuid4 ids; only the receipt
    snapshot is relabelled, so no upstream behaviour depends on this mapping."""

    def __init__(self):
        self.count = 0
        self.labels = {}

    def label(self, node_id):
        if node_id not in self.labels:
            self.count += 1
            self.labels[node_id] = "n%d" % self.count
        return self.labels[node_id]


def deterministic_summarizer(call_log):
    def summarize(texts):
        call_log.append(list(texts))
        return " / ".join(texts)
    return summarize


# --------------------------------------------------------------------------
# scripted controller
# --------------------------------------------------------------------------

COVERAGE_TOKENS = ("redundancy", "contradiction", "obsolete", "causes", "caused_by",
                   "before", "after", "overlaps", "same_episode", "temporal_order",
                   "entity")


def make_controller(overrides, representation, confidence, default_value):
    """Scripted stand-in for system-one output.

    Numeric questions whose id contains a coverage token return 0.0; per-case overrides
    replace specific base questions; other numeric questions return ``default_value``.
    The representation Choice returns ``representation`` at ``confidence``. It validates
    nothing beyond what the real jev_mock path passes through, and it never fabricates a
    key the source did not ask for.
    """

    class Audit:
        def __init__(self):
            self.events = []

        def emit(self, event, **values):
            self.events.append({"event": event, **values})

    class ProbabilityResult:
        def __init__(self, values, choices=None):
            self.values = values
            self.source = "scripted"
            self.choices = choices or {}
            self.model = "scripted-controller"
            self.usage = {}

    class Controller:
        def __init__(self):
            self.audit = Audit()
            self.calls = []

        def evaluate(self, operation, state, questions, *, mock_values=None, budget=None):
            values, choices = {}, {}
            for name, question in questions.items():
                if question.__class__.__name__ == "Choice":
                    option = representation
                    conf = float(confidence)
                    rest = (1.0 - conf) / (len(question.criteria) - 1) if \
                        len(question.criteria) > 1 else 0.0
                    probabilities = {key: (conf if key == option else round(rest, 6))
                                     for key in question.criteria}
                    probabilities[option] = 1.0 - sum(
                        value for key, value in probabilities.items() if key != option)
                    sdk = sys.modules["typesafe_sdk"]
                    choices[name] = sdk.ChoiceAnswer(option, probabilities, conf)
                    self.calls.append({"operation": operation, "question": name,
                                       "kind": "choice", "option": option,
                                       "confidence": conf})
                else:
                    value = None
                    for key, override in overrides.items():
                        if key in name:
                            value = float(override)
                            break
                    if value is None:
                        value = 0.0 if any(t in name for t in COVERAGE_TOKENS) else \
                            float(default_value)
                    values[name] = value
                    self.calls.append({"operation": operation, "question": name,
                                       "kind": "noul", "value": value})
            return ProbabilityResult(values, choices)

    return Controller()


# --------------------------------------------------------------------------
# snapshot / case execution
# --------------------------------------------------------------------------

def parse_timestamp(value):
    from datetime import datetime
    return datetime.fromisoformat(value)


def snapshot(trg, summary_ids, labeler):
    links = []
    for link in trg.graph_db.links.values():
        links.append({
            "source": labeler.label(link.source_node_id),
            "target": labeler.label(link.target_node_id),
            "type": link.link_type.value,
            "sub_type": link.properties.get("sub_type"),
            "origin": link.metadata.get("origin"),
        })
    links.sort(key=lambda row: (row["source"], row["target"], row["type"],
                                row["sub_type"] or "", row["origin"] or ""))
    return {
        "stored_ids": sorted(labeler.label(node_id) for node_id in trg.graph_db.nodes),
        "vector_ids": sorted(labeler.label(node_id) for node_id in trg.vector_db.entries),
        "summary_ids": sorted(labeler.label(node_id) for node_id in summary_ids),
        "links": links,
    }


def run_case(case, module_of, defaults):
    MemoryBuilder = module_of("memory_builder").MemoryBuilder
    JevMemConfig = module_of("jev_mem_config").JevMemConfig
    MockEncoder = module_of("mock_encoder").MockEncoder
    graph_db = module_of("graph_db")
    vector_db = module_of("vector_db")
    trg_module = module_of("trg_memory")

    config_values = dict(defaults)
    config_values.pop("note", None)
    config_values.update(case.get("config", {}))
    overrides = config_values.pop("consolidation_overrides", {})
    representation = config_values.pop("consolidation_representation", "keep_separate")
    confidence = config_values.pop("consolidation_confidence", 1.0)
    summarizer_kind = config_values.pop("summarizer", None)
    admission_scores = config_values.pop("admission_scores", None)
    default_value = config_values.pop("controller_default", 0.9)
    config = JevMemConfig(**config_values)

    labeler = Labeler()

    trg = trg_module.TemporalResonanceGraphMemory(
        graph_db=graph_db.NetworkXGraphDB(),
        vector_db=vector_db.NumpyVectorDB(MockEncoder.dimension),
        encoder=MockEncoder(),
        llm_backend=None)
    # Explicit admission_scores replace the relevant question answers; without them the
    # numeric default applies (0.9 -> admitted when admission is on).
    answers = dict(overrides)
    if admission_scores is not None:
        answers.update(admission_scores)
    controller = make_controller(answers, representation, confidence, default_value)
    builder = MemoryBuilder(str(HERE), jev_config=config, jev_client=controller,
                            trg_memory=trg, llm_enabled=False)

    summary_ids = []
    summarizer_calls = []
    summarizer = deterministic_summarizer(summarizer_calls) if summarizer_kind == "join" \
        else None

    before = snapshot(trg, summary_ids, labeler)
    outcomes = []
    decisions_log = []
    for step in case["sequence"]:
        timestamp = parse_timestamp(step["timestamp"])
        node = builder.build(step["text"], timestamp)
        if node is None:
            outcomes.append({"text": step["text"], "build": "rejected"})
            continue
        outcomes.append({"text": step["text"], "build": "stored", "id": labeler.label(node.node_id),
                         "has_jev_mem": "jev_mem" in node.attributes})
        if step.get("consolidate"):
            before = snapshot(trg, summary_ids, labeler)
            decisions_log.append(builder.consolidate(node.node_id, summarizer=summarizer))
            for node_id in trg.graph_db.nodes:
                candidate = trg.graph_db.get_node(node_id)
                if candidate.attributes.get("source") == "jev_mem_consolidation" and \
                        node_id not in summary_ids:
                    summary_ids.append(node_id)

    after = snapshot(trg, summary_ids, labeler)
    observations = collect_observations(controller, outcomes, decisions_log,
                                        summarizer_calls, trg, labeler)
    checks = evaluate_checks(case, before, after, observations)
    return {
        "id": case["id"],
        "title": case["title"],
        "role": case["role"],
        "group": case["group"],
        "intervention": case["intervention"],
        "input": {"config": config_values, "sequence": case["sequence"]},
        "before": before,
        "after": after,
        "observations": observations,
        "checks": checks,
    }


def collect_observations(controller, outcomes, decisions_log, summarizer_calls, trg, labeler):
    nodes = {}
    for node_id, node in trg.graph_db.nodes.items():
        jev = node.attributes.get("jev_mem", {})
        nodes[labeler.label(node_id)] = {
            "content": node.content_narrative,
            "source": node.attributes.get("source"),
            "has_jev_mem": "jev_mem" in node.attributes,
            "memory_type": jev.get("memory_type"),
            "admission": jev.get("admission"),
            "admission_score": jev.get("admission_score"),
            "raw_content": node.attributes.get("raw_content"),
            "source_memory_ids": [labeler.label(key) for key in node.attributes.get("source_memory_ids", [])],
            "parent_interaction_id": labeler.label(node.attributes["parent_interaction_id"]) if node.attributes.get("parent_interaction_id") else None,
            "consolidation": [{**decision, "candidate_id": labeler.label(decision["candidate_id"])} for decision in jev.get("consolidation", [])],
        }
    decisions = []
    for group in decisions_log:
        decisions.append([
            {**decision, "candidate_id": labeler.label(decision["candidate_id"])}
            for decision in group
        ])
    return {
        "build_outcomes": outcomes,
        "consolidation_decisions": decisions,
        "summarizer_calls": summarizer_calls,
        "controller_calls": controller.calls,
        "audit_events": [event["event"] for event in controller.audit.events],
        "nodes": nodes,
        "vector_count": len(trg.vector_db.entries),
    }


def evaluate_checks(case, before, after, observations):
    added = [i for i in after["stored_ids"] if i not in before["stored_ids"]]
    removed = [i for i in before["stored_ids"] if i not in after["stored_ids"]]
    v_added = [i for i in after["vector_ids"] if i not in before["vector_ids"]]
    v_removed = [i for i in before["vector_ids"] if i not in after["vector_ids"]]
    rejections = [row for row in observations["build_outcomes"] if row["build"] == "rejected"]
    checks = {}
    checks["jev_write_path_used"] = all(row.get("has_jev_mem") for row in observations["build_outcomes"] if row["build"] == "stored") and "magma_fallback" not in observations["audit_events"]
    checks["original_texts_retained"] = all(observations["nodes"][row["id"]]["content"] == row["text"] and observations["nodes"][row["id"]]["raw_content"] == row["text"] for row in observations["build_outcomes"] if row["build"] == "stored")
    checks["node_vector_membership_matches"] = after["stored_ids"] == after["vector_ids"] and observations["vector_count"] == len(after["vector_ids"])
    if case["group"] == "build-admission":
        if case["id"] == "admission-on-mean-text-rejected-cleanly":
            checks["build_rejected"] = bool(rejections)
            checks["rejection_leaves_no_trace"] = added == [] and v_added == [] and \
                before == after
        else:
            checks["node_added_count"] = len(added) == 1
            checks["vector_added_count"] = len(v_added) == 1
        if case["id"] == "default-off-admission-still-follows-judgment":
            checks["written_despite_zero_judgement"] = len(added) == 1 and not rejections and all(value == 0 for node in observations["nodes"].values() for value in node["memory_type"].values())
            checks["admission_not_queried"] = not any(call["operation"] == "observation" for call in observations["controller_calls"])
        if case["id"] == "admission-on-meaningful-observation-admitted":
            checks["admission_recorded"] = all(
                row["admission"] is not None and row["admission_score"] >= 0.5 for row in observations["nodes"].values())
    else:
        checks["no_node_removed"] = removed == []
        checks["no_vector_removed"] = v_removed == []
        decisions = observations["consolidation_decisions"][0] if \
            observations["consolidation_decisions"] else []
        checks["decision_recorded"] = len(decisions) == 1
        recorded = decisions[0] if decisions else {}
        case_overrides = case["config"].get("consolidation_overrides", {})
        if "obsolete" in case_overrides:
            checks["obsolete_probability_recorded"] = recorded.get("obsolete") == \
                case_overrides["obsolete"]
            # Both accounts are stored before consolidate(); consolidation must add and
            # remove nothing: node/vector/summary sets are unchanged by the call.
            checks["obsolete_does_not_change_counts"] = (
                before["stored_ids"] == after["stored_ids"]
                and before["vector_ids"] == after["vector_ids"]
                and after["summary_ids"] == []
                and removed == [] and v_removed == [])
        if case_overrides.get("contradiction", 0) >= 0.85:
            checks["contradiction_subtype_link"] = any(
                link["sub_type"] == "CONTRADICTS" for link in after["links"])
        if "merge" in case["config"].get("consolidation_representation", ""):
            checks["merge_representation_recorded"] = (
                recorded.get("representation", {}).get("choice") == "merge")
        if case["config"].get("summarizer"):
            expected = 1 if case["id"] == \
                "merge-with-summarizer-creates-derived-representation" else 0
            checks["summary_count_expected"] = len(after["summary_ids"]) == expected
            checks["summarizer_called_expected"] = bool(observations["summarizer_calls"]) \
                == (expected == 1)
            if expected:
                summary = observations["nodes"][after["summary_ids"][0]]
                checks["summary_preserves_source_ids"] = set(summary["source_memory_ids"]) == set(before["stored_ids"])
                checks["summary_added_alongside_originals"] = set(before["stored_ids"]) < set(after["stored_ids"]) and len(added) == 1 and len(v_added) == 1
        else:
            checks["no_summarizer_available"] = observations["summarizer_calls"] == []
            checks["no_summary_created"] = after["summary_ids"] == []
    return checks


# --------------------------------------------------------------------------
# invariants
# --------------------------------------------------------------------------

def _topology(snap):
    return (snap["stored_ids"], snap["vector_ids"], snap["summary_ids"],
            [(link["source"], link["target"], link["type"], link["sub_type"])
             for link in snap["links"]])


def summarize(cases):
    high = cases["obsolete-high-keeps-evidence-and-persists-decision"]
    low = cases["obsolete-low-keeps-evidence-and-relation"]
    invariants = {
        "obsolete_high_keeps_evidence": (
            high["before"]["stored_ids"] == ["n1", "n2"]
            and high["after"]["stored_ids"] == ["n1", "n2"]
            and high["after"]["vector_ids"] == ["n1", "n2"]
            and high["after"]["summary_ids"] == []),
        "obsolete_low_keeps_evidence": (
            low["before"]["stored_ids"] == ["n1", "n2"]
            and low["after"]["stored_ids"] == ["n1", "n2"]
            and low["after"]["vector_ids"] == ["n1", "n2"]
            and low["after"]["summary_ids"] == []),
        "obsolete_scalar_lives_only_in_decision": (
            _topology(high["after"]) == _topology(low["after"])),
        "contradiction_or_low_confidence_blocks_summary": (
            cases["contradiction-blocks-merge-summary"]["after"]["summary_ids"] == []
            and cases["low-confidence-merge-blocked-by-threshold"]["after"]["summary_ids"] == []),
        "rejection_leaves_state_identical": (
            cases["admission-on-mean-text-rejected-cleanly"]["before"]
            == cases["admission-on-mean-text-rejected-cleanly"]["after"]),
    }
    failing = sorted(case_id for case_id, row in cases.items()
                     if not row["checks"] or not all(row["checks"].values()))
    return {"cases": len(cases), "cases_with_failing_checks": failing,
            "invariants": invariants, "invariants_hold": all(invariants.values())}


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def run(source_dir, fixtures_path=FIXTURES_PATH):
    fixtures = json.loads(Path(fixtures_path).read_text(encoding="utf-8"))
    source_dir = Path(source_dir).resolve()
    binding = bind_source(source_dir, fixtures)

    install_sdk_carrier()
    install_llm_stub()
    module_of = load_package(source_dir, PACKAGE)
    for name in ("graph_db", "jev_mem_config", "keyword_enrichment", "jev_questions",
                 "mock_encoder", "temporal_parser", "episode_segmenter",
                 "answer_formatter", "jev_mem_policies", "memory_builder"):
        module_of(name)

    cases = {}
    for case in fixtures["cases"]:
        cases[case["id"]] = run_case(case, module_of, fixtures["defaults"])

    summary = summarize(cases)
    if summary["cases_with_failing_checks"] or not summary["invariants_hold"]:
        raise SystemExit("failing checks: %s" % summary["cases_with_failing_checks"])

    return {
        "schema": SCHEMA,
        "fixtures_sha256": sha256_text(json.dumps(fixtures, ensure_ascii=False, sort_keys=True)),
        "method": {
            "purpose": "Source-bound characterization of Jev-Mem's write/admission and "
                       "consolidation decisions; the model step is scripted, not executed.",
            "controller": fixtures["controller"],
            "determinism": "Real UUIDs remain in upstream execution. Receipt-only labels n1, n2 ... follow build order and replace all node references, including persisted decisions and summary provenance. Link UUIDs and internal dedup hashes are omitted; typed endpoints and relations are retained. Fixture timestamps are fixed; a generated summary has no supplied timestamp.",
            "minimum_runtime": "numpy, networkx, tqdm (upstream's declared deps). No "
                               "typesafe-sdk, faiss or sentence-transformers needed.",
        },
        "boundary": {
            "is_jev_inference": False,
            "is_embedding_accuracy": False,
            "is_benchmark": False,
            "is_model_forgetting": False,
            "find_candidates_is_semantic_retrieval": False,
            "notes": [
                "A high obsolete probability is a returned judgement about the new/candidate "
                "pair, not a deletion.",
                "The encoder is upstream's MockEncoder; candidate selection is not a real "
                "semantic-retrieval result.",
                "No scalar in this receipt measures a model's semantic ability.",
            ],
        },
        "source": binding,
        "cases": [cases[case["id"]] for case in fixtures["cases"]],
        "invariants": summary["invariants"],
        "summary": {
            "cases": summary["cases"],
            "cases_with_failing_checks": summary["cases_with_failing_checks"],
            "invariants_hold": summary["invariants_hold"],
        },
    }


def verify_checked(receipt, fixtures):
    """Offline internal-contract check: fixture binding, shape and invariants only.

    This never imports numpy/networkx, never executes upstream, and must not be presented
    as a rerun. stdlib only.
    """
    def require(condition, message):
        if not condition:
            raise SystemExit("verify-checked failed: %s" % message)

    require(receipt.get("schema") == SCHEMA, "schema")
    require(receipt.get("fixtures_sha256") == sha256_text(json.dumps(fixtures, ensure_ascii=False, sort_keys=True)), "fixture binding")
    require(receipt["source"]["repo"] == fixtures["source"]["repo"], "repo")
    require(receipt["source"]["commit"] == fixtures["source"]["commit"], "commit pin")
    require(receipt["source"]["expected_commit"] == fixtures["source"]["commit"], "expected pin")
    require(receipt["source"]["executed"] == [
        {"path": path, "symbols": symbols} for path, symbols in REAL_MODULES], "executed list")
    require(receipt["source"]["substituted"] == substitutes(), "substitute list")

    expected = fixtures["cases"]
    rows = receipt["cases"]
    require([row["id"] for row in rows] == [case["id"] for case in expected], "case ids/order")
    require(len(rows) == len(expected) > 0, "case count")
    for row, case in zip(rows, expected):
        require(row["intervention"] == case["intervention"], "%s: intervention" % case["id"])
        require(row["title"] == case["title"], "%s: title" % case["id"])
        require(row["input"]["sequence"] == case["sequence"], "%s: input sequence" % case["id"])
        config = {**fixtures["defaults"], **case.get("config", {})}
        for key in ("note", "consolidation_overrides", "consolidation_representation", "consolidation_confidence", "summarizer", "admission_scores", "controller_default"):
            config.pop(key, None)
        require(row["input"]["config"] == config, "%s: effective config" % case["id"])
        for which in ("before", "after"):
            snap = row[which]
            require(set(snap) == {"stored_ids", "vector_ids", "summary_ids", "links"},
                    "%s: %s keys" % (case["id"], which))
            for key in ("stored_ids", "vector_ids", "summary_ids"):
                require(all(isinstance(x, str) for x in snap[key]),
                        "%s: %s.%s strings" % (case["id"], which, key))
            require(isinstance(snap["links"], list), "%s: links list" % case["id"])
        require(isinstance(row["checks"], dict) and bool(row["checks"]),
                "%s: checks present" % case["id"])
        require(all(isinstance(v, bool) and v for v in row["checks"].values()),
                "%s: all checks true" % case["id"])
        require(evaluate_checks(case, row["before"], row["after"], row["observations"]) == row["checks"], "%s: recomputed checks" % case["id"])

    cases = {row["id"]: row for row in rows}
    require(summarize(cases)["invariants"] == receipt["invariants"],
            "recomputed invariants differ")
    require(all(receipt["invariants"].values()), "invariants must hold")
    computed = summarize(cases)
    require(receipt["summary"] == {key:computed[key] for key in ("cases", "cases_with_failing_checks", "invariants_hold")}, "summary consistency")
    require(cases["default-off-admission-still-follows-judgment"]["after"]["stored_ids"]
            != cases["admission-on-mean-text-rejected-cleanly"]["after"]["stored_ids"],
            "admission control must differ")
    require(cases["merge-without-summarizer-persists-links-only"]["after"]["summary_ids"]
            != cases["merge-with-summarizer-creates-derived-representation"]["after"][
                "summary_ids"],
            "summarizer control must differ")
    require(_topology(cases["obsolete-high-keeps-evidence-and-persists-decision"]["after"])
            == _topology(cases["obsolete-low-keeps-evidence-and-relation"]["after"]),
            "obsolete high/low topology must match")
    return receipt["summary"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path,
                        help="Pinned Jev-Mem checkout (required for --write/--check)")
    parser.add_argument("--write", action="store_true",
                        help="Run against --source-dir and write results.json")
    parser.add_argument("--check", action="store_true",
                        help="Run against --source-dir and compare with results.json")
    parser.add_argument("--verify-checked", action="store_true",
                        help="Check the saved receipt offline (stdlib only); no upstream run")
    parser.add_argument("--output", type=Path, default=RESULTS_PATH)
    args = parser.parse_args(argv)

    fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))

    if args.verify_checked:
        if args.write or args.check or args.source_dir:
            parser.error("--verify-checked is offline; drop --source-dir/--write/--check")
        receipt = json.loads(args.output.read_text(encoding="utf-8"))
        summary = verify_checked(receipt, fixtures)
        print("PASS: %d checked Jev-Mem cases bind to fixtures; invariants hold; "
              "upstream not rerun" % summary["cases"])
        return 0

    if not args.source_dir:
        parser.error("--source-dir is required for --write/--check")
    if not (args.write or args.check):
        parser.error("choose --write or --check (or --verify-checked)")

    result = run(args.source_dir)
    if args.check:
        saved = json.loads(args.output.read_text(encoding="utf-8"))
        if result != saved:
            raise SystemExit("Fresh execution differs from saved results")
        print("PASS: fresh source-bound execution matches %d saved cases" % len(result["cases"]))
    else:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print("wrote %s (%d cases)" % (args.output, len(result["cases"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
