"""去重测试：_dedup_notice 必须排除自身，_find_duplicates 只报跨论文对。"""
import main


def test_dedup_notice_skips_self(monkeypatch):
    hits = [
        {"paper_id": "self", "title": "Self", "page": 1, "text": "x", "score": 0.62},
        {"paper_id": "other", "title": "Other", "page": 1, "text": "y", "score": 0.41},
    ]
    monkeypatch.setattr(main.vs, "papers", {"self": {}, "other": {}})
    monkeypatch.setattr(main.vs, "search", lambda *a, **k: hits)
    out = main._dedup_notice("Self", "body text", exclude_pid="self")
    assert out is not None
    assert out["similar_to"] == "Other"
    assert out["score"] == 0.41


def test_dedup_notice_returns_none_below_threshold(monkeypatch):
    hits = [
        {"paper_id": "self", "title": "Self", "page": 1, "text": "x", "score": 0.62},
        {"paper_id": "other", "title": "Other", "page": 1, "text": "y", "score": 0.20},
    ]
    monkeypatch.setattr(main.vs, "papers", {"self": {}, "other": {}})
    monkeypatch.setattr(main.vs, "search", lambda *a, **k: hits)
    assert main._dedup_notice("Self", "body text", exclude_pid="self") is None


def test_dedup_notice_empty_library(monkeypatch):
    monkeypatch.setattr(main.vs, "papers", {})
    assert main._dedup_notice("Any", "text") is None


def test_find_duplicates_only_cross_paper(monkeypatch):
    meta = {"a": {"id": "a", "title": "A"}, "b": {"id": "b", "title": "B"}}
    monkeypatch.setattr(main, "papers_meta", meta)

    def fake_search(query, top_k=5, scope=None):
        # 每篇论文检索时都把自己排第一，另一篇 0.95
        if query == "A":
            return [
                {"paper_id": "a", "title": "A", "page": 1, "text": "t", "score": 1.0},
                {"paper_id": "b", "title": "B", "page": 1, "text": "t", "score": 0.95},
            ]
        return [
            {"paper_id": "b", "title": "B", "page": 1, "text": "t", "score": 1.0},
            {"paper_id": "a", "title": "A", "page": 1, "text": "t", "score": 0.95},
        ]

    monkeypatch.setattr(main.vs, "search", fake_search)
    dups = main._find_duplicates()
    assert len(dups) == 1, "同一对论文只应上报一次"
    assert {dups[0]["a"], dups[0]["b"]} == {"A", "B"}
    assert dups[0]["score"] == 0.95
