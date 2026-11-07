#!/usr/bin/env python3
"""Offline source intake, explicit-impact inspection, and workspace drafting.

This tool does not fetch URLs, resolve DOIs over the network, execute imported
text, or infer claims. It compares supplied identity text with the public
study/sources records and delegates graph and workspace semantics to the shared
JavaScript implementations.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STUDY_ROOT = ROOT / "study"
SOURCES = STUDY_ROOT / "sources"
ENTRIES = STUDY_ROOT / "entries"
INQUIRIES = STUDY_ROOT / "inquiries"
TRANSFERS = STUDY_ROOT / "transfers"
BRIDGE = Path(__file__).with_name("research_context.cjs")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DOI = re.compile(r"^(?:doi:|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)
ARXIV = re.compile(
    r"^(?:arxiv:)?(?P<id>\d{4}\.\d{4,5})(?:v(?P<version>\d+))?$",
    re.IGNORECASE,
)
OBJECT_KINDS = ("material", "study", "question", "finding")
DRAFT_KINDS = ("learning-note", "research-essay")
EXCERPT_ROLES = {
    "context": "上下文摘录（作者待判断）",
    "support": "可能支持（作者待核对）",
    "contrast": "可能对照或反例（作者待核对）",
    "question": "引出问题（作者待判断）",
}
WORKSPACE_BYTES = 2 * 1024 * 1024

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def family(folder: Path) -> list[dict[str, Any]]:
    if not folder.is_dir():
        raise ValueError(f"Missing study family: {folder.relative_to(ROOT).as_posix()}")
    return [load_json(path) for path in sorted(folder.glob("*.json"))]

def normalize(value: Any) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", str(value or "").casefold()).split())

def canonical_url(value: str) -> tuple[str, str | None]:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "", None
    host = parsed.netloc.casefold().removeprefix("www.")
    path = re.sub(r"/+$", "", parsed.path)
    version = None
    doi_match = DOI.fullmatch(value.strip())
    if doi_match:
        return f"doi:{doi_match.group(1).casefold().rstrip('.')}", None
    arxiv_match = re.search(r"/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v(\d+))?(?:\.pdf)?$", path)
    if (host == "arxiv.org" or host.endswith(".arxiv.org")) and arxiv_match:
        return f"arxiv:{arxiv_match.group(1)}", arxiv_match.group(2)
    return f"{host}{path}" + (f"?{parsed.query}" if parsed.query else ""), version

def source_links(source: dict[str, Any]) -> set[str]:
    links = set()
    for key in ("sourceUrl", "doi"):
        value = source.get(key)
        if not isinstance(value, str):
            continue
        target, _ = canonical_url(value if "://" in value else f"https://doi.org/{value}")
        if target:
            links.add(target)
    pdf = source.get("pdf")
    if isinstance(pdf, dict):
        for value in (pdf.get("url"), pdf.get("originalUrl")):
            if isinstance(value, str):
                target, _ = canonical_url(value)
                if target:
                    links.add(target)
    return links

def source_version(source: dict[str, Any]) -> str | None:
    scope = str(source.get("readingScope", ""))
    match = re.search(r"\bv(\d+)\b", scope, re.IGNORECASE)
    return match.group(1) if match else None

def match_source(sources: list[dict[str, Any]], value: str) -> dict[str, Any]:
    query = value.strip()
    doi_match = DOI.fullmatch(query)
    arxiv_match = ARXIV.fullmatch(query)
    target, version = canonical_url(query) if "://" in query else ("", None)
    if doi_match:
        target = f"doi:{doi_match.group(1).casefold().rstrip('.')}"
    elif arxiv_match:
        target = f"arxiv:{arxiv_match.group('id')}"
        version = arxiv_match.group("version")

    def family_identity(link: str) -> str:
        arxiv_doi = re.match(r"^(doi:10\.48550/arxiv\.)(\d{4}\.\d{4,5})(?:v\d+)?$", link)
        if arxiv_doi:
            return f"arxiv:{arxiv_doi.group(2)}"
        arxiv = re.match(r"^(arxiv:\d{4}\.\d{4,5})(?:v\d+)?$", link)
        if arxiv:
            return arxiv.group(1)
        return link

    exact_identity: list[dict[str, Any]] = []
    version_matches: list[dict[str, Any]] = []
    title_matches: list[dict[str, Any]] = []
    normalized_query = normalize(query)
    for source in sources:
        links = source_links(source)
        if target and target in links:
            exact_identity.append(source)
            if version and source_version(source) and source_version(source) != version:
                version_matches.append(source)
        elif target:
            family_ids = {family_identity(link) for link in links}
            if family_identity(target) in family_ids:
                version_matches.append(source)
        title = normalize(source.get("title"))
        if normalized_query and (normalized_query == title or (
            len(normalized_query) >= 24 and normalized_query in title
        )):
            title_matches.append(source)

    exact = exact_identity[0] if exact_identity else (title_matches[0] if len(title_matches) == 1 else None)
    if exact:
        identity_status = "exact" if exact_identity else "title-match"
        if version and exact_identity and source_version(exact) and source_version(exact) != version:
            identity_status = "new-version"
        return {
            "status": identity_status,
            "source": exact,
            "versionCandidates": version_matches if version else [],
            "titleCandidates": [item for item in title_matches if item is not exact],
        }
    if version_matches:
        return {"status": "version-family", "source": None, "versionCandidates": version_matches,
                "titleCandidates": title_matches}
    if title_matches:
        return {"status": "uncertain-title", "source": None, "versionCandidates": [],
                "titleCandidates": title_matches}
    return {"status": "unrecognized", "source": None, "versionCandidates": [],
            "titleCandidates": []}

def impact(source_id: str) -> dict[str, Any]:
    """Legacy material impact shape kept for existing CLI users."""
    sources = family(SOURCES)
    if source_id not in {source["id"] for source in sources}:
        raise ValueError(f"Unknown source id: {source_id}")
    return _legacy_impact(source_id, fresh_impact("material", source_id))

def _compiler():
    try:
        from tools import build, content
    except ModuleNotFoundError:
        import build  # type: ignore[no-redef]
        import content  # type: ignore[no-redef]
    return build, content

def fresh_data() -> dict[str, Any]:
    """Compile canonical study content in memory; never read generated projections."""
    try:
        build, content = _compiler()
        return build.validate_data(content.compile_content())
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            f"Fresh impact requires the declared content parser dependency ({exc.name}); "
            "run `python3 -m pip install -r tools/content-requirements.txt`."
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Fresh canonical compilation failed: {exc}") from exc

def _node() -> str:
    explicit = os.environ.get("AMS_NODE")
    if explicit:
        path = Path(explicit)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f"AMS_NODE does not point to an executable: {explicit}")
        return str(path)
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Fresh impact and workspace validation require Node.js on PATH.")
    return node

def _bridge_call(payload: dict[str, Any]) -> Any:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(encoded) > 64 * 1024:
        raise ValueError("Bridge envelope exceeds 64 KiB.")
    process = subprocess.run(
        [_node(), str(BRIDGE)], input=encoded, capture_output=True, timeout=60,
        cwd=ROOT, check=False,
    )
    try:
        response = json.loads(process.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        detail = process.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"Local Node bridge returned invalid output{': ' + detail if detail else '.'}") from exc
    if process.returncode != 0 or "error" in response:
        raise ValueError(response.get("error", "Local Node bridge failed."))
    return response["result"]

def _temporary_data(data: dict[str, Any]) -> Path:
    handle, name = tempfile.mkstemp(prefix="ams-author-", suffix=".json")
    path = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False)
        return path
    except BaseException:
        path.unlink(missing_ok=True)
        raise

def deep_impact(kind: str, object_id: str) -> dict[str, Any]:
    if kind not in OBJECT_KINDS:
        raise ValueError(f"Unknown object kind: {kind}")
    result = fresh_impact(kind, object_id)
    return {key: result[key] for key in ("target", "affected")}

def fresh_impact(kind: str, object_id: str) -> dict[str, Any]:
    data = fresh_data()
    path = _temporary_data(data)
    try:
        return _bridge_call({"command": "impact", "dataFile": str(path),
                             "kind": kind, "id": object_id})
    finally:
        path.unlink(missing_ok=True)

def _legacy_impact(source_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Project the shared direct-reference manifest into the pre-existing shape."""
    output = {
        "sourceId": source_id,
        "entries": [], "inquiries": [], "transfers": [],
        "mapDomains": [], "mapDirections": [],
        "target": result["target"], "affected": result["affected"],
    }
    target = f"material/{source_id}"
    titles = {
        f"{node['kind']}/{node['id']}": node["title"]
        for node in result["nodes"]
    }
    entries = set()
    questions = set()
    findings = set()
    for reference in result["references"]:
        if reference["to"] != target:
            continue
        from_key, relation = reference["from"], reference["relation"]
        if from_key.startswith("study/"):
            role = {"reading": "reading", "continuation": "continuation"}.get(relation)
            if role:
                entries.add((from_key.removeprefix("study/"), titles[from_key], role))
        elif from_key.startswith("question/"):
            role = {"related": "evidence-reading", "continuation": "continuation"}.get(relation)
            if role:
                questions.add((from_key.removeprefix("question/"), titles[from_key], role))
        elif from_key.startswith("finding/") and relation == "related":
            findings.add((from_key.removeprefix("finding/"), titles[from_key]))
    output["entries"] = [
        {"id": object_id, "title": title, "role": role}
        for object_id, title, role in sorted(entries, key=lambda row: (row[0], row[2] != "reading"))
    ]
    output["inquiries"] = [
        {"id": object_id, "title": title, "role": role}
        for object_id, title, role in sorted(questions, key=lambda row: (row[0], row[2] != "evidence-reading"))
    ]
    output["transfers"] = [
        {"id": object_id, "title": title, "role": "evidence"}
        for object_id, title in sorted(findings)
    ]
    mapping = load_json(STUDY_ROOT / "map.json") if (STUDY_ROOT / "map.json").is_file() else {}
    for domain in mapping.get("domains", []):
        if source_id in domain.get("materialIds", []):
            output["mapDomains"].append(domain["id"])
    for direction in mapping.get("directions", []):
        if source_id in direction.get("materialIds", []):
            output["mapDirections"].append(direction["id"])
    return output

