import itertools

from app.redis_client import redis_client
from app.service.geo.match_input_tip import match_locations_batch_exact
from app.service.core.status_arrange_pho import query_characters_by_path, query_by_status, convert_path_str
from app.common.path import QUERY_DB_USER, DIALECTS_DB_USER
from app.common.constants import COLUMN_VALUES, TABLE_COLUMN_SCHEMAS

import json
import hashlib
from typing import List, Dict, Optional, Any

from app.service.geo.getloc_by_name_region import query_dialect_abbreviations


def process_chars_status(path_strings, column, combine_query, exclude_columns=None, table="characters"):
    """Process path query strings and return matched character sets."""
    result = []

    if isinstance(path_strings, str):
        path_strings = [path_strings]

    if not path_strings:
        return result

    all_query_strings = []
    query_metadata = []

    schema = TABLE_COLUMN_SCHEMAS.get(table, TABLE_COLUMN_SCHEMAS["characters"])
    col_values = schema.get("column_values", COLUMN_VALUES)
    columns = column or []

    for path_string in path_strings:
        if combine_query:
            value_combinations = []
            for col in columns:
                values = col_values.get(col)
                if values:
                    value_combinations.append(values)

            if value_combinations:
                for value_combination in itertools.product(*value_combinations):
                    query_string = path_string
                    for value, col in zip(value_combination, columns):
                        query_string += f"[{value}]{{{col}}}"

                    all_query_strings.append(query_string)
                    query_metadata.append(
                        {
                            "query_string": query_string,
                            "display_name": convert_path_str(query_string, table_name=table),
                        }
                    )
            else:
                all_query_strings.append(path_string)
                query_metadata.append(
                    {
                        "query_string": path_string,
                        "display_name": convert_path_str(path_string, table_name=table),
                    }
                )
        else:
            all_query_strings.append(path_string)
            query_metadata.append(
                {
                    "query_string": path_string,
                    "display_name": convert_path_str(path_string, table_name=table),
                }
            )

    if len(all_query_strings) > 1:
        from app.service.core.status_arrange_pho import query_characters_by_path_batch

        batch_results = query_characters_by_path_batch(
            all_query_strings,
            exclude_columns=exclude_columns,
            table=table,
        )

        for (_, characters, _), metadata in zip(batch_results, query_metadata):
            if characters:
                result.append(
                    {
                        "query": metadata["display_name"],
                        "char_count": len(characters),
                        "chars": characters,
                    }
                )
    else:
        for metadata in query_metadata:
            characters, _ = query_characters_by_path(
                metadata["query_string"],
                exclude_columns=exclude_columns,
                table=table,
            )
            if characters:
                result.append(
                    {
                        "query": metadata["display_name"],
                        "char_count": len(characters),
                        "chars": characters,
                    }
                )

    return result

def _run_dialect_analysis_sync(
        char_data_list: List[Dict],
        locations: List[str],
        regions: List[str],
        features: List[str],
        region_mode: str = "yindian",
        db_path_dialect: str = DIALECTS_DB_USER,
        db_path_query: str = QUERY_DB_USER
):
    """Run dialect analysis for resolved character sets."""
    locations_new = query_dialect_abbreviations(
        regions,
        locations,
        db_path=db_path_query,
        region_mode=region_mode,
    )
    match_results = match_locations_batch_exact(" ".join(locations_new))

    if not any(res[1] == 1 for res in match_results):
        return []

    unique_abbrs = list({abbr for res in match_results for abbr in res[0]})
    all_results = []

    for item in char_data_list:
        path_str = item.get("query", "unknown_query")
        path_chars = (
            item.get("chars")
            or item.get("漢字")
            or item.get("姹夊瓧")
            or []
        )

        if not path_chars:
            continue

        for feature in features:
            df = query_by_status(
                char_list=path_chars,
                locations=unique_abbrs,
                features=[feature],
                user_input=path_str,
                db_path=db_path_dialect,
            )
            if not df.empty:
                all_results.append(df.to_dict(orient="records"))

    return all_results

# --- 1. 鐢熸垚鍞竴鐨?Cache Key ---
def generate_cache_key(
    path_strings: Any,
    column: Any,
    combine_query: bool,
    exclude_columns: Any = None,
    table: str = "characters",
) -> str:
    """Build a deterministic cache key for charlist queries."""
    safe_path = path_strings if path_strings else []
    safe_col = column if column else []
    safe_exclude = exclude_columns if exclude_columns else []

    if safe_exclude:
        safe_exclude = sorted(safe_exclude)

    key_data = {
        "path": safe_path,
        "col": safe_col,
        "combine": bool(combine_query),
        "exclude": safe_exclude,
        "table": table,
    }

    key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
    return "charlist:" + hashlib.md5(key_str.encode("utf-8")).hexdigest()

# 绶╁瓨璁€鍙?(Async)
async def get_cache(key: str) -> Optional[List[Dict]]:
    try:
        # [OK] 鍔犱笂 await
        cached_val = await redis_client.get(key)
        if cached_val:
            print(f"馃敟 [Redis Cache] Hit: {key}")
            return json.loads(cached_val)
    except Exception as e:
        print(f"[X] Redis Read Error: {e}")
    return None


# 绶╁瓨瀵叆 (Async)
async def set_cache(key: str, data: List[Dict], expire_seconds: int = 600):
    try:
        # [OK] 鍔犱笂 await
        await redis_client.set(key, json.dumps(data), ex=expire_seconds)
        print(f"[SAVE] [Redis Cache] Set: {key}")
    except Exception as e:
        print(f"[X] Redis Write Error: {e}")




