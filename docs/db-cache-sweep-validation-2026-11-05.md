# 通用 SQLite 池：逐库页缓存建议与实测

日期：2026-11-05。此次只增加本地测试脚本、结果与报告，没有改运行配置，没有连接生产服务器，没有复制数据库。

## 建议

在本轮2000/4096/8192/16000 KiB四档中，建议多数通用池从2000 KiB（约2MiB）开始，toponyms保守维持4096 KiB（4MiB），8192 KiB（8MiB）作为点位重负载的可选档。这是对所测读负载的初始预算建议，不是每库所有参数/写入场景的全局最优值。没有依据将所有库统一为16MiB，也没有依据把ORM的缓存直接照此修改。

| 实际文件/路径 | 建议每连接cache_size | 主要证据与取舍 |
| --- | --- | --- |
| query_user.db | -2000 | 地点批量、4500条地图点、分区聚合无明显差异；小工作集本就未用满大预算 |
| dialects_user.db（含notes） | -2000 | 20地点三类特征统计约41.10→39.25ms（2→16档）；notes IPA COUNT约109.85→109.62ms；2档FTS页查询比4档约多0.54ms，换取更低内存 |
| characters.db | -2000 | 20字批量、层级筛选、六表读取基本持平；十个层级字段DISTINCT约12.26→11.84ms（2→16档），差距约0.42ms |
| yubao.db | -2000 | 普通词条/语法页基本不变；总词表和独立COUNT在8档各快约0.5ms，但该默认结果已走版本缓存，且其未命中加载是短连接，不值得仅为它增大普通池 |
| villages.db | -2000 | Ngram统计约14.5→13.7ms（2→16档），包含搜索约12～13ms；大档显著增加保留内存 |
| villages_admin.db | -2000，较保守 | 通用SQL分页约0.05ms；大范围包含COUNT约663～728ms，增大缓存未改善。16档同形COUNT能快约1.4ms，但被混合大扫描后收益消失；管理负载频率未知 |
| logs.db：raw通用统计池 | -2000 | 访问/趋势/最近诊断基本不变；关键词聚合约12.45→11.96ms（2→16档），约0.5ms差异；未测试日志写入吞吐 |
| auth.db：raw通用统计池 | -2000 | usage聚合与用户分组几乎相同；不代表auth ORM写入池已测试 |
| yc_spoken.db | -2000 | 全库不足1MiB，计数/分页/LIKE无明显差异；预算降低本身几乎不省实际内存 |
| vocabulary.db：通用SQL访问 | -2000，较保守 | COUNT、分页、全库模糊COUNT、标准词子串查询均未显示大档收益；不覆盖vocabulary ORM及它的优化查询规划 |
| toponyms.db | -4096，重负载可选-8192 | 点位prefix、limit5000：4档143.15ms，8档131.59ms，中位数约快8.1%，但逐轮是两轮改善、一轮接近，并非每轮都更快；16档135.40ms，没有进一步稳定收益。相比当前4档，单连接阶段RSS约增加4.91MiB，在2GB主机上不默认增加，按线上点位负载决定是否值得 |
| dependency/gis.db | -2000（维持） | 名称、子级、Rtree候选、边界blob读取都未显示大档收益；几何JSON解码/LRU不属于页缓存，不由此测试结论调整 |

characters的ATTACH另测：主dialects预算固定16000KiB，仅改变chars_db预算。5个不同地点JOIN返回18553行：2/4/8/16档SQL阶段约15.31/15.32/15.34/15.26ms，没有增大附加库预算的证据。当前该ATTACH本来也没有随characters主池的16000设置走；不能把两条访问路径的缓存预算混为一谈。

query_admin与dialects_admin当前路径常量分别和query_user/dialects_user相同，按实际路径去重。磁盘上的旧query_admin.db/dialects_admin.db不是另一组当前池。villages_admin是独立配置库，已测试。supplements.db仅ORM、未伪装为通用池覆盖。自定义任意路径无法穷举，此次覆盖代码中已配置的固定数据库。

## 实际内存：不要用配置上限冒充RSS

