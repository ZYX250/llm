"""
main.py — 科研助手 Agent 应用系统（后端）
覆盖六大命题模块：PDF管理解析 / 抗幻觉RAG问答 / 双语阅读翻译 / 论文检索追踪 / 引用图谱综述 / 写作与可视化Copilot
增强：向量库与解析结果磁盘持久化 / 长PDF异步解析+进度 / LLM结果缓存 / Agent多步编排 / RAG置信度与护栏。
前端通过 vite 代理访问（/api 前缀被 rewrite 去掉），因此本服务路由不带 /api。
"""
import os
import re
import json
import uuid
import time
import shutil
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

import llm
import pdf_parser
from vectorstore import VectorStore
import graph_engine
import viz_engine
import arxiv_engine
import agent

BASE_DIR = Path(__file__).resolve().parent
PAPERS_DIR = BASE_DIR / "papers"
PAPERS_DIR.mkdir(exist_ok=True)
META_PATH = PAPERS_DIR / "meta.json"

# ---------------- 全局状态 ----------------
vs = VectorStore(dense_weight=0.6)
papers_meta = {}   # id -> {id, filename, path, title, page_count, used_ocr, char_count, uploaded_at}
CACHE = {}         # id -> 解析结果(大对象，含chunks)
TASKS = {}         # id -> {status, progress, error}  异步解析任务
SESSIONS = {}      # session_id -> [messages]  Agent 会话记忆


@asynccontextmanager
async def lifespan(_app):
    load_state()
    yield


