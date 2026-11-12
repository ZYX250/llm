"""
llm.py — 大模型统一封装
基于阿里云百炼(DashScope) 兼容模式 OpenAI API。
提供：对话、流式对话、文本向量化(embedding)、学术翻译、综述/框架/前沿提炼等专用生成。
新增：磁盘结果缓存（命中直接返回，省 token、提速、防抖）。
"""
import os
import re
import json
import time
import hashlib
import threading
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DASHSCOPE_API_KEY")
CHAT_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
EMB_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
CHAT_MODEL = os.getenv("QWEN_CHAT_MODEL", "qwen-plus")
EMB_MODEL = os.getenv("QWEN_EMB_MODEL", "text-embedding-v3")

# ---------------- 磁盘缓存 ----------------
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", 7 * 24 * 3600))  # 默认 7 天
os.makedirs(CACHE_DIR, exist_ok=True)
_cache_lock = threading.Lock()


def _cache_path(key):
    return os.path.join(CACHE_DIR, key + ".json")


def _cache_get(key):
    try:
        p = _cache_path(key)
        if not os.path.exists(p):
            return None
        if time.time() - os.path.getmtime(p) > CACHE_TTL:
            return None
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)["content"]
    except Exception:
        return None


def _cache_put(key, content):
    try:
        with _cache_lock:
            with open(_cache_path(key), "w", encoding="utf-8") as f:
                json.dump({"content": content}, f, ensure_ascii=False)
    except Exception:
        pass


