from dataclasses import dataclass, field
from heapq import nsmallest
from typing import Iterable

from sqlalchemy.orm import Session

from app.service.vocabulary.models import TONE_COLUMNS
from app.service.vocabulary.partitions import partition_filter
from app.service.vocabulary.script_variants import (
    build_script_variants,
    standard_word_key,
)


@dataclass(frozen=True)
class VocabularyItem:
    id: int
    standard_word: str
    local_expression: str
    ipa: str
    notes: str
    informations: str
    location_name: str
    location_label: str
    yindian_region: str = ""
    atlas_region: str = ""


@dataclass(frozen=True)
class VocabularyItemsResult:
    items: list[VocabularyItem]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class VocabularyStandardWord:
    key: str
    standard_word: str
    variants: list[str]
    entry_count: int
    location_count: int


@dataclass(frozen=True)
class VocabularyStandardWordsResult:
    standard_words: list[VocabularyStandardWord]
    total: int


@dataclass(frozen=True)
class VocabularyMapPoint:
    location_name: str
    province: str
    city: str
    county: str
    town: str
    administrative_village: str
    natural_village: str
    yindian_region: str
    atlas_region: str
    vocabulary_source: str
    description: str
    other: str
    longitude: float
    latitude: float
    entry_count: int
    t1: str = ""
    t2: str = ""
    t3: str = ""
    t4: str = ""
    t5: str = ""
    t6: str = ""
    t7: str = ""
    t8: str = ""
    t9: str = ""
    t10: str = ""


@dataclass(frozen=True)
class VocabularyMapPointsResult:
    points: list[VocabularyMapPoint]
    total_entries: int
    total_points: int
    omitted_without_coordinates: int


@dataclass(frozen=True)
class VocabularyMapItem:
    id: int
    standard_word: str
    local_expression: str
    ipa: str
    notes: str
    informations: str


@dataclass(frozen=True)
class VocabularyMapItemPoint:
    location_name: str
    province: str
    city: str
    county: str
    town: str
    administrative_village: str
    natural_village: str
    yindian_region: str
    atlas_region: str
    longitude: float
    latitude: float
    entry_count: int
    items: list[VocabularyMapItem]


@dataclass(frozen=True)
class VocabularyMapItemsResult:
    points: list[VocabularyMapItemPoint]
    total_entries: int
    total_points: int
    omitted_without_coordinates: int


@dataclass(frozen=True)
class VocabularyLocationOption:
    location_name: str
    location_label: str
    province: str = ""
    city: str = ""
    yindian_region: str = ""
    atlas_region: str = ""
    yindian_regions: list[str] = field(default_factory=list)
    atlas_regions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VocabularyLocationOptionsResult:
    locations: list[VocabularyLocationOption]
    total: int


SEARCH_FIELD_COLUMNS = {
    "definition": ("e.standard_word",),
    "headword": ("e.local_expression",),
    "pronunciation": ("e.ipa",),
    "detail": ("e.notes", "e.informations"),
    "location": (
        "e.location_name",
        "l.location_name",
        "l.province",
        "l.city",
        "l.county",
        "l.town",
        "l.administrative_village",
        "l.natural_village",
        "l.yindian_region",
        "l.atlas_region",
    ),
}
DEFAULT_SEARCH_FIELDS = ("definition", "headword", "pronunciation", "detail")
DEFAULT_STANDARD_WORD_LIMIT = 100


def _normalize_multi_value(value: str | Iterable[str] | None) -> list[str]:
    if value is None:
        return []
    raw_values = [value] if isinstance(value, str) else list(value)
    normalized = []
    for raw_value in raw_values:
        normalized.extend(part.strip() for part in str(raw_value).split(","))
    return [part for part in normalized if part]


def _normalize_search_fields(search_fields: str | Iterable[str] | None) -> list[str]:
    fields = _normalize_multi_value(search_fields)
    if not fields or "all" in fields:
        return list(DEFAULT_SEARCH_FIELDS)

    invalid = sorted(set(fields).difference(SEARCH_FIELD_COLUMNS))
    if invalid:
        raise ValueError(f"Unsupported search_fields: {', '.join(invalid)}")
    return fields


def _append_like_group(
    *,
    clauses: list[str],
    values: list[str],
    columns: Iterable[str],
    terms: Iterable[str],
) -> None:
    parts = []
    for term in terms:
        pattern = f"%{term}%"
        for column in columns:
            parts.append(f"COALESCE({column}, '') LIKE ?")
            values.append(pattern)
    if parts:
        clauses.append(f"({' OR '.join(parts)})")