表中为完成同一批重复读查询后，单连接阶段进程RSS相对建连前基线的中位增量，单位MiB。不是SQLite精确cache_used，不是单worker部署后的实测；包含SQLite分配器、TEMP工作集和Python残留分配。

| 库 | 当前预算下RSS增量 | 建议预算下RSS增量 |
| --- | ---: | ---: |
| query | 2.41 | 2.44 |
| dialects | 20.63 | 3.70 |
| characters | 8.33 | 3.31 |
| yubao | 7.47 | 3.25 |
| villages | 21.31 | 4.55 |
| villages_admin | 20.17 | 3.17 |
| logs raw | 10.91 | 7.80 |
| auth raw | 3.48 | 3.39 |
| spoken | 1.05 | 1.02 |
| vocabulary raw | 20.20 | 3.23 |
| toponyms（维持4MiB） | 5.83 | 5.83 |
| GIS（维持约2MiB） | 3.28 | 3.28 |

没有计算“差值×全部池连接×worker”并当作实际节省：各连接的真实工作集、访问分布不同，生产也未测。预算本身不是预分配。此次所有子进程的最大峰值RSS约65.1MiB；任一时刻仅一个测试子进程，子进程至多两条并发工作连接。样本参数准备阶段的query辅助连接会先关闭，不与并发查询阶段重叠。

## 测量方法与完整性

- 12个独立数据库，外加characters ATTACH场景，共13场景×4预算×3独立进程=156组。每个SQL形态连续4次，另外两轮混合顺序和一次双连接并发，共46个查询case、4416个样本。
- 每轮改变预算顺序；只改变cache_size，连接权限与temp_store等设置在各预算间一致。GIS/toponyms使用FILE，其他通用池使用MEMORY。SQLite本机版本3.53.2；没有模拟生产SQLite版本、2核CPU配额、2GB系统内存压力或多worker流量分布。
- 主库与附加库始终mode=ro，不设置WAL、不建立索引、不ANALYZE、不改持久PRAGMA。notes仅建立/删除连接本地TEMP表；这也说明以后若改notes连接，不能不加区分地开启query_only=ON，否则会阻断现有TEMP逻辑。mode=ro不等于操作系统完全不更新SQLite WAL共享内存辅助文件。
- 从真实源码查询形态选取批量定位、字段DISTINCT、特征聚合、notes FTS临时表、模糊COUNT、Ngram统计、通用SQL分页、Rtree/边界读取。部分是代表性裁剪SQL，测SQL执行/取行，不是完整HTTP接口，不能用此结果声称某端点总耗时同比下降。
- 主比较使用execute/fetch累计SQL墙钟，单独记录SQL线程CPU。逐行摘要在SQL计时外；另保留包含摘要的完整case墙钟。结果按fetchmany(32)消费，避免把全量结果列表留在Python。测量不经过Redis结果缓存，因此默认缓存命中时的线上成本可能更低。
- warm指标是每进程剔除第一次后的三次中位数，再取三个进程中位数。mixed单独记录；首次只是首次执行该SQL形态，不是冷盘：未清OS文件缓存，而且参数采样会预热部分数据库页面。
- concurrent_warm与concurrent_new分别保留：前一条连接已跑完重复/混合查询，第二条在并发阶段开始时新建、随后跨case复用，模拟突发多一条连接；不能合称稳态双连接吞吐。SQL取行也受到Python线程/GIL调度影响，不能外推为2核部署能力。
- 单连接RSS在mixed前采样；双连接RSS在mixed与线程池结束后采样。两者之差还包含额外工作集、线程和分配器开销，不能叫第二条连接的纯增量。
- 截止时间为每个case总计3秒，包含多条SQL和摘要处理，不是每条SQL另给3秒。正式样本只有一次toponyms 4096KiB首次点查询触发截止，完整记录；此前pilot也有一次2000KiB首次超时。不能由此断言8MiB会消除冷读取超时。其余正式样本成功；所有成功摘要跨预算、轮次和阶段相同。
- 主文件每组前后dev/inode/size/mtime稳定。ATTACH源characters同时作为独立库覆盖，没有针对WAL/SHM逐字节校验；本地数据不代替生产最近数据快照。不会把稀有后台写入/长事务性能视为已验证。

