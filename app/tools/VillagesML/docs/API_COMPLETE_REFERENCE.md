# API Complete Reference - Updated 2026-02-21

**Base URL:** `http://localhost:8000`
**API Version:** 1.0.0
**Total Endpoints:** 50+ endpoints
**Database Coverage:** 100% (45/45 tables)

---

## 📊 API Coverage Summary

### ✅ 100% Database Coverage

All 45 database tables now have API endpoints!

**New Modules Added (2026-02-21):**
- Semantic Composition API (5 endpoints)
- Village Data API (5 endpoints)
- Pattern Analysis API (4 endpoints)
- Regional Aggregates API (6 endpoints)
- N-gram Tendency & Significance (2 endpoints)

---

## 🗂️ API Modules

### 1. Character Analysis (字符分析)

**Endpoints: 12**

#### Frequency (频率)
- `GET /api/villages/character/frequency/global` - Global character frequency
- `GET /api/villages/character/frequency/regional` - Regional character frequency

#### Embeddings (嵌入)
- `GET /api/villages/character/embeddings/vector` - Get Word2Vec vector
- `GET /api/villages/character/embeddings/similarities` - Find similar characters
- `GET /api/villages/character/embeddings/list` - List all embeddings

#### Significance (显著性)
- `GET /api/villages/character/significance/by-character` - Character significance across regions
- `GET /api/villages/character/significance/by-region` - Significant characters in region
- `GET /api/villages/character/significance/summary` - Significance summary

#### Tendency (倾向性)
- `GET /api/villages/character/tendency/by-region` - Character tendency for region
- `GET /api/villages/character/tendency/by-char` - Character tendency across regions

---

### 2. Semantic Analysis (语义分析)

**Endpoints: 13**

#### Categories & Labels (类别与标签)
- `GET /api/villages/semantic/category/list` - List semantic categories
- `GET /api/villages/semantic/category/vtf/global` - Global VTF
- `GET /api/villages/semantic/category/vtf/regional` - Regional VTF
- `GET /api/villages/semantic/labels/by-character` - Get label for character
- `GET /api/villages/semantic/labels/by-category` - Get characters in category
- `GET /api/villages/semantic/labels/categories` - List all categories

#### Composition (组合) **NEW**
- `GET /api/villages/semantic/composition/bigrams` - Semantic bigrams
- `GET /api/villages/semantic/composition/trigrams` - Semantic trigrams
- `GET /api/villages/semantic/composition/pmi` - Pointwise mutual information
- `GET /api/villages/semantic/composition/patterns` - Composition patterns
- `GET /api/villages/semantic/indices` - Semantic intensity indices

---

### 3. Spatial Analysis (空间分析)

**Endpoints: 8**

#### Hotspots & Clusters (热点与聚类)
- `GET /api/villages/spatial/hotspots` - KDE density hotspots
- `GET /api/villages/spatial/hotspots/{hotspot_id}` - Hotspot details
- `GET /api/villages/spatial/clusters` - DBSCAN clusters
- `GET /api/villages/spatial/clusters/summary` - Cluster summary

#### Integration (整合)
- `GET /api/villages/spatial/integration` - Spatial-tendency integration
- `GET /api/villages/spatial/integration/by-character/{character}` - By character
- `GET /api/villages/spatial/integration/by-cluster/{cluster_id}` - By cluster
- `GET /api/villages/spatial/integration/summary` - Integration summary

---

### 4. N-gram Analysis (N-gram分析)

**Endpoints: 7**

#### Frequency (频率)
- `GET /api/villages/ngrams/frequency` - Global n-gram frequency
- `GET /api/villages/ngrams/regional` - Regional n-gram frequency
- `GET /api/villages/ngrams/patterns` - Structural patterns

#### Tendency & Significance (倾向性与显著性) **NEW**
- `GET /api/villages/ngrams/tendency` - N-gram tendency scores
- `GET /api/villages/ngrams/significance` - N-gram significance tests

---

### 5. Pattern Analysis (模式分析) **NEW MODULE**

**Endpoints: 4**

- `GET /api/villages/patterns/frequency/global` - Global pattern frequency
- `GET /api/villages/patterns/frequency/regional` - Regional pattern frequency
- `GET /api/villages/patterns/tendency` - Pattern tendency scores
- `GET /api/villages/patterns/structural` - Structural naming patterns

---

### 6. Village Data (村庄数据) **NEW MODULE**

**Endpoints: 5**

