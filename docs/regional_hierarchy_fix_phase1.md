# Regional Hierarchy Query Fix - Phase 1 Complete

## Summary

Successfully fixed 6 API endpoints to support complete hierarchical queries (city, county, township) to avoid ambiguity when querying regions with duplicate names.

## Changes Made

### 1. `/api/villages/semantic/indices` (semantic/composition.py)

**Added Parameters:**
- `city`: 市级过滤（精确匹配）
- `county`: 区县级过滤（精确匹配）
- `township`: 乡镇级过滤（精确匹配）
- Modified `region_name`: 区域名称（模糊匹配，向后兼容）

**Query Changes:**
- Added `city, county, township` columns to SELECT
- Priority 1: Use hierarchy parameters for exact matching
- Priority 2: Use `region_name` for fuzzy matching (backward compatibility)
- Handle 东莞市/中山市 (no county level) with `county IS NULL OR county = ''`

### 2. `/api/villages/character/significance/by-region` (character/significance.py)

**Added Parameters:**
- `city`: 市级过滤（精确匹配）
- `county`: 区县级过滤（精确匹配）
- `township`: 乡镇级过滤（精确匹配）
- Modified `region_name`: Optional, 区域名称（模糊匹配，向后兼容）

**Query Changes:**
- Priority 1: Use hierarchy parameters for exact matching
- Priority 2: Use `region_name` for fuzzy matching across all hierarchy levels
- Handle 东莞市/中山市 (no county level)

### 3. `/api/villages/regional/aggregates/city` (regional/aggregates_realtime.py)

**Function Changes:**
- Renamed parameter `city_name` → `city` in `compute_city_aggregates()`
- Updated semantic_indices query to use `city` column instead of `region_name`
- Updated merge logic to use `city` from query results

**Endpoint Changes:**
- Renamed parameter `city_name` → `city`

### 4. `/api/villages/regional/aggregates/county` (regional/aggregates_realtime.py)

**Function Changes:**
- Added `city` and `county` parameters to `compute_county_aggregates()`
- Kept `city_name` and `county_name` for backward compatibility
- Updated semantic_indices query to use `city, county` columns
- Updated merge logic to use `(city, county)` tuple as key

**Endpoint Changes:**
- Added `city` and `county` parameters
- Kept `city_name` and `county_name` for backward compatibility

### 5. `/api/villages/regional/aggregates/town` (regional/aggregates_realtime.py)

**Added Parameters:**
- `city`: 市级过滤（精确匹配）
- `county`: 区县级过滤（精确匹配）
- `township`: 乡镇级过滤（精确匹配）
- Kept `town_name` and `county_name` for backward compatibility

**Query Changes:**
- Updated semantic_indices query to use `city, county, township` columns
- Updated merge logic to use `(city, county, township)` tuple as key
- Priority 1: Use hierarchy parameters for exact matching
- Priority 2: Use legacy parameters for backward compatibility
- Handle 东莞市/中山市 (no county level)

### 6. `/api/villages/regional/spatial-aggregates` (regional/aggregates_realtime.py)

**Added Parameters:**
- `city`: 市级过滤（精确匹配）
- `county`: 区县级过滤（精确匹配）
- `town`: 乡镇级过滤（精确匹配）⚠️ **Note: uses "town" not "township"**
- Modified `region_name`: 区域名称（模糊匹配，向后兼容）

**Query Changes:**
- Added `city, county, town` columns to SELECT
- Priority 1: Use hierarchy parameters for exact matching
- Priority 2: Use `region_name` for fuzzy matching
- Handle 东莞市/中山市 (no county level)

## Pattern Used

All endpoints follow the same pattern:

```python
# Priority 1: Use hierarchy parameters (exact match)
if city is not None:
    query += " AND city = ?"
    params.append(city)
if county is not None:
    query += " AND county = ?"
    params.append(county)
elif city is not None and region_level == 'township':
    # Handle 东莞市/中山市 (no county level)
    query += " AND (county IS NULL OR county = '')"
if township is not None:
    query += " AND township = ?"
    params.append(township)

# Priority 2: Backward compatibility (fuzzy match)
if region_name is not None:
    query += " AND (city = ? OR county = ? OR township = ?)"
    params.extend([region_name, region_name, region_name])
```

## Testing

### Test Case 1: Duplicate Township Names (太平镇)

```bash
# Should return only 增城区's 太平镇
GET /api/villages/semantic/indices?region_level=township&city=广州市&county=增城区&township=太平镇

# Should return only 花都区's 太平镇
GET /api/villages/semantic/indices?region_level=township&city=广州市&county=花都区&township=太平镇

# Backward compatibility - fuzzy match (may return multiple)
GET /api/villages/semantic/indices?region_level=township&region_name=太平镇
```

### Test Case 2: 东莞市/中山市 (No County Level)

```bash
# Should work without county parameter
GET /api/villages/regional/aggregates/town?city=东莞市&township=石龙镇

# Should also work with empty county
GET /api/villages/regional/aggregates/town?city=东莞市&county=&township=石龙镇
```

### Test Case 3: City Level Queries

```bash
# Should return 广州市 data only
GET /api/villages/regional/aggregates/city?city=广州市
```

### Test Case 4: County Level Queries

```bash
# Should return 增城区 data only
GET /api/villages/regional/aggregates/county?city=广州市&county=增城区
```

## Impact

**Fixed Endpoints:** 6 endpoints across 3 files
- semantic/composition.py: 1 endpoint
- character/significance.py: 1 endpoint
- regional/aggregates_realtime.py: 4 endpoints

**Data Affected:** ~567K rows
- semantic_indices: 15,507 rows
- semantic_indices_detailed: 130,948 rows
- tendency_significance: 419,626 rows
- region_spatial_aggregates: 1,721 rows

## Backward Compatibility

All endpoints maintain backward compatibility:
- Old `region_name` parameter still works (fuzzy matching)
- Old `city_name`, `county_name`, `town_name` parameters still work
- New hierarchy parameters take priority when provided

## Next Steps (Phase 2)

Add 东莞市/中山市 support to 9 existing hierarchy APIs:
1. `/character/frequency/regional`
2. `/character/tendency/by-region`
3. `/patterns/frequency/regional`
4. `/patterns/tendency`
5. `/ngrams/regional`
6. `/ngrams/tendency`
7. `/semantic/category/vtf/regional`
8. `/semantic/category/tendency`
9. `/regions/similarity/search`

## Files Modified

1. `app/tools/VillagesML/semantic/composition.py`
2. `app/tools/VillagesML/character/significance.py`
3. `app/tools/VillagesML/regional/aggregates_realtime.py`
