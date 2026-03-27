# 文档整理方案

## 当前问题

1. **命名不一致** - 大写（FEATURE_OVERVIEW.md）和小写（custom_regions_frontend_guide.md）混用
2. **分类混乱** - 39 个文档全部平铺在 docs/ 根目录
3. **未跟踪文件** - 10 个文档未提交到 git
4. **临时文件** - temp_api_doc.py 不应该在 docs/

## 建议的文档分类结构

```
docs/
├── README.md                          # 文档索引（新建）
│
├── architecture/                      # 架构设计
│   ├── project_architecture.md        # 项目架构分析
│   ├── database_design.md             # 数据库设计
│   └── feature_overview.md            # 功能概览
│
├── api/                               # API 文档
│   ├── villagesml/                    # VillagesML API
│   │   ├── api_reference.md
│   │   ├── auth_guide.md
│   │   ├── frontend_guide.md
│   │   └── ...
│   ├── admin/                         # 管理员 API
│   │   └── custom_regions.md
│   ├── custom_regions/                # 自定义区域 API
│   │   ├── frontend_guide.md
│   │   └── frontend_checklist.md
│   └── ...
│
├── migration/                         # 迁移文档
│   ├── database_migration.md
│   ├── api_migration_guide.md
│   ├── migration_complete_report.md
│   └── ...
│
├── implementation/                    # 实现文档
│   ├── clustering/                    # 聚类功能
│   │   ├── endpoints_implementation.md
│   │   ├── endpoints_usage.md
│   │   ├── dbscan_parameter_tuning.md
│   │   ├── spatial_workflow.md
│   │   └── ...
│   ├── regions/                       # 区域功能
│   │   ├── endpoint_implementation.md
│   │   ├── hierarchy_update.md
│   │   └── ...
│   ├── vectors/                       # 向量功能
│   │   ├── api_complete.md
│   │   ├── compare_api.md
│   │   ├── fix.md
│   │   └── ...
│   └── ...
│
├── optimization/                      # 性能优化
│   ├── database_optimization.md
│   ├── indexes.md
│   ├── summary.md
│   └── ...
│
├── issues/                            # 问题报告
│   ├── database_issues.md
│   ├── regional_vectors_api_issues.md
│   └── ...
│
└── guides/                            # 使用指南
    ├── township_filter_guide.md
    ├── township_filter_standard.md
    └── ...
```

## 文件重命名和移动计划

### 1. 架构设计文档

```bash
mkdir -p docs/architecture
mv docs/FEATURE_OVERVIEW.md docs/architecture/feature_overview.md
mv docs/PROJECT_ARCHITECTURE_ANALYSIS.md docs/architecture/project_architecture.md
```

### 2. API 文档

```bash
mkdir -p docs/api/villagesml
mv docs/VILLAGESML_API_REFERENCE.md docs/api/villagesml/api_reference.md
mv docs/VILLAGESML_AUTH_GUIDE.md docs/api/villagesml/auth_guide.md
mv docs/VILLAGESML_AUTH_IMPLEMENTATION.md docs/api/villagesml/auth_implementation.md
mv docs/VILLAGESML_FRONTEND_GUIDE.md docs/api/villagesml/frontend_guide.md
mv docs/VillagesML_Regional_Hierarchy_Migration_Report.md docs/api/villagesml/regional_hierarchy_migration.md

mkdir -p docs/api/admin
mv docs/admin_custom_regions_implementation.md docs/api/admin/custom_regions.md

mkdir -p docs/api/custom_regions
mv docs/custom_regions_frontend_guide.md docs/api/custom_regions/frontend_guide.md
mv docs/custom_regions_frontend_checklist.md docs/api/custom_regions/frontend_checklist.md
```

### 3. 迁移文档

```bash
mkdir -p docs/migration
mv docs/DATABASE_MIGRATION_FOR_BACKEND.md docs/migration/database_migration.md
mv docs/BACKEND_API_MIGRATION_GUIDE.md docs/migration/api_migration_guide.md
mv docs/MIGRATION_COMPLETE_REPORT.md docs/migration/migration_complete_report.md
```

