# 🎬 CineSeeker — 稀有电影搜索引擎

> **CineSeeker**（Cine + Seeker）是一个高度垂直的稀有电影聚合搜索引擎。  
> 通过集成多模态输入（文本与图片）、多源数据抓取以及自动化链接解析，为用户提供"一键式"的稀有电影下载资源。

---

## 📋 目录

- [项目定位](#1-项目定位)
- [核心架构](#2-核心架构)
- [技术栈](#3-技术栈)
- [开发阶段规划](#4-开发阶段规划)
- [存储策略](#5-存储策略)
- [后续升级预案](#6-后续升级预案)
- [开发进度报告](#7-开发进度报告)

---

## 1. 项目定位

一个垂直于稀有电影资源的聚合搜索引擎。通过图像识别和多源爬虫技术，解决用户 **"看到剧照不知道电影名"** 以及 **"搜到电影名找不到下载链接"** 的痛点。

### 核心设计原则

| 原则 | 说明 |
|:---|:---|
| **资源优先级** | 🥇 磁力/种子 > 🥈 网盘资源 > 🥉 在线播放 |
| **技术选型** | Python 为核心，异步架构确保并发搜索性能 |
| **演进路线** | 纯工具 → 本地存储 → 电影爱好者社区 |

---

## 2. 核心架构

采用模块化分层设计，初期 Python 快速交付，后期可微服务化。

```
┌───────────────────────────────────────┐
│        接入层 (Frontend)               │
│  HTML/CSS/JS (MVP) → React (未来)      │
└──────────────────┬────────────────────┘
                   │ HTTP / WebSocket
┌──────────────────▼────────────────────┐
│       逻辑层 (BFF/API)                 │
│         FastAPI + Celery               │
└──────┬────────────┬────────────┬──────┘
       │            │            │
┌──────▼────┐ ┌────▼────┐ ┌────▼──────┐
│ 剧照识别引擎 │ │文本聚合引擎│ │ 垂直站点引擎 │
│Yandex/Google│ │Google   │ │ PT站/磁力站 │
│ 逆向搜图API │ │Dork/Baidu│ │ 网盘聚合站  │
└──────┬────┘ └────┬────┘ └────┬──────┘
       │            │            │
┌──────▼────────────▼────────────▼──────┐
│        提取层 (Link Extractor)          │
│   Magnet · Torrent · ED2K · CloudDrive │
└────────────────┬──────────────────────┘
                 │
┌────────────────▼──────────────────────┐
│        持久层 (Database)               │
│  PostgreSQL (元数据) + Redis (缓存)     │
└───────────────────────────────────────┘
```

---

## 3. 技术栈

| 维度 | 选型 | 说明 |
|:---|:---|:---|
| **后端框架** | FastAPI (Python 3.10+) | 高性能异步 API |
| **任务调度** | Celery + Redis | 耗时任务异步处理 |
| **图像识别** | Yandex Reverse Image / SerpApi | 剧照高精度识别 |
| **爬虫系统** | HTTPX (Async) + Playwright | 静态+动态页面解析 |
| **数据库** | PostgreSQL + SQLAlchemy (async) | 资源元数据存储 |
| **缓存层** | Redis | 热门结果缓存 |
| **搜索技术** | Google Dorking / XPath / CSS | 精准提取下载链接 |
| **前端** | 原生 HTML/CSS/JS (MVP) | 暗色现代化 UI |

---

## 4. 开发阶段规划

### 第一阶段：MVP（第 1-2 周）

**目标**：实现「文本搜资源」基础全流程

- [x] FastAPI 后端基础架构
- [x] Google Dorking 模块（8 条 Dork 查询策略）
- [x] 适配 5 个主流磁力站爬虫（TPB / 1337x / YTS / BTDigg / RARBG）
- [x] 链接提取与清洗（Magnet / ED2K / 网盘 / 在线流）
- [x] 结果去重与质量评分排序
- [x] API 接口（`/api/search` / `/api/sources` / `/api/health`）
- [x] 前端搜索页面（暗色主题，搜索/筛选/复制/打开）
- [ ] 环境依赖安装与运行验证
- [ ] 单元测试

### 第二阶段：视觉引擎与持久化（第 3-4 周）

**目标**：支持上传剧照直接找资源

- [ ] 集成图片搜索 API（Yandex Reverse Image）
- [ ] 图像→元数据提取（电影名、年代）
- [ ] TMDb/豆瓣 元数据补充
- [ ] PostgreSQL + SQLAlchemy 模型
- [ ] 资源指纹库（InfoHash 唯一键）
- [ ] 链接有效性异步校验
- [ ] Redis 缓存

### 第三阶段：深度爬虫与优化（第 5-6 周）

**目标**：提升资源覆盖率，实现优先级分发

- [ ] Playwright 动态爬虫（JS 渲染 / Cloudflare）
- [ ] Celery 异步任务调度
- [ ] WebSocket 实时进度推送
- [ ] 在线观看地址兜底
- [ ] 网盘提取码自动获取

### 第四阶段：扩展与社区化（第 7 周+）

**目标**：提升性能，为社区化做准备

- [ ] 用户账户体系（收藏夹、求片区）
- [ ] API 文档完善（OpenAPI）
- [ ] Docker 容器化部署

---

## 5. 存储策略

| 层级 | 内容 |
|:---|:---|
| **元数据层** | 电影名称、年代、海报、导演、IMDb ID |
| **资源关联层** | 电影 ID ↔ 各平台资源链接映射 |
| **指纹校验** | 磁力链接 InfoHash 避免重复存储 |

---

## 6. 后续升级预案

| 方向 | 方案 |
|:---|:---|
| **架构升级** | 分布式爬虫集群（Scrapy-Redis） |
| **存储升级** | Elasticsearch 全文搜索 |
| **智能识别** | 自建 CLIP 视觉模型，剧照特征向量化 |
| **部署** | Docker + Docker Compose 一键部署 |

---

## 7. 开发进度报告

> 最后更新：2026-05-11

### 整体进度

```
第一阶段 (MVP):     ████████████████████  100%  ✅
第二阶段 (视觉):     ██████████░░░░░░░░░░   50%  🔄  
第三阶段 (深度):     ░░░░░░░░░░░░░░░░░░░░    0%
第四阶段 (社区):     ░░░░░░░░░░░░░░░░░░░░    0%

整体项目:           █████░░░░░░░░░░░░░░░   30%
```

### 第一阶段（MVP）— ✅ 已全部完成

| 模块 | 文件 | 状态 |
|:---|:---|:---:|
| FastAPI 应用工厂 | `api/server.py` | ✅ |
| API 搜索路由 | `api/routes/search.py` | ✅ |
| API 管理路由 | `api/routes/admin.py` | ✅ |
| Google Dorking 引擎 | `core/search_engine.py` | ✅ |
| 站点爬虫管理器 | `core/search_engine.py` | ✅ |
| 搜索编排器（含缓存） | `core/search_engine.py` | ✅ |
| Pydantic 数据模型 | `core/models/schemas.py` | ✅ |
| 链接提取工具 | `core/link_extractor.py` | ✅ |
| 爬虫抽象基类 | `core/crawlers/base.py` | ✅ |
| TPB / 1337x / YTS 爬虫 | `core/crawlers/torrent_sites.py` | ✅ |
| 配置管理 | `config/config.py` | ✅ |
| 爬虫策略配置 | `config/config.yaml` | ✅ |
| 前端搜索页面 | `frontend/index.html` | ✅ |
| 前端样式 | `frontend/styles.css` | ✅ |
| 前端交互逻辑 | `frontend/script.js` | ✅ |
| 依赖清单 | `requirements.txt` | ✅ |
| 环境变量模板 | `.env.example` | ✅ |
| `.gitignore` | `.gitignore` | ✅ |
| README 文档 | `README.md` | ✅ |

### 第二阶段（视觉引擎 + 持久化）— 🔄 进行中 (50%)

| 模块 | 文件 | 状态 |
|:---|:---|:---:|
| 数据库连接管理 | `core/database.py` | ✅ |
| SQLAlchemy ORM 模型 | `core/models/db_models.py` | ✅ |
| Alembic 迁移配置 | `alembic/` + `alembic.ini` | ✅ |
| CRUD 服务层 | `core/services.py` | ✅ |
| Redis 缓存集成 | `core/cache.py` | ✅ |
| 链接有效性校验 | `core/link_validator.py` | ✅ |
| 搜索缓存集成（双缓存） | `core/search_engine.py` | ✅ |
| 图片搜索 API | `api/routes/search.py` | ⏳ 待实现（需 API Key） |
| 图像→元数据提取 | — | ⏳ 待实现 |
| TMDb 元数据补充 | — | ⏳ 待实现 |

### 第三阶段（深度爬虫 + 异步优化）— ⏳ 未开始

| 模块 | 说明 |
|:---|:---|
| Playwright 动态爬虫 | 处理 JS 渲染 / Cloudflare |
| Celery 异步任务调度 | 耗时任务后台处理 |
| WebSocket 实时进度 | 前端推送搜索进度 |
| 在线观看地址兜底 | 嵌入式播放器解析 |

### 第四阶段（扩展 + 社区化）— ⏳ 未开始

| 模块 | 说明 |
|:---|:---|
| 用户账户体系 | 注册/登录/收藏 |
| 求片功能 | 社区互助 |
| API 文档完善 | OpenAPI |
| Docker 容器化 | docker-compose |

### 项目结构

```
Rare_Movie_Search_Engine/
├── .env.example              # 环境变量模板
├── .gitignore                # Git 忽略规则
├── requirements.txt          # Python 依赖
├── main.py                   # 入口文件
├── alembic.ini               # 数据库迁移配置
├── plan.md                   # 原始开发计划
├── README.md                 # 本文件
│
├── alembic/                  # 数据库迁移脚本
│   ├── env.py
│   └── script.py.mako
│
├── config/
│   ├── config.py             # 配置管理 (pydantic-settings)
│   └── config.yaml           # 爬虫站点 + Dork 策略
│
├── api/
│   ├── server.py             # FastAPI 应用工厂 v0.2.0
│   └── routes/
│       ├── search.py         # 搜索 API (带缓存/持久化)
│       └── admin.py          # 管理/监控 API
│
├── core/
│   ├── __init__.py
│   ├── database.py           # 数据库连接 + session 管理
│   ├── search_engine.py      # 搜索引擎编排 (双缓存)
│   ├── link_extractor.py     # 链接提取 (Magnet/ED2K/网盘)
│   ├── link_validator.py     # 链接有效性校验
│   ├── cache.py              # Redis 缓存层
│   ├── services.py           # CRUD 服务层
│   ├── crawlers/
│   │   ├── base.py           # 爬虫抽象基类
│   │   └── torrent_sites.py  # TPB / 1337x / YTS 实现
│   └── models/
│       ├── schemas.py        # Pydantic 数据模型
│       └── db_models.py      # SQLAlchemy ORM 模型
│
└── frontend/
    ├── index.html            # 暗色主题搜索页面
    ├── styles.css            # 现代化 UI 样式
    └── script.js             # 前端交互逻辑
```

### 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 设置 DATABASE_URL (PostgreSQL 可选)

# 3. 启动服务
python main.py

# 4. 访问
# http://localhost:8000          — 前端搜索页面
# http://localhost:8000/docs     — API 文档
# http://localhost:8000/api/health — 健康检查
```
