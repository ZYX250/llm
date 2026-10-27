"""
vectorstore.py — 轻量向量库 + 混合检索(RAG)
- Sparse: 自实现 TF-IDF
- Dense: DashScope embedding（失败自动降级为仅 sparse）
- 混合加权，返回带原文锚点(文件/页码)的 top-k chunk
内存运行，覆盖单篇与多篇跨文献问答。
"""
import math
import re
from collections import Counter
import numpy as np
import llm


def _tokenize(text):
    """轻量分词：英文单词 + 中文单字 + 中英 bigram。"""
    text = text.lower()
    words = re.findall(r"[a-z][a-z0-9_\-]{1,}", text)
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    cjk_bigrams = [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
    return words + cjk + cjk_bigrams


class VectorStore:
    def __init__(self, dense_weight=0.6):
        self.papers = {}
        self.dense_weight = dense_weight
        self._flat = []
        self._sparse = []
        self._dense = None
        self._idf = {}
        self._vocab = set()

    # ---------- 管理 ----------
    def add_paper(self, paper_id, title, chunks):
        self.papers[paper_id] = {"title": title, "chunks": chunks}
        self._rebuild()

    def remove_paper(self, paper_id):
        self.papers.pop(paper_id, None)
        self._rebuild()

    def clear(self):
        self.papers = {}
        self._rebuild()

    def list_papers(self):
        return [{"id": pid, "title": p["title"], "n_chunks": len(p["chunks"])}
                for pid, p in self.papers.items()]

    # ---------- 索引 ----------
    def _rebuild(self):
        self._flat = []
        for pid, p in self.papers.items():
            for ci, ch in enumerate(p["chunks"]):
                self._flat.append((pid, ci, ch["text"], ch.get("page", 0)))
        n = len(self._flat)
        self._sparse = []
        self._vocab = set()
        for (_, _, text, _) in self._flat:
            cnt = Counter(_tokenize(text))
            self._sparse.append(cnt)
            self._vocab.update(cnt.keys())
        df = Counter()
        for cnt in self._sparse:
            for term in cnt:
                df[term] += 1
        self._idf = {t: math.log((n + 1) / (d + 1)) + 1 for t, d in df.items()}
        self._dense = None
        if n > 0:
            embs = llm.embed_texts([t for (_, _, t, _) in self._flat])
            if embs:
                self._dense = np.array(embs, dtype=np.float32)

    # ---------- 检索 ----------
    def search(self, query, top_k=6, scope=None):
        q_terms = _tokenize(query)
        q_vec = Counter(q_terms)

        idxs = range(len(self._flat))
        if scope:
            scope = set(scope)
            idxs = [i for i in idxs if self._flat[i][0] in scope]
        idxs = list(idxs)
        if not idxs:
            return []

        q_norm = math.sqrt(sum((self._idf.get(t, 0) * v) ** 2 for t, v in q_vec.items())) or 1
        sparse_scores = []
        for i in idxs:
            cnt = self._sparse[i]
            s = sum(self._idf.get(t, 0) * cnt[t] for t in q_vec)
            d_norm = math.sqrt(sum((self._idf.get(t, 0) * v) ** 2 for t, v in cnt.items())) or 1
            sparse_scores.append(s / (q_norm * d_norm))

        scores = [s * (1 - self.dense_weight) for s in sparse_scores]

        if self._dense is not None:
            q_emb = llm.embed_text(query)
            if q_emb is not None:
                q_emb = np.array(q_emb, dtype=np.float32)
                qn = np.linalg.norm(q_emb) or 1
                dmat = self._dense[idxs]
                dn = np.linalg.norm(dmat, axis=1)
                cos = (dmat @ q_emb) / (dn * qn + 1e-9)
                for k in range(len(idxs)):
                    scores[k] += float(cos[k]) * self.dense_weight

        ranked = sorted(zip(idxs, scores), key=lambda x: -x[1])
        results = []
        for i, sc in ranked[:top_k]:
            pid, ci, text, page = self._flat[i]
            results.append({
                "paper_id": pid,
                "title": self.papers[pid]["title"],
                "page": page,
                "text": text,
                "score": round(float(sc), 4),
            })
        return results
