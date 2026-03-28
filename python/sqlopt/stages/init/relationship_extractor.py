"""Extract inter-table relationships and hotspots from SQL text (app-level, not DB FK)."""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

from sqlopt.contracts.init import SQLUnit, TableHotspot, TableRelationship
from sqlopt.stages.init.table_extractor import extract_table_references_from_sql

_FK_NAMING = re.compile(r"^(?P<table>\w+)[_](?P<column>id)$", re.IGNORECASE)
_PK_NAMES = {"id", "pk", "uuid", "guid"}

_EXPLICIT_JOIN = re.compile(
    r"(?:(?P<join_type>INNER|LEFT|RIGHT|FULL|OUTER)?\s*JOIN)"
    r"\s+(?P<target>\w+)"
    r"(?:\s+(?:AS\s+)?(?P<alias>\w+))?"
    r"\s+ON\s+(?P<condition>\w+\.\w+\s*=\s*\w+\.\w+)"
    r"(?=\s*(?:WHERE|AND|OR|JOIN|UNION|ORDER|GROUP|HAVING|LIMIT|\s*$))",
    re.IGNORECASE | re.DOTALL,
)

_IMPLICIT_EQ = re.compile(
    r"(?P<table_a>\w+)\.(?P<col_a>\w+)\s*=\s*(?P<table_b>\w+)\.(?P<col_b>\w+)",
    re.IGNORECASE,
)


def extract_inter_table_relationships(
    sql_units: List[SQLUnit],
) -> Tuple[List[TableRelationship], Dict[str, TableHotspot]]:
    relationships: List[TableRelationship] = []
    co_occurrence: Dict[str, Set[str]] = {}

    for unit in sql_units:
        rels, tables = _extract_from_sql_unit(unit)
        relationships.extend(rels)
        for t in tables:
            co_occurrence.setdefault(t, set()).update(tables)

    hotspots = _build_hotspots(relationships, co_occurrence)
    return relationships, hotspots


def _extract_from_sql_unit(unit: SQLUnit) -> Tuple[List[TableRelationship], Set[str]]:
    table_refs = extract_table_references_from_sql(unit.sql_text)
    all_tables = [t for t, _ in table_refs]
    table_name_set = set(all_tables)
    rels: List[TableRelationship] = []
    seen_rels: Set[Tuple[str, str, str]] = set()

    normalized = _normalize_for_analysis(unit.sql_text)

    for m in _EXPLICIT_JOIN.finditer(normalized):
        condition = m.group("condition").strip()
        eq_matches = list(_IMPLICIT_EQ.finditer(condition))
        if not eq_matches:
            continue

        # Determine source/target by FK location
        src_table: str | None = None
        tgt_table: str | None = None
        src_col: str | None = None
        tgt_col: str | None = None

        for eq_m in eq_matches:
            ca = eq_m.group("col_a")
            cb = eq_m.group("col_b")
            ca_fk = _FK_NAMING.match(ca) is not None
            cb_fk = _FK_NAMING.match(cb) is not None
            ca_pk = ca.lower() in _PK_NAMES
            cb_pk = cb.lower() in _PK_NAMES

            if ca_pk and cb_fk:
                src_table = eq_m.group("table_b")
                tgt_table = eq_m.group("table_a")
                src_col, tgt_col = cb, ca
                break
            if cb_pk and ca_fk:
                src_table = eq_m.group("table_a")
                tgt_table = eq_m.group("table_b")
                src_col, tgt_col = ca, cb
                break

        if src_table is None or tgt_table is None:
            continue

        src_table = src_table.lower()
        tgt_table = tgt_table.lower()
        if src_table == tgt_table:
            continue

        direction, _, _ = _infer_fk_direction(src_col, tgt_col)
        if direction is None:
            continue
        key = tuple(sorted([src_table, tgt_table]))
        if key in seen_rels:
            continue
        seen_rels.add(key)
        rels.append(
            TableRelationship(
                source_table=src_table,
                target_table=tgt_table,
                via_column=src_col,
                target_column=tgt_col,
                direction=direction,
                confidence=_compute_confidence(True, src_col, tgt_col, 1),
                sql_keys=[unit.id],
                join_condition=condition[:100],
                is_explicit_join=True,
            )
        )

    # Track which table pairs were already captured by explicit JOINs
    explicit_pairs: Set[Tuple[str, str]] = set()
    for r in rels:
        explicit_pairs.add((r.source_table.lower(), r.target_table.lower()))

    for m in _IMPLICIT_EQ.finditer(normalized):
        ta, ca = m.group("table_a"), m.group("col_a")
        tb, cb = m.group("table_b"), m.group("col_b")
        if ta.lower() == tb.lower():
            continue
        src_table, tgt_table = ta, tb
        direction, src_col, tgt_col = _infer_fk_direction(ca, cb)
        if direction is None:
            continue
        key = tuple(sorted([src_table.lower(), tgt_table.lower()]))
        if key in seen_rels:
            for r in rels:
                if tuple(sorted([r.source_table.lower(), r.target_table.lower()])) == key and unit.id not in r.sql_keys:
                    r.sql_keys.append(unit.id)
                    r.confidence = min(
                        r.confidence + _compute_confidence(False, src_col, tgt_col, len(r.sql_keys)) * 0.5,
                        1.0,
                    )
            continue
        # Skip implicit if explicit JOIN already captured this table pair
        if (src_table.lower(), tgt_table.lower()) in explicit_pairs or (
            tgt_table.lower(),
            src_table.lower(),
        ) in explicit_pairs:
            continue
        seen_rels.add(key)
        rels.append(
            TableRelationship(
                source_table=src_table,
                target_table=tgt_table,
                via_column=ca,
                target_column=cb,
                direction=direction,
                confidence=_compute_confidence(False, src_col, tgt_col, 1),
                sql_keys=[unit.id],
                join_condition=f"{ta}.{ca} = {tb}.{cb}",
                is_explicit_join=False,
            )
        )

    return rels, table_name_set