独立复核发现ATTACH原采样未去重，已修复为query库中5个不同简称并重跑全部12组；原错误ATTACH样本从最终结果排除。正式报告原始输入为outputs/db-cache-sweep-final-closed.json，聚合结果见同目录db-cache-sweep-results-2026-11-05.json。

## 重现

使用现有项目虚拟环境，不安装依赖，不启动Redis。运行脚本前确认data目录指向本地数据；命令不会连接服务器。输出必须使用新文件名，以保留已有结果。

```sh
.venv/bin/python scripts/run_db_cache_sweep.py --data-dir /absolute/local/data --output outputs/db-cache-new.json
.venv/bin/python scripts/summarize_db_cache.py outputs/db-cache-new.json outputs/db-cache-new-summary.json
.venv/bin/python -m pytest tests/test_db_cache_benchmark.py -q
```

汇总器会检查完整覆盖、三轮、文件身份、ATTACH去重标记及跨预算摘要一致性；超时单独列出，不当作快查询。recommended_kib是本报告结合资源目标和业务缓存路径做的人工建议，不是自动搜索得到的全局最优。

本轮尚未修改db_pool运行配置。辅助query连接显式closing()关闭，并对涉及的dialects/ATTACH两库共24组重新运行；最终原始输入已替换为修正后的数据。

后续若采用建议，应该只改每库cache_size，先保留连接上限及事务语义，避免同时改多个变量；ORM尤其logs的64000KiB配置需要另测写入和批量事务，不能套用这次raw统计读测试。

最终复核补充：yubao默认all_items路径用len(items)算总数，故正式数据已将默认词表SELECT和非默认建议查询使用的COUNT拆开测试；词条/语法页也读取完整列。characters另加入SELECT *完整字段批量读取，避免只测窄列索引。两库全部24组重跑，旧组不混入最终结果。

验证：测试脚本的5项保护检查通过；最终156组数据重新聚合与记录的结果JSON一致，git diff --check通过。没有更改运行时代码。

## 附表：全部预算的重复SQL耗时

每格为三个进程内warm中位数的中位数，单位ms。源码中的case名用于和完整SQL/原始记录一一对应；这不是完整HTTP耗时。

### query

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| location_detail_batch20 | 0.019 | 0.019 | 0.019 | 0.019 |
| map_points_all | 2.285 | 2.252 | 2.289 | 2.295 |
| partition_group | 0.180 | 0.174 | 0.179 | 0.179 |
| 单连接阶段 RSS增量/MiB | 2.44 | 2.42 | 2.48 | 2.41 |

### dialects

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| chars20_locations20 | 0.271 | 0.274 | 0.268 | 0.271 |
| feature_count_locations20 | 41.100 | 41.203 | 40.187 | 39.245 |
| notes_fts_temp_count_page | 1.268 | 0.725 | 0.761 | 0.741 |
| notes_pronunciation_count | 109.846 | 108.437 | 108.653 | 109.615 |
| 单连接阶段 RSS增量/MiB | 3.70 | 6.31 | 11.11 | 20.62 |

### characters

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| batch20_characters | 0.032 | 0.033 | 0.033 | 0.032 |
| batch20_full_rows | 0.043 | 0.045 | 0.043 | 0.044 |
| hierarchy_知組三等 | 0.398 | 0.399 | 0.390 | 0.399 |
| hierarchy_distincts | 12.264 | 12.538 | 11.730 | 11.842 |
| six_tables_batch20 | 0.074 | 0.071 | 0.071 | 0.073 |
| 单连接阶段 RSS增量/MiB | 3.31 | 5.94 | 8.38 | 8.33 |

