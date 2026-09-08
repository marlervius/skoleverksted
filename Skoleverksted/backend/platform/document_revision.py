"""Canonical document nodes and compare-and-swap patches for quality work.

The truth layer used to edit a serialized JSON document.  That made escaping,
duplicate text and model supplied locations part of the security boundary.
This module keeps the JSON representation at the edge and gives the verifier
decoded, addressable text nodes instead.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .models import ContentNode, DocumentRevision, RepairPatch, TruthClaim


CONTRACT_VERSION = "3.0"
_REFERENCE_KEY = "$ref"
_SENTENCE_ENDINGS = ".!?"


def content_hash(value: str) -> str:
    return hashlib.sha256(str(value or "").replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _node_id(path: str) -> str:
    return hashlib.sha256(f"content-node:{path}".encode("utf-8")).hexdigest()[:24]


def _path_role(path: str) -> tuple[str, str]:
    lowered = path.casefold()
    if ".variants.støtte" in lowered or ".variants.stoette" in lowered:
        return "variant", "støtte"
    if ".variants.fordypning" in lowered:
        return "variant", "fordypning"
    if ".canonical" in lowered or path.startswith("$.canonical"):
        return "canonical", "standard"
    if "worksheet" in lowered or "oppgave" in lowered:
        return "worksheet", "felles"
    if "language_exercises" in lowered:
        return "language_exercises", "felles"
    if "faktarapport" in lowered or "teacher" in lowered:
        return "teacher_guide", "felles"
    return "content", "felles"


def _normalise_legacy_standard(value: Any) -> Any:
    """Convert only equal legacy standard copies to an explicit reference.

    A different legacy value is retained: it is independent material and must
    be checked independently.  The function is idempotent and never discards
    teacher content.
    """
    if not isinstance(value, dict):
        return value
    copied = {key: _normalise_legacy_standard(item) for key, item in value.items()}
    canonical = copied.get("canonical")
    variants = copied.get("variants")
    if isinstance(variants, dict) and "standard" in variants and canonical is not None:
        standard = variants.get("standard")
        if standard == canonical:
            copied["variants"] = {**variants, "standard": {_REFERENCE_KEY: "$.canonical"}}
    return copied


def _parse(content: str) -> tuple[Any, bool]:
    try:
        parsed = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return content, False
    if not isinstance(parsed, (dict, list)):
        return content, False
    return _normalise_legacy_standard(parsed), True


def _path_child(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}"


def _nodes(value: Any, path: str = "$") -> Iterable[ContentNode]:
    if isinstance(value, str):
        role, variant = _path_role(path)
        yield ContentNode(
            node_id=_node_id(path), path=path, role=role, variant=variant,
            content=value, content_hash=content_hash(value),
        )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _nodes(item, _path_child(path, index))
        return
    if isinstance(value, dict):
        if set(value) == {_REFERENCE_KEY}:
            return
        for key, item in value.items():
            yield from _nodes(item, _path_child(path, str(key)))


def build_document_revision(content: str, *, parent_revision_id: str = "") -> DocumentRevision:
    parsed, structured = _parse(content)
    if structured:
        nodes = list(_nodes(parsed))
        canonical = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    else:
        role, variant = _path_role("$")
        nodes = [ContentNode(
            node_id=_node_id("$"), path="$", role=role, variant=variant,
            content=str(content), content_hash=content_hash(str(content)),
        )]
        canonical = str(content)
    digest = content_hash(canonical)
    return DocumentRevision(
        revision_id=digest[:24],
        parent_revision_id=parent_revision_id,
        contract_version=CONTRACT_VERSION,
        document_hash=digest,
        nodes=nodes,
    )


def canonical_document_content(content: str) -> str:
    """Return JSON with canonical/standard duplication removed when possible."""
    parsed, structured = _parse(content)
    if not structured:
        return str(content)
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def _normalise_path(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text == "canonical":
        return "$.canonical"
    if text.startswith("$"):
        return text
    return "$." + text.lstrip(".")


def _context_hash(value: str, start: int, end: int) -> str:
    return content_hash(value[max(0, start - 120):min(len(value), end + 120)])


def bind_claim(claim: TruthClaim, revision: DocumentRevision) -> TruthClaim:
    """Bind a model claim to exactly one decoded node, or leave it unbound.

    A guessed field path never wins over text.  If a path has several matching
    leaves, the exact span still has to identify one leaf.  Ambiguity remains a
    contract failure and cannot trigger a global repair.
    """
    exact = claim.exact_text.strip()
    requested = _normalise_path(claim.field_path)
    candidates = revision.nodes
    if requested:
        candidates = [node for node in candidates if node.path == requested or node.path.startswith(requested + ".") or node.path.startswith(requested + "[")]
    matches = [node for node in candidates if exact and node.content.count(exact) == 1]
    if len(matches) != 1 and not requested:
        matches = [node for node in revision.nodes if exact and node.content.count(exact) == 1]
    if len(matches) != 1:
        return claim.model_copy(update={"node_id": "", "node_path": "", "node_revision": "", "context_hash": ""})
    node = matches[0]
    start = node.content.find(exact)
    stable_claim_id = hashlib.sha256(f"claim:{node.path}:{exact.casefold()}".encode("utf-8")).hexdigest()[:24]
    return claim.model_copy(update={
        "id": stable_claim_id,
        "node_id": node.node_id,
        "node_path": node.path,
        "node_revision": node.content_hash,
        "context_hash": _context_hash(node.content, start, start + len(exact)),
        "proposition": claim.proposition or claim.claim,
        "field_path": node.path,
        "variant": node.variant,
    })


def bind_claims(claims: Iterable[TruthClaim], revision: DocumentRevision) -> list[TruthClaim]:
    return [bind_claim(claim, revision) for claim in claims]


def _path_tokens(path: str) -> list[str | int]:
    if path == "$":
        return []
    tokens: list[str | int] = []
    for key, index in re.findall(r"\.([^\.\[]+)|\[(\d+)\]", path[1:]):
        tokens.append(int(index) if index else key)
    return tokens


def _set_path(payload: Any, path: str, replacement: str) -> Any:
    tokens = _path_tokens(path)
    if not tokens:
        return replacement
    current = payload
    for token in tokens[:-1]:
        current = current[token]  # type: ignore[index]
    current[tokens[-1]] = replacement  # type: ignore[index]
    return payload


def _complete_sentence_span(value: str, exact: str) -> tuple[int, int] | None:
    if value.count(exact) != 1:
        return None
    start = value.find(exact)
    end = start + len(exact)
    before = start - 1
    while before >= 0 and value[before] in " \t":
        before -= 1
    if before >= 0 and value[before] not in _SENTENCE_ENDINGS + "\n\r":
        return None
    if end < len(value) and value[end] in _SENTENCE_ENDINGS:
        end += 1
    elif not exact.endswith(tuple(_SENTENCE_ENDINGS)):
        return None
    if end < len(value) and not value[end].isspace():
        return None
    return start, end


def _remove_span(value: str, span: tuple[int, int]) -> str:
    start, end = span
    before, after = value[:start], value[end:]
    if before.endswith("\n") or after.startswith("\n"):
        return (before.rstrip(" \t") + after.lstrip(" \t")).strip()
    return (before.rstrip(" \t") + " " + after.lstrip(" \t")).strip()


def build_repair_patch(claim: TruthClaim) -> tuple[RepairPatch | None, str]:
    if not claim.node_id or not claim.node_revision or not claim.exact_text.strip():
        return None, "anchor_mismatch"
    before = claim.exact_text.strip()
    if claim.action == "qualify" and claim.replacement.strip():
        after = claim.replacement.strip()
    elif claim.action == "remove":
        after = ""
    else:
        return None, "no_safe_patch"
    return RepairPatch(
        node_id=claim.node_id,
        expected_revision=claim.node_revision,
        claim_ids=[claim.id],
        before=before,
        after=after,
        reason=claim.evidence or "Automatisk reparasjon av uverifisert påstand.",
        source_ids=[],
    ), ""


@dataclass(frozen=True)
class PatchResult:
    content: str
    applied: bool
    code: str = ""


def apply_repair_patch(content: str, patch: RepairPatch) -> PatchResult:
    """Apply one exact node patch with a content-hash compare-and-swap."""
    revision = build_document_revision(content)
    node = next((item for item in revision.nodes if item.node_id == patch.node_id), None)
    if node is None or node.content_hash != patch.expected_revision:
        return PatchResult(content, False, "anchor_mismatch")
    if node.content.count(patch.before) != 1:
        return PatchResult(content, False, "anchor_mismatch")
    if patch.after:
        replacement = patch.after
        candidate_node = node.content.replace(patch.before, replacement, 1)
    else:
        span = _complete_sentence_span(node.content, patch.before)
        if span is None:
            return PatchResult(content, False, "partial_anchor")
        candidate_node = _remove_span(node.content, span)
    # A patch must not turn an obligatory renderable node into a placeholder or
    # an empty field.  The orchestrator then asks for a source based
    # replacement or returns one focused review decision.
    if (
        "[Utelatt:" in candidate_node
        or (node.role in {"canonical", "worksheet"} and node.content.strip() and not candidate_node.strip())
        or (len(revision.nodes) == 1 and node.content.strip() and not candidate_node.strip())
    ):
        return PatchResult(content, False, "learning_requirement_lost")
    parsed, structured = _parse(content)
    if not structured:
        return PatchResult(candidate_node, True)
    _set_path(parsed, node.path, candidate_node)
    encoded = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    return PatchResult(encoded, True)
