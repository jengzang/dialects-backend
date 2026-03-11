# Regional Hierarchy Query Fix - Phase 2 Complete

## Summary

Successfully added 东莞市/中山市 support (no county level) to 9 existing hierarchy APIs. These APIs already had city/county/township parameters but didn't handle the special case where county is NULL.

## Changes Made

All 9 endpoints now handle 东莞市/中山市 (prefecture-level cities without county-level divisions) by adding:

```python
elif city is not None and region_level == 'township':
    # Handle 东莞市/中山市 (no county level)
    query += " AND (county IS NULL OR county = '')"
```

### 1. Character Frequency API (character/frequency.py)

**Endpoint**: `/api/villages/character/frequency/regional`

**Change**: Added 东莞市/中山市 support after county parameter check

### 2. Character Tendency API (character/tendency.py)

**Endpoints**:
- `/api/villages/character/tendency/by-region`
- `/api/villages/character/tendency/by-char`

**Change**: Added 东莞市/中山市 support to both endpoints (2 occurrences)

### 3. Pattern Analysis API (patterns/__init__.py)

**Endpoints**:
- `/api/villages/patterns/frequency/regional`
- `/api/villages/patterns/tendency`

**Change**: Added 东莞市/中山市 support to both endpoints (2 occurrences)

### 4. N-gram Analysis API (ngrams/frequency.py)

**Endpoints**:
- `/api/villages/ngrams/regional`
- `/api/villages/ngrams/tendency`

**Change**: Added 东莞市/中山市 support to both endpoints
- `/regional`: 1 occurrence (township level query)
- `/tendency`: 3 occurrences (township, county, city level queries)

### 5. Semantic Category API (semantic/category.py)

**Endpoints**:
- `/api/villages/semantic/category/vtf/regional`
- `/api/villages/semantic/category/tendency`

**Change**: Added 东莞市/中山市 support to both endpoints (2 occurrences)

### 6. Region Similarity API (regional/similarity.py)

**Endpoint**: `/api/villages/regions/similarity/search`

**Change**: Added 东莞市/中山市 support in target region query

## Pattern Used

All endpoints follow the same pattern:

```python
# 优先使用层级参数（精确匹配）
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
```

## Testing

### Test Case: 东莞市 Township Query

```bash
# Should work without county parameter
GET /api/villages/character/frequency/regional?region_level=township&city=东莞市&township=石龙镇

# Should also work with empty county
GET /api/villages/character/frequency/regional?region_level=township&city=东莞市&county=&township=石龙镇

# Should return results for 东莞市's 石龙镇 only
```

### Test Case: 中山市 Township Query

```bash
# Should work without county parameter
GET /api/villages/patterns/tendency?region_level=township&city=中山市&township=石岐街道

# Should return results for 中山市's 石岐街道 only
```

## Impact

**Fixed Endpoints**: 9 endpoints across 6 files
- character/frequency.py: 1 endpoint
- character/tendency.py: 2 endpoints
- patterns/__init__.py: 2 endpoints
- ngrams/frequency.py: 2 endpoints
- semantic/category.py: 2 endpoints
- regional/similarity.py: 1 endpoint

**Data Affected**: All regional analysis tables with hierarchy columns
- char_regional_analysis: 419,626 rows
- pattern_regional_analysis: 1,900,580 rows
- semantic_regional_analysis: 15,489 rows
- ngram_tendency: ~millions of rows
- region_similarity: ~thousands of rows

## Combined Impact (Phase 1 + Phase 2)

**Total Fixed Endpoints**: 15 endpoints
- Phase 1: 6 endpoints (added hierarchy parameters)
- Phase 2: 9 endpoints (added 东莞市/中山市 support)

All 15 endpoints now support:
1. ✅ Complete hierarchical queries (city, county, township)
2. ✅ Exact matching to avoid duplicate region names
3. ✅ 东莞市/中山市 support (no county level)
4. ✅ Backward compatibility with region_name parameter

## Files Modified

1. `app/tools/VillagesML/character/frequency.py`
2. `app/tools/VillagesML/character/tendency.py`
3. `app/tools/VillagesML/patterns/__init__.py`
4. `app/tools/VillagesML/ngrams/frequency.py`
5. `app/tools/VillagesML/semantic/category.py`
6. `app/tools/VillagesML/regional/similarity.py`

## Next Steps

All planned fixes are complete. The system now properly handles:
- Duplicate region names (e.g., 7 different "太平镇" townships)
- Prefecture-level cities without county divisions (东莞市, 中山市)
- Backward compatibility with legacy region_name parameter
