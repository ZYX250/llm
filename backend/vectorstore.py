"""
vectorstore.py — 轻量向量库 + 混合检索(RAG)
- Sparse: 自实现 TF-IDF
- Dense: DashScope embedding（失败自动降级为仅 sparse）
- 混合加权，返回带原文锚点(文件/页码)的 top-k chunk
内存运行，覆盖单篇与多篇跨文献问答。
"""
import math
import os
import re
from collections import Counter
import numpy as np
import llm

RRF_K = 60   # RRF 平滑常数（Cormack 等 2009 的经验值）

# 每篇论文的向量持久化根目录（由 main.py 设为 papers 目录）。
# 有了它，删除/新增论文只做内存拼接，不必重新调用 embedding。
VEC_DIR = None
EMB_DIM = 1024


def set_vector_dir(path):
    global VEC_DIR
    VEC_DIR = str(path) if path else None


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
        self._dense_map = {}     # pid -> 该篇全部 chunk 的向量（行序与 chunks 一致）
        self._vec_failed = set() # 本进程内算不出来的论文，避免每次 rebuild 反复等接口超时

    # ---------- 管理 ----------
    def add_paper(self, paper_id, title, chunks):
        self.papers[paper_id] = {"title": title, "chunks": chunks}
        self._rebuild()

    def add_papers_bulk(self, items):
        """批量恢复（启动时用）：只重建一次索引。
        逐篇 add_paper 会让每次 _rebuild 都重算全库 embedding，n 篇就是 O(n²) 次调用。"""
        for paper_id, title, chunks in items:
            self.papers[paper_id] = {"title": title, "chunks": chunks}
        self._rebuild()

    def remove_paper(self, paper_id):
        self.papers.pop(paper_id, None)
        # 该篇向量直接丢弃，其余篇的向量仍在内存里，rebuild 只做拼接（毫秒级）
        self._dense_map.pop(paper_id, None)
        self._vec_failed.discard(paper_id)
        self._rebuild()

    def clear(self):
        self.papers = {}
        self._dense_map = {}
        self._vec_failed = set()
        self._rebuild()

    def list_papers(self):
        return [{"id": pid, "title": p["title"], "n_chunks": len(p["chunks"])}
                for pid, p in self.papers.items()]

    # ---------- 向量持久化 ----------
    def _vec_path(self, pid):
        if not VEC_DIR:
            return None
        return os.path.join(VEC_DIR, pid, "vectors.npy")

    def _load_vectors(self, pid, n_chunks):
        """读该篇落盘的向量；条数/维度不符一律视为未命中（防止 chunk 变了导致错位）。"""
        p = self._vec_path(pid)
        if not p or not os.path.exists(p):
            return None
        try:
            arr = np.load(p)
            if arr.shape != (n_chunks, EMB_DIM):
                print(f"[向量] {pid} 条数不符（{arr.shape[0]}/{n_chunks}），重新计算")
                return None
            return arr.astype(np.float32)
        except Exception as e:
            print(f"[向量] {pid} 读取失败：{e}")
            return None

    def _save_vectors(self, pid, arr):
        p = self._vec_path(pid)
        if not p:
            return
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            np.save(p, arr)
        except Exception as e:
            print(f"[向量] {pid} 保存失败：{e}")

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
            # 补齐每篇向量：内存 → 磁盘 .npy → 才调接口。
            # 删除/新增论文时其余篇都已有缓存，这里不会产生任何网络请求。
            for pid, p in self.papers.items():
                if pid in self._dense_map or pid in self._vec_failed:
                    continue
                n_ch = len(p["chunks"])
                if n_ch == 0:
                    continue
                arr = self._load_vectors(pid, n_ch)
                if arr is None:
                    embs = llm.embed_texts([c["text"] for c in p["chunks"]])
                    if embs and len(embs) == n_ch:
                        arr = np.array(embs, dtype=np.float32)
                        self._save_vectors(pid, arr)
                if arr is None:
                    self._vec_failed.add(pid)   # 本次进程内不再重试，避免反复等超时
                else:
                    self._dense_map[pid] = arr

            ready = [pid for pid, p in self.papers.items() if p["chunks"]]
            if all(pid in self._dense_map for pid in ready):
                # 拼接顺序与 self._flat 一致（同样按 self.papers 迭代）
                self._dense = np.vstack([self._dense_map[pid] for pid in ready])
            elif ready:
                missing = [pid for pid in ready if pid not in self._dense_map]
                print(f"dense 缺失 {len(missing)} 篇（{missing}），本次检索降级为纯 sparse")

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

        has_dense = False
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
                has_dense = True

        # RRF 融合：只用来确定召回顺序，score 仍保留 0~1 的混合分。
        # 这样 _confidence / _dedup_notice / _find_duplicates / _expand_retrieval
        # 四处下游阈值全部不用改，也不会出现“RRF 原始分 0.0167 击穿 0.5/0.3/0.35/0.9”的问题。
        rrf = {}
        rank_s = sorted(range(len(idxs)), key=lambda k: -sparse_scores[k])
        for r, k in enumerate(rank_s):
            rrf[idxs[k]] = 1.0 / (RRF_K + r)
        if has_dense:
            rank_d = sorted(range(len(idxs)), key=lambda k: -float(cos[k]))
            for r, k in enumerate(rank_d):
                rrf[idxs[k]] += 1.0 / (RRF_K + r)

        # 与原来唯一的差别：排序键从 score 换成 rrf，ranked 仍是 (全局idx, 混合分) 二元组
        ranked = sorted(zip(idxs, scores), key=lambda x: -rrf.get(x[0], 0.0))
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
