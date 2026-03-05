# 沒有權限檢查的路由分類報告

總計：176 個路由

## 1. 認證相關（9 個）- ✅ 正常
這些路由本身就是處理認證的，不需要權限檢查：
- POST /register
- POST /login
- POST /refresh
- GET /verify-email
- GET /me
- POST /logout
- POST /report-online-time
- PUT /updateProfile
- GET /leaderboard

## 2. 公開頁面（8 個）- ✅ 正常
前端頁面路由，應該公開訪問：
- GET /
- GET /detail
- GET /admin
- GET /intro
- GET /menu
- GET /explore
- GET /villagesML
- GET /auth
- GET /__ping

## 3. 日誌統計（18 個）- ⚠️ 需要檢查
這些路由可能需要添加權限檢查：

### logs/logs_stats.py (9 個)
- GET /keyword/top
- GET /api/usage
- GET /keyword/search
- GET /stats/summary
- GET /stats/fields
- GET /visits/total
- GET /visits/today
- GET /visits/history
- GET /visits/by-path

### logs/stats.py (6 個)
- GET /keyword/top
- GET /keyword/search
- GET /api/usage
- GET /stats/summary
- GET /stats/fields
- GET /visits/total
- GET /visits/today
- GET /visits/history

### logs/hourly_daily.py (4 個)
- GET /hourly
- GET /daily
- GET /ranking
- GET /api-history

## 4. 管理員相關（37 個）- ⚠️ 需要檢查
這些路由看起來應該需要管理員權限：

### admin/api_usage.py (3 個)
- GET /api-summary
- GET /api-detail
- GET /api-usage

### admin/cache_manager.py (5 個)
- POST /clear_dialect_cache
- POST /clear_redis_cache
- POST /clear_all_cache
- GET /cache_stats
- GET /cache_status

### admin/custom.py (3 個)
- GET /all
- GET /num
- GET /user

### admin/custom_edit.py (2 個)
- POST /create
- POST /selected

### admin/custom_regions.py (4 個)
- GET /all
- GET /user
- GET /count
- GET /stats

### admin/custom_regions_edit.py (4 個)
- POST /create
- PUT /update
- DELETE /delete
- POST /batch-delete

### admin/get_ip.py (1 個)
- GET /{api_name}/{ip}

### admin/leaderboard.py (2 個)
- GET /rankings
- GET /available-apis

### admin/login_logs.py (2 個)
- GET /success-login-logs
- GET /failed-login-logs

### admin/users.py (5 個)
- GET /list
- GET /all
- GET /single
- POST /create
- DELETE /delete

### admin/user_stats.py (2 個)
- GET /login-history
- GET /stats

## 5. Check 工具（9 個）- ⚠️ 需要檢查
- POST /upload
- POST /analyze
- POST /execute
- POST /save
- GET /download/{task_id}
- POST /get_data
- POST /get_tone_stats
- POST /update_row
- POST /batch_delete

## 6. Jyut2IPA 工具（4 個）- ⚠️ 需要檢查
- POST /upload
- POST /process
- GET /progress/{task_id}
- GET /download/{task_id}

## 7. Merge 工具（5 個）- ⚠️ 需要檢查
- POST /upload_reference
- POST /upload_files
- POST /execute
- GET /progress/{task_id}
- GET /download/{task_id}

## 8. Praat 工具（1 個）- ✅ 正常
- GET /capabilities

## 9. VillagesML 工具（82 個）- ⚠️ 需要檢查

### admin/run_ids.py (3 個)
- GET /run-ids/available/{analysis_type}
- GET /run-ids/metadata/{run_id}
- POST /run-ids/refresh

### character/* (9 個)
- GET /vector (embeddings.py)
- GET /similarities (embeddings.py)
- GET /list (embeddings.py)
- GET /global (frequency.py)
- GET /regional (frequency.py)
- GET /by-character (significance.py)
- GET /by-region (significance.py)
- GET /summary (significance.py)
- GET /by-region (tendency.py)
- GET /by-char (tendency.py)

### clustering/* (5 個)
- GET /assignments (assignments.py)
- GET /assignments/by-region (assignments.py)
- GET /profiles (assignments.py)
- GET /metrics (assignments.py)
- GET /metrics/best (assignments.py)

