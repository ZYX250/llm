"""
pdf_parser.py — 多模态细粒度 PDF 解析
- 矢量 PDF：pymupdf 提取文本、元数据、标题树、表格、LaTeX 公式、参考文献
- 扫描件 PDF：无文本层时自动走 OCR（rapidocr-onnxruntime）
- 长文档：分块 chunking（供 RAG 建索引）
"""
import os
import re
import hashlib
import fitz  # PyMuPDF


# ---------- OCR（可选，延迟加载） ----------
_ocr_engine = None

def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
        except Exception as e:
            print("OCR 引擎加载失败：", e)
            _ocr_engine = False
    return _ocr_engine or None


def _ocr_page(img_bytes):
    engine = _get_ocr()
    if not engine:
        return "", ["OCR引擎未安装"]
    import numpy as np
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    result, _ = engine(np.asarray(img))
    if not result:
        return "", []
    lines = [r[1] for r in result]
    return "\n".join(lines), lines


# ---------- 文本抽取 ----------
def extract_text(doc, progress_cb=None):
    """返回 (每页文本列表, 是否走OCR)。progress_cb(0-100) 用于长文档进度上报。"""
    pages = []
    used_ocr = False
    n = max(len(doc), 1)
    for i, page in enumerate(doc):
        if progress_cb:
            progress_cb(int((i + 1) / n * 100))
        txt = page.get_text("text", sort=True).strip()
        if len(txt.strip()) < 20:
            # 无文本层 → OCR
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            ocr_text, _ = _ocr_page(img_bytes)
            pages.append(ocr_text)
            used_ocr = True
        else:
            pages.append(txt)
    return pages, used_ocr


def _detect_headings(doc, pages):
    """利用字体大小检测一/二/三级标题树。返回 [(level, title, page)]"""
    headings = []
    sizes = []
    for pno in range(len(doc)):
        try:
            d = doc[pno].get_text("dict")
        except Exception:
            continue
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "").strip()
                    if not txt:
                        continue
                    sizes.append(span["size"])
        break  # 只统计首页估算基准
    if not sizes:
        sizes = [12]
    body_size = max(min(sizes), 8.0)

    for pno in range(len(pages)):
        try:
            d = doc[pno].get_text("dict")
        except Exception:
            continue
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                line_txt = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
                if not line_txt or len(line_txt) > 120:
                    continue
                max_size = max((s.get("size", body_size) for s in line.get("spans", [])), default=body_size)
                if max_size >= body_size * 1.5:
                    headings.append({"level": 1, "title": line_txt, "page": pno + 1})
                elif max_size >= body_size * 1.25:
                    headings.append({"level": 2, "title": line_txt, "page": pno + 1})
    return headings


def _extract_tables(doc):
    tables = []
    for pno in range(len(doc)):
        try:
            found = doc[pno].find_tables()
        except Exception:
            continue
        for tb in found.tables:
            data = tb.extract()
            if data:
                tables.append({"page": pno + 1, "data": data[:15]})
    return tables


# TeX/数学字体家族（Computer Modern 与常见数学字体），用于版面启发式识别公式行。
# 真实 PDF 里的公式不是 $...$ 包裹的，而是用这些字体渲染，所以靠字体比正则可靠。
MATH_FONT_RE = re.compile(r"(CMR|CMMI|CMSY|CMBX|CMEX|CMSL|MSBM|MSBB|Math|Symbol|Cambria)", re.I)
MATH_RATIO_MIN = 0.6   # 行内数学字体字符占比达到该阈值才纳入候选
MERGE_GAP_PT = 26      # 上标/分母常被 PDF 拆成独立行，垂直间距小于该值则并入上一条


def _is_math_font(name):
    """判断字体是否属于 TeX/数学字体家族（CMMI/CMR/CMSY/CMBX…）。"""
    return bool(MATH_FONT_RE.search(name or ""))


