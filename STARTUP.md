# 通用信息检索与智能分析系统
## 聚合分析平台 - 系统启动文档

## 系统架构

本系统由以下三个服务组成：

1. **LightRAG Server**（端口 9622）— 提供知识图谱、文档管理、检索功能 + 前端页面
2. **平台 API Server**（端口 8000）— 提供爬虫管理和智能分析功能
3. **前端 WebUI**（已编译到 LightRAG Server 中）

## 启动步骤

### 前置条件

确保已安装以下依赖：

```bash
# Python 依赖
pip install -e .[api]
pip install "numpy<2.0"  # 解决 NumPy 2.0 兼容性问题
pip install httpx python-dotenv fastapi uvicorn

# 前端依赖（仅首次或代码更新后需要）
cd lightrag_webui
bun install --frozen-lockfile
```
### 激活环境
& d:/General_real-time_tech_info_search_and_smart_analysis_system/.venv/Scripts/Activate.ps1
---

### 步骤 1：构建前端（仅首次或前端代码更新后需要）!!!重要,重要!!!

```bash
cd d:\General_real-time_tech_info_search_and_smart_analysis_system\lightrag_webui
bun run build
cd ..
```

**说明：** 此命令会将前端编译到 `lightrag/api/webui/` 目录，供 LightRAG Server 使用。

---

### 步骤 2：启动 LightRAG Server（终端 1）

```bash
cd d:\General_real-time_tech_info_search_and_smart_analysis_system
lightrag-server
```

**或者使用：**

```bash
uvicorn lightrag.api.lightrag_server:app --host 0.0.0.0 --port 9622
```

**启动成功标志：**

```
🌐 Server Access Information:
    ├─ WebUI (local): http://localhost:9622
    ├─ API Documentation (local): http://localhost:9622/docs
```

---

### 步骤 3：启动平台 API Server（终端 2）

```bash
cd d:\General_real-time_tech_info_search_and_smart_analysis_system
python server.py
```

**启动成功标志：**

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

---

### 步骤 4：访问系统

打开浏览器访问：**http://localhost:9622**

系统包含以下功能模块：

- **文档** — LightRAG 文档管理
- **知识图谱** — 可视化知识图谱
- **检索** — 智能问答和检索
- **数据源** — 爬虫管理和文章列表（新增）
- **智能分析** — 趋势分析和智能问答（新增）

---

## 常用操作

### 1. 触发爬虫采集

**方式 1：通过前端界面**

1. 访问 http://localhost:9622
2. 点击顶部 **"数据源"** Tab
3. 在"数据源"面板找到目标爬虫（如 arxiv、github_trending）
4. 点击右侧的 **播放按钮** 触发采集

**方式 2：通过命令行**

```bash
cd d:\General_real-time_tech_info_search_and_smart_analysis_system\crawler\scrapy_project
python -m scrapy crawl arxiv -a max_results=20
```

---

### 2. 导入文章到 LightRAG（构建知识图谱）

采集完成后，需要将文章导入 LightRAG 进行实体抽取和关系识别：

```bash
cd d:\General_real-time_tech_info_search_and_smart_analysis_system
python -m crawler.ingest --source arxiv --limit 10
```

**参数说明：**

- `--source arxiv`：只导入 arxiv 来源的文章（可选，不指定则导入所有来源）
- `--limit 10`：限制导入数量（可选）

**导入过程：**

- 每篇文章会调用 LLM 进行实体抽取和关系识别
- 大约需要 10-30 秒/篇
- 导入完成后可在 **"知识图谱"** Tab 查看可视化结果

---

### 3. 使用智能分析功能

**前置条件：** 需要配置 Qwen API Key

在项目根目录创建 `.env` 文件：