- `GET /api/villages/village/ngrams/{village_id}` - Village n-grams
- `GET /api/villages/village/semantic-structure/{village_id}` - Semantic structure
- `GET /api/villages/village/features/{village_id}` - Feature vector
- `GET /api/villages/village/spatial-features/{village_id}` - Spatial features
- `GET /api/villages/village/complete/{village_id}` - Complete profile

---

### 7. Regional Aggregates (区域聚合) **NEW MODULE**

**Endpoints: 6**

- `GET /api/villages/regional/aggregates/city` - City-level aggregates
- `GET /api/villages/regional/aggregates/county` - County-level aggregates
- `GET /api/villages/regional/aggregates/town` - Town-level aggregates
- `GET /api/villages/regional/spatial-aggregates` - Regional spatial aggregates
- `GET /api/villages/regional/vectors` - Regional feature vectors

---

### 8. Clustering (聚类分析)

**Endpoints: 3**

- `GET /api/villages/clustering/assignments` - Cluster assignments
- `GET /api/villages/clustering/metrics` - Clustering metrics
- `GET /api/villages/clustering/profiles` - Cluster profiles

---

### 9. Village Search (村庄搜索)

**Endpoints: 2**

- `GET /api/villages/village/search` - Search villages by keyword
- `GET /api/villages/village/search/detail` - Get village details

---

### 10. Metadata & Stats (元数据与统计)

**Endpoints: 2**

- `GET /api/villages/metadata/stats/overview` - System overview
- `GET /api/villages/metadata/stats/tables` - Table information

---

### 11. Compute Endpoints (在线计算)

**Endpoints: 8+**

- `POST /api/villages/compute/clustering/run` - Run clustering
- `POST /api/villages/compute/clustering/scan` - Scan k values
- `POST /api/villages/compute/semantic/cooccurrence` - Semantic co-occurrence
- `POST /api/villages/compute/semantic/network` - Semantic network
- `POST /api/villages/compute/features/extract` - Extract features
- `POST /api/villages/compute/features/aggregate` - Aggregate features
- `POST /api/villages/compute/subset/cluster` - Cluster subset
- `POST /api/villages/compute/subset/compare` - Compare groups

---

## 📈 Database Table Coverage

### All 45 Tables Covered ✅

| Category | Tables | API Coverage |
|----------|--------|--------------|
| **Character Analysis** | 5 tables | ✅ 100% |
| **Semantic Analysis** | 11 tables | ✅ 100% |
| **Spatial Analysis** | 4 tables | ✅ 100% |
| **N-gram Analysis** | 7 tables | ✅ 100% |
| **Pattern Analysis** | 3 tables | ✅ 100% |
| **Village Data** | 4 tables | ✅ 100% |
| **Regional Aggregates** | 5 tables | ✅ 100% |
| **Clustering** | 4 tables | ✅ 100% |
| **Metadata** | 2 tables | ✅ 100% |

**Total: 45/45 tables (100%)**

---

## 🚀 Quick Start Examples

### Character Analysis
```bash
# Get top 10 characters
curl "http://localhost:8000/api/villages/character/frequency/global?top_n=10"

# Find similar characters
curl "http://localhost:8000/api/villages/character/embeddings/similarities?char=村&top_k=5"

# Get character significance
curl "http://localhost:8000/api/villages/character/significance/by-character?char=村"
```

### Semantic Analysis
```bash
# Get semantic categories
curl "http://localhost:8000/api/villages/semantic/category/list"

# Get semantic bigrams
curl "http://localhost:8000/api/villages/semantic/composition/bigrams?min_frequency=10"

# Get semantic indices
curl "http://localhost:8000/api/villages/semantic/indices?category=water"
```

### Spatial Analysis
```bash
# Get spatial hotspots
curl "http://localhost:8000/api/villages/spatial/hotspots"

# Get spatial-tendency integration
curl "http://localhost:8000/api/villages/spatial/integration/by-character/村"
```

### N-gram & Pattern Analysis
```bash
# Get bigrams
curl "http://localhost:8000/api/villages/ngrams/frequency?n=2&top_k=20"

# Get n-gram tendency
curl "http://localhost:8000/api/villages/ngrams/tendency?ngram=新村"

# Get pattern frequency
curl "http://localhost:8000/api/villages/patterns/frequency/global?pattern_type=suffix"
```

