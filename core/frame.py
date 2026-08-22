"""The frame-path matcher. PREDICATE-GRAMMAR.md sec 3.

Segments: identifier (a literal key), * (any single mapping key), [] (any single sequence
index), ** (any depth, including zero levels). A leading 'state.' root is stripped before
matching. A pattern that matches nothing is an error, never a vacuous pass.
"""
from __future__ import annotations

import re
from typing import Any

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WILDCARDS = frozenset({"*", "[]", "**"})


class FramePathError(Exception):
    pass


class FrameSyntaxError(FramePathError):
    """The pattern is not a valid sequence of identifier / * / [] / ** segments."""


class FrameMatchError(FramePathError):
    """The pattern is syntactically valid but matched no concrete path in the snapshot."""


class FrameResolutionError(FramePathError):
    """A concrete path (as returned by match_paths) did not resolve against the snapshot passed
    to get_path -- the key/index is missing, or a step subscripts a non-container. Typed the same
    way core/predicates.py's PathError is typed for the identical situation (sec 2.3): an
    unresolvable path is a located, catchable error, never a bare KeyError/IndexError/TypeError
    that would crash the caller."""


def parse_pattern(pattern: str) -> list[str]:
    """Validate and split a frame-path pattern into segments. Strips a leading 'state.' root."""
    if pattern is None or not pattern.strip():
        raise FrameSyntaxError(f"empty frame path: {pattern!r}")
    p = pattern
    if p == "state":
        return []
    if p.startswith("state."):
        p = p[len("state."):]
    if not p:
        raise FrameSyntaxError(f"empty frame path after stripping 'state.': {pattern!r}")
    segments = p.split(".")
    for seg in segments:
        if seg in _WILDCARDS:
            continue
        if not _IDENTIFIER.match(seg):
            raise FrameSyntaxError(f"invalid segment {seg!r} in frame path {pattern!r}")
    return segments


def match_paths(pattern: str, snapshot: Any, require_match: bool = True) -> list[tuple]:
    """Return every concrete path (pre.-stripped, as a tuple of keys/indices) that `pattern`
    matches in `snapshot`. Raises FrameMatchError if nothing matches and require_match is True
    (the default -- callers doing config-driven masking pass require_match=False)."""
    segments = parse_pattern(pattern)
    results: list[tuple] = []
    _match(segments, snapshot, (), results)
    if not results and require_match:
        raise FrameMatchError(f"frame path {pattern!r} matched nothing")
    return results


def _match(segments: list[str], node: Any, prefix: tuple, results: list[tuple]) -> None:
    if not segments:
        results.append(prefix)
        return

    seg, rest = segments[0], segments[1:]

    if seg == "**":
        _match(rest, node, prefix, results)  # zero levels of depth
        if isinstance(node, dict):
            for k, v in node.items():
                _match(segments, v, prefix + (k,), results)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                _match(segments, v, prefix + (i,), results)
        return

    if seg == "*":
        if isinstance(node, dict):
            for k, v in node.items():
                _match(rest, v, prefix + (k,), results)
        return

    if seg == "[]":
        if isinstance(node, list):
            for i, v in enumerate(node):
                _match(rest, v, prefix + (i,), results)
        return

    # plain identifier
    if isinstance(node, dict) and seg in node:
        _match(rest, node[seg], prefix + (seg,), results)


def get_path(snapshot: Any, path: tuple) -> Any:
    """Resolve a concrete path (as returned by match_paths) to its value in snapshot. Raises
    FrameResolutionError -- not a bare KeyError/IndexError/TypeError -- if a step does not
    resolve, consistent with how core/predicates.py's evaluate() turns the same underlying
    failures into a typed PathError rather than letting them crash the caller."""
    node = snapshot
    try:
        for key in path:
            node = node[key]
    except (KeyError, IndexError, TypeError) as e:
        raise FrameResolutionError(f"path {path!r} did not resolve: {e!r}") from e
    return node
