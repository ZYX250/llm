<template>
  <div class="main-page">

    <!-- ===== 左侧导航栏 ===== -->
    <aside class="sidebar">
      <!-- 品牌区 -->
      <div class="brand">
        <div class="brand-logo">AI</div>
        <div class="brand-text">
          <div class="brand-name">AI 漏洞检测</div>
          <div class="brand-sub">C / Python / Java</div>
        </div>
      </div>

      <!-- 语言选择 -->
      <div class="side-section">
        <div class="side-title">目标语言</div>
        <div class="lang-group">
          <button
            v-for="opt in langOptions"
            :key="opt.value"
            class="lang-btn"
            :class="{ active: language === opt.value }"
            @click="selectLang(opt.value)"
          >{{ opt.name }}</button>
        </div>
      </div>

      <!-- 文件上传 -->
      <div class="side-section">
        <div class="side-title">上传源码</div>
        <div class="drop-zone">
          <div class="drop-icon">📄</div>
          <div class="drop-text">选择 {{ langTitle }} 文件</div>
          <div class="drop-tip">支持 .{{ langExt }}</div>
          <input type="file" ref="fileRef" @change="onFileSelect" :accept="acceptExt" id="file-input" />
          <label for="file-input" class="file-btn">Browse files</label>
        </div>
        <div class="file-status">{{ file ? file.name : "未选择任何文件" }}</div>
        <button @click="uploadFile" class="upload-btn">上传源码文件</button>
        <div class="msg green" v-if="uploadMsg">{{ uploadMsg }}</div>
      </div>

      <div class="side-foot">AI 漏洞检测系统 v2.0</div>
    </aside>

    <!-- ===== 右侧主内容区 ===== -->
    <main class="main-area">
      <!-- 顶栏 -->
      <div class="topbar">
        <h1 class="title">{{ langTitle }} AI 漏洞检测系统</h1>
        <button class="detect-btn" @click="runAudit" :disabled="!hasCode || loading">
          {{ loading ? "检测中..." : "AI 漏洞检测" }}
        </button>
      </div>

      <!-- 能力模块卡片（参考图 4 卡片） -->
      <div class="cards-row">
        <div class="cap-card">
          <div class="cap-title">问题分类</div>
          <div class="cap-sub">编译 / 运行 / 内存 / 安全</div>
        </div>
        <div class="cap-card">
          <div class="cap-title">深度解析</div>
          <div class="cap-sub">错误行号 · 错误原理</div>
        </div>
        <div class="cap-card">
          <div class="cap-title">一键修复</div>
          <div class="cap-sub">输出完整可运行代码</div>
        </div>
        <div class="cap-card">
          <div class="cap-title">多语言支持</div>
          <div class="cap-sub">C · Python · Java</div>
        </div>
      </div>

      <!-- 常用功能按钮区（参考图"常用演示指令"） -->
      <div class="section-label">常用功能</div>
      <div class="func-row">
        <button class="func-btn" :class="{ active: activeView==='compile' }" @click="openView('compile')">找出编译错误</button>
        <button class="func-btn" :class="{ active: activeView==='runtime' }" @click="openView('runtime')">运行时错误</button>
        <button class="func-btn" :class="{ active: activeView==='memory' }" @click="openView('memory')">内存漏洞</button>
        <button class="func-btn" :class="{ active: activeView==='security' }" @click="openView('security')">安全隐患</button>
        <button class="func-btn" :class="{ active: activeView==='lineno' }" @click="openView('lineno')">标注错误行号</button>
        <button class="func-btn" :class="{ active: activeView==='principle' }" @click="openView('principle')">说明错误原理</button>
        <button class="func-btn code-fn" :class="{ active: activeView==='code' }" @click="openView('code')">输出修复代码</button>
      </div>

      <div class="loading-tip" v-if="loading">AI 正在分析代码，请稍候...</div>

      <!-- 结果 / 对话区 -->
      <div class="result-area">
        <!-- 初始欢迎态 -->
        <div class="welcome" v-if="!reportData && !activeView">
          <div class="welcome-icon">🐞</div>
          <div class="welcome-title">AI 漏洞检测助手已启动</div>
          <div class="welcome-sub">
            选择左侧语言 → 上传 {{ langTitle }} 源码文件 → 点击右上角「AI 漏洞检测」
          </div>
          <div class="welcome-sub">检测完成后，点击上方功能按钮查看对应解析</div>
        </div>

        <!-- 功能按钮区（检测后默认展示） -->
        <div class="btn-list" v-if="reportData && !activeView">
          <div class="result-head">AI 审计报告已完成，请选择查看方式：</div>
          <div class="btn-grid">
            <button class="func-btn" @click="openView('compile')">找出编译错误</button>
            <button class="func-btn" @click="openView('runtime')">运行时错误</button>
            <button class="func-btn" @click="openView('memory')">内存漏洞</button>
            <button class="func-btn" @click="openView('security')">安全隐患</button>
            <button class="func-btn" @click="openView('lineno')">标注错误行号</button>
            <button class="func-btn" @click="openView('principle')">说明错误原理</button>
          </div>
          <button class="func-btn code-fn" @click="openView('code')">输出修复后的完整可运行代码</button>
        </div>

        <!-- 解析详情 -->
        <div class="detail" v-if="activeView">
          <div class="detail-head">
            <h3>{{ viewTitle }}</h3>
            <button class="back-btn" @click="closeView">返回列表</button>
          </div>
          <template v-if="activeView === 'code'">
            <pre class="code-block"><code>{{ reportData.code || "（AI未返回修复代码）" }}</code></pre>
          </template>
          <template v-else>
            <div v-if="currentRows.length === 0" class="empty-tip">
              {{ viewTitle }}：本次报告未识别到相关内容。
            </div>
            <div class="row-card" v-for="(r, i) in currentRows" :key="i">
              <div class="row-line">
                <span class="tag">{{ r.type }}</span>
                <span class="line-no">行号 {{ r.lineno }}</span>
                <span class="sev" :class="sevClass(r.severity)">{{ r.severity }}</span>
              </div>
              <div class="row-desc">{{ r.desc }}</div>
              <div class="row-principle" v-if="activeView === 'principle'">
                <b>原理说明：</b>{{ r.principle }}
              </div>
              <div class="row-principle" v-else-if="activeView === 'lineno'">
                <b>问题：</b>{{ r.desc }}
              </div>
            </div>
          </template>
        </div>
      </div>

    </main>
  </div>