### yubao

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| word_detail_count_page50 | 0.094 | 0.092 | 0.092 | 0.094 |
| all_words_default | 1.015 | 1.151 | 0.551 | 0.537 |
| distinct_word_count | 0.768 | 0.883 | 0.303 | 0.300 |
| grammar_detail_count_page50 | 0.008 | 0.008 | 0.008 | 0.008 |
| all_sentences | 0.033 | 0.032 | 0.033 | 0.033 |
| 单连接阶段 RSS增量/MiB | 3.25 | 5.84 | 7.41 | 7.47 |

### villages

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| overview | 0.003 | 0.003 | 0.003 | 0.003 |
| regional_ngram_count | 0.005 | 0.005 | 0.005 | 0.005 |
| ngram_significance_group | 14.502 | 13.750 | 13.860 | 13.669 |
| village_contains_page100 | 12.293 | 12.420 | 12.567 | 13.001 |
| 单连接阶段 RSS增量/MiB | 4.55 | 7.06 | 11.80 | 21.31 |

### villages_admin

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| sql_count_gd | 1.455 | 1.503 | 1.627 | 0.093 |
| sql_page100_gd | 0.051 | 0.050 | 0.050 | 0.050 |
| sql_filtered_count | 663.081 | 672.407 | 703.644 | 727.569 |
| 单连接阶段 RSS增量/MiB | 3.17 | 5.70 | 10.72 | 20.17 |

### logs

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| total_visits | 0.041 | 0.042 | 0.042 | 0.041 |
| daily_trend30 | 0.027 | 0.027 | 0.027 | 0.027 |
| top_keywords | 12.454 | 12.478 | 12.009 | 11.960 |
| diagnostics_latest50 | 0.023 | 0.023 | 0.022 | 0.023 |
| 单连接阶段 RSS增量/MiB | 7.80 | 10.56 | 10.64 | 10.91 |

### auth

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| usage_totals | 0.486 | 0.492 | 0.473 | 0.477 |
| usage_by_path | 0.974 | 0.931 | 0.970 | 0.949 |
| user_counts | 0.071 | 0.070 | 0.071 | 0.071 |
| 单连接阶段 RSS增量/MiB | 3.39 | 3.41 | 3.39 | 3.48 |

### spoken

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| generic_count | 0.003 | 0.002 | 0.003 | 0.003 |
| generic_page100 | 0.052 | 0.052 | 0.052 | 0.054 |
| generic_like | 0.122 | 0.120 | 0.122 | 0.124 |
| 单连接阶段 RSS增量/MiB | 1.02 | 1.05 | 1.00 | 1.05 |

### vocabulary

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| sql_count | 2.152 | 2.164 | 2.345 | 2.514 |
| sql_page50 | 0.026 | 0.026 | 0.027 | 0.027 |
| sql_fuzzy_count | 39.569 | 39.862 | 40.483 | 41.011 |
| sql_standard_words | 1.353 | 1.352 | 1.358 | 1.366 |
| 单连接阶段 RSS增量/MiB | 3.23 | 5.78 | 10.73 | 20.20 |

### gis

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| search_beijing | 0.631 | 0.640 | 0.629 | 0.648 |
| children_beijing | 0.006 | 0.006 | 0.006 | 0.006 |
| bbox_candidates | 0.009 | 0.009 | 0.009 | 0.010 |
| boundary_blobs | 2.318 | 2.355 | 2.520 | 2.689 |
| 单连接阶段 RSS增量/MiB | 3.28 | 5.83 | 10.80 | 20.30 |

### characters_attach

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| matrix_join_5_locations | 15.315 | 15.320 | 15.345 | 15.258 |
| 单连接阶段 RSS增量/MiB | 6.75 | 6.72 | 6.78 | 6.69 |

### toponyms

| case | 2000 KiB | 4096 KiB | 8192 KiB | 16000 KiB |
| --- | ---: | ---: | ---: | ---: |
| names_contains20 | 0.023 | 0.024 | 0.024 | 0.023 |
| points_prefix5000 | 157.834 | 143.147 | 131.589 | 135.395 |
| divisions_children | 0.015 | 0.016 | 0.016 | 0.016 |
| 单连接阶段 RSS增量/MiB | 3.22 | 5.83 | 10.73 | 20.20 |
