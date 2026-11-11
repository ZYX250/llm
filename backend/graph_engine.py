"""
graph_engine.py — 局域引用图谱挖掘
两类边：
  1) 引用边 cites  —— 论文 A 的 References 文本里命中库内论文 B 的标题词；
  2) 版本边 version —— 同一篇论文的不同版本（同 arXiv ID 或标题高度相似）。
用 NetworkX 计算 PageRank / 出入度，挖掘“基石论文”与“边缘衍生论文”。
"""
import difflib
import re
import networkx as nx
import numpy as np

ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})")
VERSION_SIM_MIN = 0.85   # 标题归一化后的相似度阈值


def _title_words(title):
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{2,}", title.lower()))


def _norm_title(t):
    """归一化标题：小写、只留字母数字、压空白，便于跨版本比较。"""
    t = re.sub(r"[^a-z0-9 ]+", " ", (t or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def _arxiv_id(text):
    """从文件名/路径里取 arXiv ID，如 1706.03762v1.pdf -> 1706.03762。"""
    m = ARXIV_ID_RE.search(text or "")
    return m.group(1) if m else ""


def _title_sim(a, b):
    """标题相似度：完全相同 1.0、包含关系 0.95、否则用序列相似度。"""
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.95
    return difflib.SequenceMatcher(None, na, nb).ratio()


def build_graph(papers):
    """
    papers: list of {"id","title","references":[{"text":...},...]}
    返回 {nodes, links, cornerstone, derivative}
    """
    G = nx.DiGraph()
    title_map = {}
    for p in papers:
        G.add_node(p["id"], title=p["title"])
        title_map[p["id"]] = {"title": p["title"], "words": _title_words(p["title"])}

    for p in papers:
        ref_texts = [r.get("text", "") for r in (p.get("references") or [])]
        for rt in ref_texts:
            rt = rt.lower()
            for pid2, info in title_map.items():
                if pid2 == p["id"]:
                    continue
                t_words = info["words"]
                if len(t_words) >= 3:
                    hits = sum(1 for w in t_words if w in rt)
                    # 阈值取 80% 且至少 3 词：太低会把"某篇论文的参考文献"误判成引用该论文
                    # （实测 50% 阈值下 BERT(2018) 被误连到 T5(2019)，时间上不可能）
                    need = max(3, int(len(t_words) * 0.8))
                    if hits >= need:
                        G.add_edge(p["id"], pid2, type="cites")
                        break

    # 版本关系边：同一篇论文的不同版本之间没有引用关系（不会引自己），
    # 用「同 arXiv ID」或「标题高度相似」连接，避免库里只有多版本时图谱恒为空。
    for i, a in enumerate(papers):
        for b in papers[i + 1:]:
            aid, bid = _arxiv_id(a.get("filename", "")), _arxiv_id(b.get("filename", ""))
            same_arxiv = bool(aid) and aid == bid
            sim = _title_sim(a.get("title", ""), b.get("title", ""))
            if same_arxiv or sim >= VERSION_SIM_MIN:
                # 只连一条（双向会在图上画出两条重叠弧线），语义即“同源版本”
                if not G.has_edge(a["id"], b["id"]) and not G.has_edge(b["id"], a["id"]):
                    G.add_edge(a["id"], b["id"], type="version")

    nodes = []
    links = []
    for nid, data in G.nodes(data=True):
        nodes.append({"id": nid, "title": data.get("title", nid)})
    for s, t, data in G.edges(data=True):
        links.append({"source": s, "target": t, "type": data.get("type", "cites")})

    # 基石论文：PageRank 高
    pr = nx.pagerank(G, alpha=0.85) if G.number_of_nodes() else {}
    # 边缘衍生论文：出度大、入度小
    out_deg = dict(G.out_degree())
    in_deg = dict(G.in_degree())
    scored = []
    for nid in nodes:
        scored.append({
            "id": nid["id"], "title": nid["title"],
            "pagerank": round(pr.get(nid["id"], 0), 4),
            "in": in_deg.get(nid["id"], 0), "out": out_deg.get(nid["id"], 0),
        })
    scored.sort(key=lambda x: -x["pagerank"])
    cornerstone = scored[: max(1, len(scored) // 3)] if scored else []
    # 边缘衍生论文：引用别人多(out大) 且 被引少(in小)
    derivative = sorted(scored, key=lambda x: (x["out"], -x["in"]))[: max(1, len(scored) // 3)] if scored else []

    return {
        "nodes": nodes,
        "links": links,
        "cornerstone": cornerstone,
        "derivative": derivative,
        "stats": {
            "n_papers": len(papers),
            "n_links": len(links),
            "n_cites": sum(1 for l in links if l["type"] == "cites"),
            "n_version": sum(1 for l in links if l["type"] == "version"),
            "density": round(nx.density(G), 3) if G.number_of_nodes() else 0,
        },
    }