</template>

<script>
export default {
  name: "CodeScanner",
  data() {
    return {
      language: "c",
      langOptions: [
        { name: "C", value: "c" },
        { name: "Python", value: "python" },
        { name: "Java", value: "java" }
      ],
      file: null,
      result: "",
      loading: false,
      uploadMsg: "",
      hasCode: false,
      reportData: null,
      activeView: ""
    };
  },
  computed: {
    acceptExt() {
      return this.language === "c" ? ".c" : (this.language === "python" ? ".py" : ".java");
    },
    langExt() {
      return this.language === "c" ? "c" : (this.language === "python" ? "py" : "java");
    },
    langTitle() {
      const map = { c: "C 语言", python: "Python", java: "Java" };
      return map[this.language] || "C 语言";
    },
    viewTitle() {
      const map = {
        compile: "找出编译错误",
        runtime: "运行时错误",
        memory: "内存漏洞",
        security: "安全隐患",
        lineno: "标注错误行号",
        principle: "说明错误原理",
        code: "输出修复后的完整可运行代码"
      };
      return map[this.activeView] || "";
    },
    currentRows() {
      if (!this.reportData) return [];
      switch (this.activeView) {
        case "compile":   return this.reportData.compile;
        case "runtime":   return this.reportData.runtime;
        case "memory":    return this.reportData.memory;
        case "security":  return this.reportData.security;
        case "lineno":    return this.reportData.lineno;
        case "principle": return this.reportData.principles;
        default:          return [];
      }
    }
  },
  methods: {
    selectLang(lang) {
      this.language = lang;
      this.file = null;
      this.uploadMsg = "";
      this.hasCode = false;
      this.reportData = null;
      this.activeView = "";
      if (this.$refs.fileRef) this.$refs.fileRef.value = "";
    },
    onFileSelect(e) {
      this.file = e.target.files[0];
      this.uploadMsg = "";
      this.hasCode = false;
    },
    parseReport(raw) {
      const data = {
        compile: [], runtime: [], memory: [], security: [],
        lineno: [], principles: [], code: ""
      };
      if (!raw) return data;
      const codeMatch = raw.match(/```(\w*)\s*\n([\s\S]*?)```/);
      if (codeMatch) data.code = codeMatch[2].trim();
      const lines = raw.split("\n");
      for (const line of lines) {
        const t = line.trim();
        if (!t.startsWith("|")) continue;
        const cols = t.split("|").map(c => c.trim()).filter(c => c.length > 0);
        if (cols.length < 4) continue;
        const type = cols[0] || "";
        const lineno = cols[1] || "?";
        const desc = cols[2] || "";
        const severity = cols[3] || "";
        const principle = cols[4] || "";
        if (/类型/.test(type) && /行号/.test(lineno)) continue;
        const row = { type, lineno, desc, severity, principle };
        if (type.includes("编译") || type.includes("语法")) data.compile.push(row);
        else if (type.includes("运行")) data.runtime.push(row);
        else if (type.includes("内存")) data.memory.push(row);
        else if (type.includes("安全")) data.security.push(row);
        data.lineno.push(row);
        data.principles.push(row);
      }
      if (data.lineno.length === 0) {
        const cleaned = this.cleanText(raw);
        data.principles = [{ type: "整体分析", lineno: "-", desc: cleaned, severity: "", principle: "" }];
        data.lineno = data.principles;
        data.security = data.principles;
      }
      return data;
    },
    cleanText(t) {
      return t
        .replace(/\*\*/g, "")
        .replace(/#{1,6}\s*/g, "")
        .replace(/---+/g, "")
        .replace(/\|/g, " ");
    },
    sevClass(sev) {
      const s = (sev || "").toUpperCase();
      if (s.includes("CRITICAL")) return "sev-critical";
      if (s.includes("HIGH")) return "sev-high";
      if (s.includes("MEDIUM")) return "sev-medium";
      if (s.includes("LOW")) return "sev-low";
      return "";
    },
    openView(key) {
      this.activeView = key;
      const area = this.$refs && this.$refs.resultArea;
      const el = document.querySelector(".result-area");
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    },
    closeView() {
      this.activeView = "";
    },
    async uploadFile() {
      if (!this.file) return alert("请先选择源码文件");
      const formData = new FormData();
      formData.append("file", this.file);
      formData.append("language", this.language);
      try {
        const res = await fetch("/api/upload", { method: "POST", body: formData });
        const text = await res.text();
        let data;
        try { data = JSON.parse(text); }
        catch { throw new Error(`后端返回：${text}`); }
        if (!res.ok) throw new Error(data.msg || "请求异常");
        this.uploadMsg = data.msg;
        this.hasCode = true;
      } catch (err) {
        alert("上传出错：" + err);
      }
    },
    async runAudit() {
      if (!this.hasCode) return alert("请先上传源码文件");
      this.loading = true;
      this.activeView = "";
      this.reportData = null;
      try {
        const res = await fetch("/api/audit", { method: "POST" });
        const text = await res.text();
        let data;
        try { data = JSON.parse(text); }
        catch { throw new Error(`后端返回：${text}`); }
        if (!res.ok) throw new Error(data.msg || "请求异常");
        this.result = data.msg;
        this.reportData = this.parseReport(data.msg);
      } catch (err) {
        alert("检测请求出错：" + err);
      }
      this.loading = false;
    }
  }
};
</script>

<style scoped>
* { box-sizing: border-box; }
.main-page {
  display: flex;
  height: 100vh;
  width: 100%;
  background: linear-gradient(135deg, #eef2fb 0%, #f3eeff 100%);
  overflow: hidden;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

/* ===== 左侧导航栏 ===== */
.sidebar {
  width: 300px;
  flex-shrink: 0;
  background: #ffffff;
  border-right: 1px solid #e6e9f2;
  padding: 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 26px;
  overflow-y: auto;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-logo {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, #2266dd, #8844dd);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
}
.brand-name { font-size: 17px; font-weight: 700; color: #1c1c2e; }
.brand-sub  { font-size: 12px; color: #8a8fa3; margin-top: 2px; }

.side-section { border-top: 1px solid #f0f1f6; padding-top: 18px; }
.side-title { font-size: 13px; font-weight: 600; color: #6a6f84; margin-bottom: 12px; }

.lang-group { display: flex; gap: 8px; }
.lang-btn {
  flex: 1;
  padding: 9px 0;
  border-radius: 10px;
  font-size: 15px;
  border: 1px solid #d8dcf0;
  background: #fff;
  color: #4a4f66;
  cursor: pointer;
  transition: all 0.2s;
}
.lang-btn.active {
  background: linear-gradient(135deg, #2266dd, #8844dd);
  color: #fff;
  border-color: transparent;
}
.lang-btn:hover:not(.active) { background: #eef2ff; }

.drop-zone {
  border: 2px dashed #c9d4f2;
  border-radius: 14px;
  padding: 22px 14px;
  text-align: center;
  background: #f8faff;
}
.drop-icon { font-size: 26px; }
.drop-text { font-size: 14px; font-weight: 600; color: #3a3f55; margin-top: 6px; }
.drop-tip { font-size: 12px; color: #9aa0b5; margin-top: 4px; }
#file-input { display: none; }
.file-btn {
  display: inline-block;
  margin-top: 12px;
  padding: 8px 22px;
  border-radius: 10px;
  font-size: 14px;
  border: 1px solid #c9dcff;
  background: #eef3ff;
  color: #1a5bc4;
  cursor: pointer;
}
.file-btn:hover { background: #dcecff; }
.file-status {
  font-size: 13px;
  color: #6a6f84;
  margin: 10px 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.upload-btn {
  width: 100%;
  padding: 11px 0;
  border-radius: 12px;
  font-size: 15px;
  border: none;
  background: linear-gradient(135deg, #2266dd, #5079dd);
  color: #fff;
  cursor: pointer;
}
.upload-btn:hover { opacity: 0.92; }
.msg.green { color: #2f9e44; font-size: 13px; margin-top: 10px; }

.side-foot {
  margin-top: auto;
  font-size: 12px;
  color: #b3b8c8;
  text-align: center;
  padding-top: 10px;
}

/* ===== 右侧主内容区 ===== */
.main-area {
  flex: 1;
  overflow-y: auto;
  padding: 30px 36px;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 26px;
}
.title {
  font-size: 32px;
  margin: 0;
  background: linear-gradient(90deg, #2266dd, #8844dd);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.detect-btn {
  padding: 12px 30px;
  border-radius: 14px;
  font-size: 16px;
  border: none;
  background: linear-gradient(135deg, #2266dd, #8844dd);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(34, 102, 221, 0.3);
}
.detect-btn:disabled {
  background: #e4e7ef;
  color: #aab0c2;
  box-shadow: none;
  cursor: not-allowed;
}

.cards-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}
.cap-card {
  background: #ffffff;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(30, 60, 120, 0.06);
  border: 1px solid #eef0f7;
}
.cap-title { font-size: 16px; font-weight: 700; color: #2266dd; }
.cap-sub { font-size: 13px; color: #8a8fa3; margin-top: 6px; }

.section-label {
  font-size: 14px;
  font-weight: 600;
  color: #6a6f84;
  margin-bottom: 12px;
}
.func-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 26px;
}
.func-btn {
  padding: 12px 22px;
  border-radius: 12px;
  font-size: 15px;
  border: 1px solid #c9dcff;
  background: #eef3ff;
  color: #1a5bc4;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.func-btn:hover { background: #dcecff; }
.func-btn.active {
  background: #2266dd;
  color: #fff;
  border-color: #2266dd;
}
.code-fn { background: #fdf3e7; border-color: #f0c89b; color: #a05a12; }
.code-fn.active { background: #e8923a; border-color: #e8923a; color: #fff; }

.loading-tip {
  color: #1971c2;
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 16px;
}

.result-area {
  background: #ffffff;
  border-radius: 18px;
  padding: 28px;
  box-shadow: 0 2px 16px rgba(30, 60, 120, 0.06);
  min-height: 240px;
}
.welcome { text-align: center; padding: 30px 0; }
.welcome-icon { font-size: 44px; }
.welcome-title { font-size: 20px; font-weight: 700; color: #2c3e6b; margin: 12px 0 8px; }
.welcome-sub { color: #8a8fa3; font-size: 14px; line-height: 1.8; }

.result-head { font-size: 16px; font-weight: 600; color: #333; margin-bottom: 16px; }
.btn-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.detail-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.detail-head h3 { margin: 0; color: #1971c2; font-size: 20px; }
.back-btn {
  padding: 7px 16px;
  border-radius: 10px;
  font-size: 14px;
  border: 1px solid #d8d8d8;
  background: #fff;
  cursor: pointer;
}
.back-btn:hover { background: #f1f3f5; }

.row-card {
  background: #f8faff;
  border: 1px solid #e3e9f7;
  border-left: 4px solid #2266dd;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 12px;
}
.row-line { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; flex-wrap: wrap; }
.tag { background: #eef3ff; color: #2266dd; font-size: 13px; padding: 3px 10px; border-radius: 8px; font-weight: 600; }
.line-no { color: #333; font-weight: 600; font-size: 14px; }
.sev { font-size: 12px; padding: 2px 10px; border-radius: 8px; color: #fff; font-weight: 600; }
.sev-critical { background: #e03131; }
.sev-high     { background: #f08c00; }
.sev-medium   { background: #fab005; color: #333; }
.sev-low      { background: #82c91e; }
.row-desc { color: #333; font-size: 14px; line-height: 1.6; margin-bottom: 4px; }
.row-principle { color: #555; font-size: 13px; line-height: 1.6; background: #f1f3f9; border-radius: 8px; padding: 8px 12px; margin-top: 6px; }
.empty-tip { color: #999; font-size: 14px; }
.code-block {
  white-space: pre-wrap;
  word-break: break-all;
  background: #1e1e2e;
  color: #e6edf3;
  padding: 20px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  overflow-x: auto;
}

@media (max-width: 900px) {
  .main-page { flex-direction: column; overflow: auto; }
  .sidebar { width: 100%; border-right: none; border-bottom: 1px solid #e6e9f2; }
  .cards-row { grid-template-columns: repeat(2, 1fr); }
  .btn-grid { grid-template-columns: 1fr 1fr; }
}
</style>