def _append_search_like_group(
    *, clauses: list[str], values: list[str], columns: Iterable[str],
    terms: Iterable[str], prefilter_locations: bool = False,
) -> None:
    """Match repeated location metadata once, retaining entry-field OR branches."""
    columns = list(columns)
    terms = list(terms)
    location_columns = [column for column in columns if column.startswith('l.')]
    # COALESCE(NULL, '') LIKE '%%' is true for orphan entries. An identity
    # subquery cannot reproduce that NULL row, so retain the original LEFT JOIN.
    if (not prefilter_locations or not location_columns or not terms
            or any(not term.strip('%') for term in terms)):
        _append_like_group(clauses=clauses, values=values, columns=columns, terms=terms)
        return

    branches: list[str] = []
    entry_columns = [column for column in columns if not column.startswith('l.')]
    if entry_columns:
        _append_like_group(clauses=branches, values=values, columns=entry_columns, terms=terms)
    metadata: list[str] = []
    _append_like_group(
        clauses=metadata, values=values,
        columns=[column.replace('l.', 'p.', 1) for column in location_columns],
        terms=terms,
    )
    branches.append(
        '(e.user_id, e.location_name) IN '
        '(SELECT p.user_id, p.location_name FROM vocabulary_locations p '
        f"WHERE {' AND '.join(metadata)})"
    )
    clauses.append(f"({' OR '.join(branches)})")


def _format_location(row: dict) -> str:
    parts = [
        row["province"],
        row["city"],
        row["county"],
        row["town"],
        row["administrative_village"],
        row["natural_village"],
    ]
    clean_parts = [part for part in parts if part]
    if clean_parts:
        return " · ".join(clean_parts)
    return row["location_name"] or ""


def _location_meta_fields(row: dict) -> dict:
    return {
        "province": row.get("province") or "",
        "city": row.get("city") or "",
        "county": row.get("county") or "",
        "town": row.get("town") or "",
        "administrative_village": row.get("administrative_village") or "",
        "natural_village": row.get("natural_village") or "",
        "yindian_region": row.get("yindian_region") or "",
        "atlas_region": row.get("atlas_region") or "",
    }


def _location_meta_fields_with_vocabulary_metadata(row: dict) -> dict:
    return {
        **_location_meta_fields(row),
        "vocabulary_source": row.get("vocabulary_source") or "",
        "description": row.get("description") or "",
        "other": row.get("other") or "",
    }


def _tone_fields(row: dict) -> dict:
    return {column: row.get(column) or "" for column in TONE_COLUMNS}


