"""
arxiv_engine.py — 论文自动检索、追踪与智能推荐
调用 arXiv API 检索论文；识别摘要中的 GitHub 链接以标记“易复现”；
支持按相关性排序并给出推荐理由。
"""
import re
import requests
import xml.etree.ElementTree as ET

ARXIV_API = "http://export.arxiv.org/api/query"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _clean(tag):
    return re.sub(r"\{[^}]*\}", "", tag)


def search(query, max_results=10):
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
    }
    r = requests.get(ARXIV_API, params=params, timeout=30)
    root = ET.fromstring(r.content)
    items = []
    for entry in root.findall("atom:entry", NS):
        title = re.sub(r"\s+", " ", entry.findtext("atom:title", "", NS)).strip()
        summary = re.sub(r"\s+", " ", entry.findtext("atom:summary", "", NS)).strip()
        authors = [a.findtext("atom:name", "", NS) for a in entry.findall("atom:author", NS)]
        link = entry.findtext("atom:id", "", NS)
        pub = entry.findtext("atom:published", "", NS)
        github = re.search(r"(https?://(?:github\.com|gitlab\.com|huggingface\.co)[^\s>]+)", summary)
        items.append({
            "title": title,
            "authors": authors[:8],
            "abstract": summary,
            "url": link,
            "pdf": link.replace("/abs/", "/pdf/") + ".pdf",
            "published": pub,
            "github": github.group(1) if github else None,
            "reproducible": bool(github),
        })
    return items


def recommend(items, local_titles):
    """根据与本地文献库的相关性给推荐理由，优先带 GitHub 代码。"""
    local_words = []
    for t in local_titles:
        local_words += re.findall(r"[a-z][a-z0-9_\-]{2,}", t.lower())
    from collections import Counter
    lw = Counter(local_words)
    out = []
    for it in items:
        words = set(re.findall(r"[a-z][a-z0-9_\-]{2,}", it["title"].lower()))
        overlap = sum(lw[w] for w in words if lw[w] > 0)
        reason = "与本地文献主题相关" if overlap >= 2 else "主题匹配度一般"
        if it.get("github"):
            reason += "；附带开源代码，易复现"
        out.append({**it, "reason": reason})
    return out
