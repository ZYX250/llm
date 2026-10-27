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


def run_plan(query, history=None, run_tool=None):
    """
    核心编排：Function Calling 多步执行。
    - query: 用户请求
    - history: 该会话的最近消息列表（供上下文/记忆）
    - run_tool: callable(tool_name, query) -> dict，执行单个工具
    返回 (steps, result)：steps 为已执行步骤，result 为最终人话回答。
    失败或无法调用工具时回退到关键词多步计划(plan_agent)。
    """
    system = (
        "你是「科研助手 Agent」，帮助用户完成论文解析、知识问答、引用图谱、综述与写作辅助等科研任务。"
        "你可以直接调用下面这些工具完成任务。调用工具后，根据工具返回的结果，"
        "给用户一个简洁、有帮助的中文最终回答，并说明应该去哪个模块查看或操作。"
        "如果某工具提示需要先上传论文，请如实转达。不要编造工具没有返回的信息。"
    )
    messages = [{"role": "system", "content": system}]
    if history:
        messages += history[-8:]  # 保留最近上下文做记忆
    messages.append({"role": "user", "content": query})

    steps = []
    try:
        msg = llm.chat_message(messages, tools=_tools_schema(), temperature=0.2)
        calls = msg.get("tool_calls") or []
        if calls:
            # 把首次 assistant 回复（含 tool_calls）回填，随后追加各 tool 结果
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
                steps.append({"tool": name, "action": action, "result": out})
                messages.append({
                    "role": "tool",
                    "tool_call_id": c.get("id", f"call_{i}"),
                    "content": _summarize(out),
                })
            # 总结轮：让模型基于工具结果产出最终人话回答
            final = llm.chat_message(messages, temperature=0.2)
            plan = [{"step": f"步骤{i + 1}", "tool": s["tool"], "action": s["action"]}
                    for i, s in enumerate(steps)]
            result = {
                "answer": (final.get("content") or "已完成相关操作，请前往对应模块查看。").strip(),
                "plan": plan,
            }
        else:
            result = {"answer": (msg.get("content") or "已理解你的需求。").strip(), "plan": []}
        return steps, result
    except Exception as e:
        # 兜底：关键词多步计划
        steps = plan_agent(query)
        result = {"plan": steps, "answer": ""}
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
