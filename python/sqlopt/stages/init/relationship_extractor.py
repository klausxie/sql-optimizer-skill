"""Extract inter-table relationships and hotspots using AST (sqlglot)."""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

import sqlglot
from sqlglot import exp
from sqlopt.contracts.init import SQLUnit, TableHotspot, TableRelationship
from sqlopt.stages.init.table_extractor import extract_table_references_from_sql

_FK_NAMING = re.compile(r"^(?P<table>\w+)[_](?P<column>id)$", re.IGNORECASE)
_PK_NAMES = {"id", "pk", "uuid", "guid"}


def _normalize_table_name(table_expr: str) -> str:
    """Extract last segment after dot (schema.table -> table) and lowercase."""
    return table_expr.split(".")[-1].lower() if table_expr else ""


def _get_table_info(node: exp.Table) -> Tuple[str, str | None, str | None]:
    """Extract (table_name, schema, alias) from a sqlglot Table node."""
    table_name = node.this.this if hasattr(node.this, "this") else str(node.this)
    schema = node.db.this if node.db and hasattr(node.db, "this") else (str(node.db) if node.db else None)
    alias = node.alias.this if node.alias and hasattr(node.alias, "this") else (str(node.alias) if node.alias else None)
    return table_name.lower(), schema.lower() if schema else None, alias


def _resolve_column(col: exp.Column, alias_map: Dict[str, str]) -> Tuple[str | None, str]:
    """Resolve column's table reference to normalized table name via alias_map."""
    table_ref = str(col.table) if col.table else None
    col_name = col.this.this if hasattr(col.this, "this") else str(col.this)
    resolved = alias_map.get(table_ref, table_ref.lower()) if table_ref else None
    return resolved, col_name.lower()


def _extract_tables_and_aliases(sql_text: str) -> Tuple[List[str], Dict[str, str]]:
    """Extract normalized table names and alias->table mapping via AST."""
    try:
        tree = sqlglot.parse_one(sql_text, dialect=None)
    except sqlglot.errors.SqlglotError:
        table_refs = extract_table_references_from_sql(sql_text)
        return [t for t, _ in table_refs], {a: t for t, a in table_refs if a}

    normalized_tables: List[str] = []
    alias_map: Dict[str, str] = {}

    for node in tree.find_all(exp.Table):
        table_name, _schema, alias = _get_table_info(node)
        normalized_tables.append(table_name)
        if alias:
            alias_map[alias] = table_name

    return normalized_tables, alias_map


def _is_fk(col_name: str) -> bool:
    return _FK_NAMING.match(col_name) is not None


def _is_pk(col_name: str) -> bool:
    return col_name.lower() in _PK_NAMES


def _infer_fk_direction(via_col: str, tgt_col: str) -> Tuple[str, str, str] | Tuple[None, None, None]:
    """Infer relationship direction from FK/PK column names."""
    via_lower, tgt_lower = via_col.lower(), tgt_col.lower()
    if tgt_lower in _PK_NAMES:
        return "one-to-many", via_col, tgt_col
    if via_lower in _PK_NAMES:
        return "many-to-one", via_col, tgt_col
    if _FK_NAMING.match(via_col) and tgt_lower in _PK_NAMES:
        return "one-to-many", via_col, tgt_col
    return "many-to-many", via_col, tgt_col


def _compute_confidence(is_explicit: bool, via_col: str, tgt_col: str, sql_count: int) -> float:
    """Compute confidence score for a relationship."""
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


def _extract_from_join(join_node: exp.Join, alias_map: Dict[str, str], sql_key: str) -> List[TableRelationship]:
    """Extract relationships from a single JOIN node via AST."""
    rels = []
    on_cond = join_node.args.get("on")
    if not on_cond:
        return rels

    for eq in on_cond.find_all(exp.EQ):
        left, right = eq.this, eq.expression
        if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
            continue

        left_table, left_col = _resolve_column(left, alias_map)
        right_table, right_col = _resolve_column(right, alias_map)
        if not left_table or not right_table or left_table == right_table:
            continue

        src_table, tgt_table = None, None
        src_col, tgt_col_name = None, None

        if _is_pk(left_col) and _is_fk(right_col):
            src_table, tgt_table = right_table, left_table
            src_col, tgt_col_name = right_col, left_col
        elif _is_pk(right_col) and _is_fk(left_col):
            src_table, tgt_table = left_table, right_table
            src_col, tgt_col_name = left_col, right_col
        else:
            continue

        direction, _, _ = _infer_fk_direction(src_col, tgt_col_name)
        if direction is None:
            continue

        rels.append(
            TableRelationship(
                source_table=src_table,
                target_table=tgt_table,
                via_column=src_col,
                target_column=tgt_col_name,
                direction=direction,
                confidence=_compute_confidence(True, src_col, tgt_col_name, 1),
                sql_keys=[sql_key],
                join_condition=str(on_cond)[:100],
                is_explicit_join=True,
            )
        )
    return rels