```bash
QWEN_API_KEY=your_dashscope_api_key_here
QWEN_MODEL=qwen-plus
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**功能：**

1. **趋势分析** — 分析已采集文章的技术趋势
2. **智能问答** — 基于已采集文章的上下文问答（支持流式输出）

---

## 故障排查

### 问题 1：`lightrag-server` 命令找不到

**解决方案：**

```bash
pip install -e .[api]
```

或直接使用：

```bash
uvicorn lightrag.api.lightrag_server:app --host 0.0.0.0 --port 9622
```

---

### 问题 2：NumPy 2.0 兼容性错误

**错误信息：**

```
AttributeError: `np.float_` was removed in the NumPy 2.0 release
```

**解决方案：**

```bash
pip install "numpy<2.0"
```

---

### 问题 3：前端 CORS 跨域错误

**错误信息：**

```
Access to XMLHttpRequest at 'http://localhost:8000/api/...' has been blocked by CORS policy
```

**解决方案：**

确认 `server.py` 中的 CORS 配置包含前端地址：

```python
allow_origins=["http://localhost:9622", "http://127.0.0.1:9622", ...]
```

修改后重启 `python server.py`。

---

### 问题 4：导入文章时提示 "Found 0 articles"

**原因：** 文章状态不是 `"raw"`（可能已导入过）

**解决方案：** 重置文章状态

```bash
python -c "import json; path=r'd:\General_real-time_tech_info_search_and_smart_analysis_system\data\articles\index.json'; data=json.load(open(path,'r',encoding='utf-8')); [x.update({'status':'raw'}) for x in data]; json.dump(data,open(path,'w',encoding='utf-8'),ensure_ascii=False,indent=2); print('Reset',len(data),'articles')"
```

---

## 停止系统

在各个终端窗口按 **Ctrl+C** 停止对应服务：

1. 终端 1：停止 LightRAG Server
2. 终端 2：停止平台 API Server

---

## 开发模式（可选）

如果需要前端热更新（修改前端代码后自动刷新），可以使用开发模式：

### 终端 1：LightRAG Server

```bash
lightrag-server
```

### 终端 2：平台 API Server

```bash
python server.py
```

### 终端 3：前端开发服务器

```bash
cd lightrag_webui
bun run dev
```

然后访问 **http://localhost:5173** 进行前端开发。

---

## 技术栈

- **后端框架**：FastAPI + LightRAG
- **前端框架**：React 19 + TypeScript + Vite + Bun
- **爬虫框架**：Scrapy
- **LLM**：Qwen（通义千问）
- **知识图谱**：NetworkX + NanoVectorDB
- **UI 组件**：Radix UI + Tailwind CSS

---

## 目录结构

```
d:\General_real-time_tech_info_search_and_smart_analysis_system\
├── server.py                    # 平台 API 主入口
├── crawler/
│   ├── api.py                   # 爬虫管理 API
│   ├── ingest.py                # 文章导入脚本
│   └── scrapy_project/          # Scrapy 爬虫项目
│       └── tech_spider/
│           └── spiders/         # 各个爬虫
├── algorithm/
│   ├── analysis.py              # Qwen 智能分析模块
│   └── api.py                   # 智能分析 API
├── data/
│   └── articles/                # 已采集文章（JSON）
│       ├── index.json           # 文章索引
│       └── arxiv/               # 按来源分类
├── lightrag/                    # LightRAG 核心库
├── lightrag_webui/              # 前端源码
│   └── src/
│       ├── features/
│       │   ├── DataSourceManager.tsx    # 数据源管理
│       │   └── SmartAnalysis.tsx        # 智能分析
│       └── api/
│           └── platform.ts      # 平台 API 调用
└── rag_storage/                 # LightRAG 存储目录
    └── tech_info_system/        # 工作空间
```

---

## 联系与支持

如有问题，请查看：

- LightRAG 文档：https://github.com/HKUDS/LightRAG
- Scrapy 文档：https://docs.scrapy.org/
- 通义千问 API：https://help.aliyun.com/zh/dashscope/