def _font_formula_lines(doc):
    """基于 span 字体与坐标的版面启发式抽公式行。

    判定三步：
    1) 行内数学字体字符占比 ≥ MATH_RATIO_MIN（正文用 NimbusRom/Roman，占比极低）；
    2) 相邻行垂直间距小则合并（公式的上标、分母、根号常被拆成独立行）；
    3) 合并后必须含等号——公式的强特征，同时滤掉表格里用数学字体排的数字串。
    """
    out = []
    for pno, page in enumerate(doc):
        try:
            d = page.get_text("dict")
        except Exception:
            continue
        cand = []
        for b in d.get("blocks", []):
            if b.get("type") != 0:      # 只处理文本块，跳过图片块
                continue
            for l in b.get("lines", []):
                spans = l.get("spans", [])
                txt = "".join(s.get("text", "") for s in spans)
                total = len(txt)
                if total < 5:
                    continue
                math_ch = sum(len(s.get("text", "")) for s in spans if _is_math_font(s.get("font", "")))
                if math_ch / max(total, 1) < MATH_RATIO_MIN:
                    continue
                cand.append([l["bbox"][0], l["bbox"][1], l["bbox"][3], txt.strip()])
        merged = []
        for x0, y0, y1, txt in cand:
            if merged and abs(y0 - merged[-1][2]) < MERGE_GAP_PT and len(merged[-1][3]) + len(txt) <= 160:
                merged[-1][3] = merged[-1][3] + " " + txt
                merged[-1][2] = y1
            else:
                merged.append([x0, y0, y1, txt])
        for x0, y0, y1, txt in merged:
            if "=" in txt:
                out.append({"text": txt[:200], "page": pno + 1})
    return out


def _extract_formulas(full_text, doc, pages_text):
    """抽取公式，返回 (公式文本列表, 对应页码列表)。

    两条路径合并去重：
    1) 原文自带 LaTeX 标记（$$...$$ / $...$）的 PDF —— 少数排版产物才有；
    2) 字体与坐标启发式 —— 覆盖绝大多数真实 PDF（公式由 TeX 数学字体渲染，不含 $ 标记）。
    """
    formulas, pages_of = [], []

    # 路径 1：LaTeX 标记
    for m in re.finditer(r"\$\$([^$]+)\$\$|\$([^$]+)\$", full_text):
        t = (m.group(1) or m.group(2)).strip()
        if t:
            formulas.append(t)
            pages_of.append(0)      # 0 表示页码待定位

    # 路径 2：字体启发式（页码已知）
    for it in _font_formula_lines(doc):
        formulas.append(it["text"])
        pages_of.append(it["page"])

    # 去重（按去空白后的文本），保序
    seen, uniq_f, uniq_p = set(), [], []
    for f, p in zip(formulas, pages_of):
        key = re.sub(r"\s+", "", f)
        if not key or key in seen:
            continue
        seen.add(key)
        uniq_f.append(f)
        uniq_p.append(p)

    # 尚未定位页码的用页面文本子串匹配补
    if any(p == 0 for p in uniq_p):
        located = _locate_formula_pages(uniq_f, pages_text)
        uniq_p = [located[i] if p == 0 else p for i, p in enumerate(uniq_p)]

    return uniq_f[:30], uniq_p[:30]


def _locate_formula_pages(formulas, pages):
    """为每个公式定位所在页码（去空白后按子串匹配），供阅读/解析视图显示 pxx 锚点。

    注意：formulas 本身仍是字符串数组，页码放在并行字段 formula_pages 里，
    这样前端原有的 parse.formulas.join('\\n') 渲染不会退化成 [object Object]。
    """
    compact = [re.sub(r"\s+", "", t) for t in pages]
    out = []
    for f in formulas:
        key = re.sub(r"\s+", "", f)[:40]
        page = 0
        if key:
            for pno, txt in enumerate(compact):
                if key in txt:
                    page = pno + 1
                    break
        out.append(page)
    return out


