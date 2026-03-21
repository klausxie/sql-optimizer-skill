"""
XML Utility Functions

Consolidated utilities for XML namespace handling used across the codebase.
"""

from __future__ import annotations


def _local_name(tag: str) -> str:
    """Strip XML namespace prefix from a tag.

    Handles tags in the form {namespace}localname by extracting just the local name.
    """
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _qualify_ref(namespace: str, refid: str | None) -> str:
    """Qualify a fragment reference with namespace.

    If the ref already contains a dot (already qualified), returns it unchanged.
    Otherwise, prepends the namespace if present.
    """
    ref = str(refid or "").strip()
    if not ref:
        return ""
    if "." in ref:
        return ref
    return f"{namespace}.{ref}" if namespace else ref