def _parse_coordinates(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None
    parts = value.replace("，", ",").split(",")
    if len(parts) < 2:
        return None
    try:
        longitude = float(parts[0].strip())
        latitude = float(parts[1].strip())
    except ValueError:
        return None
    return longitude, latitude


def _row_to_vocabulary_item(row: dict) -> VocabularyItem:
    return VocabularyItem(
        id=int(row["id"]),
        standard_word=row["standard_word"] or "",
        local_expression=row["local_expression"] or "",
        ipa=row["ipa"] or "",
        notes=row["notes"] or "",
        informations=row["informations"] or "",
        location_name=row["location_name"] or "",
        location_label=_format_location(row),
        yindian_region=row.get("yindian_region") or "",
        atlas_region=row.get("atlas_region") or "",
    )


def _row_to_map_item(row: dict) -> VocabularyMapItem:
    return VocabularyMapItem(
        id=int(row["id"]),
        standard_word=row["standard_word"] or "",
        local_expression=row["local_expression"] or "",
        ipa=row["ipa"] or "",
        notes=row["notes"] or "",
        informations=row["informations"] or "",
    )


def _build_filter_clause(
    *,
    q: str | None,
    search_fields: str | Iterable[str] | None,
    locations: str | Iterable[str] | None,
    province: str | None = None,
    city: str | None = None,
    regions: str | Iterable[str] | None = None,
    region_mode: str = "yindian",
    location_scope_first: bool = False,
) -> tuple[str, list[str]]:
    region_clause, region_values = partition_filter(regions, region_mode, alias='p')
    if region_clause:
        # Evaluate paths over locations once, then probe the existing entry identity index.
        # Keep both identity columns: unrelated users may use the same location name.
        region_clause = (
            '(e.user_id, e.location_name) IN '
            '(SELECT p.user_id, p.location_name FROM vocabulary_locations p '
            f'WHERE {region_clause})'
        )
    fields = _normalize_search_fields(search_fields)
    location_terms = _normalize_multi_value(locations)
    clauses: list[str] = []
    values: list[str] = []
    # Exact province/city and partition constraints already have efficient
    # identity plans. Keep their combinations on the previously measured path.
    prefilter_locations = not (province or city or region_clause)
    search_clauses = [] if location_scope_first else clauses
    search_values = [] if location_scope_first else values

    if q and q.strip():
        search_columns = [
            column
            for field in fields
            for column in SEARCH_FIELD_COLUMNS[field]
        ]
        _append_search_like_group(
            clauses=search_clauses,
            values=search_values,
            columns=search_columns,
            terms=build_script_variants(q),
            prefilter_locations=prefilter_locations,
        )

    if location_terms:
        _append_search_like_group(
            clauses=clauses,
            values=values,
            columns=SEARCH_FIELD_COLUMNS["location"],
            terms=location_terms,
            prefilter_locations=prefilter_locations,
        )

    if province:
        clauses.append("l.province = ?")
        values.append(province)
    if city:
        clauses.append("l.city = ?")
        values.append(city)

    if region_clause:
        clauses.append(region_clause)
        values.extend(region_values)

    if location_scope_first:
        clauses.extend(search_clauses)
        values.extend(search_values)

    return " AND ".join(clauses) if clauses else "1=1", values


def _prefer_location_identity_scan(*, q, fields, locations, province, city, regions) -> bool:
    """Measured path for default content search narrowed by literal location text.

    Single-field covering scans, metadata ORs, exact scopes and wildcard paths
    have different costs; leave them to their existing plans.
    """
    if not (
        q and q.strip() and not any(char in q for char in '%_\x00')
        and locations and not any(char in term for term in locations for char in '%_\x00')
        and not (province or city or regions)
        and set(fields) == set(DEFAULT_SEARCH_FIELDS)
    ):
        return False
    # Correlated keyword/scope text can match most rows, making the old
    # covering/grouping path cheaper than content lookups plus sorting.
    # Compare the same script variants that the actual content search uses.
    keywords = [variant.casefold() for variant in build_script_variants(q)]
    return all(keyword not in term.casefold() and term.casefold() not in keyword
               for term in locations for keyword in keywords)


def _filter_uses_locations(where_clause: str) -> bool:
    """过滤条件是否引用了 vocabulary_locations（别名 l.）。

    参数值都以占位符传入，SQL 片段里出现 "l." 只可能来自地点表的列引用。
    """
    return "l." in where_clause


def _prefer_scoped_standard_word_scan(*, q, fields, locations, province, city, regions) -> bool:
    """Measured non-covering headword shapes; retain definition's covering scan.

    This changes index traversal/locality, not substring indexability. Reuse the
    literal/overlap guards without widening entries' separate count policy.
    """
    return set(fields) in ({'headword'}, {'definition', 'headword'}) and _prefer_location_identity_scan(
        q=q, fields=DEFAULT_SEARCH_FIELDS, locations=locations,
        province=province, city=city, regions=regions,
    )


def _append_script_variant_standard_word_filter(
    *,
    clauses: list[str],
    values: list[str],
    standard_words: str | Iterable[str] | None,
    standard_word_key_value: str | None = None,
) -> None:
    words = _normalize_multi_value(standard_words)
    if standard_word_key_value and standard_word_key_value.strip():
        words.append(standard_word_key_value.strip())
    expanded_words = [
        variant
        for word in words
        for variant in build_script_variants(word)
    ]
    unique_words = list(dict.fromkeys(expanded_words))
    if not unique_words:
        return
    placeholders = ",".join(["?"] * len(unique_words))
    clauses.append(f"e.standard_word IN ({placeholders})")
    values.extend(unique_words)


def _location_first_count_sql(
    locations: list[str], fallback_sql: str, fallback_values: list[str],
) -> tuple[str, list[str]]:
    """Count disjoint name/metadata matches with existing covering indexes.

    MIN seeks skip repeated names instead of scanning every entry. Enumerate
    at most 257 names; above 256 distinct names CASE lazily runs the old count.
    This bounds extra work as location cardinality grows, without limiting data.
    Entry location names are NOT NULL. Keep orphan entries in the name branch
    and both identity columns in the metadata branch.
    """
    name_clauses, name_values, meta_clauses, meta_values = [], [], [], []
    _append_like_group(clauses=name_clauses, values=name_values,
                       columns=['n.name'], terms=locations)
    _append_like_group(
        clauses=meta_clauses, values=meta_values,
        columns=[column.replace('l.', 'p.', 1)
                 for column in SEARCH_FIELD_COLUMNS['location'] if column.startswith('l.')],
        terms=locations,
    )
    # The lazy fallback duplicates predicates in one statement. Stay below
    # older SQLite parameter/expression-depth budgets for many search terms.
    if len(name_values) + len(fallback_values) + len(meta_values) > 400:
        return fallback_sql, fallback_values
    sql = (
        'WITH RECURSIVE location_names(name) AS ('
        'SELECT MIN(location_name) FROM vocabulary_entries '
        'UNION ALL SELECT (SELECT MIN(location_name) FROM vocabulary_entries '
        'WHERE location_name > n.name) FROM location_names n '
        'WHERE n.name IS NOT NULL LIMIT 257), '
        'matched_names AS (SELECT n.name FROM location_names n '
        f"WHERE n.name IS NOT NULL AND {' AND '.join(name_clauses)}) "
        'SELECT CASE WHEN EXISTS (SELECT 1 FROM location_names '
        'WHERE name IS NOT NULL LIMIT 1 OFFSET 256) '
        f'THEN ({fallback_sql}) ELSE '
        '(SELECT COUNT(*) FROM vocabulary_entries '
        'WHERE location_name IN (SELECT name FROM matched_names)) + '
        '(SELECT COUNT(*) FROM vocabulary_entries e '
        'WHERE (e.user_id, e.location_name) IN ('
        'SELECT p.user_id, p.location_name FROM vocabulary_locations p '
        f"WHERE {' AND '.join(meta_clauses)} "
        'AND p.location_name NOT IN (SELECT name FROM matched_names))) END'
    )
    return sql, name_values + fallback_values + meta_values


def query_vocabulary_items(
    *,
    session: Session,
    q: str | None = None,
    search_fields: str | Iterable[str] | None = None,
    locations: str | Iterable[str] | None = None,
    province: str | None = None,
    city: str | None = None,
    regions: str | Iterable[str] | None = None,
    region_mode: str = "yindian",
    standard_words: str | Iterable[str] | None = None,
    page: int = 1,
    page_size: int = 50,
    _count_loader=None,
    _count_resolver=None,
) -> VocabularyItemsResult:
    if page < 1:
        raise ValueError("page must be at least 1")
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    if page_size > 200:
        raise ValueError("page_size cannot exceed 200")

    fields = _normalize_search_fields(search_fields)
    location_terms = _normalize_multi_value(locations)
    # Multiple location ORs can cost more than a selective content predicate;
    # retain their original order and automatic count plan.
    location_identity_scan = not standard_words and len(location_terms) == 1 and _prefer_location_identity_scan(
        q=q, fields=fields, locations=location_terms, province=province, city=city, regions=regions,
    )
    where_clause, values = _build_filter_clause(
        q=q,
        search_fields=fields,
        locations=location_terms,
        province=province,
        city=city,
        regions=regions,
        region_mode=region_mode,
        location_scope_first=location_identity_scan,
    )
    clauses = [where_clause]
    _append_script_variant_standard_word_filter(
        clauses=clauses,
        values=values,
        standard_words=standard_words,
    )
    combined_where_clause = " AND ".join(clauses)
    offset = (page - 1) * page_size
    conn = session.connection().connection
    cursor = conn.cursor()
    entry_columns = (
        "e.id, e.standard_word, e.local_expression, e.ipa, e.notes, e.informations, "
        "e.location_name"
    )
    location_columns = (
        "l.coordinates, l.province, l.city, l.county, l.town, "
        "l.administrative_village, l.natural_village, l.yindian_region, l.atlas_region "
    )
    location_join = (
        "LEFT JOIN vocabulary_locations l "
        "ON l.user_id = e.user_id AND l.location_name = e.location_name "
    )
    uses_locations = _filter_uses_locations(combined_where_clause)
    if uses_locations:
        # Metadata filters must run before pagination, including location LIKEs.
        select_sql = (
            f"SELECT {entry_columns}, {location_columns}"
            f"FROM vocabulary_entries e {location_join}"
            f"WHERE {combined_where_clause} "
            "ORDER BY e.id DESC LIMIT ? OFFSET ?"
        )
    else:
        # LIMIT prevents flattening: join metadata for just this page, not every
        # candidate/offset row. Keep LEFT JOIN so orphan entries still appear.
        select_sql = (
            f"SELECT {entry_columns}, {location_columns}"
            f"FROM (SELECT {entry_columns}, e.user_id FROM vocabulary_entries e "
            f"WHERE {combined_where_clause} "
            "ORDER BY e.id DESC LIMIT ? OFFSET ?) e "
            f"{location_join}ORDER BY e.id DESC"
        )
    count_join = location_join if uses_locations else ""
    # Count has no ID ordering requirement. Its narrow identity scan can reject
    # out-of-scope entries before reading content; keep pagination's own plan.
    count_source = (
        'vocabulary_entries e INDEXED BY idx_vocabulary_entries_user_location '
        if location_identity_scan else 'vocabulary_entries e '
    )
    count_sql = (
        f"SELECT COUNT(*) FROM {count_source}"
        f"{count_join}WHERE {combined_where_clause}"
    )
    count_values = values
    if (not (q and q.strip()) and location_terms
            and not (standard_words or province or city or regions)):
        count_sql, count_values = _location_first_count_sql(location_terms, count_sql, values)

    rows = None

    def read_page():
        cursor.execute(select_sql, values + [page_size, offset])
        names = [description[0] for description in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    # Only measured non-covering content shapes may infer a cold first-page
    # count. In particular, definition-only COUNT has a cheaper covering scan.
    page_first = (
        page == 1 and not standard_words
        and set(fields) in ({'headword'}, {'definition', 'headword'})
        and _prefer_location_identity_scan(
            q=q, fields=DEFAULT_SEARCH_FIELDS, locations=location_terms,
            province=province, city=city, regions=regions,
        )
    )

    def execute_count():
        nonlocal rows
        if page_first:
            # Legacy sqlite3 transaction mode does not begin on SELECT. A read
            # savepoint gives the page and a full-page COUNT the same snapshot,
            # including when another connection commits between the two reads.
            cursor.execute('SAVEPOINT vocabulary_first_page')
            try:
                rows = read_page()
                if len(rows) < page_size:
                    return len(rows)
                return cursor.execute(count_sql, count_values).fetchone()[0]
            finally:
                cursor.execute('RELEASE SAVEPOINT vocabulary_first_page')
        cursor.execute(count_sql, count_values)
        return cursor.fetchone()[0]

    # Resolve the existing independent count cache before computing anything.
    # Its miss callback may infer an exact total from a short first page. Keep
    # legacy two-argument loaders count-first for existing service callers.
    if _count_resolver is not None:
        total = _count_resolver(count_sql, count_values, execute_count)
    elif _count_loader is not None:
        total = _count_loader(count_sql, count_values)
    else:
        total = execute_count()
    if offset >= total:
        return VocabularyItemsResult(items=[], total=total, page=page, page_size=page_size)

    if rows is None:
        rows = read_page()
    return VocabularyItemsResult(
        items=[_row_to_vocabulary_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def query_vocabulary_standard_words(
    *,
    session: Session,
    q: str | None = None,
    search_fields: str | Iterable[str] | None = None,
    locations: str | Iterable[str] | None = None,
    province: str | None = None,
    city: str | None = None,
    regions: str | Iterable[str] | None = None,
    region_mode: str = "yindian",
    limit: int | None = DEFAULT_STANDARD_WORD_LIMIT,
) -> VocabularyStandardWordsResult:
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")

    # Reuse normalized fields even when the caller passed a one-shot iterable.
    fields = _normalize_search_fields(search_fields)
    location_terms = _normalize_multi_value(locations)
    where_clause, values = _build_filter_clause(
        q=q,
        search_fields=fields,
        locations=location_terms,
        province=province,
        city=city,
        regions=regions,
        region_mode=region_mode,
    )
    conn = session.connection().connection
    cursor = conn.cursor()
    # 只有过滤条件引用地点表时才需要 JOIN：LEFT JOIN 在 (user_id, location_name)
    # 唯一约束下不会放大行数，结果与省略 JOIN 一致。省略后分组可走覆盖索引有序扫描。
    join_clause = (
        "LEFT JOIN vocabulary_locations l "
        "ON l.user_id = e.user_id AND l.location_name = e.location_name "
        if _filter_uses_locations(where_clause)
        else ""
    )
    # With a partition scope, the identity index avoids scanning every standard word
    # for an empty/small selection. Unscoped queries retain their covering group index.
    entry_source = (
        'vocabulary_entries e INDEXED BY idx_vocabulary_entries_user_location '
        if regions or _prefer_location_identity_scan(
            q=q, fields=fields, locations=location_terms, province=province, city=city, regions=regions,
        ) or _prefer_scoped_standard_word_scan(
            q=q, fields=fields, locations=location_terms, province=province, city=city, regions=regions,
        ) else 'vocabulary_entries e '
    )
    # For unscoped LIKEs on non-covering fields, ordered index traversal causes
    # table lookups for most candidates. Scan once and group only matches.
    # Keep covering scans, selective identity plans, and wildcard paths intact.
    if (q and q.strip() and '%' not in q and '_' not in q
            and not (location_terms or province or city or regions)
            and 'location' not in fields
            and any(field in {'headword', 'pronunciation', 'detail'} for field in fields)):
        entry_source = 'vocabulary_entries e NOT INDEXED '
    select_sql = (
        "SELECT "
        "e.standard_word, e.location_name, COUNT(*) AS entry_count "
        f"FROM {entry_source}"
        f"{join_clause}"
        f"WHERE {where_clause} AND e.standard_word <> '' "
        "GROUP BY e.standard_word, e.location_name"
    )

    cursor.execute(select_sql, values)
    # GROUP BY yields contiguous rows for each spelling; retain only its last key.
    previous_word = previous_key = None
    grouped: dict[str, list] = {}
    for word, location_name, entry_count in cursor:
        if word != previous_word:
            previous_word, previous_key = word, standard_word_key(word)
        key = previous_key
        group = grouped.get(key)
        if group is None:
            # Most normalized words have one spelling and one location. Keep
            # scalars until a second distinct value requires a set/dict.
            group = grouped[key] = [0, None, word]
        group[0] += entry_count
        if location_name:
            if group[1] is None:
                group[1] = location_name
            elif isinstance(group[1], str):
                if group[1] != location_name:
                    group[1] = {group[1], location_name}
            else:
                group[1].add(location_name)
        if isinstance(group[2], str):
            if group[2] != word:
                # Before promotion every previous row belonged to the first
                # spelling, even across multiple locations or other word keys.
                group[2] = {group[2]: group[0] - entry_count, word: entry_count}
        else:
            group[2][word] = group[2].get(word, 0) + entry_count

    def sort_key(key: str) -> tuple:
        entry_count, locations, variant_counts = grouped[key]
        representative = (variant_counts if isinstance(variant_counts, str) else min(
            variant_counts, key=lambda variant: (-variant_counts[variant], variant)))
        location_count = 1 if isinstance(locations, str) else len(locations or ())
        return (-location_count, -entry_count, representative)

    # 先按轻量元组排序再切片：全库有近 4 万个分组，而 limit 通常只有 100，
    # 给最终会被丢弃的分组建 dataclass 是白做功。
    total = len(grouped)
    ordered_keys = (sorted(grouped, key=sort_key) if limit is None
                    else nsmallest(limit, grouped, key=sort_key))

    standard_word_groups = []
    for key in ordered_keys:
        entry_count, locations, variant_counts = grouped[key]
        variants = ([variant_counts] if isinstance(variant_counts, str) else sorted(
            variant_counts, key=lambda variant: (-variant_counts[variant], variant)))
        standard_word_groups.append(
            VocabularyStandardWord(
                key=key,
                standard_word=variants[0],
                variants=variants,
                entry_count=entry_count,
                location_count=1 if isinstance(locations, str) else len(locations or ()),
            )
        )

    return VocabularyStandardWordsResult(
        standard_words=standard_word_groups,
        total=total,
    )


def query_vocabulary_map_points(
    *,
    session: Session,
    q: str | None = None,
    search_fields: str | Iterable[str] | None = None,
    locations: str | Iterable[str] | None = None,
    province: str | None = None,
    city: str | None = None,
    regions: str | Iterable[str] | None = None,
    region_mode: str = "yindian",
) -> VocabularyMapPointsResult:
    fields = _normalize_search_fields(search_fields)
    location_terms = _normalize_multi_value(locations)
    where_clause, values = _build_filter_clause(
        q=q,
        search_fields=fields,
        locations=location_terms,
        province=province,
        city=city,
        regions=regions,
        region_mode=region_mode,
    )
    conn = session.connection().connection
    cursor = conn.cursor()
    # Aggregate narrow identities before fetching wide location metadata.
    inner_join = (
        'LEFT JOIN vocabulary_locations l '
        'ON l.user_id = e.user_id AND l.location_name = e.location_name '
        if _filter_uses_locations(where_clause) else ''
    )
    # Identity-ordered grouping otherwise reads non-covering content through
    # the index for every candidate. Only the measured unscoped literal paths
    # scan directly; narrow scopes and covering/wildcard plans stay automatic.
    table_scan = (
        q and q.strip() and not any(char in q for char in '%_\x00')
        and not (location_terms or province or city or regions)
        and set(fields) in ({'definition'}, {'headword'}, {'definition', 'headword'})
    )
    if table_scan:
        # A literal can still match almost every row. Probe at most 128 recent
        # entries, returning only two scalars, to retain ordered grouping for
        # dense content. This selects a plan, never the scope/result of a query.
        matches, sampled = cursor.execute(
            'SELECT SUM(matched), COUNT(*) FROM ('
            f'SELECT ({where_clause}) AS matched FROM vocabulary_entries e NOT INDEXED '
            'ORDER BY e.id DESC LIMIT 128)', values,
        ).fetchone()
        table_scan = not sampled or (matches or 0) * 4 < sampled * 3
    entry_source = 'vocabulary_entries e NOT INDEXED ' if table_scan else 'vocabulary_entries e '
    select_sql = (
        'SELECT e.location_name, l.coordinates, l.province, l.city, l.county, l.town, '
        'l.administrative_village, l.natural_village, l.yindian_region, l.atlas_region, '
        'l.vocabulary_source, l.description, l.other, '
        + ', '.join(f'l.{column}' for column in TONE_COLUMNS) + ', '
        'e.entry_count, e.first_entry_id FROM ('
        'SELECT e.user_id, e.location_name, COUNT(*) AS entry_count, MIN(e.id) AS first_entry_id '
        f'FROM {entry_source}'
        f'{inner_join}WHERE {where_clause} GROUP BY e.user_id, e.location_name'
        ') e LEFT JOIN vocabulary_locations l '
        'ON l.user_id = e.user_id AND l.location_name = e.location_name '
        'ORDER BY e.first_entry_id ASC'
    )

    cursor.execute(select_sql, values)
    column_names = [description[0] for description in cursor.description]
    rows = [
        {column_names[index]: value for index, value in enumerate(row)}
        for row in cursor.fetchall()
    ]

    points: list[VocabularyMapPoint] = []
    omitted_without_coordinates = 0
    total_entries = 0
    for row in rows:
        entry_count = int(row["entry_count"] or 0)
        total_entries += entry_count
        parsed_coordinates = _parse_coordinates(row["coordinates"])
        if parsed_coordinates is None:
            omitted_without_coordinates += 1
            continue

        longitude, latitude = parsed_coordinates
        points.append(
            VocabularyMapPoint(
                location_name=row["location_name"] or "",
                **_location_meta_fields_with_vocabulary_metadata(row),
                **_tone_fields(row),
                longitude=longitude,
                latitude=latitude,
                entry_count=entry_count,
            )
        )

    return VocabularyMapPointsResult(
        points=points,
        total_entries=total_entries,
        total_points=len(points),
        omitted_without_coordinates=omitted_without_coordinates,
    )


def query_vocabulary_map_items(
    *,
    session: Session,
    standard_words: str | Iterable[str] | None = None,
    q: str | None = None,
    search_fields: str | Iterable[str] | None = None,
    locations: str | Iterable[str] | None = None,
    province: str | None = None,
    city: str | None = None,
    regions: str | Iterable[str] | None = None,
    region_mode: str = "yindian",
    standard_word_key: str | None = None,
) -> VocabularyMapItemsResult:
    selected_standard_words = _normalize_multi_value(standard_words)
    if not selected_standard_words and not (
        standard_word_key and standard_word_key.strip()
    ):
        raise ValueError("standard_words is required")

    where_clause, values = _build_filter_clause(
        q=q,
        search_fields=search_fields,
        locations=locations,
        province=province,
        city=city,
        regions=regions,
        region_mode=region_mode,
    )
    clauses = [where_clause]
    _append_script_variant_standard_word_filter(
        clauses=clauses,
        values=values,
        standard_words=selected_standard_words,
        standard_word_key_value=standard_word_key,
    )
    combined_where_clause = " AND ".join(clauses)
    conn = session.connection().connection
    cursor = conn.cursor()
    select_sql = (
        "SELECT "
        "e.id, e.standard_word, e.local_expression, e.ipa, e.notes, e.informations, "
        "e.location_name, l.coordinates, l.province, l.city, l.county, l.town, "
        "l.administrative_village, l.natural_village, l.yindian_region, l.atlas_region "
        "FROM vocabulary_entries e "
        "LEFT JOIN vocabulary_locations l "
        "ON l.user_id = e.user_id AND l.location_name = e.location_name "
        f"WHERE {combined_where_clause} "
        "ORDER BY e.id ASC"
    )
    cursor.execute(select_sql, values)
    column_names = [description[0] for description in cursor.description]
    rows = [
        {column_names[index]: value for index, value in enumerate(row)}
        for row in cursor.fetchall()
    ]

    grouped_rows: dict[tuple, list[dict]] = {}
    total_entries = 0
    for row in rows:
        total_entries += 1
        key = (
            row["location_name"],
            row["coordinates"],
            row["province"],
            row["city"],
            row["county"],
            row["town"],
            row["administrative_village"],
            row["natural_village"],
            row["yindian_region"],
            row["atlas_region"],
        )
        grouped_rows.setdefault(key, []).append(row)

    points: list[VocabularyMapItemPoint] = []
    omitted_without_coordinates = 0
    for group in grouped_rows.values():
        first_row = group[0]
        parsed_coordinates = _parse_coordinates(first_row["coordinates"])
        if parsed_coordinates is None:
            omitted_without_coordinates += len(group)
            continue
        longitude, latitude = parsed_coordinates
        points.append(
            VocabularyMapItemPoint(
                location_name=first_row["location_name"] or "",
                **_location_meta_fields(first_row),
                longitude=longitude,
                latitude=latitude,
                entry_count=len(group),
                items=[_row_to_map_item(row) for row in group],
            )
        )

    return VocabularyMapItemsResult(
        points=points,
        total_entries=total_entries,
        total_points=len(points),
        omitted_without_coordinates=omitted_without_coordinates,
    )


def query_vocabulary_location_options(
    *, session: Session, regions: str | Iterable[str] | None = None,
    region_mode: str = "yindian", province: str | None = None, city: str | None = None,
) -> VocabularyLocationOptionsResult:
    region_clause, values = partition_filter(regions, region_mode)
    clauses = [region_clause] if region_clause else []
    for column, value in (("province", province), ("city", city)):
        if value:
            clauses.append(f"l.{column} = ?")
            values.append(value)
    where = " AND ".join(clauses) if clauses else "1=1"
    cursor = session.connection().connection.cursor()
    cursor.execute(
        "SELECT l.location_name, l.province, l.city, l.county, l.town, "
        "l.administrative_village, l.natural_village, l.yindian_region, l.atlas_region "
        f"FROM vocabulary_locations l WHERE {where} ORDER BY l.location_name, l.id", values)
    columns = [description[0] for description in cursor.description]
    grouped = {}
    for values_row in cursor:
        row = dict(zip(columns, values_row))
        name = row["location_name"] or ""
        if not name:
            continue
        if name not in grouped:
            grouped[name] = (row, set(), set())
        _, yindian, atlas = grouped[name]
        yindian.add(row["yindian_region"] or "")
        atlas.add(row["atlas_region"] or "")
    locations = [VocabularyLocationOption(
        location_name=name, location_label=_format_location(row),
        province=row["province"] or "", city=row["city"] or "",
        yindian_region=next(iter(yindian)) if len(yindian) == 1 else "",
        atlas_region=next(iter(atlas)) if len(atlas) == 1 else "",
        yindian_regions=sorted(yindian - {""}), atlas_regions=sorted(atlas - {""}),
    ) for name, (row, yindian, atlas) in grouped.items()]
    return VocabularyLocationOptionsResult(locations=locations, total=len(locations))