def _infer_direction_from_condition(
    condition: str,
) -> Tuple[str, str, str] | Tuple[None, None, None]:
    for m in _IMPLICIT_EQ.finditer(condition):
        ca = m.group("col_a")
        cb = m.group("col_b")
        ca_fk = _FK_NAMING.match(ca) is not None
        cb_fk = _FK_NAMING.match(cb) is not None
        ca_pk = ca.lower() in _PK_NAMES
        cb_pk = cb.lower() in _PK_NAMES
        if ca_pk and cb_fk:
            return _infer_fk_direction(cb, ca)
        if cb_pk and ca_fk:
            return _infer_fk_direction(ca, cb)
    return None, None, None


def _infer_fk_direction(via_column: str, target_column: str) -> Tuple[str, str, str] | Tuple[None, None, None]:
    via_lower = via_column.lower()
    tgt_lower = target_column.lower()

    if tgt_lower in _PK_NAMES:
        return "one-to-many", via_column, target_column
    if via_lower in _PK_NAMES:
        return "many-to-one", via_column, target_column

    m_via = _FK_NAMING.match(via_column)
    if m_via and tgt_lower in _PK_NAMES:
        return "one-to-many", via_column, target_column

    return "many-to-many", via_column, target_column


def _compute_confidence(is_explicit: bool, via_col: str, tgt_col: str, sql_count: int) -> float:
    score = 0.0
    if is_explicit:
        score += 0.4
    if _FK_NAMING.match(via_col):
        score += 0.3
    if tgt_col.lower() in _PK_NAMES:
        score += 0.2
    if sql_count >= 3:
        score += 0.1
    return min(score, 1.0)


def _normalize_for_analysis(sql_text: str) -> str:
    normalized = sql_text
    normalized = re.sub(r"#\{[^}]*\}", " ? ", normalized)
    normalized = re.sub(r"\$\{[^}]*\}", " ? ", normalized)
    normalized = re.sub(r"</?[^>]+>", " ", normalized)
    normalized = re.sub(r"'(?:''|[^'])*'", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _build_hotspots(
    relationships: List[TableRelationship], co_occurrence: Dict[str, Set[str]]
) -> Dict[str, TableHotspot]:
    incoming: Dict[str, int] = {}
    outgoing: Dict[str, int] = {}
    sql_keys_map: Dict[str, List[str]] = {}

    for rel in relationships:
        incoming.setdefault(rel.target_table, 0)
        outgoing.setdefault(rel.source_table, 0)
        incoming[rel.target_table] += 1
        outgoing[rel.source_table] += 1
        sql_keys_map.setdefault(rel.source_table, []).extend(rel.sql_keys)
        sql_keys_map.setdefault(rel.target_table, []).extend(rel.sql_keys)

    hotspots: Dict[str, TableHotspot] = {}
    all_tables = set(incoming) | set(outgoing) | set(co_occurrence)

    for table in all_tables:
        inc = incoming.get(table, 0)
        out = outgoing.get(table, 0)
        co_tables = list(co_occurrence.get(table, set()))
        score = inc * 2.0 + len(co_tables) * 1.0 + out * 0.5

        if score > 10:
            risk = "high"
        elif score > 5:
            risk = "medium"
        else:
            risk = "low"

        seen_keys: Set[str] = set()
        keys: List[str] = []
        for k in sql_keys_map.get(table, []):
            if k not in seen_keys:
                seen_keys.add(k)
                keys.append(k)

        hotspots[table] = TableHotspot(
            table_name=table,
            incoming_ref_count=inc,
            outgoing_ref_count=out,
            co_occurrence_tables=co_tables,
            hotspot_score=score,
            risk_level=risk,
            sql_keys=keys,
        )

    return hotspots