### Village Data
```bash
# Get complete village profile
curl "http://localhost:8000/api/villages/village/complete/VILLAGE_ID"

# Get village n-grams
curl "http://localhost:8000/api/villages/village/ngrams/VILLAGE_ID"

# Get village semantic structure
curl "http://localhost:8000/api/villages/village/semantic-structure/VILLAGE_ID"
```

### Regional Aggregates
```bash
# Get city aggregates
curl "http://localhost:8000/api/villages/regional/aggregates/city"

# Get county aggregates
curl "http://localhost:8000/api/villages/regional/aggregates/county?city_name=广州市"

# Get spatial aggregates
curl "http://localhost:8000/api/villages/regional/spatial-aggregates?region_level=city"
```

---

## 📊 Performance Characteristics

### Query Performance
- **Precomputed Endpoints**: <100ms (most queries)
- **Village Lookup**: <50ms (indexed by village_id)
- **Aggregation Queries**: <200ms (with proper filters)
- **Compute Endpoints**: 1-10s (real-time analysis)

### Response Sizes
- **Small**: <10KB (single records, summaries)
- **Medium**: 10-100KB (top-N queries, filtered lists)
- **Large**: 100KB-1MB (full aggregates, complete profiles)

### Rate Limiting
- No rate limiting currently implemented
- Recommended: 100 requests/minute per IP in production

---

## 🔒 Security & Best Practices

### Input Validation
- All query parameters are validated
- SQL injection protection via parameterized queries
- Type checking on all inputs

### Error Handling
- Standard HTTP status codes
- Detailed error messages in development
- Generic messages in production (recommended)

### CORS
- Currently allows all origins (`*`)
- **Production**: Restrict to specific domains

---

## 📖 Documentation

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Additional Resources
- **API Quick Reference**: `docs/frontend/API_QUICK_REFERENCE.md`
- **Frontend Integration**: `docs/frontend/FRONTEND_INTEGRATION_GUIDE.md`
- **Deployment Guide**: `docs/frontend/API_DEPLOYMENT_GUIDE.md`

---

## 🆕 What's New (2026-02-21)

### New Modules (20+ endpoints)
1. **Semantic Composition** - Bigrams, trigrams, PMI, patterns
2. **Village Data** - Complete village profiles and features
3. **Pattern Analysis** - Pattern frequency and tendency
4. **Regional Aggregates** - City/county/town statistics
5. **N-gram Extensions** - Tendency and significance

### Coverage Improvements
- **Before**: ~85% coverage (30-34 endpoints)
- **After**: 100% coverage (50+ endpoints)
- **New Tables**: 15+ tables now accessible via API

### Performance Enhancements
- Optimized queries for large tables
- Better indexing on frequently queried columns
- Pagination support for all list endpoints

---

## 💡 Usage Tips

### Filtering Best Practices
1. Always use `limit` parameter for large result sets
2. Apply filters at the database level (query parameters)
3. Use specific queries (by-character, by-region) when possible

### Pagination
```bash
# Get first 100 results
curl "http://localhost:8000/api/endpoint?limit=100"

# Get next 100 results (if supported)
curl "http://localhost:8000/api/endpoint?limit=100&offset=100"
```

### Combining Queries
```bash
# Multiple filters
curl "http://localhost:8000/api/villages/ngrams/frequency?n=2&min_frequency=100&top_k=50"

# Regional + type filters
curl "http://localhost:8000/api/villages/patterns/frequency/regional?region_level=city&pattern_type=suffix"
```

---

## 🎯 Common Use Cases

### 1. Character Analysis Workflow
```bash
# 1. Get top characters
GET /api/villages/character/frequency/global?top_n=20

# 2. Analyze specific character
GET /api/villages/character/significance/by-character?char=村

# 3. Find similar characters
GET /api/villages/character/embeddings/similarities?char=村&top_k=10
```

### 2. Regional Analysis Workflow
```bash
# 1. Get regional aggregates
GET /api/villages/regional/aggregates/city

# 2. Get regional patterns
GET /api/villages/patterns/frequency/regional?region_level=city&region_name=广州市

# 3. Get regional n-grams
GET /api/villages/ngrams/regional?n=2&region_level=city&region_name=广州市
```

### 3. Village Profile Workflow
```bash
# 1. Search for village
GET /api/villages/village/search?query=新村

# 2. Get complete profile
GET /api/villages/village/complete/{village_id}

# 3. Get specific features
GET /api/villages/village/spatial-features/{village_id}
```

---

**Last Updated**: 2026-02-21
**API Version**: 1.0.0
**Database Version**: 45 tables, 285,860 villages
