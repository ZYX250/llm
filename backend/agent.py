"""
agent.py — Agent 编排与工具路由
实现 Task-Planning + Function Calling 风格的 Agent：
1) 把工具注册表(TOOLS)转成 OpenAI tools schema；
2) 让大模型(qwen)自己选工具、填参数、返回 tool_calls；
3) 逐个执行工具并把结果回填上下文，再让模型总结人话回答；
4) 关键词多步计划(plan_agent)作为兜底，保证离线/失败也能用。
"""
import json
import llm


# 工具注册表：name / 描述 / 所属模块
TOOLS = [
    {"name": "rag_qa", "module": "模块二·抗幻觉问答", "desc": "对已入库的论文做单篇或多篇 RAG 问答，带原文溯源锚点与置信度"},
    {"name": "dedup", "module": "模块一·语义去重", "desc": "检测文献库中重复/相似版本的论文并给出核对建议"},
    {"name": "read_translate", "module": "模块三·双语阅读", "desc": "列出现有论文供中英对比阅读、逐页翻译"},
    {"name": "arxiv_search", "module": "模块四·论文检索", "desc": "检索 arXiv 最新论文并推荐、标记可复现代码"},
    {"name": "graph_review", "module": "模块五·引用图谱", "desc": "生成引用图谱、找基石/衍生论文、写领域综述与未来方向"},
    {"name": "writing_copilot", "module": "模块六·写作Copilot", "desc": "论文框架、拓扑图脚本(TikZ/Mermaid/Graphviz)、CSV可视化、学术翻译"},
    {"name": "general", "module": "通用", "desc": "无法归类时的一般性回答"},
]

INTENT_RULES = [
    (("问答", "提问", "对比", "区别", "贝塔", "参数", "参考文献", "引用信息", "论文中", "论文里", "超参数", "BLEU"), "rag_qa"),
    (("去重", "重复", "版本", "最新", "相似度"), "dedup"),
    (("翻译", "双语", "对照", "阅读", "划词", "悬停"), "read_translate"),
    (("检索", "搜索", "最新论文", "推荐", "追踪", "arxiv", "arXiv"), "arxiv_search"),
    (("图谱", "综述", "基石", "未来方向", "Future", "引用关系", "衍生"), "graph_review"),
    (("框架", "写作", "Abstract", "拓扑", "TikZ", "Mermaid", "Graphviz", "可视化", "CSV", "图表", "Figure", "英文"), "writing_copilot"),
]

# 工具 → 人话动作标签
TOOL_ACTION = {
    "rag_qa": "知识问答",
    "dedup": "文献去重",
    "read_translate": "双语阅读",
    "arxiv_search": "论文检索",
    "graph_review": "引用图谱",
    "writing_copilot": "写作Copilot",
    "general": "通用",
}


def _tool_desc(name):
    for t in TOOLS:
        if t["name"] == name:
            return t["desc"]
    return ""


def _tools_schema():
    """把 TOOLS 转成 OpenAI function calling schema（general 不暴露，避免误触发）。"""
    out = []
    for t in TOOLS:
        if t["name"] == "general":
            continue
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["desc"] + f"（所属模块：{t['module']}）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string",
                                  "description": "用户针对该工具的请求原文或提炼后的具体问题"},
                    },
                    "required": ["query"],
                },
            },
        })
    return out


def _summarize(out):
    """把工具返回的 dict 压缩成给模型的 tool 结果文本。"""
    if not isinstance(out, dict):
        return str(out)[:1500]
    keys = ("answer", "note", "msg", "notice", "summary", "future", "translated", "framework")
    for k in keys:
        if out.get(k):
            v = out[k]
            return (v[:1500] if isinstance(v, str) else json.dumps(v, ensure_ascii=False))[:1500]
    # 通用：列出关键字段
    safe = {k: (str(v)[:200] if not isinstance(v, (dict, list)) else v) for k, v in list(out.items())[:6]}
    return json.dumps(safe, ensure_ascii=False)[:1500]


MAX_ROUNDS = 3   # ReAct 最多循环轮数，防止工具之间互相触发造成无限调用


def _plan_of(steps):
    return [{"step": f"步骤{i + 1}", "tool": s["tool"], "action": s["action"]}
            for i, s in enumerate(steps)]


