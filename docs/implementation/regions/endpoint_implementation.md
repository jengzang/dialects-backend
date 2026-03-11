# Regions Endpoint Implementation

**Date:** 2026-02-23
**Status:** ✅ Implemented and Tested
**Priority:** P0 (Critical - Unblocks Frontend)

---

## Summary

Implemented the missing `/api/villages/metadata/stats/regions` endpoint to provide region lists (cities, counties, townships) for frontend dropdown selectors.

---

## Endpoint Specification

### Path
```
GET /api/villages/metadata/stats/regions
```

### Query Parameters

| Parameter | Type   | Required | Description                                    | Example |
|-----------|--------|----------|------------------------------------------------|---------|
| level     | string | Yes      | Region level: 'city', 'county', or 'township'  | city    |
| parent    | string | No       | Parent region name for hierarchical filtering  | 广州市  |

### Response Format

```json
[
  {
    "name": "广州市",
    "level": "city",
    "village_count": 12543
  },
  {
    "name": "深圳市",
    "level": "city",
    "village_count": 8234
  }
]
```

### Behavior

1. **Without parent parameter:**
   - `level=city` → Return all unique cities
   - `level=county` → Return all unique counties
   - `level=township` → Return all unique townships

2. **With parent parameter:**
   - `level=county&parent=广州市` → Return all counties in 广州市
   - `level=township&parent=番禺区` → Return all townships in 番禺区

### Error Responses

- **422 Validation Error** - Invalid level (must be 'city', 'county', or 'township')
- **422 Validation Error** - City level does not support parent parameter
- **404 Not Found** - No regions found for the given parameters

---

## Implementation Details

### Files Modified

1. **`app/tools/VillagesML/models/__init__.py`**
   - Added `RegionInfo` Pydantic model

2. **`app/tools/VillagesML/metadata/stats.py`**
   - Added `_get_regions_sync()` function for database queries
   - Added `get_regions()` async endpoint handler
   - Added `Optional` to imports

### Database Queries

```sql
-- Get all cities
SELECT 市级 as name, 'city' as level, COUNT(*) as village_count
FROM 广东省自然村
WHERE 市级 IS NOT NULL AND 市级 != ''
GROUP BY 市级
ORDER BY name;

-- Get counties in a city
SELECT 区县级 as name, 'county' as level, COUNT(*) as village_count
FROM 广东省自然村
WHERE 市级 = ? AND 区县级 IS NOT NULL AND 区县级 != ''
GROUP BY 区县级
ORDER BY name;

-- Get townships in a county
SELECT 乡镇级 as name, 'township' as level, COUNT(*) as village_count
FROM 广东省自然村
WHERE 区县级 = ? AND 乡镇级 IS NOT NULL AND 乡镇级 != ''
GROUP BY 乡镇级
ORDER BY name;
```

---

## Test Results

All tests passed successfully:

```
Testing: Get all cities
[OK] Found 21 cities

Testing: Get counties in Guangzhou
[OK] Found 10 counties in Guangzhou

Testing: Get townships in Panyu
[OK] Found 16 townships in Panyu

Testing: Invalid level parameter
[OK] Correctly raised error: 422

Testing: City level with parent (should fail)
[OK] Correctly raised error: 422
```

---

## Usage Examples

### JavaScript/TypeScript

```javascript
// Get all cities
const cities = await fetch('/api/villages/metadata/stats/regions?level=city')
  .then(res => res.json());

// Get counties in 广州市
const counties = await fetch('/api/villages/metadata/stats/regions?level=county&parent=广州市')
  .then(res => res.json());

// Get townships in 番禺区
const townships = await fetch('/api/villages/metadata/stats/regions?level=township&parent=番禺区')
  .then(res => res.json());
```

### Python

```python
import requests

# Get all cities
response = requests.get('http://localhost:5000/api/villages/metadata/stats/regions',
                       params={'level': 'city'})
cities = response.json()

# Get counties in 广州市
response = requests.get('http://localhost:5000/api/villages/metadata/stats/regions',
                       params={'level': 'county', 'parent': '广州市'})
counties = response.json()
```

