"""
API 配置文件
包含两套并行的 API 日志记录系统配置
"""

# ========== 第一套：流量统计系统（TrafficLoggingMiddleware）=============
"""
# 用于记录 API 流量统计（请求次数、大小、响应时间等）
# 对应中间件：app/logs/service/api_logger.py -> TrafficLoggingMiddleware
# 记录到：ApiUsageLog 表（auth.db）
 1. TrafficLoggingMiddleware（流量统计）
位置：app/logs/service/api_logger.py
配置：RECORD_API / IGNORE_API
数据库：auth.db -> ApiUsageLog 表

功能：
- 记录每个 API 请求的流量统计
- 数据包括：请求次数、请求大小、响应大小、响应时间、用户 ID
- 过滤逻辑：
  if any(k in path for k in IGNORE_API) or not any(k in path for k in RECORD_API):
      跳过记录
用途：性能监控、用量统计、用户行为分析
"""

# 是否刪除一星期前的api記錄
CLEAR_WEEK = True

# 只记录路径中包含以下词的 API（简单字符串匹配）
RECORD_API = [
    "phonology",  # 可以匹配 "/api/phonology"
    "get_coordinates",  # 可以匹配 "/api/get_coordinates"
    "search_tones",  # 可以匹配 "/api/search_tones/"
    "search_chars",  # 可以匹配 "/api/search_chars/"
    "submit_form",
    "delete_form",
    "ZhongGu",
    "YinWei",
    "charlist",
    "sql",
    "api/tools",
]

# 不記錄帶有以下字段的 API（排除特定路由）
IGNORE_API = [
    "download",  # 下载类 API（避免记录大量下载请求）
    "progress",  # 进度查询类 API（避免记录频繁的轮询请求）
]

# ========== 第二套：详细参数日志系统（ApiLoggingMiddleware）=============
"""
# 用于记录 API 的详细参数（查询参数、请求体字段）
# 对应中间件：app/logs/service/api_limit_keyword.py -> ApiLoggingMiddleware
# 记录到：ApiKeywordLog 表（logs.db）
### 2. ApiLoggingMiddleware（详细参数日志）
位置：app/logs/service/api_limit_keyword.py
配置：API_ROUTE_CONFIG / API_WHITELIST / API_BLACKLIST
数据库：logs.db -> ApiKeywordLog 表

功能：
- 记录每个 API 请求的详细参数
- 数据包括：具体的查询参数、请求体字段
- 过滤逻辑：
  1. 检查黑名单（强制记录）
  2. 检查白名单（跳过记录）
  3. 精确匹配路由配置
  4. 通配符匹配路由配置
  5. 使用默认配置

用途：详细查询分析、调试、用户意图分析


## 匹配优先级（ApiLoggingMiddleware）

1. 黑名单（最高优先级）- 强制启用所有检查
2. 白名单 - 完全跳过检查
3. 精确匹配 - /api/phonology
4. 通配符匹配 - /sql/*
5. 默认配置（最低优先级）


## 配置建议

### 什么时候启用 log_params / log_body？
- 需要分析用户查询内容时：启用
- 查询 API、搜索 API：启用 log_params
- 提交表单、创建数据：启用 log_body
- 频繁轮询的进度查询：不启用（避免日志爆炸）
- 包含敏感 ID 的路由：不启用（避免泄露 task_id 等）

### 什么时候启用 rate_limit？
- 计算密集型 API：启用（防止滥用）
- 写入操作：启用（防止恶意提交）
- 简单查询 API：不启用（提升用户体验）

### 什么时候启用 require_login？
- 写入操作：启用（需要用户身份）
- 个人数据查询：启用（需要权限）
- 公开查询 API：不启用（方便访问）
"""

