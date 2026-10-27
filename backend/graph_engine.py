"""
graph_engine.py — 局域引用图谱挖掘
基于每篇论文的 References 解析相互引用关系，
用 NetworkX 计算 PageRank / 中介中心性，挖掘“基石论文”与“边缘衍生论文”。
"""
import re
import networkx as nx
import numpy as np


def _title_words(title):
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_\-]{2,}", title.lower()))


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
                    if hits >= max(2, int(len(t_words) * 0.5)):
                        G.add_edge(p["id"], pid2)
                        break

    nodes = []
    links = []
    for nid, data in G.nodes(data=True):
        nodes.append({"id": nid, "title": data.get("title", nid)})
    for s, t in G.edges():
        links.append({"source": s, "target": t})

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
            "density": round(nx.density(G), 3) if G.number_of_nodes() else 0,
        },
    }
