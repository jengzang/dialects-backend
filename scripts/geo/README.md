# Geo data prep scripts

第一阶段目标：
- 读取 data/geo/source/ok_geo.csv（官方 GCJ-02 边界数据）
- 转成 WGS84 GeoJSON
- 输出 full + 按 deep(0/1/2) 分层文件
- 生成 manifest 供后续 Java/FastAPI 服务层消费

目录约定：
- 输入：data/geo/source/
- 输出：data/geo/generated/geojson/wgs84/
- 清单：data/geo/generated/manifest/
- 日志：data/geo/generated/logs/

建议执行顺序：
1. python3 scripts/geo/inspect_areacity.py
2. python3 scripts/geo/convert_areacity_to_geojson.py
3. python3 scripts/geo/validate_geojson.py

说明：
- 原始源数据保持不改，只挪到 source/ 目录。
- 第一阶段仅处理 ok_geo.csv 的省/市/区三级 geometry。
- ok_data_level3.csv / ok_data_level4.csv 暂存于 source/，后续服务层或第二阶段再进一步接入。
