# 压力测试配置文件
# Stress Test Configuration

# ==================== 基础配置 ====================
# 服务器地址（根据您的测试环境修改）
BASE_URL = "http://localhost:5000"  # 本地测试
# BASE_URL = "https://dialects.yzup.top"  # 生产环境测试（谨慎使用！）

# ==================== 测试用户配置 ====================
# 测试用户凭证（需要先在系统中创建这些用户）
TEST_USERS = [
    {"username": "testuser1", "password": "Test123456"},
    {"username": "testuser2", "password": "Test123456"},
    {"username": "testuser3", "password": "Test123456"},
]

# 管理员用户（用于测试管理员端点）
ADMIN_USER = {
    "username": "admin",
    "password": "AdminPass123"
}

# ==================== 测试数据配置 ====================
# 用于测试的汉字列表
TEST_CHARACTERS = ["我", "你", "他", "中", "国", "语", "言", "方", "音", "字"]

# 用于测试的地点名称
TEST_LOCATIONS = ["北京", "上海", "广州", "深圳", "杭州"]

# 用于测试的区域
TEST_REGIONS = ["华北", "华东", "华南", "西南", "东北"]

# ==================== 压测参数配置 ====================
# 并发用户数
CONCURRENT_USERS = 50

# 每秒启动用户数
SPAWN_RATE = 5

# 测试持续时间（秒）
TEST_DURATION = 300  # 5分钟

# 用户请求间隔（秒）
WAIT_TIME_MIN = 1
WAIT_TIME_MAX = 3

# ==================== 端点权重配置 ====================
# 不同端点的访问权重（模拟真实用户行为）
ENDPOINT_WEIGHTS = {
    "search_chars": 40,      # 搜索字符 - 最常用
    "phonology": 20,         # 音韵分析 - 较常用
    "get_locs": 15,          # 获取地点列表
    "get_coordinates": 10,   # 获取坐标
    "get_regions": 10,       # 获取区域
    "custom_query": 5,       # 自定义查询
}

# ==================== 监控配置 ====================
# 是否启用详细日志
VERBOSE_LOGGING = True

# 响应时间阈值（毫秒）
RESPONSE_TIME_THRESHOLD = {
    "fast": 100,      # 快速响应
    "normal": 500,    # 正常响应
    "slow": 1000,     # 慢响应
    "timeout": 5000,  # 超时阈值
}
