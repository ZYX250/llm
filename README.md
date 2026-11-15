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
├── pack.ps1             # 打包提交 ZIP（排除 .env/.venv/node_modules/缓存/_old，含泄漏检查）
├── deploy_server.sh     # 云服务器(Ubuntu)一键部署：nginx 反代 + systemd 自启（公网常驻演示）
├── deploy_demo.ps1      # 本地 Windows 一键演示（含 ngrok 隧道，适合现场答辩）
├── README.md
├── backend/
│   ├── main.py            # FastAPI 应用与全部路由（含持久化/异步解析/Agent多步）
│   ├── llm.py             # 大模型封装（含磁盘结果缓存）
│   ├── pdf_parser.py      # PDF 多模态细粒度解析（矢量/OCR/标题树/表格/公式/参考文献/分块，支持进度回调）
│   ├── vectorstore.py     # 向量库 + 稀疏&Dense双路检索，RRF 融合定序(RAG)
│   ├── graph_engine.py    # 引用图谱 + PageRank/中介中心性挖掘基石论文
│   ├── viz_engine.py      # CSV 数据可视化 + 学术 Figure Caption
│   ├── arxiv_engine.py    # arXiv 检索 + GitHub 可复现标记 + 个性化推荐
│   ├── agent.py           # Agent 编排：工具注册表 + 意图路由 + 多步计划
│   ├── requirements.txt
│   ├── verify.py          # 抗幻觉程序判定（引用白名单 + 逐句数值回查 + 拒答）
│   ├── tests/             # pytest：去重 / 检索RRF / 图谱 / 引用校验（24 例）
│   ├── .env               # 配置 DASHSCOPE_API_KEY（必需，从 .env.example 复制）
│   └── papers/            # 论文落盘目录（parse.json + meta.json 持久化）
└── frontend/
    ├── src/App.vue        # 六大模块前端界面
    ├── vite.config.js     # /api 代理到 8000
    ├── public/echarts.min.js  # ECharts 本地化（离线可用）
    └── index.html         # 引用本地 ECharts
```

## 启动步骤

### 步骤 0：配置 API Key（首次必做）
```cmd
copy backend\.env.example backend\.env
```
然后编辑 `backend\.env`，把 `DASHSCOPE_API_KEY=` 后面填上百炼 API Key。
`.env` 已被 `.gitignore` 排除，既不进仓库、也不进打包 ZIP。

### 方式一：一键启动（推荐）
```cmd
python start.py
```
自动拉起后端(8000) + 前端(5173)，就绪后访问 `http://localhost:5173`，按 `Ctrl+C` 停止。

### 方式二：两个终端
**后端**（必须先进入 `backend` 目录，否则会报 `Could not import module "main"`）：
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

### 方式三：只启动后端
前端已经在跑、只想重启后端时，直接双击项目根目录的 `start-backend.bat`（或执行 `.\start-backend.ps1`）。
脚本会自动切到 `backend` 目录、调用虚拟环境里的 python，并在启动前检查 8000 端口是否被占用。
加 `-NoReload` 可关闭热重载（答辩演示用，启动更快更稳）：

```powershell
.\start-backend.ps1 -NoReload
```

