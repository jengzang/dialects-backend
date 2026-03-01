# 🚀 API 启动 - 最终指南

> **📚 完整文档已更新！** 查看以下新文档获取详细信息：
> - [API Reference](API_REFERENCE.md) - 完整的端点文档（18个端点）
> - [Frontend Integration Guide](FRONTEND_INTEGRATION_GUIDE.md) - Vue 3 集成指南
> - [API Deployment Guide](API_DEPLOYMENT_GUIDE.md) - 部署和配置指南
> - [API Quick Reference](API_QUICK_REFERENCE.md) - 快速参考手册

## 你遇到的问题

### 问题1：ImportError
```bash
python api/main.py  ❌
# ImportError: attempted relative import with no known parent package
```

**原因**：不能直接运行 `api/main.py`，因为它使用了相对导入。

### 问题2：502 Bad Gateway
测试脚本报错 502，因为 API 服务器没有运行。

## ✅ 解决方案：正确启动API

### 第1步：打开终端

- **Windows**: PowerShell 或 CMD
- **Cygwin/Git Bash**: Bash 终端

### 第2步：进入项目目录

```bash
cd C:\Users\joengzaang\PycharmProjects\villages-ML
```

**验证**：运行 `dir` (Windows) 或 `ls`，应该看到 `api` 文件夹。

### 第3步：启动API服务器

**方式A：使用 uvicorn（推荐）**

```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

**方式B：使用启动脚本**

```bash
# Windows
start_api.bat

# Linux/Mac/Cygwin
./start_api.sh
```

### 第4步：确认启动成功

看到以下输出说明成功：

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] with StatReload
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**⚠️ 重要**：保持这个终端窗口运行！不要关闭它。

### 第5步：验证API工作

**方法1：浏览器（最简单）**

打开浏览器，访问：
```
http://127.0.0.1:8000/docs
```

应该看到 Swagger UI 文档界面。

**方法2：curl 命令**

在**新的终端窗口**运行：
```bash
curl http://127.0.0.1:8000/health
```

应该返回：
```json
{"status":"healthy"}
```

**方法3：测试脚本**

在**新的终端窗口**运行：
```bash
cd C:\Users\joengzaang\PycharmProjects\villages-ML
python scripts\test_api.py
```

## 🎯 快速命令参考

```bash
# 1. 进入目录
cd C:\Users\joengzaang\PycharmProjects\villages-ML

# 2. 启动API（选择一种）
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
# 或
start_api.bat

# 3. 在浏览器访问
# http://127.0.0.1:8000/docs

# 4. 停止服务器
# 按 Ctrl+C
```

## ❌ 常见错误

### 错误：ModuleNotFoundError: No module named 'fastapi'

**解决**：
```bash
pip install -r api/requirements.txt
```

### 错误：ModuleNotFoundError: No module named 'api'

**解决**：确保在项目根目录
```bash
cd C:\Users\joengzaang\PycharmProjects\villages-ML
pwd  # 或 cd（查看当前目录）
```

### 错误：Address already in use

**解决**：端口被占用，使用不同端口
```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8001
```

### 错误：sqlite3.OperationalError

**解决**：检查数据库文件
```bash
ls data/villages.db  # 或 dir data\villages.db
```

## 📋 完整检查清单

启动前：
- [ ] 已安装依赖：`pip install -r api/requirements.txt`
- [ ] 在项目根目录：`cd C:\Users\joengzaang\PycharmProjects\villages-ML`
- [ ] 数据库文件存在：`ls data/villages.db`

启动时：
- [ ] 使用正确命令：`uvicorn api.main:app ...`
- [ ] 看到 "Application startup complete" 消息
- [ ] 终端保持运行

验证时：
- [ ] 浏览器可访问：http://127.0.0.1:8000/docs
- [ ] 或 curl 返回正常：`curl http://127.0.0.1:8000/health`

## 🆘 仍然有问题？

### 运行诊断脚本

```bash
cd C:\Users\joengzaang\PycharmProjects\villages-ML
python scripts/diagnose_api.py
```

这会检查：
- Python 版本
- 依赖是否安装
- 数据库文件是否存在
- 模块是否可以导入

### 查看详细文档

- `docs/API_CORRECT_STARTUP.md` - 正确启动方式详解
- `docs/API_STARTUP_VISUAL_GUIDE.md` - 图解说明
- `docs/API_QUICKSTART.md` - 快速启动指南

## 💡 关键要点

1. **不要直接运行** `python api/main.py`
2. **必须使用** `uvicorn api.main:app`
3. **必须在项目根目录**运行命令
4. **保持终端运行**，API 才能响应请求
5. **使用浏览器**访问 `/docs` 最简单

## 🎉 成功标志

当你看到：
- ✅ 终端显示 "Application startup complete"
- ✅ 浏览器能打开 http://127.0.0.1:8000/docs
- ✅ Swagger UI 显示所有 API 端点

恭喜！API 已成功启动，可以开始使用了。