def _headers():
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def _post_retry(url, payload, timeout=180, retries=3):
    """带指数退避的请求，仅对限流/服务端 5xx 重试，网络异常也重试。"""
    last = None
    for i in range(retries):
        try:
            r = requests.post(url, headers=_headers(), json=payload, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(f"HTTP {r.status_code}")
            return r
        except Exception as e:
            last = e
            if i < retries - 1:
                time.sleep(2 * (i + 1))
    raise last if isinstance(last, Exception) else RuntimeError("请求失败")


def chat(messages, model=None, temperature=0.3, max_tokens=4096, json_mode=False):
    """非流式对话，返回纯文本。json_mode=True 时强制返回可解析JSON。含磁盘缓存。"""
    if not API_KEY:
        return "错误：.env 未配置 DASHSCOPE_API_KEY"
    model = model or CHAT_MODEL
    key = hashlib.md5(json.dumps(
        {"m": model, "msg": messages, "t": temperature, "jm": json_mode},
        ensure_ascii=False, sort_keys=True
    ).encode("utf-8")).hexdigest()
    cached = _cache_get(key)
    if cached is not None:
        return cached
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    resp = _post_retry(CHAT_URL, payload, timeout=180)
    res = resp.json()
    if "error" in res:
        raise RuntimeError(f"API调用失败：{res['error'].get('message', res['error'])}")
    if "choices" not in res:
        raise RuntimeError(f"API返回异常：{res}")
    content = res["choices"][0]["message"]["content"]
    if json_mode:
        # 校验并尽量修复返回的 JSON（模型偶尔夹带解释文本）
        obj = None
        try:
            obj = json.loads(content)
        except Exception:
            m = re.search(r"\{.*\}", content, re.S)
            if m:
                try:
                    obj = json.loads(m.group(0))
                except Exception:
                    obj = None
        if obj is None:
            content = content  # 无法解析则保留原文，由调用方兜底
    _cache_put(key, content)
    return content


def chat_message(messages, model=None, temperature=0.3, tools=None, max_tokens=4096):
    """非流式，返回完整 assistant message（可能含 tool_calls），供 Function Calling 编排使用。不走缓存。"""
    if not API_KEY:
        return {"content": "错误：.env 未配置 DASHSCOPE_API_KEY", "tool_calls": None}
    payload = {
        "model": model or CHAT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    r = _post_retry(CHAT_URL, payload, timeout=180)
    res = r.json()
    if "error" in res:
        raise RuntimeError(f"API调用失败：{res['error'].get('message', res['error'])}")
    if "choices" not in res:
        raise RuntimeError(f"API返回异常：{res}")
    return res["choices"][0]["message"]


def stream_chat(messages, model=None, temperature=0.3):
    """流式对话，SSE 生成器，逐段产出文本（流式不走缓存）。"""
    if not API_KEY:
        yield "错误：.env 未配置 DASHSCOPE_API_KEY"
        return
    payload = {
        "model": model or CHAT_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    with requests.post(CHAT_URL, headers=_headers(), json=payload, stream=True, timeout=180) as r:
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                delta = obj["choices"][0]["delta"].get("content", "")
                if delta:
                    yield delta
            except Exception:
                continue


_EMB_MEM = {}   # 单条文本 -> 向量（进程内）。增删论文时只需算增量，不必全库重算


def embed_texts(texts):
    """批量文本向量化（两级缓存）。失败返回 None，调用方应降级为 sparse。

    1) 进程内按单条文本缓存：删除/新增论文只会重算涉及的 chunk，其余直接命中；
       旧实现按整批文本做 key，删一篇后批次全变，导致缓存 100% 失效、删除要等数十秒。
    2) 磁盘按整批缓存：进程重启后同一批文本仍可免调用。
    注意 DashScope 兼容模式单次 input 有条数上限（实测 120 条整体失败、10 条正常），
    因此按 10 条分批；任意一批失败就返回 None，由上层降级为纯 sparse。
    """
    if not API_KEY or not texts:
        return None

    # 只收集尚未缓存的文本，并去重（不同页可能出现相同 chunk）
    miss, seen = [], set()
    for t in texts:
        if t not in _EMB_MEM and t not in seen:
            seen.add(t)
            miss.append(t)

    if miss:
        key = hashlib.md5(json.dumps(
            {"m": EMB_MODEL, "v": 2, "n": len(miss), "s": miss},
            ensure_ascii=False, sort_keys=True
        ).encode("utf-8")).hexdigest()
        cached = _cache_get(key)
        if cached is not None and len(cached) == len(miss):
            for t, e in zip(miss, cached):
                _EMB_MEM[t] = e
        else:
            out = []
            batch = 10
            failed_batch = None
            for i in range(0, len(miss), batch):
                part = miss[i:i + batch]
                ok = False
                last_err = None
                for _attempt in range(2):
                    try:
                        resp = requests.post(
                            EMB_URL, headers=_headers(),
                            json={"model": EMB_MODEL, "input": part, "dimensions": 1024},
                            timeout=60,
                        )
                        res = resp.json()
                        if "data" in res and len(res["data"]) == len(part):
                            # 每批成功立即写入内存缓存：后面即使断连，已算好的部分也不会白丢
                            for t, d in zip(part, res["data"]):
                                _EMB_MEM[t] = d["embedding"]
                            out.extend(d["embedding"] for d in res["data"])
                            ok = True
                            break
                        last_err = str(res)[:150]
                    except Exception as e:
                        last_err = f"{type(e).__name__}: {e}"
                        time.sleep(0.5)
                if not ok:
                    failed_batch = i // batch + 1
                    break
            if failed_batch is not None:
                print(f"embedding 第 {failed_batch} 批失败（已缓存 {len(out)}/{len(miss)} 条），本次降级 sparse：{last_err}")
                return None
            # 校验条数：DashScope 偶尔会少返回（空文本/超长会被跳过），
            # 条数不一致会造成向量与 chunk 错位，比直接降级更危险，这里一律返回 None。
            if len(out) != len(miss):
                print(f"embedding 返回条数不匹配（{len(out)}/{len(miss)}），本次降级 sparse")
                return None
            _cache_put(key, out)

    vecs = [_EMB_MEM.get(t) for t in texts]
    if any(v is None for v in vecs):
        return None
    return vecs


def embed_text(text):
    emb = embed_texts([text])
    return emb[0] if emb else None


# ---------------- 各模块专用生成函数 ----------------

def translate(text, source_lang=None, target_lang=None):
    # 自动判定语言方向：中文为主 → 译成英文；否则（英文为主）→ 译成中文
    zh_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    en_words = len(re.findall(r'[a-zA-Z]+', text))
    if not source_lang or not target_lang:
        if zh_chars > 40 and zh_chars > en_words:
            source_lang = source_lang or "中文"
            target_lang = target_lang or "英文"
        else:
            source_lang = source_lang or "英文"
            target_lang = target_lang or "中文"
    sys = f"你是学术翻译专家，把{source_lang}精准翻译成{target_lang}，术语准确、时态严谨，符合学术规范。输出纯文本，禁止任何 Markdown 标记（不要 ** 加粗、不要 # 标题、不要 --- 分隔线、不要列表符号、不要反引号），不要保留原文的 ∗ † 等脚注符号。"
    prompt = f"请把下面的{source_lang}内容精准翻译成{target_lang}（保持原有段落结构，公式与专有名词保留）：\n\n{text}"
    return chat([{"role": "system", "content": sys}, {"role": "user", "content": prompt}], temperature=0.2)


def write_summary(papers_text):
    sys = "你是学术综述专家。"
    prompt = (
        "基于以下多篇论文的标题、摘要与引用关系，生成一段领域简短综述（300字以内），"
        "总结研究脉络与共识。\n\n论文资料：\n" + papers_text
    )
    return chat([{"role": "system", "content": sys}, {"role": "user", "content": prompt}], temperature=0.4)


def future_ideas(papers_text):
    sys = "你是科研前沿分析师。"
    prompt = (
        "基于以下论文的 Future Work 与最新进展，排除已经被解决的旧 idea，"
        "提炼 3 条真正具有探索价值的未来研究方向，逐条说明理由。\n\n论文资料：\n" + papers_text
    )
    return chat([{"role": "system", "content": sys}, {"role": "user", "content": prompt}], temperature=0.4)


def writing_framework(idea, refs_text=""):
    sys = "你是学术写作专家，输出必须是真实无幻觉的内容。"
    prompt = (
        f"给定研究 idea：{idea}\n\n"
        "请输出一篇论文的完整框架，包含：Abstract、Introduction、Related Work、"
        "（可选的）Method 章节要点。References 只可引用以下提供的真实文献（不要杜撰），"
        "并用标准学术引用格式。\n"
        f"可用参考文献：\n{refs_text or '(无，只写正文框架，References 留占位)'}"
    )
    return chat([{"role": "system", "content": sys}, {"role": "user", "content": prompt}], temperature=0.5)


def write_reading_notes(papers_text):
    sys = "你是科研助手。"
    prompt = "请把以下文献要点整理成便于阅读的结构化笔记：\n\n" + papers_text
    return chat([{"role": "system", "content": sys}, {"role": "user", "content": prompt}], temperature=0.4)