# 版权/许可/arXiv 页眉等噪声行，不能当标题（v7 版的版权页就曾被误判成标题）
TITLE_BLOCK_RE = re.compile(
    r"(?i)(provided proper attribution|permission to reproduce|arxiv:\d|licensed under|"
    r"all rights reserved|copyright|preprint|under review|www\.|http)"
)


def _is_boilerplate(t):
    return bool(TITLE_BLOCK_RE.search(t or ""))


def _page1_title(doc):
    """取第 1 页字号最大的行作为标题，跳过版权声明、页眉、URL 等噪声行。"""
    try:
        d = doc[0].get_text("dict")
    except Exception:
        return ""
    cands = []
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for l in b.get("lines", []):
            spans = l.get("spans", [])
            txt = re.sub(r"\s+", " ", "".join(s.get("text", "") for s in spans)).strip()
            size = max([s.get("size", 0) for s in spans] or [0])
            if len(txt) < 8 or len(txt) > 200 or not re.search(r"[A-Za-z]", txt):
                continue
            if _is_boilerplate(txt):
                continue
            cands.append((size, l["bbox"][1], txt))
    if not cands:
        return ""
    max_size = max(c[0] for c in cands)
    top = [c for c in cands if c[0] >= max_size - 1.5]
    top.sort(key=lambda c: c[1])      # 同字号取最靠上的
    return top[0][2]


def _extract_metadata(full_text, doc):
    meta = {}
    # 标题：优先 PDF 内嵌元数据，噪声值则回退到第 1 页最大字号行
    m = doc.metadata or {}
    t = (m.get("title") or "").strip()
    if t and not _is_boilerplate(t):
        meta["title"] = t
    else:
        meta["title"] = _page1_title(doc) or (full_text.splitlines()[0] if full_text.splitlines() else "")
    # 摘要
    msum = re.search(r"(?is)abstract\s*[:\-]?\s*(.*?)(?=\n\s*(introduction|1\s|一、|\n\d\.))", full_text)
    meta["abstract"] = msum.group(1).strip()[:1200] if msum else ""
    # 作者 / 机构
    authors = re.findall(r"(?i)(?:author|authors)\s*[:\-]\s*(.+)", full_text[:4000])
    meta["authors"] = authors[0].strip()[:300] if authors else ""
    meta["page_count"] = len(doc)
    return meta


# 参考文献标题必须独占一行，避免命中图注里的 "references listed at the end of this caption"
REF_HEAD_RE = re.compile(r"(?im)^[ \t]*(references|bibliography|参考文献)[ \t]*$")
# 无编号（作者-年份）条目的切分锚点：行首为「名 姓,」或「名 姓 大写词」
REF_START_RE = re.compile(r"\n(?=[A-Z][A-Za-z'\-]+(?:,| and | [A-Z][A-Za-z'\-]+(?:,|\.)))")


