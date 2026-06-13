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
- [后续开发计划](#6-后续开发计划)
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
┌─────────────────────────────────────────┐
│          接入层 (Frontend)               │
│    HTML/CSS/JS (MVP) → SPA (未来)       │
└──────────────┬──────────────┬───────────┘
               │ HTTP/REST    │ WebSocket
┌──────────────▼──────────────▼───────────┐
│         逻辑层 (BFF/API)                 │
│    FastAPI v0.3.0 + Celery + WebSocket   │
└──────┬──────────┬──────────┬────────────┘
       │          │          │
┌──────▼──┐ ┌────▼───┐ ┌───▼────────┐
│ 剧照识别  │ │文本聚合  │ │ 垂直站点    │
│ Yandex   │ │Google   │ │ TPB/1337x  │
│ SerpApi  │ │Dork策略  │ │ YTS/BTDigg │
│ ImageHost│ │Baidu Dork│ │ 动态爬虫(3)│
└──────┬──┘ └────┬───┘ └───┬────────┘
       │          │          │
┌──────▼──────────▼──────────▼──────────┐
│       提取层 (Link Extractor)          │
│ Magnet · Torrent · ED2K · CloudDrive  │
│ Stream · 提取码提取 · 链接有效性校验    │
└────────────────┬──────────────────────┘
                 │
┌────────────────▼──────────────────────┐
│       持久层 (Database + Cache)        │
│ PostgreSQL (元数据) ←→ Redis (快速缓存) │
│ 双缓存策略: Redis(5min) + DB(30min)    │
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

### 第一阶段：MVP ✅ 已完成

**目标**：实现「文本搜资源」基础全流程

- [x] FastAPI 后端基础架构
- [x] Google Dorking 模块（8 条 Dork 查询策略）
- [x] 适配 5 个主流磁力站爬虫（TPB / 1337x / YTS / BTDigg / RARBG）
- [x] 链接提取与清洗（Magnet / ED2K / 网盘 / 在线流）
- [x] 结果去重与质量评分排序
- [x] API 接口（`/api/search` / `/api/sources` / `/api/health`）
- [x] 前端搜索页面（暗色主题，搜索/筛选/复制/打开）
- [ ] ⬜ 环境依赖安装与运行验证
- [ ] ⬜ 单元测试（pytest）

### 第二阶段：视觉引擎 + 持久化 ✅ 已完成

**目标**：支持上传剧照直接找资源

- [x] 集成图片搜索 API（Yandex Reverse Image + SerpApi Google Lens）
- [x] 图像→元数据提取（电影名、年代）
- [x] TMDb/OMDb 元数据补充
- [x] PostgreSQL + SQLAlchemy 模型
- [x] 资源指纹库（InfoHash 唯一键）
- [x] 链接有效性异步校验
- [x] Redis 缓存
- [x] 图片上传托管服务（ImgBB + Telegraph）

### 第三阶段：深度爬虫 + 异步优化 ✅ 大部分已完成

**目标**：提升资源覆盖率，实现优先级分发

- [x] Playwright 动态爬虫（TorrentGalaxy / LimeTorrents / Nyaa.si）
- [x] Celery 异步任务调度（搜索 / 链接验证）
- [x] WebSocket 实时进度推送
- [x] 在线观看地址兜底（流媒体解析）
- [x] 网盘提取码自动获取（百度/阿里/夸克）
- [ ] ⬜ 云盘直连爬虫完善（BaiduPan 直接搜索）

### 第四阶段：稳定化 + 测试覆盖 🔄 当前阶段

**目标**：提升项目健壮性与可维护性

- [ ] 单元测试（pytest + pytest-asyncio）
- [ ] 集成测试（API 端点全链路）
- [ ] 环境一键部署验证
- [ ] 爬虫容错与重试机制增强
- [ ] Google 反爬绕过策略优化
- [ ] 前端错误处理与体验优化
- [ ] 配置热加载

### 第五阶段：社区化 + 部署扩展（未来）

**目标**：提升性能，为社区化做准备

- [ ] 用户账户体系（注册/登录/收藏夹）
- [ ] 求片功能（社区互助）
- [ ] Vue/React 前端重构
- [ ] Docker + Docker Compose 容器化
- [ ] Elasticsearch 全文搜索
- [ ] 分布式爬虫集群（Scrapy-Redis）

---

## 5. 存储策略

| 层级 | 内容 |
|:---|:---|
| **元数据层** | 电影名称、年代、海报、导演、IMDb ID |
| **资源关联层** | 电影 ID ↔ 各平台资源链接映射 |
| **指纹校验** | 磁力链接 InfoHash 避免重复存储 |

---

## 6. 后续开发计划

### 短期目标（第 1-2 周）— 稳定化 + 测试

| 优先级 | 任务 | 说明 |
|:---:|:---|:---|
| 🔴 P0 | **单元测试覆盖** | 为 `search_engine`、`link_extractor`、`link_validator`、`crawlers` 编写 pytest 测试 |
| 🔴 P0 | **集成测试** | 编写 API 端点全链路测试（`/api/search`, `/api/health`, `/api/admin/stats`） |
| 🔴 P0 | **环境验证** | 验证 `pip install -r requirements.txt` + `python main.py` 完整流程 |
| 🟡 P1 | **爬虫容错增强** | 添加请求重试、指数退避、代理轮换机制 |
| 🟡 P1 | **Google 反爬绕过** | 集成 `rotating_proxies` + 请求间隔随机化 |
| 🟡 P1 | **前端错误处理** | 完善超时/断网/空结果的 UI 反馈 |
| 🟢 P2 | **配置热加载** | 修改 `config.yaml` 后无需重启服务 |

### 中期目标（第 3-4 周）— 功能增强

| 优先级 | 任务 | 说明 |
|:---:|:---|:---|
| 🔴 P0 | **云盘直连爬虫** | 补齐 `core/crawlers/cloud_drives.py` 中的 BaiduPan 直接搜索 |
| 🟡 P1 | **搜索结果缓存预热** | 热门搜索词定时刷新缓存 |
| 🟡 P1 | **搜索历史趋势** | `/api/admin/trends` 展示热门搜索词 |
| 🟢 P2 | **代理池集成** | 对接免费/付费代理 API，自动切换 |
| 🟢 P2 | **Playwright 云盘爬虫** | 用 Playwright 处理需要登录的云盘页面 |

### 长期目标（第 5 周+）

| 方向 | 方案 |
|:---|:---|
| **容器化部署** | Docker + Docker Compose（FastAPI + Redis + PostgreSQL + Celery Worker） |
| **前端重构** | Vue 3 / React SPA，支持图片上传拖拽 |
| **用户体系** | 注册/登录/收藏夹/搜索历史 |
| **社区功能** | 求片区、资源评分、评论 |
| **存储升级** | Elasticsearch 全文搜索 |
| **架构升级** | 分布式爬虫集群（Scrapy-Redis） |
| **智能识别** | 自建 CLIP 视觉模型，剧照特征向量化 |

---

## 7. 开发进度报告

> 最后更新：2026-06-11

### 整体进度

```
第一阶段 (MVP):     ████████████████████  100%  ✅
第二阶段 (视觉):     ██████████████████░░   90%  ✅
第三阶段 (深度):     ████████████████░░░░   80%  ✅
第四阶段 (社区):     ░░░░░░░░░░░░░░░░░░░░    0%  ⏳

整体项目:           ███████████░░░░░░░░░░   55%
```

### 第一阶段（MVP）— ✅ 已完成（19/19 模块）

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

> ⬜ **待办**：环境依赖安装与运行验证 · 单元测试（pytest）

### 第二阶段（视觉引擎 + 持久化）— ✅ 已完成（9/9 模块）

| 模块 | 文件 | 状态 |
|:---|:---|:---:|
| 数据库连接管理 | `core/database.py` | ✅ |
| SQLAlchemy ORM 模型 | `core/models/db_models.py` | ✅ |
| Alembic 迁移配置 | `alembic/` + `alembic.ini` | ✅ |
| CRUD 服务层（Movie/Resource/Cache） | `core/services.py` | ✅ |
| Redis 缓存集成 | `core/cache.py` | ✅ |
| 链接有效性校验（磁力/HTTP/网盘） | `core/link_validator.py` | ✅ |
| 图片搜索 API（Yandex + SerpApi） | `api/routes/search.py` | ✅ |
| 图像→元数据提取 | `core/image_search.py` | ✅ |
| TMDb/OMDb 元数据补充 | `core/metadata.py` | ✅ |
| 图片上传托管服务 | `core/uploader.py` | ✅ |

> ⚠️ **注意**：图像搜索功能需要配置 API Key（`SERPAPI_KEY` / `TMDB_API_KEY`），参见 `.env.example`。Yandex 免费逆向搜图无需 Key。

### 第三阶段（深度爬虫 + 异步优化）— ✅ 大部分已完成（5/6 模块）

| 模块 | 文件 | 状态 |
|:---|:---|:---:|
| Playwright 动态爬虫（3 站点） | `core/crawlers/dynamic.py` | ✅ |
| Celery 异步任务调度 | `core/tasks.py` | ✅ |
| WebSocket 实时进度推送 | `api/routes/ws.py` | ✅ |
| 在线观看地址兜底 | `core/stream_parser.py` | ✅ |
| 网盘提取码自动获取 | `core/cloud_extractor.py` | ✅ |
| 云盘直连爬虫（Baidu/Ali/Quark 占位） | `core/crawlers/cloud_drives.py` | ⏳ 占位实现 |

### 第四阶段（社区化 + 部署）— ⏳ 未开始

| 模块 | 说明 |
|:---|:---|
| 用户账户体系 | 注册/登录/收藏夹 |
| 求片功能 | 社区互助 |
| Vue/React 前端重构 | 从原生 HTML → SPA |
| Docker 容器化 | docker-compose |
| 性能压测 | 并发搜索基准测试 |

### 项目结构（v0.3.0）

```
Rare_Movie_Search_Engine/
├── .env.example              # 环境变量模板
├── .gitignore                # Git 忽略规则
├── requirements.txt          # Python 依赖
├── main.py                   # 入口文件
├── alembic.ini               # 数据库迁移配置
├── plan.md                   # 原始开发计划
├── README.md                 # 本文件
├── quick_test.py             # 快速集成测试脚本
│
├── alembic/                  # 数据库迁移脚本
│   ├── env.py                # Alembic 异步引擎配置
│   └── script.py.mako        # 迁移模板
│
├── config/
│   ├── config.py             # 配置管理 (pydantic-settings)
│   └── config.yaml           # 爬虫站点 + Dork 策略
│
├── api/
│   ├── server.py             # FastAPI 应用工厂 v0.3.0
│   └── routes/
│       ├── search.py         # 搜索 API (文本 + 图片 + 上传)
│       ├── admin.py          # 管理/监控 API (统计/缓存/健康)
│       └── ws.py             # WebSocket 实时搜索进度
│
├── core/
│   ├── __init__.py
│   ├── database.py           # 数据库连接 + session 管理
│   ├── search_engine.py      # 搜索引擎编排 (双缓存)
│   ├── link_extractor.py     # 链接提取 (Magnet/ED2K/网盘)
│   ├── link_validator.py     # 链接有效性校验
│   ├── cache.py              # Redis 缓存层
│   ├── services.py           # CRUD 服务层
│   ├── image_search.py       # 逆向搜图 (Yandex + SerpApi)
│   ├── metadata.py           # 元数据补充 (TMDb + OMDb)
│   ├── uploader.py           # 图片上传托管 (ImgBB + Telegraph)
│   ├── cloud_extractor.py    # 网盘提取码自动提取
│   ├── stream_parser.py      # 在线流媒体地址兜底
│   ├── tasks.py              # Celery 异步任务定义
│   ├── crawlers/
│   │   ├── base.py           # 爬虫抽象基类
│   │   ├── torrent_sites.py  # TPB / 1337x / YTS 实现
│   │   ├── cloud_drives.py   # 网盘爬虫 (Baidu/Ali/Quark)
│   │   └── dynamic.py        # Playwright 动态爬虫
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

# 2. （可选）安装 Playwright 浏览器（动态爬虫需要）
playwright install chromium

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 设置 API Key（可选，不设置仍可使用基础搜索）
#   SERPAPI_KEY   — 图片搜索（已有测试 Key）
#   TMDB_API_KEY  — 元数据补充（免费注册）
#   DATABASE_URL  — PostgreSQL（可选，不设置使用无持久化模式）

# 4. 启动服务
python main.py

# 5. 访问
# http://localhost:8000             — 前端搜索页面
# http://localhost:8000/docs        — API 文档 (Swagger)
# http://localhost:8000/api/health  — 健康检查
```

### API 概览

| 端点 | 方法 | 说明 |
|:---|:---:|:---|
| `/api/search?q=Inception` | GET | 文本搜索电影资源 |
| `/api/search/image?image_url=...` | GET | 图片 URL 搜索 |
| `/api/search/image/upload` | POST | 上传图片文件搜索 |
| `/api/sources` | GET | 列出所有可用搜索源 |
| `/api/admin/stats` | GET | 数据库统计 |
| `/api/admin/cache/clear` | POST | 清除缓存 |
| `/api/admin/health/full` | GET | 完整健康检查 |
| `/ws/search?q=Inception` | WS | WebSocket 实时搜索 |
