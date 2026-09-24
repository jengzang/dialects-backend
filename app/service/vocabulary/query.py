from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.service.vocabulary.models import TONE_COLUMNS
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
) -> tuple[str, list[str]]:
    fields = _normalize_search_fields(search_fields)
    location_terms = _normalize_multi_value(locations)
    clauses: list[str] = []
    values: list[str] = []

    if q and q.strip():
        search_columns = [
            column
            for field in fields
            for column in SEARCH_FIELD_COLUMNS[field]
        ]
        _append_like_group(
            clauses=clauses,
            values=values,
            columns=search_columns,
            terms=build_script_variants(q),
        )

    if location_terms:
        _append_like_group(
            clauses=clauses,
            values=values,
            columns=SEARCH_FIELD_COLUMNS["location"],
            terms=location_terms,
        )

    if province:
        clauses.append("l.province = ?")
        values.append(province)
    if city:
        clauses.append("l.city = ?")
        values.append(city)

    return " AND ".join(clauses) if clauses else "1=1", values


def _filter_uses_locations(where_clause: str) -> bool:
    """过滤条件是否引用了 vocabulary_locations（别名 l.）。

    参数值都以占位符传入，SQL 片段里出现 "l." 只可能来自地点表的列引用。
    """
    return "l." in where_clause


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


