Rare Movie Search Engine (CineSeeker) 开发计划书
1. 项目定位一个垂直于稀有电影资源的聚合搜索引擎。通过图像识别和多源爬虫技术，解决用户“看到剧照不知道电影名”以及“搜到电影名找不到下载链接”的痛点。
2. 核心架构 (Architecture)采用模块化分层设计，确保初期使用 Python 快速交付，后期可将核心模块（如爬虫、识别）微服务化。接入层 (Frontend): React/Next.js (Web 端) 或简单的 Streamlit (原型阶段)。逻辑层 (BFF/API): FastAPI (Python)，负责异步任务调度。引擎层 (Search Engines):剧照识别引擎：对接 Yandex/Google/Bing 逆向搜图 API。文本聚合引擎：封装对 Google/Baidu/DuckDuckGo 的搜索指令（Dorking）。
垂直站点引擎：针对 PT 站、磁力索引站、网盘聚合站的定制化爬虫。提取层 (Link Extractor): 自动解析目标网页，提取 Magnet/Torrent/CloudDrive 链接。持久层 (Database): PostgreSQL (存储电影元数据与资源链接) + Redis (缓存搜索结果)。
3. 开发阶段规划第一阶段：原型构建 (Phase 1: Foundation) 
- 第 1-2 周目标：实现“文本搜资源”的基础全流程。核心开发：搭建 FastAPI 基础框架。开发“Google Dorking”模块：通过 site: 指令精准锁定常见的磁力站和资源论坛。编写基础爬虫：适配 3-5 个主流磁力站（如 The Pirate Bay, 1337x）和网盘索引站。实现链接清洗：从 HTML 中提取标准 Magnet 协议和网盘分享链接。交付物：一个简单的 API，输入电影名，返回初步清洗后的磁力链接列表。第二阶段：图像识别增强 (Phase 2: Visual Search) 
- 第 3-4 周目标：支持上传剧照直接找资源。核心开发：集成图像识别：调用 Yandex Image Search API（目前对电影剧照识别率最高）。元数据提取：从识别结果中提取电影正式名称、上映年份。链式搜索逻辑：剧照 -> 电影名 -> 磁力搜索 -> 链接返回。存储系统：建立本地缓存表：如果同一个电影被多次搜索，直接从本地 DB 返回资源，减少 API 调用。第三阶段：深度解析与“兜底”机制 (Phase 3: Deep Crawling)
- 第 5-6 周目标：提升资源覆盖率，实现“磁力 > 网盘 > 在线”的优先级分发。核心开发：深度爬虫：使用 Playwright 处理那些需要模拟点击或绕过简单反爬的网页。优先级排序逻辑：磁力/种子（优先匹配 1080p/4K 关键字）。网盘资源（阿里云盘、夸克、百度云）。在线观看链接（嵌入式播放器地址解析）。链接状态校验：简单的异步 HEAD 请求，检测链接是否 404（针对网盘）。第四阶段：优化与扩展准备 (Phase 4: Optimization) 
- 第 7 周+目标：提升性能，为社区化做准备。性能优化：引入 Celery 异步处理耗时较长的全网搜索任务。前端接入 WebSocket，实时推送搜索进度。社区化预留：设计用户账户系统（收藏夹、求片区）。开放 API 接口，方便后续与其他影视工具集成。

4. 关键技术细节 (Tech Stack)模块推荐技术备注语言Python 3.10+核心生态丰富识别Yandex Reverse Image / SerpApi剧照识别的首选方案爬虫HTTPX (异步) + BeautifulSoup4 / Playwright处理动态加载页面数据库PostgreSQL + Tortoise-ORM结构化存储资源元数据搜索策略Google Dorking (e.g. intitle:index.of? mkv)绕过搜索引擎过滤，直达资源目录
5. 后续升级预案 (Scalability)架构升级：若访问量激增，将爬虫模块剥离为分布式爬虫集群（Scrapy-Redis）。存储升级：引入 Elasticsearch 实现对本地存储资源的全文搜索。智能识别：自建 CLIP 视觉模型，对剧照进行特征向量化，实现更精准的私有库识别。下一步行动建议环境配置：建议先申请一个 SerpApi 的 Key 或者研究 Yandex 搜图的解析脚本。小规模实验：手动收集 10 个最难找的电影名，测试在 Google 中使用哪些 Dorking 指令能直接搜到磁力链接，将这些逻辑转化为代码。