# 路由配置字典：为每个路由定义细粒度的控制
# 支持精确匹配（/api/phonology）和通配符匹配（/sql/*）
API_ROUTE_CONFIG = {
    "/api/phonology": {
        "rate_limit": True,  # 启用限流
        "require_login": False,  # 不强制登录（公开 API）
        "log_params": True,  # 记录查询参数（用于分析用户查询内容）
        "log_body": True,  # 记录请求体
    },
    "/api/phonology_matrix": {
        "rate_limit": True,
        "require_login": False,
        "log_params": True,
        "log_body": True,
    }, "/api/phonology_classification_matrix": {
        "rate_limit": True,
        "require_login": False,
        "log_params": True,
        "log_body": True,
    }, "/api/charlist": {
        "rate_limit": True,
        "require_login": False,
        "log_params": True,
        "log_body": True,
    }, "/api/ZhongGu": {
        "rate_limit": True,
        "require_login": False,
        "log_params": True,
        "log_body": True,
    }, "/api/YinWei": {
        "rate_limit": True,
        "require_login": False,
        "log_params": True,
        "log_body": True,
    }, "/api/search_chars": {
        "rate_limit": True,
        "require_login": False,
        "log_params": True,
        "log_body": False,  # GET 请求无 body，不需要记录
    }, "/api/search_tones": {
        "rate_limit": True,
        "require_login": False,
        "log_params": True,
        "log_body": False,
    }, "/sql/*": {
        "rate_limit": True,
        "require_login": False,
        "log_params": True,
        "log_body": True,
    }, "/api/get_coordinates": {
        "rate_limit": False,  # 不限流（查询类 API）
        "require_login": False,
        "log_params": True,
        "log_body": False,
    }, "/api/get_custom": {
        "rate_limit": False,
        "require_login": False,
        "log_params": True,
        "log_body": False,
    }, "/api/get_custom_feature": {
        "rate_limit": False,
        "require_login": False,
        "log_params": True,
        "log_body": False,
    }, "/api/get_locs/*": {
        "rate_limit": False,
        "require_login": False,
        "log_params": True,
        "log_body": False,
    }, "/api/get_partitions": {
        "rate_limit": False,
        "require_login": False,
        "log_params": True,
        "log_body": False,
    }, "/api/get_regions": {
        "rate_limit": False,
        "require_login": False,
        "log_params": True,
        "log_body": False,
    },

    # ===== Praat 声学分析 API =====
    # 路径设计规则：
    # - 创建操作（POST /uploads, POST /jobs）：不含 /progress/，返回新的 ID
    # - 查询/操作已有资源（包含 {task_id}/{job_id} 的路由）：包含 /progress/
    # - IGNORE_API 中的 "progress" 会过滤掉所有 /progress/* 路由的流量统计
    "/api/tools/praat/uploads": {
        "rate_limit": True,
        "require_login": True,  # 要求登录
        "log_params": False,  # 不记录参数
        "log_body": False,  # 不记录音频二进制数据（太大）
    }, "/api/tools/praat/uploads/progress/*": {
        "rate_limit": False,  # 不限流（查询、下载操作）
        "require_login": True,  # 要求登录
        "log_params": False,  # 不记录参数（避免泄露 task_id）
        "log_body": False,
    }, "/api/tools/praat/jobs": {
        "rate_limit": True,
        "require_login": True,  # 要求登录
        "log_params": False,  # 不记录参数
        "log_body": True,  # 记录分析参数（用于分析用户使用习惯）
    }, "/api/tools/praat/jobs/progress/*": {
        "rate_limit": False,  # 允许频繁轮询
        "require_login": True,  # 要求登录
        "log_params": False,  # 不记录参数（避免泄露 job_id）
        "log_body": False,
    }, "/api/tools/praat/capabilities": {
        "rate_limit": False,
        "require_login": False,  # 公开的能力查询接口
        "log_params": False,
        "log_body": False,
    }}

# ===== 默认配置 =====
# 未在 API_ROUTE_CONFIG 中列出的路由使用此默认配置
API_DEFAULT_CONFIG = {
    "rate_limit": False,  # 默认不限流
    "require_login": False,  # 默认不要求登录
    "log_params": False,  # 默认不记录参数
    "log_body": False,  # 默认不记录请求体
}

# ===== 白名单 =====
# 这些路由完全跳过 ApiLoggingMiddleware 检查
# 用于静态文件、认证页面等不需要日志记录的路由
API_WHITELIST = [
    "/auth/*",  # 认证相关（登录、注册等）
    "/__ping",  # 健康检查
    "/",  # 首页
    "/admin",  # 管理页面
    "/detail",  # 详情页
    "/intro",  # 介绍页
    "/menu",  # 菜单页
    "/explore",  # 探索页
    "/statics/*",  # 静态文件（CSS、JS、图片等）
]

# ===== 黑名单 =====
# 这些路由强制启用所有检查（限流、登录、日志）
# 用于敏感的管理员 API
API_BLACKLIST = [
    "/admin/api/*",  # 管理员 API（强制所有检查）
]

# ========== 中间件工作流程说明 =============
"""
## 两套并行的中间件系统

### 1. TrafficLoggingMiddleware（流量统计）
位置：app/logs/service/api_logger.py
配置：RECORD_API / IGNORE_API
数据库：auth.db -> ApiUsageLog 表

功能：
- 记录每个 API 请求的流量统计
- 数据包括：请求次数、请求大小、响应大小、响应时间、用户 ID
- 过滤逻辑：
  if any(k in path for k in IGNORE_API) or not any(k in path for k in RECORD_API):
      跳过记录

用途：性能监控、用量统计、用户行为分析


### 2. ApiLoggingMiddleware（详细参数日志）
位置：app/logs/service/api_limit_keyword.py
配置：API_ROUTE_CONFIG / API_WHITELIST / API_BLACKLIST
数据库：logs.db -> ApiKeywordLog 表

功能：
- 记录每个 API 请求的详细参数
- 数据包括：具体的查询参数、请求体字段
- 过滤逻辑：
  1. 检查黑名单（强制记录）
  2. 检查白名单（跳过记录）
  3. 精确匹配路由配置
  4. 通配符匹配路由配置
  5. 使用默认配置

用途：详细查询分析、调试、用户意图分析


## 匹配优先级（ApiLoggingMiddleware）

1. 黑名单（最高优先级）- 强制启用所有检查
2. 白名单 - 完全跳过检查
3. 精确匹配 - /api/phonology
4. 通配符匹配 - /sql/*
5. 默认配置（最低优先级）


## 配置建议

### 什么时候启用 log_params / log_body？
- 需要分析用户查询内容时：启用
- 查询 API、搜索 API：启用 log_params
- 提交表单、创建数据：启用 log_body
- 频繁轮询的进度查询：不启用（避免日志爆炸）
- 包含敏感 ID 的路由：不启用（避免泄露 task_id 等）

### 什么时候启用 rate_limit？
- 计算密集型 API：启用（防止滥用）
- 写入操作：启用（防止恶意提交）
- 简单查询 API：不启用（提升用户体验）

### 什么时候启用 require_login？
- 写入操作：启用（需要用户身份）
- 个人数据查询：启用（需要权限）
- 公开查询 API：不启用（方便访问）
"""
