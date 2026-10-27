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


def _extract_formulas(text):
    """粗略抽取 LaTeX 公式（$...$ 或 $$...$$）。"""
    formulas = re.findall(r"\$\$([^$]+)\$\$|\$([^$]+)\$", text)
    out = [ (a or b).strip() for a, b in formulas if (a or b).strip() ]
    return out[:30]


def _extract_metadata(full_text, doc):
    meta = {}
    # 标题：取文档元数据标题或第一行
    m = doc.metadata or {}
    meta["title"] = (m.get("title") or "").strip() or (full_text.splitlines()[0] if full_text.splitlines() else "")
    # 摘要
    msum = re.search(r"(?is)abstract\s*[:\-]?\s*(.*?)(?=\n\s*(introduction|1\s|一、|\n\d\.))", full_text)
    meta["abstract"] = msum.group(1).strip()[:1200] if msum else ""
    # 作者 / 机构
    authors = re.findall(r"(?i)(?:author|authors)\s*[:\-]\s*(.+)", full_text[:4000])
    meta["authors"] = authors[0].strip()[:300] if authors else ""
    meta["page_count"] = len(doc)
    return meta


def _extract_references(full_text, pages_text):
    refs = []
    # 定位 References / REFERENCES / 参考文献
    m = re.search(r"(?i)\breferences?\s*\n", full_text)
    if not m:
        m = re.search(r"(?i)\n\s*(?:references|bibliography)\s*\n", full_text)
    if m:
        seg = full_text[m.end():]
        seg = seg[:20000]
        # 按 [n] 条目切分
        for mm in re.finditer(r"\[(\d+)\]\s*(.+)", seg):
            refs.append({"idx": mm.group(1), "text": mm.group(2).strip()[:400]})
    # 页级扫描补充
    if not refs:
        for pno, t in enumerate(pages_text):
            if re.search(r"(?i)\breferences?\b", t):
                for mm in re.finditer(r"\[(\d+)\]\s*(.+)", t):
                    refs.append({"idx": mm.group(1), "text": mm.group(2).strip()[:400]})
    return refs


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
    formulas = _extract_formulas(full_text)
    meta = _extract_metadata(full_text, doc)
    refs = _extract_references(full_text, pages)
    chunks = chunk_text(pages)
    doc.close()
    return {
        "meta": meta,
        "headings": headings,
        "tables": tables,
        "formulas": formulas,
        "references": refs,
        "chunks": chunks,
        "page_count": meta.get("page_count", 0),
        "used_ocr": used_ocr,
        "char_count": len(full_text),
    }


def fingerprint(text):
    """内容指纹（用于语义去重）。"""
    return hashlib.md5(re.sub(r"\s+", "", text)[:3000].encode("utf-8")).hexdigest()
