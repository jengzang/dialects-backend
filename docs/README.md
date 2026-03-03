# 项目文档索引

**最后更新：** 2026-03-03

本目录包含 FastAPI 方言比较工具的所有技术文档，按功能模块分类组织。

---

## 📁 目录结构

```
docs/
├── README.md                          # 本文件（文档索引）
├── architecture/                      # 架构设计文档
├── api/                               # API 接口文档
├── migration/                         # 数据库和 API 迁移文档
├── implementation/                    # 功能实现文档
├── optimization/                      # 性能优化文档
└── issues/                            # 问题报告和修复文档
```

---

## 🏗️ 架构设计 (architecture/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [project_architecture.md](architecture/project_architecture.md) | 项目架构分析与重组建议 | 16KB |
| [feature_overview.md](architecture/feature_overview.md) | 功能概览（完整功能清单） | 74KB |
| [reorganization_plan.md](architecture/reorganization_plan.md) | 文档重组计划 | - |

---

## 🔌 API 文档 (api/)

### VillagesML 自然村分析 API (api/villagesml/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [api_reference.md](api/villagesml/api_reference.md) | API 参考文档 | 3.6KB |
| [auth_guide.md](api/villagesml/auth_guide.md) | 认证指南 | 8.7KB |
| [auth_implementation.md](api/villagesml/auth_implementation.md) | 认证实现文档 | 11KB |
| [frontend_guide.md](api/villagesml/frontend_guide.md) | 前端对接指南 | 20KB |
| [regional_hierarchy_migration.md](api/villagesml/regional_hierarchy_migration.md) | 区域层级迁移报告 | 7.5KB |

### 管理员 API (api/admin/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [custom_regions.md](api/admin/custom_regions.md) | 管理员自定义区域管理接口 | 7.2KB |

### 自定义区域 API (api/custom_regions/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [frontend_guide.md](api/custom_regions/frontend_guide.md) | 前端对接指南 | 11KB |
| [frontend_checklist.md](api/custom_regions/frontend_checklist.md) | 前端开发检查清单 | 7.3KB |

---

## 🔄 迁移文档 (migration/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [database_migration.md](migration/database_migration.md) | 数据库迁移指南 | 22KB |
| [api_migration_guide.md](migration/api_migration_guide.md) | API 迁移指南 | 12KB |
| [migration_complete_report.md](migration/migration_complete_report.md) | 迁移完成报告 | 9.2KB |

---

## 🛠️ 功能实现文档 (implementation/)

### 聚类功能 (implementation/clustering/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [endpoints_implementation.md](implementation/clustering/endpoints_implementation.md) | 聚类端点实现 | 8.5KB |
| [endpoints_usage.md](implementation/clustering/endpoints_usage.md) | 聚类端点使用指南 | 11KB |
| [dbscan_parameter_tuning.md](implementation/clustering/dbscan_parameter_tuning.md) | DBSCAN 参数调优 | 3.7KB |
| [spatial_workflow.md](implementation/clustering/spatial_workflow.md) | 空间聚类工作流 | 5.9KB |
| [spatial_regeneration_2026-02-24.md](implementation/clustering/spatial_regeneration_2026-02-24.md) | 空间聚类重新生成 | 4.6KB |
| [api_changes_for_multi_clustering.md](implementation/clustering/api_changes_for_multi_clustering.md) | 多聚类 API 变更 | 8.9KB |

### 区域功能 (implementation/regions/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [endpoint_implementation.md](implementation/regions/endpoint_implementation.md) | 区域端点实现 | 8.3KB |
| [hierarchy_update.md](implementation/regions/hierarchy_update.md) | 层级端点更新 | 6.9KB |
| [hierarchy_fix_complete.md](implementation/regions/hierarchy_fix_complete.md) | 层级修复完成 | 7.1KB |
| [hierarchy_fix_phase1.md](implementation/regions/hierarchy_fix_phase1.md) | 层级修复第一阶段 | 6.4KB |
| [hierarchy_fix_phase2.md](implementation/regions/hierarchy_fix_phase2.md) | 层级修复第二阶段 | 4.7KB |
| [api_hierarchy_status.md](implementation/regions/api_hierarchy_status.md) | API 层级状态 | 7.7KB |

### 向量功能 (implementation/vectors/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [api_complete.md](implementation/vectors/api_complete.md) | 向量 API 完整实现 | 9.1KB |
| [compare_api.md](implementation/vectors/compare_api.md) | 向量对比 API | 5.2KB |
| [fix.md](implementation/vectors/fix.md) | 向量获取修复 | 4.9KB |

### 语义功能 (implementation/semantic/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [subcategory_api_update.md](implementation/semantic/subcategory_api_update.md) | 语义子类别 API 更新 | 9.8KB |

### 村庄功能 (implementation/village/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [search_empty_name_filter.md](implementation/village/search_empty_name_filter.md) | 村庄搜索空名称过滤 | 2.9KB |

### 乡镇功能 (implementation/township/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [filter_guide.md](implementation/township/filter_guide.md) | 乡镇过滤指南 | 6.4KB |
| [filter_standard.md](implementation/township/filter_standard.md) | 乡镇过滤标准 | 4.7KB |
| [full_path_support.md](implementation/township/full_path_support.md) | 完整路径支持 | 5.2KB |

### 子集功能 (implementation/subset/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [compare_api_update.md](implementation/subset/compare_api_update.md) | 子集对比 API 更新 | 6.2KB |

---

## ⚡ 性能优化 (optimization/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [database_optimization.md](optimization/database_optimization.md) | 数据库优化更新 | 11KB |
| [indexes.md](optimization/indexes.md) | 索引优化 | 2.6KB |
| [summary.md](optimization/summary.md) | 性能优化总结 | 3.6KB |

---

## 🐛 问题报告 (issues/)

| 文档 | 说明 | 大小 |
|------|------|------|
| [database_issues.md](issues/database_issues.md) | 数据库问题报告 | 6.3KB |
| [regional_vectors_api_issues.md](issues/regional_vectors_api_issues.md) | 区域向量 API 问题 | 9.9KB |

---

## 📝 文档规范

### 命名规范
- 使用小写字母 + 下划线（snake_case）
- 文件名应简洁明了，反映文档内容
- 示例：`api_reference.md`、`database_migration.md`

### 目录组织
- **architecture/** - 架构设计、系统概览
- **api/** - API 接口文档、前端对接指南
- **migration/** - 数据迁移、API 迁移
- **implementation/** - 具体功能实现细节
- **optimization/** - 性能优化相关
- **issues/** - 问题报告和修复记录

### 文档模板
每个文档应包含：
1. 标题和简介
2. 目录（如果内容较长）
3. 主要内容
4. 示例代码（如适用）
5. 注意事项
6. 更新日期

---

## 🔗 相关资源

- [项目 README](../README.md) - 项目主文档
- [CLAUDE.md](../CLAUDE.md) - Claude Code 项目指南
- [API 在线文档](http://localhost:5000/docs) - FastAPI 自动生成的 API 文档

---

## 📊 文档统计

- **总文档数：** 39 个
- **总大小：** ~350KB
- **最后整理：** 2026-03-03

---

**维护说明：** 添加新文档时，请更新本索引文件，并遵循命名和组织规范。