### 4. 实现文档

```bash
mkdir -p docs/implementation/clustering
mv docs/NEW_CLUSTERING_ENDPOINTS_IMPLEMENTATION.md docs/implementation/clustering/endpoints_implementation.md
mv docs/NEW_CLUSTERING_ENDPOINTS_USAGE.md docs/implementation/clustering/endpoints_usage.md
mv docs/DBSCAN_PARAMETER_TUNING.md docs/implementation/clustering/dbscan_parameter_tuning.md
mv docs/SPATIAL_CLUSTERING_WORKFLOW.md docs/implementation/clustering/spatial_workflow.md
mv docs/Spatial_Clustering_Regeneration_2026-02-24.md docs/implementation/clustering/spatial_regeneration_2026-02-24.md
mv docs/BACKEND_API_CHANGES_FOR_MULTI_CLUSTERING.md docs/implementation/clustering/api_changes_for_multi_clustering.md

mkdir -p docs/implementation/regions
mv docs/REGIONS_ENDPOINT_IMPLEMENTATION.md docs/implementation/regions/endpoint_implementation.md
mv docs/Regions_Hierarchy_Endpoint_Update.md docs/implementation/regions/hierarchy_update.md
mv docs/regional_hierarchy_fix_complete.md docs/implementation/regions/hierarchy_fix_complete.md
mv docs/regional_hierarchy_fix_phase1.md docs/implementation/regions/hierarchy_fix_phase1.md
mv docs/regional_hierarchy_fix_phase2.md docs/implementation/regions/hierarchy_fix_phase2.md
mv docs/api_hierarchy_status.md docs/implementation/regions/api_hierarchy_status.md

mkdir -p docs/implementation/vectors
mv docs/vector_api_complete.md docs/implementation/vectors/api_complete.md
mv docs/vector_compare_api.md docs/implementation/vectors/compare_api.md
mv docs/get_vectors_fix.md docs/implementation/vectors/fix.md

mkdir -p docs/implementation/semantic
mv docs/SEMANTIC_SUBCATEGORY_API_UPDATE.md docs/implementation/semantic/subcategory_api_update.md

mkdir -p docs/implementation/village
mv docs/Village_Search_Empty_Name_Filter.md docs/implementation/village/search_empty_name_filter.md

mkdir -p docs/implementation/township
mv docs/TOWNSHIP_FILTER_GUIDE.md docs/implementation/township/filter_guide.md
mv docs/TOWNSHIP_FILTER_STANDARD.md docs/implementation/township/filter_standard.md
mv docs/TOWNSHIP_FULL_PATH_SUPPORT.md docs/implementation/township/full_path_support.md

mkdir -p docs/implementation/subset
mv docs/subset_compare_api_update.md docs/implementation/subset/compare_api_update.md
```

### 5. 性能优化文档

```bash
mkdir -p docs/optimization
mv docs/API_Update_For_Database_Optimization.md docs/optimization/database_optimization.md
mv docs/performance_optimization_indexes.md docs/optimization/indexes.md
mv docs/performance_optimization_summary.md docs/optimization/summary.md
```

### 6. 问题报告

```bash
mkdir -p docs/issues
mv docs/DATABASE_ISSUES_REPORT.md docs/issues/database_issues.md
mv docs/regional_vectors_api_issues.md docs/issues/regional_vectors_api_issues.md
```

### 7. 清理临时文件

```bash
mkdir -p scripts
mv docs/temp_api_doc.py scripts/
```

## 执行顺序

1. 创建目录结构
2. 移动和重命名文件
3. 创建 docs/README.md 索引
4. 提交到 git
5. 更新 CLAUDE.md 中的文档路径引用

## 预期效果

- ✅ 文档按功能分类，易于查找
- ✅ 命名统一为小写 + 下划线
- ✅ 目录结构清晰，层次分明
- ✅ 所有文档提交到 git
- ✅ 临时文件移到 scripts/