def _extract_implicit_rels(
    tree: sqlglot.Expression, alias_map: Dict[str, str], sql_key: str
) -> List[TableRelationship]:
    """Extract implicit relationships from WHERE clause via AST."""
    rels = []
    where_clause = None
    for node in tree.walk():
        if isinstance(node, exp.Where):
            where_clause = node.this
            break
    if not where_clause:
        return rels

    for eq in where_clause.find_all(exp.EQ):
        left, right = eq.this, eq.expression
        if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
            continue

        left_table, left_col = _resolve_column(left, alias_map)
        right_table, right_col = _resolve_column(right, alias_map)
        if not left_table or not right_table or left_table == right_table:
            continue

        src_table, tgt_table = None, None
        src_col, tgt_col_name = None, None

        if _is_pk(left_col) and _is_fk(right_col):
            src_table, tgt_table = right_table, left_table
            src_col, tgt_col_name = right_col, left_col
        elif _is_pk(right_col) and _is_fk(left_col):
            src_table, tgt_table = left_table, right_table
            src_col, tgt_col_name = left_col, right_col
        else:
            continue

        direction, _, _ = _infer_fk_direction(src_col, tgt_col_name)
        if direction is None:
            continue

        rels.append(
            TableRelationship(
                source_table=src_table,
                target_table=tgt_table,
                via_column=src_col,
                target_column=tgt_col_name,
                direction=direction,
                confidence=_compute_confidence(False, src_col, tgt_col_name, 1),
                sql_keys=[sql_key],
                join_condition=f"{left_table}.{left_col} = {right_table}.{right_col}",
                is_explicit_join=False,
            )
        )
    return rels


def extract_inter_table_relationships(
    sql_units: List[SQLUnit],
) -> Tuple[List[TableRelationship], Dict[str, TableHotspot]]:
    """Extract inter-table relationships and hotspots using AST."""
    relationships: List[TableRelationship] = []
    co_occurrence: Dict[str, Set[str]] = {}

    for unit in sql_units:
        rels, tables = _extract_from_sql_unit(unit)
        relationships.extend(rels)
        for t in tables:
            co_occurrence.setdefault(t, set()).update(tables)

    return relationships, _build_hotspots(relationships, co_occurrence)


def _extract_from_sql_unit(unit: SQLUnit) -> Tuple[List[TableRelationship], Set[str]]:
    """Extract relationships from a single SQL unit using AST, with regex fallback."""
    normalized_tables, alias_map = _extract_tables_and_aliases(unit.sql_text)
    table_name_set = set(normalized_tables)
    rels: List[TableRelationship] = []
    seen_rels: Set[Tuple[str, str, str]] = set()

    try:
        tree = sqlglot.parse_one(unit.sql_text, dialect=None)
    except sqlglot.errors.SqlglotError:
        return _extract_regex_fallback(unit)

    for join_node in tree.find_all(exp.Join):
        for rel in _extract_from_join(join_node, alias_map, unit.id):
            key = tuple(sorted([rel.source_table, rel.target_table]))
            if key not in seen_rels:
                seen_rels.add(key)
                rels.append(rel)

    explicit_pairs = {(r.source_table, r.target_table) for r in rels}
    for rel in _extract_implicit_rels(tree, alias_map, unit.id):
        key = tuple(sorted([rel.source_table, rel.target_table]))
        if key in seen_rels:
            for existing in rels:
                if tuple(sorted([existing.source_table, existing.target_table])) == key:
                    if unit.id not in existing.sql_keys:
                        existing.sql_keys.append(unit.id)
                    break
        elif key not in explicit_pairs and (key[1], key[0]) not in explicit_pairs:
            seen_rels.add(key)
            rels.append(rel)

    return rels, table_name_set


