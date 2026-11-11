"""引用校验（程序判定）的单元测试：全部离线，不调任何 API。"""
import verify

HITS = [
    {
        "title": "Attention Is All You Need",
        "page": 1,
        "text": "The Transformer has 6 layers and 8 attention heads.",
        "score": 0.4,
    },
    {
        "title": "Layer Normalization",
        "page": 2,
        "text": "We apply layer normalization with epsilon 0.000001.",
        "score": 0.3,
    },
]


def test_context_uses_pure_numeric_ids():
    ctx = verify.build_context(HITS)
    assert ctx.startswith("[1] 来源")
    assert "[2] 来源" in ctx


def test_fragment_prefix_is_not_extracted():
    # [片段1] 不符合 REF_RE —— 这正是 ctx 必须写纯数字的原因
    assert verify.extract_citations("[片段1] 里提到 6 层") == set()


def test_valid_answer_passes():
    ans = "Transformer 由 6 层堆叠而成 [1]，并使用了 8 个注意力头 [1]。"
    v = verify.verify_answer(ans, HITS)
    assert v["status"] == "pass"
    assert v["ok"] is True
    assert v["citations"] == [1]


def test_out_of_range_citation_fails():
    v = verify.verify_answer("结论见 [7]。", HITS)
    assert v["status"] == "fail"
    assert v["invalid_citations"] == [7]
    assert v["refusal"]


def test_fabricated_number_fails():
    # 12 层在 HITS 任何片段里都不存在 → 判编造
    v = verify.verify_answer("该模型共有 12 层 [1]。", HITS)
    assert v["status"] == "fail"
    assert v["unverified_numbers"][0]["value"] == "12"


def test_number_in_other_chunk_warns():
    # 0.000001 确实存在于片段 2，但句子标的是 [1] → 存疑而非拒答
    v = verify.verify_answer("epsilon 取 0.000001 [1]。", HITS)
    assert v["status"] == "warn"
    assert v["ok"] is True
    assert v["misplaced_numbers"][0]["value"] == "0.000001"


def test_page_and_year_are_exempt():
    v = verify.verify_answer("第 3 页的 2017 年论文 [1] 提出了 6 层结构。", HITS)
    assert v["status"] == "pass"


def test_declared_insufficiency_is_not_hallucination():
    v = verify.verify_answer("证据不足，片段中没有给出该参数。", HITS)
    assert v["status"] == "pass"
    assert v["ok"] is True


def test_finalize_answer_rewrites_on_fail():
    v = verify.verify_answer("该模型共有 12 层 [1]。", HITS)
    assert verify.finalize_answer("该模型共有 12 层 [1]。", v) == verify.REFUSAL_TEXT
