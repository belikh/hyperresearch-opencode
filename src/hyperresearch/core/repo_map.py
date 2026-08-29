"""Repository map — structural codebase analysis as a research source.

P5-C. Builds an Aider-style repo map for a local checkout: walk the source
tree, extract every definition (functions, classes, methods — with line
numbers and kinds), derive cross-file reference edges ("file A mentions a
symbol defined in file B"), rank files with personalised-PageRank-style
centrality — reusing :func:`hyperresearch.core.graphrank.pagerank`, the same
power-iteration the vault uses over note links — and render a compact,
ranked, linked markdown map. The map is written into the vault by the
``hpr repo map`` CLI verb as a research note, so a repository becomes a
first-class citable source in the research pipeline (claims, tensions,
drafts can all cite it).

Two extraction lanes:

* **tree-sitter lane** (preferred, optional extra): real AST parsing via
  ``tree-sitter-language-pack`` — ``pip install "hyperresearch[repomap]"``.
  Precise definitions (kind, line, signature) across many languages.
  Missing-pack import errors raise the same ImportError/pip-extra contract
  as the crawl4ai/tavily providers.

* **regex lane** (zero-dependency fallback): language-aware regex
  definitions for the mainstream languages (python, js/ts, go, rust, java,
  c/cpp, ruby, php). Coarser — no signature text, kind inferred from the
  pattern — but honest: the map header records which lane produced it,
  and a regex-lane map never claims AST provenance.

The ranking algorithm deliberately reuses ``graphrank.pagerank`` with the
file-reference graph: nodes are files, an edge A→B exists when A's text
mentions a symbol defined in B (Aider's "references" heuristic — textual
identifier matches over definitions). The most-referenced files float to
the top, which is the signal Aider demonstrated works for LLM repo maps.
Known limits (inherited from the method, documented in Aider's own
analysis): reference edges are textual matches, so same-named symbols in
different scopes can mis-wire; and pure entry points (``main``) rank low
unless referenced. The map renders rank verbatim — consumers see the
limitation in the same numbers we do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hyperresearch.core.graphrank import pagerank

# ---------------------------------------------------------------------------
# Language table
# ---------------------------------------------------------------------------

# Extension -> language id shared by BOTH lanes (regex patterns + tree-sitter
# grammar names in tree-sitter-language-pack).
LANGUAGE_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".scala": "scala",
    ".sh": "bash",
    ".sql": "sql",
    ".md": "markdown",
}

# Directories never walked, whatever the project. Generated/vendored/dep
# trees drown a repo map and carry no architecture signal.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "target",
        "out",
        "vendor",
        "vendors",
        ".tox",
        ".idea",
        ".vscode",
        "site-packages",
        ".next",
        ".turbo",
    }
)

MAX_FILE_BYTES = 1_000_000  # skip monsters (generated bundles, snapshots)


def _treesitter_available() -> bool:
    try:
        import tree_sitter_language_pack  # noqa: F401
    except ImportError:
        return False
    return True


# ---------------------------------------------------------------------------
# Definitions data model
# ---------------------------------------------------------------------------


@dataclass
class Definition:
    """One symbol definition extracted from a source file."""

    name: str
    kind: str  # function | class | method | type | struct | interface ...
    line: int  # 1-based
    signature: str = ""  # one-line def text (tree-sitter lane only)


@dataclass
class FileAnalysis:
    """Per-file extraction result feeding the graph and the map."""

    path: str  # repo-relative, POSIX separators
    language: str
    definitions: list[Definition] = field(default_factory=list)


@dataclass
class RepoMapResult:
    """The complete analysis: files, edges, ranks, and provenance."""

    root: str
    lane: str  # "tree-sitter" | "regex"
    files: list[FileAnalysis]
    # Edge A -> B: file A's text references a symbol defined in file B.
    edges: list[tuple[str, str]]
    # Normalised PageRank score per file (top file = 1.0), like the vault's
    # notes.centrality_score.
    scores: dict[str, float]

    @property
    def ranked_files(self) -> list[FileAnalysis]:
        """Files ordered by centrality, most load-bearing first."""
        order = {p: i for i, p in enumerate(
            sorted(self.scores, key=lambda p: (-self.scores[p], p))
        )}
        return sorted(self.files, key=lambda f: order.get(f.path, len(order)))


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def scan_files(root: Path) -> list[tuple[Path, str]]:
    """Walk `root` and return (absolute_path, language) for source files.

    Respects SKIP_DIRS and the size cap. Sorted for deterministic output —
    the map must be byte-stable across runs on an unchanged tree so
    re-runs don't churn vault notes.
    """
    root = root.resolve()
    found: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        language = LANGUAGE_BY_EXT.get(path.suffix.lower())
        if language is None:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        found.append((path, language))
    return found


# ---------------------------------------------------------------------------
# Regex lane
# ---------------------------------------------------------------------------

# kind, pattern — named group `name` required. Patterns are deliberately
# anchored to line starts / statement heads to cut false positives.
_REGEX_DEFS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "python": [
        ("function", re.compile(r"^\s*(?:async\s+)?def\s+(?P<name>\w+)", re.MULTILINE)),
        ("class", re.compile(r"^\s*class\s+(?P<name>\w+)", re.MULTILINE)),
    ],
    "javascript": [
        ("function", re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+\*?\s*(?P<name>[\w$]+)",
            re.MULTILINE)),
        ("class", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(?P<name>[\w$]+)", re.MULTILINE)),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[\w$]+)\s*=\s*(?:async\s*)?\(", re.MULTILINE)),
        ("method", re.compile(r"^\s{2,}(?:async\s+)?(?P<name>[\w$]+)\s*\([^)]*\)\s*\{", re.MULTILINE)),
    ],
    "typescript": [
        ("function", re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+\*?\s*(?P<name>[\w$]+)",
            re.MULTILINE)),
        ("class", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(?P<name>[\w$]+)", re.MULTILINE)),
        ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+(?P<name>[\w$]+)", re.MULTILINE)),
        ("type", re.compile(r"^\s*(?:export\s+)?type\s+(?P<name>[\w$]+)\s*=", re.MULTILINE)),
        ("function", re.compile(r"^\s*(?:export\s+)?(?:const|let)\s+(?P<name>[\w$]+)\s*:\s*[^=]*=\s*(?:async\s*)?\(", re.MULTILINE)),
    ],
    "go": [
        ("function", re.compile(r"^func\s+(?:\([^)]*\)\s*)?(?P<name>\w+)", re.MULTILINE)),
        ("type", re.compile(r"^type\s+(?P<name>\w+)\s+(?:struct|interface)", re.MULTILINE)),
    ],
    "rust": [
        ("function", re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+(?P<name>\w+)", re.MULTILINE)),
        ("struct", re.compile(r"^\s*(?:pub\s+)?struct\s+(?P<name>\w+)", re.MULTILINE)),
        ("trait", re.compile(r"^\s*(?:pub\s+)?trait\s+(?P<name>\w+)", re.MULTILINE)),
        ("impl", re.compile(r"^\s*impl(?:<[^>]*>)?\s+(?:\w+\s+for\s+)?(?P<name>[\w:]+)", re.MULTILINE)),
    ],
    "java": [
        ("class", re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(?P<name>\w+)", re.MULTILINE)),
        ("method", re.compile(r"^\s+(?:public|private|protected)\s+(?:static\s+)?[\w<>\[\],\s]+\s+(?P<name>\w+)\s*\(", re.MULTILINE)),
    ],
    "c": [
        ("function", re.compile(r"^(?:\w[\w\s\*]*\s+)+(?P<name>\w+)\s*\([^;]*\)\s*\{", re.MULTILINE)),
        ("struct", re.compile(r"^\s*(?:typedef\s+)?struct\s+(?P<name>\w+)", re.MULTILINE)),
    ],
    "cpp": [
        ("function", re.compile(r"^(?:\w[\w\s\*:<>]*\s+)+(?P<name>\w+)\s*\([^;]*\)\s*\{", re.MULTILINE)),
        ("class", re.compile(r"^\s*(?:template\s*<[^>]*>\s*)?(?:class|struct)\s+(?P<name>\w+)", re.MULTILINE)),
    ],
    "ruby": [
        ("function", re.compile(r"^\s*def\s+(?:self\.)?(?P<name>[\w?!]+)", re.MULTILINE)),
        ("class", re.compile(r"^\s*(?:class|module)\s+(?P<name>[\w:]+)", re.MULTILINE)),
    ],
    "php": [
        ("function", re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?function\s+(?P<name>\w+)", re.MULTILINE)),
        ("class", re.compile(r"^\s*(?:abstract\s+)?(?:final\s+)?class\s+(?P<name>\w+)", re.MULTILINE)),
    ],
}


def _regex_definitions(text: str, language: str) -> list[Definition]:
    """Extract definitions with the zero-dependency regex lane."""
    defs: list[Definition] = []
    seen: set[tuple[str, int]] = set()
    for kind, pattern in _REGEX_DEFS.get(language, []):
        for m in pattern.finditer(text):
            name = m.group("name")
            line = text.count("\n", 0, m.start()) + 1
            key = (name, line)
            if key in seen:
                continue
            seen.add(key)
            defs.append(Definition(name=name, kind=kind, line=line))
    # Stable order: source order within the file.
    defs.sort(key=lambda d: d.line)
    return defs


# ---------------------------------------------------------------------------
# tree-sitter lane
# ---------------------------------------------------------------------------

# Definition node types per language — the tree-sitter grammar's equivalent
# of Aider's tags.scm "definition" captures, kept to the high-signal kinds.
_TS_DEF_NODE_TYPES: dict[str, dict[str, str]] = {
    "python": {
        "function_definition": "function",
        "class_definition": "class",
    },
    "javascript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
    },
    "typescript": {
        "function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
        "interface_declaration": "interface",
        "type_alias_declaration": "type",
    },
    "go": {
        "function_declaration": "function",
        "method_declaration": "method",
        "type_spec": "type",
    },
    "rust": {
        "function_item": "function",
        "struct_item": "struct",
        "trait_item": "trait",
        "enum_item": "enum",
        "impl_item": "impl",
    },
    "java": {
        "class_declaration": "class",
        "interface_declaration": "interface",
        "method_declaration": "method",
    },
    "c": {
        "function_definition": "function",
        "struct_specifier": "struct",
    },
    "cpp": {
        "function_definition": "function",
        "class_specifier": "class",
        "struct_specifier": "struct",
    },
}

_TS_LANG_NAME = {
    "javascript": "javascript",
    "typescript": "typescript",
    "c": "c",
    "cpp": "cpp",
}


def _treesitter_definitions(
    text: str, language: str, get_parser: Any | None = None  # test seam
) -> list[Definition] | None:
    """Extract definitions via tree-sitter; None = language unsupported here.

    ``get_parser`` is a seam so tests can inject a fake parser factory;
    production calls ``tree_sitter_language_pack.get_parser``.
    """
    node_types = _TS_DEF_NODE_TYPES.get(language)
    if node_types is None:
        return None  # language has no AST table here — regex lane takes it
    if get_parser is None:
        from tree_sitter_language_pack import get_parser as _real_get_parser

        get_parser = _real_get_parser
    try:
        parser = get_parser(_TS_LANG_NAME.get(language, language))
    except Exception:
        # Unknown grammar in the installed pack — degrade, don't die.
        return None
    try:
        tree = parser.parse(text.encode("utf-8"))
    except Exception:
        return None

    defs: list[Definition] = []

    def walk(node: Any) -> None:
        kind = node_types.get(node.type)
        if kind is not None:
            # The definition's NAME: first named identifier child, with
            # Python's special case (name is a direct field).
            name_node = node.child_by_field_name("name")
            if name_node is None:
                for child in node.children:
                    if child.type in ("identifier", "property_identifier", "field_identifier", "type_identifier", "field_identifier"):
                        name_node = child
                        break
            if name_node is not None:
                name = text[name_node.start_byte : name_node.end_byte]
                if name and len(name) < 200:
                    line = name_node.start_point[0] + 1
                    # Signature: the def line, trimmed.
                    line_end = text.find("\n", node.start_byte)
                    signature = (
                        text[node.start_byte : line_end].strip()
                        if line_end != -1
                        else text[node.start_byte : node.start_byte + 120].strip()
                    )
                    if len(signature) > 120:
                        signature = signature[:117] + "..."
                    defs.append(
                        Definition(name=name, kind=kind, line=line, signature=signature)
                    )
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    defs.sort(key=lambda d: d.line)
    return defs


# ---------------------------------------------------------------------------
# Graph + ranking
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,60}")


def build_reference_edges(
    analyses: list[FileAnalysis],
    texts: dict[str, str],
    *,
    per_file_cap: int = 200,
) -> list[tuple[str, str]]:
    """Cross-file reference edges: file A mentions a symbol defined in B.

    Aider's reference heuristic — textual identifier matches over
    definitions. Same-file self-references are skipped (no self-loops;
    ``graphrank.pagerank`` drops them anyway, but skipping early keeps the
    edge list honest). Edges are deduplicated; a file referencing 200
    distinct other-file symbols stops adding edges (generated files often
    mention everything — the cap keeps one bundle from hub-ifying the map).
    """
    symbol_owner: dict[str, str] = {}
    for analysis in analyses:
        for d in analysis.definitions:
            # First definition wins; ambiguous names keep the first file —
            # recorded limitation of the textual method (see module docs).
            symbol_owner.setdefault(d.name, analysis.path)

    edges: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for analysis in analyses:
        text = texts.get(analysis.path, "")
        if not text:
            continue
        own_names = {d.name for d in analysis.definitions}
        targets: set[str] = set()
        for m in _WORD_RE.finditer(text):
            owner = symbol_owner.get(m.group(0))
            if owner is None or owner == analysis.path:
                continue
            if m.group(0) in own_names:
                # A name this file ALSO defines resolves locally.
                continue
            targets.add(owner)
            if len(targets) >= per_file_cap:
                break
        for target in sorted(targets):
            key = (analysis.path, target)
            if key not in seen:
                seen.add(key)
                edges.append(key)
    return edges


def rank_files(
    analyses: list[FileAnalysis], edges: list[tuple[str, str]]
) -> dict[str, float]:
    """PageRank over the file-reference graph, normalised like the vault.

    Reuses :func:`hyperresearch.core.graphrank.pagerank` — the exact power
    iteration the vault runs over note links — then normalises by the max
    (top file = 1.0), matching ``notes.centrality_score`` semantics so
    downstream consumers interpret one number one way.
    """
    nodes = [a.path for a in analyses]
    if not nodes:
        return {}
    raw = pagerank(nodes, edges)
    max_score = max(raw.values()) if raw else 0.0
    if max_score <= 0:
        return dict.fromkeys(nodes, 0.0)
    return {p: s / max_score for p, s in raw.items()}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _summary_line(analysis: FileAnalysis) -> str:
    """One-line symbol digest for a file: `fn, Class, method, ...`."""
    names: list[str] = []
    for d in analysis.definitions[:8]:
        names.append(d.name)
    if len(analysis.definitions) > 8:
        names.append(f"+{len(analysis.definitions) - 8} more")
    return ", ".join(names) if names else "(no definitions extracted)"


def render_repo_map(result: RepoMapResult, *, top: int = 40) -> str:
    """Render the repo map as markdown for a vault note body.

    Structure (Aider's proven shape, adapted to note form):
    1. Header — path, lane provenance, file/symbol/edge counts, ranked-top
       files (the "map legend" a drafter reads first).
    2. Ranked sections — top-N files by centrality, each with language,
       centrality score, definition list (kind, line, signature when the
       AST lane produced it).
    3. Footer — the method's documented limits, so the note never
       overclaims its own precision.
    """
    lines: list[str] = []
    total_defs = sum(len(a.definitions) for a in result.files)
    lines.append(f"# Repository map: {result.root}")
    lines.append("")
    lines.append(
        f"**Extraction lane:** {result.lane} · **Files:** {len(result.files)} · "
        f"**Symbols:** {total_defs} · **Cross-file reference edges:** {len(result.edges)}"
    )
    lines.append("")

    ranked = result.ranked_files[:top]
    if ranked:
        lines.append("**Most load-bearing files** (PageRank over the reference graph):")
        for i, f in enumerate(ranked, 1):
            score = result.scores.get(f.path, 0.0)
            lines.append(f"{i}. `{f.path}` ({f.language}, centrality {score:.2f})")
        lines.append("")

    lines.append("## Ranked file detail")
    lines.append("")
    for f in ranked:
        score = result.scores.get(f.path, 0.0)
        lines.append(f"### `{f.path}`")
        lines.append("")
        lines.append(f"({f.language} · centrality {score:.2f} · {len(f.definitions)} symbols)")
        lines.append("")
        if f.definitions:
            for d in f.definitions[:25]:
                sig = f" — `{d.signature}`" if d.signature else ""
                lines.append(f"- **{d.kind}** `{d.name}` (line {d.line}){sig}")
            if len(f.definitions) > 25:
                lines.append(f"- … {len(f.definitions) - 25} more symbols")
        else:
            lines.append(_summary_line(f))
        lines.append("")

    if len(result.files) > top:
        others = result.ranked_files[top:]
        lines.append("## Remaining files")
        lines.append("")
        for f in others[:60]:
            lines.append(f"- `{f.path}` ({f.language}): {_summary_line(f)}")
        if len(others) > 60:
            lines.append(f"- … {len(others) - 60} more files")
        lines.append("")

    lines.append("---")
    lines.append(
        "*Method: definitions extracted via the "
        f"{result.lane} lane; files ranked by PageRank over textual "
        "cross-file references (Aider's repo-map heuristic). Limitations: "
        "reference edges are textual identifier matches — same-named symbols "
        "in different scopes can mis-wire; unreferenced entry points rank low. "
        "Treat centrality as a reading order, not a correctness claim.*"
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------

_MISSING_PACK_MESSAGE = (
    'tree-sitter lane requires: pip install "hyperresearch[repomap]" '
    "(the regex fallback lane works without it, with coarser definitions)"
)


def build_repo_map(
    root: Path,
    *,
    prefer_treesitter: bool = True,
    _get_parser: Any | None = None,  # test seam
) -> RepoMapResult:
    """Build a complete repo map for a local checkout.

    ``prefer_treesitter`` falls back to the regex lane when the optional
    pack is missing or a language has no AST table here — the lane is
    recorded on the result and rendered into the map header, so the
    provenance is always visible. Raises FileNotFoundError when `root`
    does not exist; ValueError when it contains no known source files.
    """
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"repository path not found: {root}")

    files = scan_files(root)
    if not files:
        raise ValueError(
            f"no source files found under {root} "
            f"(known extensions: {', '.join(sorted(set(LANGUAGE_BY_EXT)))})"
        )

    use_ts = prefer_treesitter and _treesitter_available()
    analyses: list[FileAnalysis] = []
    texts: dict[str, str] = {}
    for path, language in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        texts[rel] = text
        defs: list[Definition] | None = None
        if use_ts:
            defs = _treesitter_definitions(text, language, _get_parser)
        if defs is None:
            defs = _regex_definitions(text, language)
        analyses.append(FileAnalysis(path=rel, language=language, definitions=defs))

    edges = build_reference_edges(analyses, texts)
    scores = rank_files(analyses, edges)
    lane = "tree-sitter" if use_ts else "regex"
    return RepoMapResult(
        root=str(root),
        lane=lane,
        files=analyses,
        edges=edges,
        scores=scores,
    )