### cURL

```bash
# Get all cities
curl "http://localhost:5000/api/villages/metadata/stats/regions?level=city"

# Get counties in 广州市
curl "http://localhost:5000/api/villages/metadata/stats/regions?level=county&parent=广州市"

# Get townships in 番禺区
curl "http://localhost:5000/api/villages/metadata/stats/regions?level=township&parent=番禺区"
```

---

## Frontend Integration

### Vue 3 Example (Cascading Selectors)

```vue
<template>
  <div>
    <select v-model="selectedCity" @change="onCityChange">
      <option value="">Select City</option>
      <option v-for="city in cities" :key="city.name" :value="city.name">
        {{ city.name }} ({{ city.village_count }})
      </option>
    </select>

    <select v-model="selectedCounty" @change="onCountyChange" :disabled="!selectedCity">
      <option value="">Select County</option>
      <option v-for="county in counties" :key="county.name" :value="county.name">
        {{ county.name }} ({{ county.village_count }})
      </option>
    </select>

    <select v-model="selectedTownship" :disabled="!selectedCounty">
      <option value="">Select Township</option>
      <option v-for="township in townships" :key="township.name" :value="township.name">
        {{ township.name }} ({{ township.village_count }})
      </option>
    </select>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const API_BASE = 'http://localhost:5000';

const cities = ref([]);
const counties = ref([]);
const townships = ref([]);

const selectedCity = ref('');
const selectedCounty = ref('');
const selectedTownship = ref('');

async function getRegions(level, parent = null) {
  const params = new URLSearchParams({ level });
  if (parent) params.append('parent', parent);

  const response = await fetch(`${API_BASE}/api/villages/metadata/stats/regions?${params}`);
  return response.json();
}

onMounted(async () => {
  cities.value = await getRegions('city');
});

async function onCityChange() {
  selectedCounty.value = '';
  selectedTownship.value = '';
  townships.value = [];

  if (selectedCity.value) {
    counties.value = await getRegions('county', selectedCity.value);
  } else {
    counties.value = [];
  }
}

async function onCountyChange() {
  selectedTownship.value = '';

  if (selectedCounty.value) {
    townships.value = await getRegions('township', selectedCounty.value);
  } else {
    townships.value = [];
  }
}
</script>
```

---

## Performance

- **Query Time:** < 100ms (simple GROUP BY query)
- **Response Size:**
  - Cities: ~21 records (~1KB)
  - Counties: ~100 records (~5KB)
  - Townships: ~1000 records (~50KB)

---

## Documentation Updates

Updated the following documentation files:

1. **`app/tools/VillagesML/docs/API_QUICK_REFERENCE.md`**
   - Added regions endpoint examples

2. **`app/tools/VillagesML/docs/FRONTEND_INTEGRATION_GUIDE.md`**
   - Added "Get Region Lists" use case with Vue 3 example

---

## Next Steps (Optional Enhancements)

### P1: Region Hierarchy Endpoint

```
GET /api/villages/metadata/stats/regions/hierarchy
```

Returns complete hierarchy in one request:

```json
{
  "广州市": {
    "番禺区": ["石楼镇", "市桥镇"],
    "天河区": ["龙洞街道", "石牌街道"]
  },
  "深圳市": {
    "南山区": ["南头街道", "沙河街道"]
  }
}
```

**Benefits:** Reduces API calls from 3 to 1 for full hierarchy

### P2: Region Statistics Endpoint

```
GET /api/villages/metadata/stats/regions/stats?level=city&name=广州市
```

Returns detailed statistics for a region:

```json
{
  "name": "广州市",
  "level": "city",
  "village_count": 12543,
  "character_diversity": 234,
  "most_common_chars": ["村", "新", "大"],
  "semantic_categories": {
    "water": 1234,
    "mountain": 567
  }
}
```

**Benefits:** Enriches region selector panels with statistics

---

## Conclusion

The `/api/villages/metadata/stats/regions` endpoint is now fully implemented, tested, and documented. This unblocks the frontend team and provides a clean, efficient API for region selection functionality.

**Status:** ✅ Ready for Production
