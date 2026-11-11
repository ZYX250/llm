"""检索层测试：RRF 只换排序键，score 仍保留混合分；dense 缺失时不崩。"""
import llm
import vectorstore
from vectorstore import VectorStore


def _offline_store(monkeypatch, dense_weight=0.6):
    """把 embedding 全部置空，模拟无 API key / 无 dense 的最坏场景。"""
    monkeypatch.setattr(llm, "embed_texts", lambda texts: None)
    monkeypatch.setattr(llm, "embed_text", lambda query: None)
    vs = VectorStore(dense_weight=dense_weight)
    vs.add_paper("p1", "Attention Is All You Need", [
        {"text": "attention is all you need transformer encoder decoder self attention", "page": 1},
        {"text": "layer normalization epsilon residual connection positional encoding", "page": 2},
    ])
    vs.add_paper("p2", "Layer Normalization", [
        {"text": "layer normalization stabilizes training and reduces covariate shift", "page": 1},
    ])
    return vs


def test_search_survives_missing_dense(monkeypatch):
    vs = _offline_store(monkeypatch)
    res = vs.search("attention transformer", top_k=3)
    assert res, "dense 缺失时也必须返回结果"
    assert all(0.0 <= r["score"] <= 1.0 for r in res)
    # score 不能变成 RRF 原始分（1/(K+0) ≈ 0.0167）
    rrf_first = round(1.0 / (vectorstore.RRF_K + 0), 4)
    assert all(abs(r["score"] - rrf_first) > 1e-4 for r in res)


def test_single_route_order_matches_score(monkeypatch):
    """只有 sparse 一路时，RRF 排序与混合分排序必须完全等价（数学必然）。"""
    vs = _offline_store(monkeypatch)
    res = vs.search("layer normalization", top_k=3)
    scores = [r["score"] for r in res]
    assert scores == sorted(scores, reverse=True)


def test_scope_filters_other_papers(monkeypatch):
    vs = _offline_store(monkeypatch)
    res = vs.search("layer normalization", top_k=5, scope=["p2"])
    assert len(res) == 1
    assert res[0]["paper_id"] == "p2"


def test_remove_paper_rebuilds_index(monkeypatch):
    vs = _offline_store(monkeypatch)
    vs.remove_paper("p1")
    res = vs.search("attention", top_k=5)
    assert all(r["paper_id"] == "p2" for r in res)