def _extract_references_impl(full_text, pages_text):
    """抽参考文献，兼容两种主流排版：
    1) 编号式 [1] ...（多数 CV/NLP 会议论文）；
    2) 作者-年份式（无编号，如 BERT/ACL 格式），按行首姓名切分。
    """
    refs = []
    seg = ""
    m = REF_HEAD_RE.search(full_text)
    if not m:
        # 双栏排版下 get_text(sort=True) 会把 "References" 与右栏文字排进同一行，
        # 独占行匹配落空；此时从后往前找 "references"，要求其后紧跟条目特征（编号或年份）
        for mm in reversed(list(re.finditer(r"(?i)\breferences\b", full_text))):
            tail = full_text[mm.end():mm.end() + 1200]
            if re.search(r"\[\s*1\s*\]|(?:19|20)\d{2}", tail):
                m = mm
                break
    if not m:
        m = re.search(r"(?i)\breferences?\s*\n", full_text)
    if m:
        seg = full_text[m.end():][:60000]   # 参考文献段落上限，60000 可覆盖 60+ 页论文的全量条目
        numbered = list(re.finditer(r"\[(\d+)\]\s*(.+)", seg))
        if numbered:
            for mm in numbered:
                refs.append({"idx": mm.group(1), "text": mm.group(2).strip()[:400]})

    # 编号式抽不到 -> 按作者-年份条目切分（BERT 这类格式）
    if not refs and seg:
        parts = [re.sub(r"\s+", " ", p).strip() for p in REF_START_RE.split(seg)]
        parts = [p for p in parts if len(p) > 20]
        for i, p in enumerate(parts):
            refs.append({"idx": str(i + 1), "text": p[:400]})
        # 切分不可靠时保留整段：引用图谱只需能匹配到被引标题，条数不准好过全空
        if len(refs) < 3:
            refs = [{"idx": "0", "text": re.sub(r"\s+", " ", seg)[:8000]}]

    # 页级扫描补充
    if not refs:
        for pno, t in enumerate(pages_text):
            if re.search(r"(?im)^[ \t]*(references|bibliography)[ \t]*$", t):
                for mm in re.finditer(r"\[(\d+)\]\s*(.+)", t):
                    refs.append({"idx": mm.group(1), "text": mm.group(2).strip()[:400]})
    return refs


def _extract_references(full_text, pages_text, doc=None):
    """参考文献抽取入口。

    extract_text 为保阅读顺序用了 sort=True，双栏论文会把左右栏文字交错排在同一行，
    导致 "References" 标题不再独占一行、条目被切碎（实测 BERT 由 63 条降到 19 条）。
    条数偏少时用末尾 10 页的无排序文本重抽一次，取更完整的结果。
    """
    refs = _extract_references_impl(full_text, pages_text)
    if doc is None:
        return refs
    start = max(0, len(doc) - 14)
    tail_pages = [doc[i].get_text().strip() for i in range(start, len(doc))]
    tail_text = "\n".join(tail_pages)
    if not tail_text.strip():
        return refs
    alt = _extract_references_impl(tail_text, tail_pages)
    return alt if len(alt) > len(refs) else refs


# ---------- 分块 chunking ----------
def chunk_text(pages, chunk_size=900, overlap=150):
    """把带页码的全文切成带 source 锚点的 chunk。每页独立分块，页码准确。"""
    chunks = []
    for pno, txt in enumerate(pages):
        if not txt.strip():
            continue
        buf_page = pno + 1
        buffer = ""
        for para in re.split(r"\n\s*\n", txt):
            para = para.strip()
            if not para:
                continue
            buffer += (" " + para if buffer else para)
            while len(buffer) >= chunk_size:
                chunks.append({"text": buffer[:chunk_size], "page": buf_page})
                buffer = buffer[chunk_size - overlap:]
        if buffer.strip():
            chunks.append({"text": buffer, "page": buf_page})
    return chunks


# ---------- 总入口 ----------
def parse_pdf(path, progress_cb=None):
    """解析 PDF，返回结构化结果。progress_cb(0-100) 可选。"""
    doc = fitz.open(path)
    pages, used_ocr = extract_text(doc, progress_cb)
    full_text = "\n".join(pages)
    headings = _detect_headings(doc, pages)
    tables = _extract_tables(doc)
    formulas, formula_pages = _extract_formulas(full_text, doc, pages)
    meta = _extract_metadata(full_text, doc)
    refs = _extract_references(full_text, pages, doc)
    chunks = chunk_text(pages)
    doc.close()
    return {
        "meta": meta,
        "headings": headings,
        "tables": tables,
        "formulas": formulas,
        "formula_pages": formula_pages,
        "references": refs,
        "chunks": chunks,
        "page_count": meta.get("page_count", 0),
        "used_ocr": used_ocr,
        "char_count": len(full_text),
    }


def fingerprint(text):
    """内容指纹（用于语义去重）。"""
    return hashlib.md5(re.sub(r"\s+", "", text)[:3000].encode("utf-8")).hexdigest()
