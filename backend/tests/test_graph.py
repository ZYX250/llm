"""引用图谱测试：标题词命中 ≥50% 才建边，节点与统计结构完整。"""
import graph_engine


PAPERS = [
    {
        "id": "a",
        "title": "Attention Is All You Need",
        "references": [{"idx": "1", "text": "Attention is all you need. NeurIPS 2017."}],
    },
    {
        "id": "b",
        "title": "Layer Normalization",
        "references": [{"idx": "1", "text": "Ashish Vaswani. Attention is all you need."}],
    },
    {
        "id": "c",
        "title": "BERT Pre-training",
        "references": [{"idx": "1", "text": "Unrelated bibliography entry about datasets."}],
    },
]


def test_nodes_cover_all_papers():
    g = graph_engine.build_graph(PAPERS)
    assert {n["id"] for n in g["nodes"]} == {"a", "b", "c"}
    assert g["stats"]["n_papers"] == 3


def test_reference_title_hit_builds_edge():
    g = graph_engine.build_graph(PAPERS)
    # b 的参考文献里出现 a 的完整标题词 → b -> a
    assert {"source": "b", "target": "a"} in g["links"]
    # c 的参考文献与任何标题无关 → 无边
    assert not any(l["source"] == "c" for l in g["links"])


def test_no_self_loop():
    g = graph_engine.build_graph(PAPERS)
    assert all(l["source"] != l["target"] for l in g["links"])


def test_empty_library_does_not_crash():
    g = graph_engine.build_graph([])
    assert g["nodes"] == []
    assert g["links"] == []
    assert g["stats"]["n_papers"] == 0


def test_pagerank_ranks_cited_paper_higher():
    g = graph_engine.build_graph(PAPERS)
    by_id = {n["id"]: n["pagerank"] for n in g["cornerstone"] + g["derivative"]}
    assert by_id["a"] > by_id.get("c", 0.0)