def query_vocabulary_items(
    *,
    session: Session,
    q: str | None = None,
    search_fields: str | Iterable[str] | None = None,
    locations: str | Iterable[str] | None = None,
    province: str | None = None,
    city: str | None = None,
    standard_words: str | Iterable[str] | None = None,
    page: int = 1,
    page_size: int = 50,
) -> VocabularyItemsResult:
    if page < 1:
        raise ValueError("page must be at least 1")
    if page_size < 1:
        raise ValueError("page_size must be at least 1")
    if page_size > 200:
        raise ValueError("page_size cannot exceed 200")

    where_clause, values = _build_filter_clause(
        q=q,
        search_fields=search_fields,
        locations=locations,
        province=province,
        city=city,
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
    select_sql = (
        "SELECT "
        "e.id, e.standard_word, e.local_expression, e.ipa, e.notes, e.informations, "
        "e.location_name, l.coordinates, l.province, l.city, l.county, l.town, "
        "l.administrative_village, l.natural_village "
        "FROM vocabulary_entries e "
        "LEFT JOIN vocabulary_locations l "
        "ON l.user_id = e.user_id AND l.location_name = e.location_name "
        f"WHERE {combined_where_clause} "
        "ORDER BY e.id DESC LIMIT ? OFFSET ?"
    )
    count_sql = (
        "SELECT COUNT(*) "
        "FROM vocabulary_entries e "
        "LEFT JOIN vocabulary_locations l "
        "ON l.user_id = e.user_id AND l.location_name = e.location_name "
        f"WHERE {combined_where_clause}"
    )

    cursor.execute(select_sql, values + [page_size, offset])
    column_names = [description[0] for description in cursor.description]
    rows = [
        {column_names[index]: value for index, value in enumerate(row)}
        for row in cursor.fetchall()
    ]
    cursor.execute(count_sql, values)
    total = cursor.fetchone()[0]

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
    limit: int | None = DEFAULT_STANDARD_WORD_LIMIT,
) -> VocabularyStandardWordsResult:
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")

    where_clause, values = _build_filter_clause(
        q=q,
        search_fields=search_fields,
        locations=locations,
        province=province,
        city=city,
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
    select_sql = (
        "SELECT "
        "e.standard_word, e.location_name, COUNT(*) AS entry_count "
        "FROM vocabulary_entries e "
        f"{join_clause}"
        f"WHERE {where_clause} AND e.standard_word <> '' "
        "GROUP BY e.standard_word, e.location_name"
    )

    cursor.execute(select_sql, values)
    # 直接按位置解包元组，避免为 5.9 万行各建一个 dict；word_keys 让同一标准词
    # 在一个请求内只换算一次 key。
    word_keys: dict[str, str] = {}
    grouped: dict[str, list] = {}
    for word, location_name, entry_count in cursor.fetchall():
        key = word_keys.get(word)
        if key is None:
            key = word_keys[word] = standard_word_key(word)
        group = grouped.get(key)
        if group is None:
            group = grouped[key] = [0, set(), {}]
        group[0] += entry_count
        if location_name:
            group[1].add(location_name)
        variant_counts = group[2]
        variant_counts[word] = variant_counts.get(word, 0) + entry_count

    def sort_key(key: str) -> tuple:
        entry_count, locations, variant_counts = grouped[key]
        representative = min(
            variant_counts,
            key=lambda variant: (-variant_counts[variant], variant),
        )
        return (-len(locations), -entry_count, representative)

    # 先按轻量元组排序再切片：全库有近 4 万个分组，而 limit 通常只有 100，
    # 给最终会被丢弃的分组建 dataclass 是白做功。
    ordered_keys = sorted(grouped, key=sort_key)
    total = len(ordered_keys)
    if limit is not None:
        ordered_keys = ordered_keys[:limit]

    standard_word_groups = []
    for key in ordered_keys:
        entry_count, locations, variant_counts = grouped[key]
        variants = sorted(
            variant_counts,
            key=lambda variant: (-variant_counts[variant], variant),
        )
        standard_word_groups.append(
            VocabularyStandardWord(
                key=key,
                standard_word=variants[0],
                variants=variants,
                entry_count=entry_count,
                location_count=len(locations),
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
) -> VocabularyMapPointsResult:
    where_clause, values = _build_filter_clause(
        q=q,
        search_fields=search_fields,
        locations=locations,
        province=province,
        city=city,
    )
    conn = session.connection().connection
    cursor = conn.cursor()
    # 分组键只用 e 的两列：地点表的字段由 (user_id, location_name) 唯一确定，
    # 按全部 l.* 列分组会引入 temp b-tree；按这两列分组可复用
    # idx_vocabulary_entries_user_location 的有序扫描，结果等价。
    select_sql = (
        "SELECT "
        "e.location_name, l.coordinates, l.province, l.city, l.county, l.town, "
        "l.administrative_village, l.natural_village, l.yindian_region, l.atlas_region, "
        "l.vocabulary_source, l.description, l.other, "
        + ", ".join(f"l.{column}" for column in TONE_COLUMNS) + ", "
        "COUNT(*) AS entry_count, "
        "MIN(e.id) AS first_entry_id "
        "FROM vocabulary_entries e "
        "LEFT JOIN vocabulary_locations l "
        "ON l.user_id = e.user_id AND l.location_name = e.location_name "
        f"WHERE {where_clause} "
        "GROUP BY e.user_id, e.location_name "
        "ORDER BY first_entry_id ASC"
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


def query_vocabulary_location_options(*, session: Session) -> VocabularyLocationOptionsResult:
    conn = session.connection().connection
    cursor = conn.cursor()
    select_sql = (
        "SELECT "
        "location_name, province, city, county, town, "
        "administrative_village, natural_village, MIN(id) AS first_location_id "
        "FROM vocabulary_locations "
        "GROUP BY "
        "location_name, province, city, county, town, "
        "administrative_village, natural_village "
        "ORDER BY location_name ASC, first_location_id ASC"
    )

    cursor.execute(select_sql)
    column_names = [description[0] for description in cursor.description]
    rows = [
        {column_names[index]: value for index, value in enumerate(row)}
        for row in cursor.fetchall()
    ]

    seen_location_names = set()
    locations: list[VocabularyLocationOption] = []
    for row in rows:
        location_name = row["location_name"] or ""
        if not location_name or location_name in seen_location_names:
            continue
        seen_location_names.add(location_name)
        locations.append(
            VocabularyLocationOption(
                location_name=location_name,
                location_label=_format_location(row),
                province=row.get("province") or "",
                city=row.get("city") or "",
            )
        )

    return VocabularyLocationOptionsResult(
        locations=locations,
        total=len(locations),
    )