def _extract_regex_fallback(unit: SQLUnit) -> Tuple[List[TableRelationship], Set[str]]:
    """Fallback regex-based extraction for malformed SQL."""
    explicit_join_pat = re.compile(
        r"(?:(?P<join_type>INNER|LEFT|RIGHT|FULL|OUTER)?\s*JOIN)"
        r"\s+(?P<target>\w+)"
        r"(?:\s+(?:AS\s+)?(?P<alias>\w+))?"
        r"\s+ON\s+(?P<condition>\w+\.\w+\s*=\s*\w+\.\w+)"
        r"(?=\s*(?:WHERE|AND|OR|JOIN|UNION|ORDER|GROUP|HAVING|LIMIT|\s*$))",
        re.IGNORECASE | re.DOTALL,
    )
    implicit_eq_pat = re.compile(
        r"(?P<table_a>\w+)\.(?P<col_a>\w+)\s*=\s*(?P<table_b>\w+)\.(?P<col_b>\w+)",
        re.IGNORECASE,
    )

    table_refs = extract_table_references_from_sql(unit.sql_text)
    all_tables = [t for t, _ in table_refs]
    table_name_set = set(all_tables)
    alias_map = {a: t for t, a in table_refs if a}
    rels: List[TableRelationship] = []
    seen_rels: Set[Tuple[str, str, str]] = set()

    normalized = _normalize_sql_for_analysis(unit.sql_text)

    for m in explicit_join_pat.finditer(normalized):
        condition = m.group("condition").strip()
        eq_matches = list(implicit_eq_pat.finditer(condition))
        if not eq_matches:
            continue

        src_table: str | None = None
        tgt_table: str | None = None
        src_col: str | None = None
        tgt_col: str | None = None

        for eq_m in eq_matches:
            ca, cb = eq_m.group("col_a"), eq_m.group("col_b")
            ca_fk, cb_fk = _FK_NAMING.match(ca) is not None, _FK_NAMING.match(cb) is not None
            ca_pk, cb_pk = ca.lower() in _PK_NAMES, cb.lower() in _PK_NAMES

            if ca_pk and cb_fk:
                src_table, tgt_table = eq_m.group("table_b"), eq_m.group("table_a")
                src_col, tgt_col = cb, ca
                break
            if cb_pk and ca_fk:
                src_table, tgt_table = eq_m.group("table_a"), eq_m.group("table_b")
                src_col, tgt_col = ca, cb
                break

        if not src_table or not tgt_table:
            continue

        src_table = alias_map.get(src_table.lower(), src_table.lower())
        tgt_table = alias_map.get(tgt_table.lower(), tgt_table.lower())

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

    explicit_pairs = {(r.source_table, r.target_table) for r in rels}

    for m in implicit_eq_pat.finditer(normalized):
        ta, ca = m.group("table_a"), m.group("col_a")
        tb, cb = m.group("table_b"), m.group("col_b")
        if ta.lower() == tb.lower():
            continue

        ta = alias_map.get(ta.lower(), ta.lower())
        tb = alias_map.get(tb.lower(), tb.lower())

        src_table, tgt_table = ta, tb
        direction, src_col, tgt_col = _infer_fk_direction(ca, cb)
        if direction is None:
            continue
        key = tuple(sorted([src_table, tgt_table]))
        if key in seen_rels:
            continue
        if (src_table, tgt_table) in explicit_pairs or (tgt_table, src_table) in explicit_pairs:
            continue
        seen_rels.add(key)
        rels.append(
            TableRelationship(
                source_table=src_table,
                target_table=tgt_table,
                via_column=ca,
                target_column=cb,
                direction=direction,
                confidence=_compute_confidence(False, ca, cb, 1),
                sql_keys=[unit.id],
                join_condition=f"{ta}.{ca} = {tb}.{cb}",
                is_explicit_join=False,
            )
        )

    return rels, table_name_set


def _normalize_sql_for_analysis(sql_text: str) -> str:
    """Normalize SQL text for regex-based analysis."""
    result = sql_text
    result = re.sub(r"#\{[^}]*\}", " ? ", result)
    result = re.sub(r"\$\{[^}]*\}", " ? ", result)
    result = re.sub(r"</?[^>]+>", " ", result)
    result = re.sub(r"'(?:''|[^'])*'", " ", result)
    return re.sub(r"\s+", " ", result).strip()


def _build_hotspots(
    relationships: List[TableRelationship], co_occurrence: Dict[str, Set[str]]
) -> Dict[str, TableHotspot]:
    """Build hotspot analysis from relationships."""
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

        risk = "high" if score > 10 else ("medium" if score > 5 else "low")

        seen_keys: Set[str] = set()
        keys = [k for k in sql_keys_map.get(table, []) if k not in seen_keys and not seen_keys.add(k)]

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
