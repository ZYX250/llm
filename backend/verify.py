"""
verify.py — 抗幻觉「程序判定」
把原来只靠 GUARD_PROMPT 的软约束，升级为可复核的硬判定：
1. 引用白名单：答案里的 [n] 必须落在本次检索片段的 1..N 范围内（编号由 build_context 下发）；
2. 数字回查：逐句把答案中的数值与「该句所引片段」的数值集合比对（归一化后精确比对，不做子串包含）；
3. 拒答策略：编号越界 / 数字全库无出处 → 判 fail 并替换为拒答文案；数字只在别的片段里 → 判 warn（提示可能标错编号，不拒答）。

配套要求（缺一处就空转）：
- ctx 必须用 build_context() 生成，编号格式是纯数字 [1]、[2] …（写成 [片段1] 时 REF_RE 抽不到）；
- GUARD_PROMPT 必须要求模型用 [n] 标注；
- 白名单取本次 hits 的 1..len(hits)，不是论文参考文献的 idx。
"""
import re

# 引用编号 [1]..[N]：只认纯数字，[片段1]、[1-3] 都不会命中（这是刻意的）
REF_RE = re.compile(r"\[(\d+)\]")
# 页码上下文整体豁免，避免「第 3 页」被当成待回查的数字
PAGE_RE = re.compile(r"第\s*\d+(?:\s*[-–~]\s*\d+)?\s*页")
# 行首序号（1. / 2、 / (3)）豁免，避免把列表编号当数据
LIST_MARK_RE = re.compile(r"(?m)^\s*(?:\d+[.、)）]|[（(]\d+[)）])")
# 数值 token：千分位 / 小数 / 科学计数。前面禁止紧贴字母或点（避免从 3.5.1 中间开始匹配），
# 后面只禁止字母数字（允许句号收尾，否则 "0.000001." 这种句末数值会漏检）
NUM_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?![\w])")
# 句子切分：中文标点直接切；英文句号只在「点 + 空白」时切，
# 否则 "0.000001" 这种小数会被小数点切成两段，导致数值回查误判
SPLIT_RE = re.compile(r"[。！？；\n]+|(?<=[.!?])\s+")

REFUSAL_TEXT = (
    "（已拒答 · 未通过引用校验）本次回答中的引用编号或数值无法在检索片段中找到出处，"
    "为避免给出无依据的结论，系统不输出该内容。可换一种问法，或补充相关论文后重试。"
)


def build_context(hits):
    """给每个检索片段加纯数字编号，供模型在答案里用 [n] 标注。"""
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(f"[{i}] 来源《{h['title']}》第{h['page']}页\n{h['text']}")
    return "\n\n".join(parts)


def _to_float(raw):
    try:
        return float(str(raw).replace(",", ""))
    except ValueError:
        return None


def _clean(text):
    """剔除不需要回查的数字来源（引用编号、页码、行首序号）。"""
    text = REF_RE.sub(" ", text)
    text = PAGE_RE.sub(" ", text)
    text = LIST_MARK_RE.sub(" ", text)
    return text


def _num_set(text):
    """文本中的数值集合（用 9 位精度归一，避免 1e-6 被 round 成 0 而误判）。"""
    out = set()
    for m in NUM_RE.finditer(_clean(text)):
        v = _to_float(m.group(1))
        if v is not None:
            out.add(_key(v))
    return out


def _key(v):
    """数值归一化 key：统一 -0.0 与 0.0 的哈希差异。"""
    k = round(float(v), 9)
    return 0.0 if k == 0 else k


def extract_citations(answer):
    """抽取答案里出现的全部引用编号。"""
    return {int(x) for x in REF_RE.findall(answer or "")}


def verify_answer(answer, hits):
    """返回判定字典：ok / status(pass|warn|fail) / 明细 / reason / refusal。"""
    answer = answer or ""
    n = len(hits)
    cites = extract_citations(answer)
    invalid = sorted(c for c in cites if c < 1 or c > n)

    pools = [_num_set(h["text"]) for h in hits]     # 每个片段各自的数值集合
    all_pool = set()
    for p in pools:
        all_pool |= p

    unverified = []   # 全库都找不到 → 视为编造，判 fail
    misplaced = []    # 只在「别的片段」里找得到 → 可能标错编号，判 warn

    for raw in SPLIT_RE.split(answer):
        if not raw or not raw.strip():
            continue
        s_cites = [int(x) for x in REF_RE.findall(raw)]
        valid = [c for c in s_cites if 1 <= c <= n]
        target = valid or list(range(1, n + 1))      # 句内没标引用时放宽到全部片段
        sent_pool = set()
        for c in target:
            sent_pool |= pools[c - 1]
        for m in NUM_RE.finditer(_clean(raw)):
            v = _to_float(m.group(1))
            if v is None:
                continue
            if float(v).is_integer() and 1900 <= v <= 2100:
                continue                             # 年份豁免
            key = _key(v)
            if key in sent_pool:
                continue
            item = (m.group(1), raw.strip()[:60])
            if key in all_pool:
                misplaced.append(item)
            else:
                unverified.append(item)

    # 模型主动声明「证据不足」且没给数字 → 属于合规拒答，不算幻觉
    if re.search(r"证据不足|无法回答|未能找到|未检索到", answer) and not _num_set(answer):
        return _verdict(True, "pass", "模型主动声明证据不足（合规拒答）", n, cites, invalid, [], [])

    if not hits:
        return _verdict(True, "pass", "无检索片段，跳过校验", n, cites, invalid, [], [])

    if invalid:
        return _verdict(False, "fail", f"引用编号越界：{invalid}（本次仅检索到 {n} 个片段）",
                        n, cites, invalid, unverified, misplaced)

    if unverified:
        return _verdict(False, "fail", f"数值在检索片段中找不到出处：{unverified[:3]}",
                        n, cites, invalid, unverified, misplaced)

    if misplaced:
        # 不拒答：数字真实存在，只是可能标错了编号，交给人工判断
        return _verdict(True, "warn", f"数值存在但不在所引片段内（可能标错编号）：{misplaced[:3]}",
                        n, cites, invalid, unverified, misplaced)

    if not cites and _num_set(answer):
        return _verdict(False, "fail", "答案含数值但未标注任何 [n] 引用",
                        n, cites, invalid, unverified, misplaced)

    return _verdict(True, "pass", "引用编号与数值均能在检索片段中找到出处",
                    n, cites, invalid, unverified, misplaced)


def _verdict(ok, status, reason, n, cites, invalid, unverified, misplaced):
    return {
        "ok": ok,
        "status": status,
        "reason": reason,
        "n_hits": n,
        "citations": sorted(cites),
        "invalid_citations": invalid,
        "unverified_numbers": [{"value": v, "context": c} for v, c in unverified[:5]],
        "misplaced_numbers": [{"value": v, "context": c} for v, c in misplaced[:5]],
        "refusal": REFUSAL_TEXT if status == "fail" else None,
    }


def finalize_answer(answer, verdict):
    """按判定结果决定最终下发给前端的答案。"""
    if verdict.get("status") == "fail":
        return REFUSAL_TEXT
    return answer
