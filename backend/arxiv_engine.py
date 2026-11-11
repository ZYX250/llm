"""
arxiv_engine.py — 论文自动检索、追踪与智能推荐
调用 arXiv API 检索论文；识别摘要中的 GitHub 链接以标记“易复现”；
支持按相关性排序并给出推荐理由。
"""
import re
import time
import requests
import xml.etree.ElementTree as ET

ARXIV_API = "https://export.arxiv.org/api/query"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ResearchAssistant/1.0; +https://github.com/ZYX250/llm)"}
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def _clean(tag):
    return re.sub(r"\{[^}]*\}", "", tag)


def _normalize_query(q):
    """arXiv 接口必须带字段前缀：裸词查询（如 Large Language Model）会让服务端长时间不返回。"""
    q = (q or "").strip()
    if not q:
        return 'all:""'
    if re.match(r"^(all|ti|au|abs|cat|co|jr|rn|id)\s*:", q, re.I):
        return q
    q = q.replace('"', "")
    return 'all:"%s"' % q


_CACHE = {}
_CACHE_TTL = 600  # 10 分钟内同一查询直接复用，避免重复等待


def search(query, max_results=10):
    key = ((query or "").strip().lower(), max_results)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]
    params = {
        "search_query": _normalize_query(query),
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
    }
    root = None
    last_err = None
    # arXiv 在部分网络下会长时间挂起：限制连接/读取超时并重试一次
    for attempt in range(2):
        try:
            r = requests.get(ARXIV_API, params=params, headers=HEADERS, timeout=(10, 30))
            r.raise_for_status()
            root = ET.fromstring(r.content)
            break
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(1)
    if root is None:
        raise RuntimeError(f"arXiv 接口无响应（{type(last_err).__name__}）：请检查网络或稍后重试")
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
    _CACHE[key] = (time.time(), items)
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