app = FastAPI(title="科研助手 Agent 系统", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- 持久化 ----------------
def _save_paper(pid):
    """把单篇解析结果落盘（含 chunks 供重启重建向量库）。"""
    try:
        parse = CACHE.get(pid)
        if parse is None:
            return
        pdir = PAPERS_DIR / pid
        pdir.mkdir(exist_ok=True)
        with open(pdir / "parse.json", "w", encoding="utf-8") as f:
            json.dump({"meta": parse["meta"], "headings": parse["headings"],
                       "tables": parse["tables"], "formulas": parse["formulas"],
                       "references": parse["references"], "chunks": parse["chunks"],
                       "page_count": parse["page_count"], "used_ocr": parse["used_ocr"],
                       "char_count": parse["char_count"]}, f, ensure_ascii=False)
    except Exception as e:
        print("持久化失败：", e)


def _save_meta():
    try:
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(papers_meta, f, ensure_ascii=False)
    except Exception as e:
        print("meta 保存失败：", e)


def load_state():
    """启动时从磁盘恢复论文元数据、解析结果与向量库。"""
    if META_PATH.exists():
        try:
            with open(META_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            for pid, p in loaded.items():
                pf = PAPERS_DIR / pid / "parse.json"
                if not pf.exists():
                    continue
                with open(pf, "r", encoding="utf-8") as f:
                    parse = json.load(f)
                papers_meta[pid] = p
                CACHE[pid] = parse
                vs.add_paper(pid, p.get("title", ""), parse.get("chunks", []))
            print(f"[恢复] 已加载 {len(papers_meta)} 篇论文与向量库")
        except Exception as e:
            print("状态恢复失败：", e)


# ---------------- 工具函数 ----------------
def _dedup_notice(title, full_text):
    """语义去重：与已入库论文比较，返回重复提示。"""
    if not vs.papers:
        return None
    hits = vs.search(title + " " + full_text[:1500], top_k=1)
    if hits and hits[0]["score"] >= 0.35:
        dup = hits[0]
        return {
            "similar_to": dup["title"],
            "score": dup["score"],
            "notice": f"检测到与《{dup['title']}》高度相似，请核对是否重复版本，建议保留最新版。",
        }
    return None


def _new_paper_id():
    return uuid.uuid4().hex[:10]


# ---------------- 模块一：PDF 上传 / 异步解析 / 进度 / 去重 ----------------
def _run_parse(pid, path, filename):
    """后台线程：解析 PDF → 入库 → 持久化 → 更新任务状态。"""
    try:
        def cb(p):
            TASKS[pid]["progress"] = min(p, 99)
        parse = pdf_parser.parse_pdf(str(path), progress_cb=cb)
        title = parse["meta"].get("title") or Path(filename).stem
        vs.add_paper(pid, title, parse["chunks"])
        papers_meta[pid] = {
            "id": pid, "filename": filename, "path": str(path),
            "title": title, "page_count": parse["page_count"],
            "used_ocr": parse["used_ocr"], "char_count": parse["char_count"],
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        CACHE[pid] = parse
        _save_paper(pid)
        _save_meta()
        TASKS[pid].update(status="done", progress=100, error="", dedup=_dedup_notice(
            title, " ".join(c["text"] for c in parse["chunks"])))
    except Exception as e:
        TASKS[pid].update(status="error", error=str(e))
        print(f"解析 {filename} 失败：", e)


@app.post("/upload")
async def upload_pdfs(files: list[UploadFile] = File(...)):
    """批量上传 PDF，保存文件后立即返回并后台异步解析，支持进度查询。"""
    results = []
    for f in files:
        if not (f.filename or "").lower().endswith(".pdf"):
            results.append({"filename": f.filename, "ok": False, "msg": "仅支持PDF"})
            continue
        pid = _new_paper_id()
        pdir = PAPERS_DIR / pid
        pdir.mkdir(exist_ok=True)
        path = pdir / f.filename
        raw = await f.read()
        path.write_bytes(raw)
        TASKS[pid] = {"status": "parsing", "progress": 0, "error": ""}
        threading.Thread(target=_run_parse, args=(pid, path, f.filename), daemon=True).start()
        results.append({"id": pid, "filename": f.filename, "ok": True,
                        "status": "parsing", "title": Path(f.filename).stem})
    return {"results": results, "papers": list(papers_meta.values()),
            "parsing": [r["id"] for r in results if r.get("status") == "parsing"]}


@app.get("/parse/{pid}/status")
def parse_status(pid: str):
    """查询某 PDF 的异步解析进度。"""
    t = TASKS.get(pid)
    if not t:
        if pid in papers_meta:
            return {"status": "done", "progress": 100, "error": ""}
        return JSONResponse({"ok": False, "msg": "任务不存在"}, status_code=404)
    return {"status": t["status"], "progress": t["progress"], "error": t.get("error", ""), "dedup": t.get("dedup")}


@app.get("/papers")
def list_papers():
    return {"papers": list(papers_meta.values())}


@app.post("/papers/{pid}/reparse")
async def reparse_paper(pid: str):
    """重新解析已入库论文：OCR 全页重扫，覆盖旧解析与向量索引（用于扫描页无文本的情况）。"""
    if pid not in papers_meta:
        return JSONResponse({"ok": False, "msg": "论文不存在"}, status_code=404)
    meta = papers_meta[pid]
    path = Path(meta["path"])
    if not path.exists():
        return JSONResponse({"ok": False, "msg": "原 PDF 文件缺失，无法重扫"}, status_code=404)
    TASKS[pid] = {"status": "parsing", "progress": 0, "error": ""}
    vs.remove_paper(pid)  # 先移除旧索引，避免重复
    threading.Thread(target=_run_parse, args=(pid, path, meta["filename"]), daemon=True).start()
    return {"ok": True, "status": "parsing",
            "msg": "已开始重新解析（含 OCR 全页重扫），完成后每页原文即可查看，请稍候刷新。"}


@app.delete("/papers/{pid}")
def delete_paper(pid: str):
    papers_meta.pop(pid, None)
    vs.remove_paper(pid)
    CACHE.pop(pid, None)
    TASKS.pop(pid, None)
    pdir = PAPERS_DIR / pid
    if pdir.exists():
        shutil.rmtree(pdir)
    _save_meta()
    return {"ok": True}


@app.get("/papers/{pid}/parse")
def paper_parse(pid: str):
    p = papers_meta.get(pid)
    parse = CACHE.get(pid)
    if not p or not parse:
        return JSONResponse({"ok": False, "msg": "论文不存在或未解析"}, status_code=404)
    return {
        "ok": True,
        "meta": parse["meta"],
        "headings": parse["headings"][:200],
        "tables": parse["tables"],
        "formulas": parse["formulas"],
        "references": parse["references"],
        "used_ocr": parse["used_ocr"],
        "page_count": parse["page_count"],
    }


@app.get("/papers/{pid}/read")
def paper_read(pid: str, page: int = 1, size: int = 2):
    """按页返回正文，用于阅读视图（含页码锚点）。"""
    parse = CACHE.get(pid)
    if not parse:
        return JSONResponse({"ok": False, "msg": "未解析"}, status_code=404)
    pages = []
    start = (page - 1) * size
    by_page = {}
    for ch in parse["chunks"]:
        by_page.setdefault(ch["page"], []).append(ch["text"])
    total_pages = parse["page_count"] or max(by_page.keys(), default=1)
    for pno in range(start + 1, min(start + size, total_pages) + 1):
        pages.append({"page": pno, "text": "\n\n".join(by_page.get(pno, [])) or "（本页无文本，可能为扫描图）"})
    # 为每个章节计算真实页码：从字体检测到的原始页开始往后搜完整标题，保证页码单调递增
    enriched = []
    prev_page = 0
    for h in parse["headings"]:
        t = re.sub(r"\s+", " ", (h.get("title") or "").strip().lower())
        rp = h.get("page", 1)
        if t:
            for ch in parse["chunks"]:
                if ch["page"] < rp:          # 只从原始检测页往后找，不往前翻
                    continue
                if t in re.sub(r"\s+", " ", ch["text"].lower()):
                    rp = ch["page"]
                    break
        if rp < prev_page:                   # 单调化：不小于上一章节的页码
            rp = prev_page
        prev_page = rp
        enriched.append({**h, "real_page": rp})
    return {"ok": True, "title": papers_meta[pid]["title"], "pages": pages, "total_pages": total_pages,
            "headings": enriched}


@app.get("/papers/{pid}/locate")
def locate_heading(pid: str, q: str = ""):
    """按标题文本在已解析正文中搜索真实所在页码（比字体检测更准）。"""
    parse = CACHE.get(pid)
    if not parse:
        return JSONResponse({"ok": False, "msg": "未解析"}, status_code=404)
    qq = re.sub(r"\s+", " ", (q or "").strip().lower())
    if not qq:
        return {"ok": False, "page": 1}
    # 按 chunk 顺序找第一个包含该标题的页
    for ch in parse["chunks"]:
        text_norm = re.sub(r"\s+", " ", ch["text"].lower())
        if qq in text_norm:
            return {"ok": True, "page": ch["page"]}
    # 兜底：用标题词首词再试一次
    first = qq.split()[0] if qq.split() else qq
    for ch in parse["chunks"]:
        text_norm = re.sub(r"\s+", " ", ch["text"].lower())
        if first and first in text_norm:
            return {"ok": True, "page": ch["page"]}
    return {"ok": False, "page": 1}


# ---------------- 模块二：抗幻觉 RAG 问答 ----------------
class QABody(BaseModel):
    query: str
    paper_ids: list[str] = []
    top_k: int = 6


GUARD_PROMPT = (
    "你是一名科研助手，基于【原文片段】回答用户问题。必须遵守：\n"
    "1. 只依据给定片段作答，禁止编造或臆测（抗幻觉）；\n"
    "2. 回答中标注引用来源，如 [来源 论文名 第X页]；\n"
    "3. 若片段不足以回答，明确说明“证据不足”，并给出最接近的信息，不要强行下结论；\n"
    "4. 区分事实（片段支持）与推测（明确标注“推测”）；\n"
    "5. 若问题涉及多篇论文且观点不同，请分别指出各论文的立场并标注分歧（跨文献对比）。\n\n"
)


def _confidence(max_score, n_hits=1):
    """结合最高命中分数与命中数量分级，单命中高分谨慎降档。"""
    if max_score >= 0.5:
        return "高" if n_hits >= 2 else "中"
    if max_score >= 0.3:
        return "中"
    return "低"


def _expand_retrieval(query, scope=None, top_k=6):
    """查询改写 + 融合检索：原查询与一个改写查询分别检索，按(论文,页码)去重取更高分。"""
    hits = vs.search(query, top_k=top_k, scope=scope)
    if len(query) < 6:
        return hits
    try:
        alt = llm.chat(
            [{"role": "user", "content":
              "把下面这个问题改写成一个更利于在学术论文库中检索的查询，只输出改写后的查询文本，不要解释。\n问题：" + query + "\n改写："}],
            temperature=0)
        alt = (alt or "").strip()
        if len(alt) > 3 and alt != query.strip():
            hits2 = vs.search(alt, top_k=top_k, scope=scope)
            best = {}
            for h in list(hits) + list(hits2):
                k = (h["title"], h["page"])
                if k not in best or h["score"] > best[k]["score"]:
                    best[k] = h
            hits = sorted(best.values(), key=lambda x: -x["score"])[:top_k]
    except Exception:
        pass
    return hits


@app.post("/qa")
def qa(body: QABody):
    scope = body.paper_ids or None
    hits = _expand_retrieval(body.query, scope=scope, top_k=body.top_k)
    if not hits:
        return {"answer": "（未检索到相关内容，请先上传并解析论文）", "sources": []}
    ctx = "\n\n".join(
        f"[来源 {h['title']} 第{h['page']}页]\n{h['text']}" for h in hits
    )
    prompt = GUARD_PROMPT + f"【原文片段】\n{ctx}\n\n【问题】{body.query}"
    answer = llm.chat([{"role": "user", "content": prompt}], temperature=0.2)
    sources = [{"title": h["title"], "page": h["page"], "snippet": h["text"][:220],
                "score": h["score"], "confidence": _confidence(h["score"], len(hits))} for h in hits]
    return {"answer": answer, "sources": sources, "confidence": _confidence(hits[0]["score"], len(hits)),
            "papers": list_papers()["papers"]}


@app.post("/qa/stream")
async def qa_stream(body: QABody):
    """SSE 流式问答（带来源锚点 + 置信度 + 查询改写）。"""
    scope = body.paper_ids or None
    hits = _expand_retrieval(body.query, scope=scope, top_k=body.top_k)
    if not hits:
        async def empty():
            yield "data: " + json.dumps({"error": "未检索到内容"}, ensure_ascii=False) + "\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    ctx = "\n\n".join(f"[来源 {h['title']} 第{h['page']}页]\n{h['text']}" for h in hits)
    prompt = GUARD_PROMPT + f"【原文片段】\n{ctx}\n\n【问题】{body.query}"

    def gen():
        yield "data: " + json.dumps({"sources": [
            {"title": h["title"], "page": h["page"], "snippet": h["text"][:220],
             "score": h["score"], "confidence": _confidence(h["score"], len(hits))} for h in hits
        ], "confidence": _confidence(hits[0]["score"], len(hits))}, ensure_ascii=False) + "\n\n"
        for piece in llm.stream_chat([{"role": "user", "content": prompt}], temperature=0.2):
            yield "data: " + json.dumps({"delta": piece}, ensure_ascii=False) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------- 模块三：翻译 ----------------
class TranslateBody(BaseModel):
    text: str
    source: str | None = None   # 不传则 llm 自动识别语言方向
    target: str | None = None


@app.post("/translate")
def translate(body: TranslateBody):
    try:
        out = llm.translate(body.text, body.source, body.target)
        return {"ok": True, "translated": out}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


# ---------------- 模块四：论文检索 / 追踪 ----------------
@app.get("/search/arxiv")
def search_arxiv(q: str, max_results: int = 8):
    try:
        items = arxiv_engine.search(q, max_results=max_results)
        local_titles = [p["title"] for p in papers_meta.values()]
        return {"ok": True, "items": arxiv_engine.recommend(items, local_titles)}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


# ---------------- 模块五：引用图谱 + 综述 ----------------
@app.get("/graph")
def get_graph():
    if not papers_meta:
        return {"ok": True, "empty": True, "nodes": [], "links": []}
    papers = []
    for pid, p in papers_meta.items():
        refs = CACHE.get(pid, {}).get("references", [])
        papers.append({"id": pid, "title": p["title"], "references": refs})
    g = graph_engine.build_graph(papers)
    return {"ok": True, "empty": False, **g}


class SummaryBody(BaseModel):
    scope: list[str] = []


@app.post("/graph/summary")
def graph_summary(body: SummaryBody):
    scope = body.scope
    texts = []
    for pid in (scope or list(papers_meta)):
        if pid not in papers_meta:
            continue
        title = papers_meta[pid]["title"]
        abs_ = CACHE.get(pid, {}).get("meta", {}).get("abstract", "")[:600]
        texts.append(f"- 《{title}》摘要：{abs_ or '(无摘要)'}")
    if not texts:
        return {"ok": False, "msg": "请先上传论文"}
    try:
        s = llm.write_summary("\n".join(texts))
        fw = llm.future_ideas("\n".join(texts))
        return {"ok": True, "summary": s, "future": fw}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


# ---------------- 模块六：写作 Copilot ----------------
class FrameworkBody(BaseModel):
    idea: str


@app.post("/writing/framework")
def writing_framework(body: FrameworkBody):
    refs_text = "\n".join(
        f"- {r['text']}" for pid in papers_meta
        for r in (CACHE.get(pid, {}).get("references", [])[:10])
    )
    try:
        out = llm.writing_framework(body.idea, refs_text)
        return {"ok": True, "framework": out}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@app.post("/viz/csv")
async def viz_csv(file: UploadFile = File(...), kind: str = Form("line"), x_col: str = Form(""), y_col: str = Form("")):
    text = (await file.read()).decode("utf-8", errors="replace")
    try:
        if kind == "radar3d":
            image = viz_engine.make_radar3d(text, y_col or None)
        else:
            image = viz_engine.make_chart(text, kind=kind, x_col=x_col or None, y_col=y_col or None)
        table = viz_engine.make_table(text)
        caption = viz_engine.make_caption(text, f"图表类型 {kind}")
        return {"ok": True, "image": image, "table": table, "caption": caption}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@app.post("/writing/topology")
def topology(kind: str = Form("mermaid"), prompt: str = Form("")):
    sys = "你是架构绘图专家，只输出合法的绘图脚本，不要任何解释文字。"
    p = f"根据描述生成 {kind} 架构/拓扑图脚本：\n{prompt}"
    try:
        out = llm.chat([{"role": "system", "content": sys}, {"role": "user", "content": p}], temperature=0.3)
        return {"ok": True, "kind": kind, "script": out}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


# ---------------- Agent 编排入口（多步） ----------------
class AgentBody(BaseModel):
    query: str
    session_id: str = "default"


@app.get("/agent/tools")
def agent_tools():
    return {"ok": True, "tools": agent.describe_tools()}


def _find_duplicates():
    """真去重：扫描文献库内互相高度相似的论文对。"""
    dups = []
    meta = list(papers_meta.values())
    seen = set()
    for p in meta:
        hits = vs.search(p["title"], top_k=5)
        for h in hits:
            key = (p["id"], h["paper_id"]) if p["id"] < h["paper_id"] else (h["paper_id"], p["id"])
            if h["paper_id"] == p["id"] or key in seen:
                continue
            if h["score"] >= 0.9:
                dups.append({"a": p["title"], "b": h["title"], "score": h["score"]})
                seen.add(key)
    return dups


def _readable_papers():
    return [{"title": p["title"], "page_count": p["page_count"], "ocr": bool(p.get("used_ocr"))}
            for p in papers_meta.values()]


def _run_tool(tool, query):
    if tool == "rag_qa":
        return qa(QABody(query=query))
    if tool == "arxiv_search":
        return search_arxiv(query)
    if tool == "graph_review":
        return get_graph()
    if tool == "dedup":
        dups = _find_duplicates()
        note = "已扫描文献库，未发现重复版本。" if not dups else \
            "检测到以下高度相似的论文对，请核对是否保留最新版本："
        return {"duplicates": dups, "note": note}
    if tool == "read_translate":
        return {"note": "以下论文已入库，可前往「双语阅读」模块进行中英对照阅读与逐页翻译。",
                "papers": _readable_papers()}
    if tool == "writing_copilot":
        if any(k in query for k in ("框架", "idea", "Idea", "思路", "Abstract", "方法论")):
            try:
                fw = llm.writing_framework(query)
                return {"framework": fw}
            except Exception as e:
                return {"msg": str(e)}
        return {"note": "写作Copilot支持：论文框架 / 拓扑图脚本(TikZ·Mermaid·Graphviz) / CSV可视化+Caption / 学术翻译。",
                "capabilities": ["论文框架", "拓扑图脚本", "CSV可视化", "学术翻译"],
                "papers": len(papers_meta)}
    return {"note": "已收到：" + query}


@app.post("/agent/chat")
def agent_chat(body: AgentBody):
    hist = SESSIONS.get(body.session_id, [])
    steps, result = agent.run_plan(body.query, history=hist, run_tool=_run_tool)
    plan = result.get("plan") or []
    if not plan and steps:
        plan = [{"step": f"步骤{i + 1}", "tool": s["tool"], "action": s["action"]}
                for i, s in enumerate(steps)]
    plan = [{**p, "status": "done"} for p in plan]
    # 会话记忆：追加本次对话
    SESSIONS.setdefault(body.session_id, []).append({"role": "user", "content": body.query})
    if result.get("answer"):
        SESSIONS[body.session_id].append({"role": "assistant", "content": result["answer"]})
    return {"ok": True, "plan": plan, "steps": steps, "result": result}


class RoadmapBody(BaseModel):
    scope: list[str] = []


@app.post("/research/roadmap")
def research_roadmap(body: RoadmapBody):
    """研究路线图（创新点）：从基石论文到前沿方向，串成一条研究演进路线。"""
    g = get_graph()
    scope = body.scope or None
    texts = []
    for pid, p in papers_meta.items():
        if scope and pid not in scope:
            continue
        abs_ = CACHE.get(pid, {}).get("meta", {}).get("abstract", "")[:400]
        texts.append(f"- 《{p['title']}》摘要：{abs_ or '(无摘要)'}")
    if not texts:
        return {"ok": False, "msg": "请先上传论文"}
    corner = [n["title"] for n in (g.get("cornerstone") or [])][:5]
    try:
        data = "\n".join(texts)
        corner_line = "（由引用关系推断）" if not corner else "、".join(corner)
        roadmap = llm.chat([{"role": "user", "content":
            f"基于以下论文，产出一条研究路线图：从基石/经典论文出发，经中间发展，到最后沿方向，分3-5步，每步用一句话说明演进关系与核心贡献。\n基石论文：{corner_line}\n\n论文资料：\n{data}\n\n输出：研究路线图"}], temperature=0.4)
        return {"ok": True, "roadmap": roadmap}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@app.get("/")
def root():
    return {"app": "科研助手 Agent 系统", "status": "running", "papers": len(papers_meta),
            "cached": len(os.listdir(llm.CACHE_DIR)) if os.path.exists(llm.CACHE_DIR) else 0}
