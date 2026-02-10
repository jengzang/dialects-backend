"""
serve.py
統一入口（放在項目根目錄）：
- 提供給 Docker / gunicorn 使用
- 保證 sys.path 正確，能導入 app/main.py 里的 FastAPI 實例
"""

import sys
from pathlib import Path

# 項目根目錄
BASE_DIR = Path(__file__).resolve().parent

# 確保項目根在 sys.path
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 導入真正的 FastAPI app
from app.main import app  # noqa
