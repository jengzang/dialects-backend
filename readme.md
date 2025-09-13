# 方言比较小站 - 后端

访问网站：[方音圖鑒 - dialects.yzup.top](https://dialects.yzup.top/)

## 项目概述

**方言比较小站** 是一个基于 **FastAPI** 的网站，主要提供以下功能：

- 按中古地位整理汉字读音
- 查询某音位的中古来源
- 查字、查调
- 获取地理坐标等
- 用户登录系统

该项目旨在为方言学术研究提供便捷的数据查询与分析平台。

## 相关仓库

- **[预处理字表](https://github.com/jengzang/dialects-build)**  
  [![dialects-build](https://img.shields.io/badge/Repo-dialects--build-ff69b4?logo=github&logoColor=white&style=for-the-badge)](https://github.com/jengzang/dialects-build)  
  方言比较网站的数据预处理仓库。

- **[前端代码](https://github.com/jengzang/dialects-js-frontend)**  
  [![dialects-js-frontend](https://img.shields.io/badge/Repo-dialects--js--frontend-0088ff?logo=github&logoColor=white&style=for-the-badge)](https://github.com/jengzang/dialects-js-frontend)  
  方言比较网站的前端代码，基于原生 JavaScript 和 Vue 框架。


## 安装依赖及运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务
```bash
python run.py
```

## 项目结构

```plaintext
backend-fastapi/
├── app/
│   ├── __init__.py      # 初始化文件
│   ├── main.py          # FastAPI 应用入口
│   ├── auth/            # 用户登录模块
│   ├── custom/          # 用户添加、读取自定义数据
│   ├── routes/          # 路由文件
│   ├── schemas/         # 数据模型/模式
│   ├── service/         # 服务逻辑层
│   └── statics/         # 静态文件
├── common/              # 通用工具类
├── data/                # 数据相关文件
├── logs/                # 日志文件
└── requirements.txt     # 项目依赖
```