def inspect(value: str) -> dict[str, Any]:
    sources = family(SOURCES)
    match = match_source(sources, value)
    source = match["source"]
    output = {
        "input": value,
        "lookup": "offline-identity-comparison",
        "matchStatus": match["status"],
        "recognized": source is not None,
        "source": None,
        "versionCandidates": [
            {"id": item["id"], "title": item["title"], "version": source_version(item)}
            for item in match["versionCandidates"]
        ],
        "titleCandidates": [
            {"id": item["id"], "title": item["title"]} for item in match["titleCandidates"]
        ],
        "dependencies": None,
        "note": (
            "Input was not recognized. No title, version, claims, or content were fetched or invented."
            if source is None else
            "A public source candidate was found; inspect matchStatus. Dependencies are explicit evidence, not claim validation."
        ),
    }
    if source:
        output["source"] = {key: source.get(key) for key in
                            ("id", "title", "authors", "year", "sourceUrl", "doi",
                             "readingScope", "noteDepth")}
        output["dependencies"] = impact(source["id"])
    return output

DRAFT_BODY = """# {title}

{label}

从使你想研究这个对象的一句话、例子或疑惑开始。把已经讲清的内容写在这里；外部事实附上实际阅读的来源与范围。

这仍是草稿。进入公开研究体之前，替换提示文字，核对署名与依据。
"""