### 常见启动错误
| 现象 | 原因 | 处理 |
|---|---|---|
| `Error loading ASGI app. Could not import module "main"` | 在项目根目录执行了 `uvicorn main:app`，而 `main.py` 在 `backend\` 下 | 先 `cd backend`，或直接 `python start.py` / `start-backend.bat` |
| 启动时 `[Errno 10048] address already in use` | 上次加载失败的 uvicorn 未退出，以 `Bound` 状态占着 8000 | `Get-NetTCPConnection -LocalPort 8000` 查 PID，再 `Stop-Process -Id <PID>` |
| 前端代理报 `ECONNREFUSED 127.0.0.1:8000` | 后端仍在启动阶段（读元数据、后台重建向量索引） | 等控制台出现 `Application startup complete` 和 `[恢复] 向量索引就绪`，通常 10 秒内 |

> 首次需 `pip install -r requirements.txt` 与 `npm install`；`.env` 中必须配置 `DASHSCOPE_API_KEY`。

## 六大功能模块（对应赛题）
| 模块 | 界面 Tab | 后端接口 | 说明 |
|---|---|---|---|
| 模块一 · PDF管理与细粒度解析 | 📁 文献库 | `/upload` `/parse/{id}/status` `/papers/{id}/parse` | 批量上传、**异步解析+进度条**、语义去重、扫描件OCR、标题树/表格/公式/参考文献 |
| 模块二 · 抗幻觉知识问答 | 💬 智能问答 | `/qa` `/qa/stream` | 混合检索 RAG（RRF 融合定序）+ 程序判定(verify) 抗幻觉 + 流式回答 + `[1][2]` 溯源编号 + **置信度分级** |
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
    (OCR/表格/公式)   (稀疏+Dense, RRF)   (缓存/护栏/翻译)
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
- **Agent/工作流（35%）**：`/agent/chat` 与 `/agent/chat/stream` —— 多轮 ReAct 循环（最多 3 轮，工具结果回喂模型决定下一步）、六大工具注册表、SSE 逐步推送推理轨迹、会话记忆落盘
- **抗幻觉 RAG**：混合检索（RRF 融合定序）+ 回答带 `[1][2]` 引用编号 + **程序判定层**（引用越界判 fail、数值无出处判 fail、误引判 warn）+ 置信度分级
- **多模态解析**：扫描件自动 OCR、标题树、公式（数学字体启发式）、表格、参考文献，长文档异步解析
- **工程可复现**：模块化解耦、requirements.txt、磁盘持久化、结果缓存、本地 ECharts、24 条 pytest
## 运行测试与打包

```cmd
cd backend
.venv\Scripts\python.exe -m pytest tests -q
```
预期 `24 passed`，覆盖语义去重、RRF 检索、引用图谱、抗幻觉引用校验四块。

打提交包（自动排除 `.env`、`.venv`、`node_modules`、`.cache`、`chroma_db`、`papers`、`dist`、`*_old*`、`ngrok.exe`；打包后会回读 ZIP 做泄漏检查，命中敏感文件即报错并删除产物）：
```powershell
powershell -ExecutionPolicy Bypass -File .\pack.ps1
```

## 评审模式（带账号的常驻演示）

设置环境变量 `REVIEWER_TOKEN` 后，服务额外开放四个**只读**端点，供评委现场核对内部决策，
普通功能（上传/解析/问答/图谱等）保持原样、不需要 token。

```powershell
# 1. 生成一个令牌（示例，可自行替换）
python -c "import secrets;print(secrets.token_urlsafe(16))"

# 2. 写进 backend\.env
REVIEWER_TOKEN=<上一步生成的串>

# 3. 正常启动，然后用浏览器/curl 带 token 访问
curl "http://127.0.0.1:8000/reviewer/info?token=<TOKEN>"
```

| 端点 | 用途 |
|---|---|
| `GET /reviewer/info?token=` | 语料规模、`dense` 是否实际启用、`RRF_K` 取值、引用判定策略、篇目清单 |
| `GET /reviewer/search?token=&query=&top_k=` | 检索明细：每条命中的论文/页码/混合分/片段，用于核对召回 |
| `GET /reviewer/qa?token=&query=` | 走完整问答链路并回传 `verify` 明细与被拒答的原始答案，用于演示抗幻觉 |
| `GET /reviewer/graph?token=` | 引用图谱每条边的 `type`（`cites` / `version`）与统计 |

未配置 `REVIEWER_TOKEN` 时上述端点返回 503（"评审模式未启用"），不泄露任何内部信息。
对外演示（隧道/公网）时把 `ALLOW_ORIGINS` 设为 `*`，服务会自动关闭 `allow_credentials`，
避免 `allow_origins=["*"]` 与凭证共用这个浏览器禁止的非法组合。

## 部署到云服务器（公网常驻演示）

满足"评审期间须保持服务可用"：把服务部署到一台常开的云服务器，由 systemd 托管（开机自启、崩溃自愈），nginx 反代 `/api`，评委只用固定公网地址即可访问，**无需你本地电脑开机**。

前置：Ubuntu 22.04 云服务器（2 核 2G 足够，LLM 走 DashScope 云端 API 无需 GPU）；云控制台安全组放行 22 与 80 入站。

```bash
# 1. 先把本项目上传到服务器（排除本地虚拟环境与缓存；papers/ 数据会随 rsync 一起拷贝）
rsync -avz --exclude '.venv' --exclude 'node_modules' --exclude '.cache' \
  /path/to/llm_competition/ root@<服务器IP>:/opt/llm_competition/

# 2. 在服务器上以 root 执行一键部署（交互要求输入 DASHSCOPE_API_KEY，并自动生成 REVIEWER_TOKEN）
sudo bash /opt/llm_competition/deploy_server.sh
```

脚本完成后会打印：
- 评委演示地址：`http://<服务器公网IP>/`
- 评审只读模式：`http://<服务器公网IP>/api/reviewer/info?token=<自动生成的令牌>`

后端 `lifespan` 启动时自动加载 `papers/` 下已打包的论文，评委打开即有数据；服务以 systemd 托管，重启/崩溃自动恢复，无需守着。

## 团队信息

- 参赛者：赵羽翔
- 学校：马鞍山学院
- 学院：大数据与人工智能学院
- 专业：计算机科学与技术
- 联系方式：GitHub @ZYX250
