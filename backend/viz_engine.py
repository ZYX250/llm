"""
viz_engine.py — 数据可视化与学术图注 Copilot
读取 CSV，生成折线图/柱状图/散点图/三维雷达图（base64 PNG），
并用大模型提炼学术规范的 Figure Caption。
"""
import io
import base64
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import llm

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def read_csv(text):
    return pd.read_csv(io.StringIO(text))


def _to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode()


def make_chart(text, kind="line", x_col=None, y_col=None):
    df = read_csv(text)
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    if y_col and y_col in df.columns:
        yc = y_col
    elif num_cols:
        yc = num_cols[0]
    else:
        raise ValueError("找不到数值列")
    xc = x_col if (x_col and x_col in df.columns) else (cat_cols[0] if cat_cols else df.columns[0])

    fig, ax = plt.subplots(figsize=(7, 4.5))
    if kind == "line":
        ax.plot(df[xc].astype(str), df[yc], marker="o", color="#2266dd")
        ax.set_title(f"{yc} vs {xc} (line)")
    elif kind == "bar":
        ax.bar(df[xc].astype(str), df[yc], color="#5b8ff9")
        ax.set_title(f"{yc} vs {xc} (bar)")
    elif kind == "scatter":
        ax.scatter(df[xc], df[yc], color="#e8923a")
        ax.set_title(f"{yc} vs {xc} (scatter)")
    else:
        # 默认折线
        ax.plot(df[xc].astype(str), df[yc], marker="o", color="#2266dd")
        ax.set_title(f"{yc} vs {xc}")

    plt.xticks(rotation=30, ha="right")
    ax.set_xlabel(str(xc))
    ax.set_ylabel(str(yc))
    ax.grid(alpha=0.3)
    plt.tight_layout()
    return _to_b64(fig)


def make_radar3d(text, y_col=None):
    """三维雷达/柱状图。"""
    df = read_csv(text)
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    cat_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    yc = y_col if (y_col and y_col in df.columns) else (num_cols[0] if num_cols else df.columns[-1])
    xc = cat_cols[0] if cat_cols else df.columns[0]

    fig = plt.figure(figsize=(7, 5.5))
    ax = fig.add_subplot(111, projection="3d")
    xs = range(len(df))
    zs = df[yc].values
    ax.bar(list(xs), zs, zdir="y")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(df[xc].astype(str).tolist(), rotation=45, ha="right", fontsize=8)
    ax.set_ylabel(str(xc))
    ax.set_zlabel(str(yc))
    ax.set_title(f"3D {yc} by {xc}")
    plt.tight_layout()
    return _to_b64(fig)


def make_table(text):
    df = read_csv(text)
    return df.head(30).to_html(classes="viz-table", border=0, index=False)


def make_caption(text, chart_desc):
    """用大模型提炼学术 Figure Caption。"""
    prompt = (
        "你是一名学术论文作者。基于下面 CSV 数据的统计信息和图表描述，"
        "写一段符合学术规范的 Figure Caption（含图表编号，说明趋势/对比/核心结论，60-120字，中英文各一句）：\n\n"
        f"CSV前几行：\n{text[:800]}\n\n图表描述：{chart_desc}"
    )
    try:
        return llm.chat([{"role": "user", "content": prompt}], temperature=0.4)
    except Exception as e:
        return f"（Caption 生成失败：{e}）"