### compute/* (2 個)
- GET /cache-stats (clustering.py)
- DELETE /cache (clustering.py)

### metadata/* (3 個)
- GET /overview (stats.py)
- GET /tables (stats.py)
- GET /regions (stats.py)

### ngrams/* (6 個)
- GET /frequency (frequency.py)
- GET /regional (frequency.py)
- GET /patterns (frequency.py)
- GET /tendency (frequency.py)
- GET /significance (frequency.py) - 重複
- GET /significance (frequency.py) - 重複

### regional/* (22 個)
- GET /aggregates/city (aggregates_deprecated.py)
- GET /aggregates/county (aggregates_deprecated.py)
- GET /aggregates/town (aggregates_deprecated.py)
- GET /spatial-aggregates (aggregates_deprecated.py)
- GET /vectors (aggregates_deprecated.py)
- GET /aggregates/city (aggregates_realtime.py)
- GET /aggregates/county (aggregates_realtime.py)
- GET /aggregates/town (aggregates_realtime.py)
- GET /spatial-aggregates (aggregates_realtime.py)
- GET /vectors (aggregates_realtime.py)
- POST /vectors/compare (aggregates_realtime.py)
- POST /vectors/compare/batch (aggregates_realtime.py)
- POST /vectors/reduce (aggregates_realtime.py)
- POST /vectors/cluster (aggregates_realtime.py)
- POST /vectors/compare/batch (batch_operations_code.py)
- POST /vectors/reduce (batch_operations_code.py)
- POST /vectors/cluster (batch_operations_code.py)
- GET /similarity/search (similarity.py)
- GET /similarity/pair (similarity.py)
- GET /similarity/matrix (similarity.py)
- GET /list (similarity.py)

### semantic/* (18 個)
- GET /list (category.py)
- GET /vtf/global (category.py)
- GET /vtf/regional (category.py)
- GET /tendency (category.py)
- GET /composition/bigrams (composition.py)
- GET /composition/trigrams (composition.py)
- GET /composition/pmi (composition.py)
- GET /composition/patterns (composition.py)
- GET /indices (composition.py)
- GET /by-character (labels.py)
- GET /by-category (labels.py)
- GET /categories (labels.py)
- GET /list (subcategories.py)
- GET /chars/{subcategory} (subcategories.py)
- GET /vtf/global (subcategories.py)
- GET /vtf/regional (subcategories.py)
- GET /tendency/top (subcategories.py)
- GET /comparison (subcategories.py)

### spatial/* (12 個)
- GET /hotspots (hotspots.py)
- GET /hotspots/{hotspot_id} (hotspots.py)
- GET /clusters (hotspots.py)
- GET /clusters/summary (hotspots.py)
- GET /clusters/available-runs (hotspots.py)
- GET /integration (integration.py)
- GET /integration/by-character/{character} (integration.py)
- GET /integration/by-cluster/{cluster_id} (integration.py)
- GET /integration/summary (integration.py)
- GET /integration/available-characters (integration.py)
- GET /integration/clusterlist (integration.py)

### village/* (6 個)
- GET /ngrams/{village_id} (data.py)
- GET /semantic-structure/{village_id} (data.py)
- GET /features/{village_id} (data.py)
- GET /spatial-features/{village_id} (data.py)
- GET /complete/{village_id} (data.py)
- GET /detail (search.py)

## 總結

### ✅ 正常（不需要權限檢查）：18 個
- 認證相關：9 個
- 公開頁面：8 個
- Praat capabilities：1 個

### ⚠️ 需要檢查（可能需要添加權限）：158 個
- 日誌統計：18 個（可能需要管理員權限）
- 管理員相關：37 個（**應該需要管理員權限**）
- Check 工具：9 個
- Jyut2IPA 工具：4 個
- Merge 工具：5 個
- VillagesML 工具：82 個

### 建議優先處理
1. **管理員路由（37 個）** - 這些路由名稱中包含 "admin"，但沒有權限檢查，存在安全風險
2. **日誌統計路由（18 個）** - 敏感數據，應該限制訪問
3. **工具路由（18 個）** - Check、Jyut2IPA、Merge 工具可能需要登錄或限流