def run_plan_events(query, history=None, run_tool=None):
    """ReAct 编排：act(调工具) → observe(回填工具结果) → reason(下一轮决策)，逐轮循环。

    每轮都把上一轮的工具结果交给模型，由它自己决定「继续调工具」还是「直接作答」；
    最多 MAX_ROUNDS 轮，用尽后强制收敛成一次不带 tools 的回答。
    生成器产出 ("step", {...}) 与 ("final", result)，供 /agent/chat（收集）
    和 /agent/chat/stream（SSE 逐步推送）共用同一套逻辑。
    """
    system = (
        "你是「科研助手 Agent」，帮助用户完成论文解析、知识问答、引用图谱、综述与写作辅助等科研任务。"
        "你可以直接调用下面这些工具完成任务。调用工具后，先判断工具结果是否已经足够回答用户；"
        "如果还需要别的工具或还需要补充查询，可以继续调用；如果已经足够，就直接给出最终中文回答，"
        "并说明应该去哪个模块查看或操作。若某工具提示需要先上传论文，请如实转达。不要编造工具没有返回的信息。"
        "\n\n【硬性规则】只要用户的问题涉及已入库论文的具体内容、实验数据、结论或需要引用原文，"
        "必须先调用 rag_qa 检索，拿到片段后才组织回答；不得凭模型自身记忆直接作答。"
        "涉及重复/版本判断先调 dedup，涉及引用关系/综述先调 graph_review。"
    )
    messages = [{"role": "system", "content": system}]
    if history:
        messages += history[-8:]  # 保留最近上下文做记忆
    messages.append({"role": "user", "content": query})

    steps = []
    try:
        for rnd in range(1, MAX_ROUNDS + 1):
            msg = llm.chat_message(messages, tools=_tools_schema(), temperature=0.2)
            calls = msg.get("tool_calls") or []
            if not calls:
                # 模型判断无需（或无需再）调用工具：本句即最终回答
                answer = (msg.get("content") or "").strip() or "已理解你的需求。"
                yield "final", {"answer": answer, "plan": _plan_of(steps)}
                return

            messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
            for i, c in enumerate(calls):
                fn = c.get("function") or {}
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                q = args.get("query") or query
                action = TOOL_ACTION.get(name, name)
                try:
                    out = run_tool(name, q) if run_tool else {"note": "工具未绑定"}
                except Exception as e:
                    out = {"msg": str(e)}
                step = {"tool": name, "action": action, "round": rnd}
                steps.append(step)
                yield "step", step
                messages.append({
                    "role": "tool",
                    "tool_call_id": c.get("id", f"call_{i}"),
                    "content": _summarize(out),
                })

        # 轮数用尽：不再给 tools，强制模型基于已有工具结果收敛成回答
        final = llm.chat_message(messages, temperature=0.2)
        yield "final", {"answer": (final.get("content") or "已完成相关操作，请前往对应模块查看。").strip(),
                        "plan": _plan_of(steps)}
    except Exception as e:
        # 兜底：关键词多步计划（保证离线/接口异常时仍有可展示的步骤）
        plan = plan_agent(query)
        yield "final", {"plan": plan, "answer": "", "error": str(e)}


def run_plan(query, history=None, run_tool=None):
    """同步版本：把 run_plan_events 收集成 (steps, result)。"""
    steps, result = [], {}
    for ev, data in run_plan_events(query, history, run_tool):
        if ev == "step":
            steps.append(data)
        else:
            result = data
    if not steps and result.get("plan"):
        steps = result["plan"]   # 兜底路径的步骤
    return steps, result


def route_intent(query):
    """关键词优先，命中失败再走大模型。"""
    q = query.lower()
    for keys, tool in INTENT_RULES:
        if any(k.lower() in q for k in keys):
            return tool
    # 大模型兜底
    try:
        prompt = (
            "根据用户请求，从下列工具中选一个最合适的，只输出工具名：\n"
            + "\n".join(f"- {t['name']}: {t['desc']}" for t in TOOLS)
            + f"\n\n用户请求：{query}\n输出："
        )
        ans = llm.chat([{"role": "user", "content": prompt}], temperature=0).strip().lower()
        for t in TOOLS:
            if t["name"] in ans:
                return t["name"]
    except Exception:
        pass
    return "general"


def plan_agent(query):
    """兜底多步计划：解析出可能命中的多个工具，按顺序去重。"""
    q = query.lower()
    tools = []
    for keys, tool in INTENT_RULES:
        if any(k.lower() in q for k in keys) and tool not in tools:
            tools.append(tool)
    if not tools:
        tools = [route_intent(query)]
    return [{
        "step": f"步骤{i + 1}",
        "tool": t,
        "action": TOOL_ACTION.get(t, t),
        "desc": _tool_desc(t),
    } for i, t in enumerate(tools, 1)]


def describe_tools():
    return [{"name": t["name"], "module": t["module"], "desc": t["desc"]} for t in TOOLS]
