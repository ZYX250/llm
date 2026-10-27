# 科研助手 Agent 应用系统

面向前沿学术研究与论文写作场景的全栈式科研助手 Agent 系统，覆盖赛题要求的**六大命题功能模块**。
支持 PDF 多模态细粒度解析、抗幻觉 RAG 问答、版式感知双语阅读、论文检索追踪、引用图谱与综述、学术写作与可视化 Copilot。

## 技术栈
- **后端**：Python + FastAPI，模块化设计（LLM 封装 / PDF 解析 / 混合检索 RAG / 图算法 / 数据可视化 / arXiv 检索 / Agent 编排）
- **前端**：Vue 3 + Vite + ECharts（本地化，离线可用）
- **大模型**：阿里云百炼 DashScope（通义千问 qwen-plus + text-embedding-v3）

## 目录结构
```
llm_competition/
├── start.py             # 一键启动（后端+前端同时拉起，Ctrl+C 停止）
├── README.md
├── backend/
│   ├── main.py            # FastAPI 应用与全部路由（含持久化/异步解析/Agent多步）
│   ├── llm.py             # 大模型封装（含磁盘结果缓存）
│   ├── pdf_parser.py      # PDF 多模态细粒度解析（矢量/OCR/标题树/表格/公式/参考文献/分块，支持进度回调）
│   ├── vectorstore.py     # 向量库 + TF-IDF稀疏&Dense混合检索(RAG)
│   ├── graph_engine.py    # 引用图谱 + PageRank/中介中心性挖掘基石论文
│   ├── viz_engine.py      # CSV 数据可视化 + 学术 Figure Caption
│   ├── arxiv_engine.py    # arXiv 检索 + GitHub 可复现标记 + 个性化推荐
│   ├── agent.py           # Agent 编排：工具注册表 + 意图路由 + 多步计划
│   ├── requirements.txt
│   ├── .env               # 配置 DASHSCOPE_API_KEY（必需）
│   └── papers/            # 论文落盘目录（parse.json + meta.json 持久化）
└── frontend/
    ├── src/App.vue        # 六大模块前端界面
    ├── vite.config.js     # /api 代理到 8000
    ├── public/echarts.min.js  # ECharts 本地化（离线可用）
    └── index.html         # 引用本地 ECharts
```

## 启动步骤

### 方式一：一键启动（推荐）
```cmd
python start.py
```
自动拉起后端(8000) + 前端(5173)，就绪后访问 `http://localhost:5173`，按 `Ctrl+C` 停止。

### 方式二：两个终端
**后端**（`backend` 目录）：
```cmd
cd D:\vue\llm_competition\backend
.venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
接口文档：`http://127.0.0.1:8000/docs`

**前端**（`frontend` 目录）：
```cmd
cd D:\vue\llm_competition\frontend
npm run dev
```
访问：`http://localhost:5173`

> 首次需 `pip install -r requirements.txt` 与 `npm install`；`.env` 中必须配置 `DASHSCOPE_API_KEY`。

## 六大功能模块（对应赛题）
| 模块 | 界面 Tab | 后端接口 | 说明 |
|---|---|---|---|
| 模块一 · PDF管理与细粒度解析 | 📁 文献库 | `/upload` `/parse/{id}/status` `/papers/{id}/parse` | 批量上传、**异步解析+进度条**、语义去重、扫描件OCR、标题树/表格/公式/参考文献 |
| 模块二 · 抗幻觉知识问答 | 💬 智能问答 | `/qa` `/qa/stream` | 混合检索 RAG，流式回答 + 原文溯源锚点 + **置信度分级** + 抗幻觉护栏 |
| 模块三 · 版式感知阅读翻译 | 📖 双语阅读 | `/papers/{id}/read` `/translate` | 分页阅读、标题树导航、中英对照、字号/跳页、整篇翻译 |
| 模块四 · 论文检索追踪 | 🔍 检索追踪 | `/search/arxiv` | arXiv 检索、GitHub可复现标记、个性化推荐、结果画像 |
| 模块五 · 引用图谱与综述 | 🕸 引用图谱 | `/graph` `/graph/summary` | 引用拓扑图(ECharts)、基石/衍生论文、PageRank影响力条、综述+Future Work |
| 模块六 · 写作与可视化 | ✍️ 写作Copilot | `/writing/*` `/viz/csv` `/translate` | 无幻觉论文框架、TikZ/Mermaid/Graphviz脚本、CSV图表+Caption、翻译 |

## 系统架构
```
┌─────────────────────────────────────────────────────────┐
│  前端 Vue3 (localhost:5173)                              │
│  文献库 · 问答 · 阅读 · 检索 · 图谱 · 写作 · Agent对话     │
└───────────────┬─────────────────────────────────────────┘
                │ /api (vite 代理)
┌───────────────▼─────────────────────────────────────────┐
│  FastAPI (localhost:8000)                                │
│  /upload → 后台线程解析 → 进度 /parse/{id}/status         │
│  /qa → 混合检索(RAG) → 溯源锚点+置信度                    │
│  /graph → 引用图谱 → 基石/衍生 → 综述/Future Work         │
│  /agent/chat → 多步工具编排（逐步执行）                   │
└───────┬──────────────────┬───────────────┬───────────────┘
        │                  │               │
        ▼                  ▼               ▼
    PDF解析引擎       向量库(RAG)      大模型(DashScope)
    pdf_parser       vectorstore          llm
    (OCR/表格/公式)   (TF-IDF+Dense)   (缓存/护栏/翻译)
```

## 工程优化亮点
- **向量库持久化**：论文解析结果与元数据落盘到 `backend/papers/*.json`，重启自动恢复，不丢失文献库与图谱。
- **LLM 结果缓存**：`llm.py` 内置磁盘缓存（默认 7 天 TTL），重复问题/翻译直接命中，省 token、提速、防抖。
- **长 PDF 异步解析**：上传即返回，后台线程解析，前端实时进度条；541 页长文档不再阻塞接口。
- **Agent 多步编排**：`/agent/chat` 依据意图解析出**有序多步工具计划**并在前端展示执行步骤条。
- **抗幻觉增强**：QA 系统提示加入护栏（禁止臆造、证据不足明确说明、区分事实与推测）；返回命中**置信度分级**（高/中/低）与原文锚点。
- **ECharts 本地化**：图表库下载到本地，离线也能生成引用图谱。

## 官方测试数据集
将赛题提供的 `pdf/` 目录下文件通过「文献库」上传即可，重点覆盖：
- `1706.03762v1.pdf` —— 标准矢量双栏（文本/标题/公式/表格）
- `1706.03762v1_img.pdf` —— 图像扫描件（OCR）
- `UnderstandingDeepLearning_02_09_26_C.pdf` —— 541 页长教材（分块/索引/异步进度）

## 验证要点（对应评审）
- **Agent/工作流（35%）**：`/agent/chat` 多步编排、六大工具注册表、前端步骤条
- **抗幻觉 RAG**：混合检索 + 每个回答带 `[来源 论文名 第X页]` 锚点 + 置信度
- **多模态解析**：扫描件自动 OCR、标题树、公式、表格、参考文献，长文档异步解析
- **工程可复现**：模块化解耦、requirements.txt、磁盘持久化、结果缓存、本地 ECharts