def create_draft(slug: str, title: str, kind: str, out_dir: Path) -> tuple[Path, Path]:
    if not SLUG.fullmatch(slug):
        raise ValueError("SLUG must use lowercase ASCII words separated by hyphens")
    if kind not in DRAFT_KINDS:
        raise ValueError("--kind must be learning-note or research-essay")
    if not title.strip():
        raise ValueError("--title must be non-empty")
    _assert_outside_repo(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{slug}.json"
    markdown_path = out_dir / f"{slug}.md"
    if json_path.exists() or markdown_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing draft: {json_path if json_path.exists() else markdown_path}")
    record = {
        "id": slug,
        "title": title.strip(),
        "kind": kind,
        "date": datetime.date.today().isoformat(),
        "byline": "Draft author",
        "intro": "Draft introduction to complete before editorial review.",
        "bodyFile": markdown_path.name,
        "draft": True,
    }
    markdown = DRAFT_BODY.format(
        title=title.strip(),
        label="私人作者草稿；须由作者核对事实、出处、署名与是否公开。",
    )
    _write_pair(json_path, record, markdown_path, markdown)
    return json_path, markdown_path

def _assert_outside_repo(path: Path) -> None:
    original = path.absolute()
    if original.is_symlink():
        raise ValueError("Draft output directory must not be a symlink")
    resolved = original.resolve()
    repository = ROOT.resolve()
    repository_display = ROOT.absolute()
    if resolved == repository or resolved.is_relative_to(repository):
        raise ValueError("Draft output must be outside this public repository")
    if original == repository_display or original.is_relative_to(repository_display):
        raise ValueError("Draft output must be outside this public repository")

def _assert_regular_input(path: Path) -> Path:
    candidate = Path(os.path.abspath(path))
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError("--input must be a regular non-symlink workspace file")
    repository = ROOT.resolve()
    repository_display = ROOT.absolute()
    resolved = candidate.resolve(strict=True)
    if candidate == repository_display or candidate.is_relative_to(repository_display):
        raise ValueError("--input must be outside this public repository")
    if resolved == repository or resolved.is_relative_to(repository):
        raise ValueError("--input must be outside this public repository")
    return resolved

def _check_input(path: Path) -> Path:
    source = _assert_regular_input(path)
    if source.stat().st_size > WORKSPACE_BYTES:
        raise ValueError("Workspace input exceeds 2 MiB.")
    return source

def _public_reference(item: dict[str, Any], kind: str) -> str:
    fields = {
        "material": ("authors", "year", "title", "sourceUrl", "readingScope", "noteDepth"),
        "study": ("title", "byline", "date", "intro", "sourcePath"),
        "question": ("title", "byline", "updated", "question", "intro"),
        "finding": ("title", "byline", "updated", "claim", "when", "limit"),
    }[kind]
    lines = [f"- 公开身份：{kind}:{item['id']}"]
    for field in fields:
        value = item.get(field)
        if isinstance(value, list):
            value = ", ".join(str(value_part) for value_part in value)
        if value:
            lines.append(f"- {field}：{value}")
    if kind == "material":
        lines.append(f"- 出处：{item.get('sourceUrl', '')}")
    elif item.get("sourcePath"):
        lines.append(f"- 正文出处：{item['sourcePath']}")
    return "\n".join(lines)

REVISION_NOTES = {
    "current": "所据公开内容与当前相同。",
    "changed": "所据公开内容在保存后已有变化；私人摘录与批注保留原样，发布前须重新核对。",
    "unknown": "没有公开内容快照，日期不能确认正文身份。",
    "invalid": "保存的公开内容快照不可比较；不能据此确认摘录与当前正文的关系。",
}

def _workspace_markdown(work: dict[str, Any], data: dict[str, Any], title: str,
                        urls: dict[str, str], revisions: dict[str, dict[str, Any]]) -> str:
    lines = [
        f"# {title.strip()}", "",
        "> 私人作者草稿。以下包含案头问题、个人笔记、摘录与角色判断；",
        "> 这些是继续研究和编辑的原料，不是公开结论，也不自动证明摘录支持某个论点。",
        "> 发布前须由作者核对事实、出处、署名，并自行选择应公开的内容。", "",
    ]
    for field, heading in (("question", "当前问题"), ("synthesis", "已有理解"), ("next", "继续位置")):
        lines.extend([f"## {heading}", "", work.get(field) or "（作者尚未填写。）", ""])
    families = {"material": "materials", "study": "studies", "question": "questions", "finding": "findings"}
    lines.extend(["## 案头对象", ""])
    if not work.get("items"):
        lines.append("（案头未包含对象。）")
    for entry in work.get("items", []):
        item = next(item for item in data[families[entry["kind"]]] if item["id"] == entry["id"])
        key = f"{entry['kind']}:{entry['id']}"
        revision = revisions[key]["object"]
        lines.extend([f"### {item['title']}", "", _public_reference(item, entry["kind"]),
                      f"- 公开页面：{urls[key]}{entry.get('anchor', '')}", "",
                      f"- 案头身份：{entry['kind']}:{entry['id']}",
                      f"- 笔记所据内容日期：{entry.get('contentVersion') or '未标日期'}",
                      f"- 笔记版本检查：{REVISION_NOTES[revision['status']]}"])
        if revision.get("fields"):
            lines.append(f"- 变化字段：{', '.join(revision['fields'])}")
        if entry.get("anchor"):
            lines.append(f"- 接续位置：{entry['anchor']}")
        if entry.get("note"):
            lines.extend(["", "#### 我的笔记", "", entry["note"]])
        for excerpt in entry.get("excerpts", []):
            excerpt_revision = revisions[key]["excerpts"][excerpt["id"]]
            lines.extend([
                "", "#### 私人摘录", "",
                f"- 摘录身份：{excerpt.get('id', '')}",
                f"- 作者角色：{EXCERPT_ROLES.get(excerpt.get('role'), '作者待判断')}",
                f"- 来源定位：{excerpt.get('anchor') or '未标位置'}",
                f"- 摘录所据内容日期：{excerpt.get('contentVersion') or '未标日期'}",
                f"- 摘录来源链接：{urls[key]}{excerpt.get('anchor') or ''}",
                f"- 摘录版本检查：{REVISION_NOTES[excerpt_revision['status']]}",
                "", "> 摘录原文（私人文字，发布前须回到公开对象核对）：", "",
                "\n".join("> " + line if line else ">" for line in excerpt.get("quote", "").splitlines()),
            ])
            if excerpt_revision.get("fields"):
                lines.append(f"- 摘录所据内容变化字段：{', '.join(excerpt_revision['fields'])}")
            if excerpt.get("comment"):
                lines.extend(["", "个人评论：", "", excerpt["comment"]])
        lines.append("")
    lines.extend(["## 公开署名与版权核对", "",
                  "材料作者与本站札记作者是两个不同身份。上方 metadata 的 `byline` 尚未填写；",
                  "发布前请填写实际公开署名，并核对每段公开文字的来源与阅读范围。", ""])
    return "\n".join(lines).rstrip() + "\n"

def draft_from_workspace(input_path: Path, slug: str, title: str, kind: str,
                         out_dir: Path) -> tuple[Path, Path]:
    if not SLUG.fullmatch(slug):
        raise ValueError("SLUG must use lowercase ASCII words separated by hyphens")
    if kind not in DRAFT_KINDS:
        raise ValueError("--kind must be learning-note or research-essay")
    if not title.strip():
        raise ValueError("--title must be non-empty")
    _assert_outside_repo(out_dir)
    source = _check_input(input_path)
    data = fresh_data()
    temporary = _temporary_data(data)
    try:
        context = _bridge_call({
            "command": "workspace",
            "workspaceFile": str(source),
            "dataFile": str(temporary),
        })
    finally:
        temporary.unlink(missing_ok=True)
    work = context["workspace"]
    markdown = _workspace_markdown(work, data, title, context["urls"], context["revisions"])
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{slug}.json"
    markdown_path = out_dir / f"{slug}.md"
    if json_path.exists() or markdown_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing draft: {json_path if json_path.exists() else markdown_path}")
    record = {
        "id": slug,
        "title": title.strip(),
        "kind": kind,
        "date": datetime.date.today().isoformat(),
        "byline": "Draft author",
        "intro": "Draft introduction to complete before editorial review; based on private workspace material.",
        "bodyFile": markdown_path.name,
        "draft": True,
    }
    _write_pair(json_path, record, markdown_path, markdown)
    return json_path, markdown_path

def _write_pair(json_path: Path, record: dict[str, Any], markdown_path: Path,
                markdown: str) -> None:
    output_dir = json_path.parent
    json_fd, json_temp = tempfile.mkstemp(prefix=".author-", suffix=".json", dir=output_dir)
    markdown_temp = None
    try:
        with os.fdopen(json_fd, "w", encoding="utf-8") as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        markdown_fd, markdown_temp = tempfile.mkstemp(prefix=".author-", suffix=".md", dir=output_dir)
        with os.fdopen(markdown_fd, "w", encoding="utf-8") as stream:
            stream.write(markdown)
        if json_path.exists() or markdown_path.exists():
            raise FileExistsError("Refusing to overwrite existing draft")
        # Exclusive publication is also required when two invocations race after
        # the preflight check. Both temporary files live on the output filesystem.
        os.link(json_temp, json_path)
        try:
            os.link(markdown_temp, markdown_path)
        except BaseException:
            json_path.unlink()
            raise
    finally:
        Path(json_temp).unlink(missing_ok=True)
        if markdown_temp is not None:
            Path(markdown_temp).unlink(missing_ok=True)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect_parser = sub.add_parser("inspect", help="compare an offline URL, DOI, arXiv id, or title")
    inspect_parser.add_argument("input")
    impact_parser = sub.add_parser("impact", help="inspect explicit incoming references")
    impact_parser.add_argument("source_id", nargs="?")
    impact_parser.add_argument("--kind", choices=OBJECT_KINDS)
    impact_parser.add_argument("--id")
    draft_parser = sub.add_parser("new-study", help="write a minimal editable draft outside the canonical tree")
    draft_parser.add_argument("slug")
    draft_parser.add_argument("--title", required=True)
    draft_parser.add_argument("--kind", required=True)
    draft_parser.add_argument("--out", type=Path, required=True)
    workspace_parser = sub.add_parser("draft-from-workspace",
                                      help="render a private workspace into an outside-repo author draft")
    workspace_parser.add_argument("--input", type=Path, required=True)
    workspace_parser.add_argument("--slug", required=True)
    workspace_parser.add_argument("--title", required=True)
    workspace_parser.add_argument("--kind", required=True)
    workspace_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            print(json.dumps(inspect(args.input), ensure_ascii=False, indent=2))
        elif args.command == "impact":
            object_id = args.id or args.source_id
            object_kind = args.kind or "material"
            if not object_id:
                raise ValueError("impact requires SOURCE_ID or --id with --kind")
            if args.id and args.source_id:
                raise ValueError("Specify either SOURCE_ID or --id with --kind, not both")
            if object_kind == "material" and not args.kind:
                print(json.dumps(impact(object_id), ensure_ascii=False, indent=2))
            else:
                result = deep_impact(object_kind, object_id)
                print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "new-study":
            json_path, markdown_path = create_draft(args.slug, args.title, args.kind, args.out)
            print(f"wrote draft JSON: {json_path}")
            print(f"wrote draft Markdown: {markdown_path}")
            print("Draft is outside the canonical study tree. Review it before moving it into study/entries/.")
        else:
            json_path, markdown_path = draft_from_workspace(
                args.input, args.slug, args.title, args.kind, args.out
            )
            print(f"wrote draft JSON: {json_path}")
            print(f"wrote draft Markdown: {markdown_path}")
            print("Draft contains private workspace material; review authorship, evidence, and disclosure before publication.")
    except (ValueError, FileExistsError, RuntimeError, OSError) as exc:
        print(f"author error: {exc}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
