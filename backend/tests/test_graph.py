"""引用图谱测试：标题词命中 ≥80% 且 ≥3 词才建引用边；同源版本按 arXiv ID 连版本边。"""
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
    # b 的参考文献里出现 a 的完整标题词 → b -> a，且边类型为 cites
    assert any(l["source"] == "b" and l["target"] == "a" and l["type"] == "cites"
               for l in g["links"])
    # c 的参考文献与任何标题无关 → 无边
    assert not any(l["source"] == "c" for l in g["links"])


def test_partial_title_hit_does_not_build_edge():
    """只命中一小部分标题词不应建边，否则会把无关论文误判成引用（实测 BERT→T5 假边即由此产生）。"""
    papers = [
        {"id": "t5", "title": "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer",
         "references": []},
        {"id": "b", "title": "BERT Pre-training",
         "references": [{"idx": "1", "text": "A study on transfer learning and text data."}]},
    ]
    g = graph_engine.build_graph(papers)
    assert g["links"] == []


def test_same_arxiv_id_builds_version_edge():
    """同一 arXiv 编号的不同版本之间没有引用关系，用版本边连接，保证多版本库里图谱不空。"""
    papers = [
        {"id": "v1", "title": "Attention Is All You Need", "filename": "1706.03762v1.pdf", "references": []},
        {"id": "v7", "title": "Attention Is All You Need", "filename": "1706.03762v7.pdf", "references": []},
    ]
    g = graph_engine.build_graph(papers)
    assert len(g["links"]) == 1
    assert g["links"][0]["type"] == "version"


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
