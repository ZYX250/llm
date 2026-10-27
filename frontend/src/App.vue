<template>
  <div class="app">
    <!-- ===== 左侧功能导航栏 ===== -->
    <aside class="sidebar">
      <div class="brand">
        <svg class="logo" viewBox="0 0 640 512" xmlns="http://www.w3.org/2000/svg" aria-label="学位帽">
          <path fill="#ffffff" d="M623.1 136.9l-282.7-101.2c-13.73-4.91-28.7-4.91-42.43 0L16.05 136.9C6.438 140.4 0 149.6 0 160s6.438 19.65 16.05 23.09l76.63 27.39v107.1c0 26.63 40.75 49.21 91.32 61.43C238.5 400.3 276.1 416 320 416s81.5-15.73 136-36.99c50.56-12.22 91.32-34.8 91.32-61.43v-107.1l73.68-26.35V288c0 17.69 14.31 32 32 32s32-14.31 32-32V160C640 149.6 633.6 140.4 623.1 136.9zM320 352c-79.25 0-144-29.76-144-64v-39.75l99.81 35.66c13.73 4.91 28.7 4.91 42.43 0l90.5-32.35V288C464 322.2 399.2 352 320 352z"/>
        </svg>
        <div class="brand-txt">
          <div class="brand-name">科研助手</div>
          <div class="brand-sub">Agent 应用系统</div>
        </div>
      </div>

      <div class="side-block">
        <div class="side-title">控制台</div>
        <button class="nav-item" :class="{ active: view === 'home' }" @click="switchView('home')">
          <span class="ni-ico">🏠</span>统一入口
        </button>
      </div>

      <div class="side-block">
        <div class="side-title">六大功能模块</div>
        <button v-for="t in mods" :key="t.key" class="nav-item" :class="{ active: view === t.key }" @click="switchView(t.key)">
          <span class="ni-ico">{{ t.ico }}</span>
          <span class="ni-name">{{ t.name }}</span>
          <span v-if="modHint[t.key]" class="ni-hint">{{ modHint[t.key] }}</span>
        </button>
      </div>

      <div class="side-foot">科研助手 Agent v2.0<br/>PDF · RAG · 图谱 · 写作</div>
    </aside>

    <!-- ===== 右侧主区域 ===== -->
    <main class="main">
      <!-- ===== 控制台首页 ===== -->
      <section v-if="view === 'home'" class="panel home-panel">
        <div class="panel-banner">
          <div>
            <h1 class="banner-title">科研助手 Agent 系统</h1>
            <p class="banner-sub">PDF 细粒度解析 · 抗幻觉 RAG 问答 · 引用图谱挖掘 · 学术写作 Copilot</p>
          </div>
          <div class="banner-pills">
            <span class="pill">📁 已入库 {{ papers.length }} 篇</span>
            <span class="pill">🔗 图谱节点 {{ graph.nodes.length }}</span>
            <span class="pill">✨ Agent 已就绪</span>
          </div>
        </div>

        <div class="cards-row">
          <div v-for="c in capCards" :key="c.key" class="cap-card" @click="switchView(c.key)">
            <div class="cap-ico">{{ c.ico }}</div>
            <div>
              <div class="cap-title">{{ c.title }}</div>
              <div class="cap-sub">{{ c.sub }}</div>
            </div>
          </div>
        </div>

        <div class="section-label">快捷操作 · 点一下直接出结果
          <select v-if="papers.length" class="paper-picker" v-model="homeSelectedPid">
            <option value="">全部已入库论文</option>
            <option v-for="p in papers" :key="p.id" :value="p.id">{{ p.title }}</option>
          </select>
        </div>
        <div class="func-row">
          <button v-for="f in funcBtns" :key="f.key" class="func-btn" :class="{active: homeAction===f.key}" @click="runAction(f.key)">
            <span class="fb-ico">{{ f.ico }}</span>{{ f.name }}
          </button>
        </div>
        <div class="home-result" v-if="homeResult">
          <div class="hr-head">{{ homeActionTitle }} <span v-if="homeBusy" class="hr-loading">生成中…</span></div>
          <div class="hr-body" v-if="!homeBusy" v-html="homeResult"></div>
          <div class="hr-body hr-loading-body" v-else>正在调用大模型，请稍候…</div>
        </div>

        <div class="chat-card">
          <div class="chat-head">
            <div>
              <div class="chat-title">✨ 科研助手 Agent 已启动</div>
              <div class="chat-sub">我是科研助手，负责论文解析、知识问答、引用图谱与写作辅助。试试输入：帮我解析这篇论文 / 生成引用图谱 / 写一篇综述…</div>
            </div>
            <span class="chat-time">{{ nowTime }}</span>
          </div>

          <div class="chat-presets" v-if="!agentMsgs.length">
            <span class="cp-label">试试：</span>
            <button v-for="q in homePresets" :key="q" class="cp-btn" @click="agentInput = q">{{ q }}</button>
          </div>

          <div class="chat-body" ref="chatBody">
            <div class="msg" :class="m.role" v-for="(m, i) in agentMsgs" :key="i">
              <div v-if="m.role === 'assistant' && m.steps && m.steps.length" class="agent-steps">
                <span v-for="(s, si) in m.steps" :key="si" class="astp">
                  <span class="astp-n">{{ si + 1 }}</span>{{ s.action }}
                  <span v-if="si < m.steps.length - 1" class="astp-arrow">→</span>
                </span>
              </div>
              <div class="bubble">
                <span v-if="m.role === 'assistant' && m.toolLabel" class="tool-tag">{{ m.toolLabel }}</span>
                {{ m.text }}
              </div>
              <button v-if="m.role === 'assistant' && m.jump" class="jump-btn" @click="switchView(m.jump)">前往使用 →</button>
            </div>
          </div>

          <div class="chat-input">
            <input v-model="agentInput" placeholder="输入需求，例如：帮我解析上传的论文 / 生成引用图谱 / 写一篇综述" @keyup.enter="agentSend" />
            <button class="btn primary" :disabled="!agentInput || agentBusy" @click="agentSend">{{ agentBusy ? "思考中…" : "发送" }}</button>
          </div>
        </div>
      </section>

      <!-- ===== 模块一 文献库 ===== -->
      <section v-else-if="view === 'library'" class="panel">
        <div class="panel-head">
          <h2><span class="m-ico" style="background:linear-gradient(135deg,#fff7e0,#ffe9b0)">📁</span> 模块一 · PDF 管理与细粒度解析</h2>
          <div class="head-right">
            <span class="info">已入库 {{ papers.length }} 篇</span>
            <button class="btn primary" :disabled="uploading" @click="triggerUpload">上传 PDF（可多选）</button>
            <input type="file" ref="fileInput" accept=".pdf" multiple hidden @change="uploadFiles" />
          </div>
        </div>

        <!-- 小部件：统计概览 -->
        <div class="mini-stats">
          <div class="mini-stat"><div class="ms-num">{{ papers.length }}</div><div class="ms-label">论文总数</div></div>
          <div class="mini-stat"><div class="ms-num">{{ totalPages }}</div><div class="ms-label">总页数</div></div>
          <div class="mini-stat"><div class="ms-num">{{ ocrCount }}</div><div class="ms-label">OCR 扫描件</div></div>
          <div class="mini-stat"><div class="ms-num">{{ dedupCount }}</div><div class="ms-label">去重提醒</div></div>
        </div>

        <div class="notice" v-if="dedupNotice">{{ dedupNotice }}</div>

        <div class="drop-tip" @dragover.prevent @drop.prevent="onDrop">📂 拖拽 PDF 到此处，或点击右上角上传（支持批量、自动 OCR / 去重）</div>

        <!-- 小部件：上传解析进度条 -->
        <div class="upload-progress" v-if="uploadTasks.length">
          <div class="up-title">⏳ 解析进度</div>
          <div v-for="t in uploadTasks" :key="t.pid" class="up-item">
            <span class="up-name">{{ t.name }}</span>
            <span class="up-track"><span class="up-fill" :class="'st'+t.status" :style="{ width: (t.progress||0) + '%' }"></span></span>
            <span class="up-pct">{{ t.progress || 0 }}%</span>
            <span class="up-st" :class="t.status">{{ t.status==='done' ? '✔ 完成' : (t.status==='error' ? '✘ 失败' : '解析中…') }}</span>
          </div>
        </div>

        <!-- 小部件：使用流程指引 -->
        <div class="lib-steps">
          <div class="lst-item"><span class="lst-n">1</span>上传 PDF</div>
          <div class="lst-arrow">→</div>
          <div class="lst-item"><span class="lst-n">2</span>细粒度解析</div>
          <div class="lst-arrow">→</div>
          <div class="lst-item"><span class="lst-n">3</span>抗幻觉问答</div>
          <div class="lst-arrow">→</div>
          <div class="lst-item"><span class="lst-n">4</span>图谱 / 写作</div>
        </div>

        <div class="cards">
          <div v-for="p in papers" :key="p.id" class="paper-card">
            <div class="pc-head">
              <div class="pc-title">{{ p.title || p.filename }}</div>
              <button class="btn danger small" @click="delPaper(p.id)">删除</button>
            </div>
            <div class="pc-meta">
              <span>{{ p.filename }}</span><span>{{ p.page_count }} 页</span>
              <span v-if="p.used_ocr" class="badge ocr">OCR</span><span v-else class="badge">矢量</span>
            </div>
            <div class="pc-actions">
              <button class="btn small" @click="showParse(p.id)">细粒度解析</button>
              <button class="btn small" @click="askThis(p.id, p.title)">就本文提问</button>
              <button class="btn small" @click="reparse(p.id)">重新解析(OCR)</button>
            </div>
          </div>
        </div>
        <div class="empty" v-if="!papers.length">尚未上传论文，请上传 PDF（官方测试集：1706.03762 等）</div>

        <div class="parse-box" v-if="parse">
          <div class="parse-head"><h3>细粒度解析结果</h3><button class="btn small" @click="parse = null">关闭</button></div>
          <div class="pmeta">
            <div><b>标题：</b>{{ parse.meta.title }}</div>
            <div><b>作者/机构：</b>{{ parse.meta.authors || "—" }}</div>
            <div><b>摘要：</b>{{ parse.meta.abstract || "—" }}</div>
          </div>
          <div class="ptabs">
            <button v-for="pt in parseTabs" :key="pt" class="btn small" :class="{active: parseTab===pt}" @click="parseTab=pt">{{ pt }}</button>
          </div>
          <div v-if="parseTab==='标题树'">
            <ul class="tree">
              <li v-for="(h,i) in parse.headings.slice(0,50)" :key="i" :class="'lv'+h.level"><span class="lv-tag">{{ 'H'+h.level }}</span> {{ h.title }} <em>p{{ h.page }}</em></li>
            </ul>
          </div>
          <div v-if="parseTab==='公式'"><pre class="formula">{{ parse.formulas.slice(0,20).join('\n') || '无' }}</pre></div>
          <div v-if="parseTab==='表格'">
            <div v-for="(t,i) in parse.tables.slice(0,5)" :key="i"><div class="tbl-caption">p{{ t.page }}</div><table class="tbl"><tr v-for="(row,ri) in t.data" :key="ri"><td v-for="(c,ci) in row" :key="ci">{{ c }}</td></tr></table></div>
          </div>
          <div v-if="parseTab==='参考文献'"><ol class="refs"><li v-for="r in parse.references.slice(0,20)" :key="r.idx">[{{r.idx}}] {{ r.text }}</li></ol></div>
        </div>
      </section>

      <!-- ===== 模块二 智能问答 ===== -->
      <section v-else-if="view === 'qa'" class="panel">
        <div class="panel-head"><h2><span class="m-ico" style="background:linear-gradient(135deg,#f0e9ff,#ddd2ff)">💬</span> 模块二 · 抗幻觉知识问答</h2><span class="info">RAG 溯源锚点 · 多文跨文献推理</span></div>

        <!-- 小部件：热门问题快捷提问 -->
        <div class="widget">
          <div class="widget-title">🔥 热门问题 · 点击直接提问</div>
          <div class="chip-row">
            <button v-for="q in qaPresets" :key="q" class="chip" @click="askPreset(q)">{{ q }}</button>
          </div>
        </div>

        <!-- 小部件：提问技巧提示 -->
        <div class="qa-tips">
          <div class="qt"><span class="qt-ico">🎯</span><b>问具体数值</b>超参、GPU、数据量等可精确到数字</div>
          <div class="qt"><span class="qt-ico">🔀</span><b>多文对比</b>选择多篇论文可做跨文献推理</div>
          <div class="qt"><span class="qt-ico">📌</span><b>溯源锚点</b>回答自动附原文页码出处</div>
        </div>

        <div class="qa-scope">
          <span>检索范围：</span>
          <button v-for="p in papers" :key="p.id" class="btn small" :class="{ active: qaScope.includes(p.id) }" @click="toggleQaScope(p.id)">{{ p.title.slice(0,14) }}</button>
          <button class="btn small" :class="{ active: qaScope.length===0 }" @click="qaScope=[]">全库 ({{ papers.length }})</button>
        </div>

        <div class="qa-input">
          <textarea v-model="qaQuery" rows="2" placeholder="提问，例如：这篇论文的β_1/β_2 超参数是多少？训练的GPU型号与数量？对比 BERT 与 Transformer Encoder 的关系…"></textarea>
          <button class="btn primary" :disabled="!qaQuery || qaLoading" @click="askQA">{{ qaLoading ? "分析中…" : "提问" }}</button>
        </div>

        <div class="chat" v-if="qaAnswer || qaStreamText">
          <div class="qa-conf" v-if="qaConfidence">回答置信度 <span class="conf" :class="'c'+qaConfidence">{{ qaConfidence }}</span>（依据检索命中率估算）</div>
          <div class="bubble">
            <div class="bubble-tools">
              <button class="copy-btn" @click="copyText(qaStreamText || qaAnswer)">📋 复制</button>
            </div>
            {{ qaStreamText || qaAnswer }}
          </div>
          <div v-if="qaSources.length" class="sources">
            <div class="src-title">📌 原文溯源锚点（{{ qaSources.length }}）</div>
            <div v-for="(s,i) in qaSources" :key="i" class="src">
              <div class="src-head"><b>{{ s.title }} · 第 {{ s.page }} 页</b><span class="conf" :class="'c'+(s.confidence||'低')">{{ s.confidence||'低' }}置信</span></div>
              <span class="src-snip">{{ s.snippet }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- ===== 模块三 双语阅读 ===== -->
      <section v-else-if="view === 'read'" class="panel">
        <div class="panel-head">
          <h2><span class="m-ico" style="background:linear-gradient(135deg,#e8f1ff,#cde4ff)">📖</span> 模块三 · 版式感知阅读与翻译</h2>
          <div class="head-right">
            <span class="info">已入库 {{ papers.length }} 篇</span>
            <div class="paper-pick">
              <span class="pick-ico">📄</span>
              <select class="sel" v-model="readPaper" @change="loadRead">
                <option value="">选择论文…</option>
                <option v-for="p in papers" :key="p.id" :value="p.id">{{ p.title }}</option>
              </select>
            </div>
          </div>
        </div>

        <!-- ===== 未选择：引导面板（消除空白） ===== -->
        <div v-if="!readData" class="read-welcome">
          <div class="rw-stats">
            <div class="mini-stat"><div class="ms-num">{{ papers.length }}</div><div class="ms-label">可用论文</div></div>
            <div class="mini-stat"><div class="ms-num">{{ totalPages }}</div><div class="ms-label">可读总页数</div></div>
            <div class="mini-stat"><div class="ms-num">{{ maxPages }}</div><div class="ms-label">最长论文页数</div></div>
            <div class="mini-stat"><div class="ms-num">{{ avgPages }}</div><div class="ms-label">平均页数</div></div>
          </div>

          <div class="rw-features">
            <div class="rwf-card"><div class="rwf-ico">📑</div><div class="rwf-t">目录导航</div><div class="rwf-s">标题树一键跳转到任意章节</div></div>
            <div class="rwf-card"><div class="rwf-ico">🔄</div><div class="rwf-t">中英对照</div><div class="rwf-s">原文与译文逐页双栏对照</div></div>
            <div class="rwf-card"><div class="rwf-ico">📈</div><div class="rwf-t">进度追踪</div><div class="rwf-s">实时显示阅读进度百分比</div></div>
            <div class="rwf-card"><div class="rwf-ico">🌐</div><div class="rwf-t">整篇翻译</div><div class="rwf-s">一键生成当前页学术翻译</div></div>
          </div>

          <div class="rw-list-title">📚 从文献库选择要阅读的论文</div>
          <div v-if="papers.length" class="rw-list">
            <div v-for="p in papers" :key="p.id" class="rw-item" @click="gotoReadPaper(p.id)">
              <span class="rw-file">{{ p.filename }}</span>
              <span class="rw-name">{{ p.title }}</span>
              <span class="rw-meta">{{ p.page_count }} 页 · {{ p.used_ocr ? '扫描件' : '矢量版' }}</span>
              <span class="rw-go">开始阅读 →</span>
            </div>
          </div>
          <div v-else class="empty">文献库暂无论文，请先在「📁 文献库」上传 PDF</div>
        </div>

        <!-- ===== 已选择：阅读界面 ===== -->
        <div v-if="readData">
          <!-- 小部件：论文信息条 + 阅读工具 -->
          <div class="paper-info-bar">
            <div class="pi-left">
              <div class="pi-title">{{ readData.title || readPaper }}</div>
              <div class="pi-meta">{{ readData.total_pages }} 页 · {{ (readData.headings||[]).length }} 个章节 · 当前第 {{ readPage }} 页</div>
            </div>
            <div class="pi-tools">
              <span class="font-ctl">
                <button class="btn small" @click="changeFont(-1)">A-</button>
                <span class="font-val">{{ fontSize }}px</span>
                <button class="btn small" @click="changeFont(1)">A+</button>
              </span>
              <span class="jump-ctl">
                <input type="number" v-model.number="readJump" min="1" :max="readData.total_pages" class="jump-in" @keyup.enter="jumpToPage" />
                <button class="btn small" @click="jumpToPage">跳页</button>
              </span>
            </div>
          </div>

          <!-- 小部件：阅读进度条 -->
          <div class="progress-wrap">
            <div class="progress-bar"><div class="progress-fill" :style="{ width: readProgress + '%' }"></div></div>
            <span class="progress-txt">已读 {{ readPage }} / {{ readData.total_pages }} 页（{{ readProgress }}%）</span>
          </div>

          <div class="read-layout">
            <div class="read-toc">
              <div class="toc-title">📑 目录导航</div>
              <div v-for="(h,i) in filteredHeadings" :key="h.title+h.page" class="toc-item" :class="['tlv'+h.level, {cur: h.title===activeToc}]" @click="gotoToc(h)">
                <span class="toc-idx">{{ i+1 }}</span>
                <span class="toc-t">{{ h.title }}</span>
                <span class="toc-p">p.{{ h.real_page || h.page }}</span>
              </div>
              <div class="toc-empty" v-if="!filteredHeadings.length">未检测到章节标题</div>
            </div>
            <div class="read-main">
              <div class="read-toolbar">
                <button class="btn small" @click="prevPage">← 上一页</button>
                <span>第 {{ readPage }} / {{ readData.total_pages }} 页</span>
                <button class="btn small" @click="nextPage">下一页 →</button>
                <span class="mode-toggle">
                  <button class="btn small" :class="{active: mode==='single'}" @click="mode='single'">原文</button>
                  <button class="btn small" :class="{active: mode==='dual'}" @click="mode='dual'">中英对照</button>
                </span>
              </div>
              <div class="dual" v-if="mode==='dual'">
                <div class="col en"><div class="col-label">原文（EN）</div><div class="col-body paper-text" :style="{ fontSize: fontSize+'px' }">{{ fmtText(readCurrent) }}</div></div>
                <div class="col zh"><div class="col-label">译文（ZH）</div><div class="col-body paper-text" :style="{ fontSize: fontSize+'px' }">
                  <template v-if="readTranslated">{{ fmtText(readTranslated) }}</template>
                  <template v-else>
                    <span v-if="translating">翻译中…</span>
                    <button v-else class="btn small translate-inline" @click="translatePage">📝 翻译本页（中英对照）</button>
                  </template>
                </div></div>
              </div>
              <div class="col single-body" v-else><div class="col-body paper-text" :style="{ fontSize: fontSize+'px' }">{{ fmtText(readCurrent) }}</div></div>
            </div>
          </div>
        </div>
      </section>

      <!-- ===== 模块四 论文检索 ===== -->
      <section v-else-if="view === 'search'" class="panel">
        <div class="panel-head"><h2><span class="m-ico" style="background:linear-gradient(135deg,#e0f7f4,#c2f2ea)">🔍</span> 模块四 · 论文检索、追踪与推荐</h2></div>

        <!-- 小部件：示例检索词 -->
        <div class="widget">
          <div class="widget-title">🎯 热门检索词</div>
          <div class="chip-row">
            <button v-for="s in searchPresets" :key="s" class="chip" @click="searchQuery=s; doSearch()">{{ s }}</button>
          </div>
        </div>

        <div class="qa-input">
          <input v-model="searchQuery" class="txt" placeholder="输入论文名/关键词，如 Transformer attention 或参考文献条目" @keyup.enter="doSearch" />
          <button class="btn primary" :disabled="!searchQuery" @click="doSearch">检索 arXiv</button>
        </div>
        <!-- 小部件：结果画像 -->
        <div class="search-stat" v-if="searchResults.length">
          <div class="ss-item"><b>{{ searchResults.length }}</b> 检索结果</div>
          <div class="ss-item"><b>{{ searchResults.filter(it=>it.reproducible).length }}</b> 附开源代码</div>
          <div class="ss-item"><b>{{ searchResults.length - searchResults.filter(it=>it.reproducible).length }}</b> 无代码</div>
          <div class="ss-bar" title="可复现论文占比"><span :style="{ width: (searchResults.filter(it=>it.reproducible).length / searchResults.length * 100) + '%' }"></span></div>
        </div>
        <div class="cards">
          <div v-for="(it,i) in searchResults" :key="i" class="paper-card">
            <div class="pc-title">{{ it.title }}</div>
            <div class="pc-meta">{{ (it.authors||[]).slice(0,3).join(', ') }} · {{ (it.published||'').slice(0,10) }}</div>
            <p class="abs">{{ (it.abstract||'').slice(0,220) }}…</p>
            <div class="row">
              <span class="badge" :class="it.reproducible ? 'ocr' : ''">{{ it.reproducible ? "🔧 附开源代码·易复现" : "无代码" }}</span>
              <a :href="it.pdf" target="_blank" class="btn small">PDF</a>
              <a :href="it.url" target="_blank" class="btn small">详情</a>
            </div>
            <div class="reason">推荐理由：{{ it.reason }}</div>
          </div>
        </div>
        <div class="empty" v-if="!searchResults.length">输入关键词检索 arXiv 最新论文</div>
      </section>

      <!-- ===== 模块五 引用图谱 ===== -->
      <section v-else-if="view === 'graph'" class="panel">
        <div class="panel-head">
          <h2><span class="m-ico" style="background:linear-gradient(135deg,#ffe9f2,#ffd4e2)">🕸</span> 模块五 · 引用图谱挖掘与综述</h2>
          <div class="head-right">
            <button class="btn" @click="loadGraph">生成图谱</button>
            <button class="btn primary" :disabled="!graph.nodes.length" @click="genSummary">综述 + 前沿探索</button>
          </div>
        </div>

        <!-- 小部件：图谱统计 -->
        <div class="mini-stats">
          <div class="mini-stat"><div class="ms-num">{{ graph.nodes.length }}</div><div class="ms-label">论文节点</div></div>
          <div class="mini-stat"><div class="ms-num">{{ graph.links.length }}</div><div class="ms-label">引用连线</div></div>
          <div class="mini-stat"><div class="ms-num">{{ (graph.cornerstone||[]).length }}</div><div class="ms-label">基石论文</div></div>
          <div class="mini-stat"><div class="ms-num">{{ (graph.derivative||[]).length }}</div><div class="ms-label">衍生论文</div></div>
        </div>

        <div v-if="graph.nodes.length" class="graph-wrap">
          <div ref="graphEl" class="graph-box"></div>
          <div class="graph-side">
            <div class="pr-block" v-if="(graph.cornerstone||[]).length">
              <h4>🔥 基石论文影响力</h4>
              <div v-for="n in graph.cornerstone.slice(0,4)" :key="n.id" class="pr-item">
                <span class="pr-name">{{ n.title.slice(0,20) }}</span>
                <span class="pr-track"><span class="pr-fill" :style="{ width: (Math.min(n.pagerank,1)*100) + '%' }"></span></span>
                <span class="pr-val">{{ n.pagerank }}</span>
              </div>
            </div>
            <h4>📌 基石论文（PageRank）</h4>
            <ul><li v-for="n in graph.cornerstone" :key="n.id"><b>{{ n.title }}</b> <em>PR {{ n.pagerank }}</em></li></ul>
            <h4>🧩 边缘衍生论文</h4>
            <ul><li v-for="n in graph.derivative" :key="n.id">{{ n.title }}</li></ul>
            <h4>💡 图例</h4>
            <p class="legend">节点=论文 · 连线=引用关系 · 圆圈大小=影响力；拖动可调整布局，滚轮缩放</p>
          </div>
        </div>
        <div class="empty" v-if="!graph.nodes.length">上传 ≥2 篇有引用关系的论文后可生成引用图谱</div>
        <div v-if="summaryText" class="gen-box">
          <h4>领域简短综述</h4><p>{{ summaryText }}</p>
          <h4>前沿探索（Future Work 提炼）</h4><pre>{{ futureText }}</pre>
        </div>
      </section>

      <!-- ===== 模块六 写作Copilot ===== -->
      <section v-else-if="view === 'write'" class="panel">
        <div class="panel-head"><h2><span class="m-ico" style="background:linear-gradient(135deg,#fff0e6,#ffdfc4)">✍️</span> 模块六 · 学术写作与可视化 Copilot</h2></div>
        <div class="tabs2">
          <button v-for="wt in writeTabs" :key="wt.key" class="btn small" :class="{active:writeTab===wt.key}" @click="writeTab=wt.key">{{ wt.ico }} {{ wt.name }}</button>
        </div>

        <!-- 小部件：使用提示 -->
        <div class="write-hint">💡 生成内容后可用「📋 复制」直接插入论文：框架→起草骨架，拓扑→插入图表，CSV→自动配 Figure Caption，翻译→学术润色。</div>

        <div v-if="writeTab==='frame'" class="sub">
          <div class="widget"><div class="widget-title">📝 示例 Idea</div>
            <div class="chip-row">
              <button v-for="s in framePresets" :key="s" class="chip" @click="idea=s">{{ s }}</button>
            </div>
          </div>
          <textarea v-model="idea" class="txt big" placeholder="输入研究 idea，例如：基于检索增强的多文档长上下文理解模型"></textarea>
          <button class="btn primary" :disabled="!idea.trim() || frameworkLoading" @click="genFramework">{{ frameworkLoading ? "正在生成…" : "生成无幻觉论文框架" }}</button>
          <div v-if="frameworkLoading" class="out-wrap"><div class="hr-body hr-loading-body">正在调用大模型生成论文骨架，请稍候（约10-20秒）…</div></div>
          <div v-else-if="framework" class="out-wrap"><pre class="out">{{ framework }}</pre><button class="copy-btn" @click="copyText(framework)">📋 复制</button></div>
        </div>

        <div v-if="writeTab==='topo'" class="sub">
          <div class="row2">
            <select v-model="topoKind" class="sel"><option>mermaid</option><option>graphviz</option><option>tikz</option><option>matplotlib</option></select>
            <button v-for="s in topoPresets" :key="s" class="chip" @click="topoPrompt=s">{{ s }}</button>
          </div>
          <textarea v-model="topoPrompt" class="txt big" placeholder="描述要绘制的架构/拓扑，例如：一个RAG检索增强生成流程图"></textarea>
          <button class="btn primary" :disabled="!topoPrompt" @click="genTopology">生成绘图脚本</button>
          <div v-if="topologyScript" class="out-wrap"><pre class="out">{{ topologyScript }}</pre><button class="copy-btn" @click="copyText(topologyScript)">📋 复制</button></div>
        </div>

        <div v-if="writeTab==='viz'" class="sub">
          <div class="row">
            <select v-model="vizKind" class="sel"><option value="line">折线图</option><option value="bar">柱状图</option><option value="scatter">散点图</option><option value="radar3d">三维图</option></select>
            <input type="file" accept=".csv" ref="csvInput" @change="uploadViz" />
          </div>
          <div class="viz-grid" v-if="vizResult.image">
            <img :src="vizResult.image" class="viz-img" />
            <div class="viz-info">
              <div v-html="vizResult.table"></div>
              <div class="caption" v-if="vizResult.caption"><b>Figure Caption：</b>{{ vizResult.caption }}</div>
              <button v-if="vizResult.caption" class="btn small" @click="copyText(vizResult.caption)">📋 复制 Caption</button>
            </div>
          </div>
          <div class="empty" v-if="vizError">{{ vizError }}</div>
        </div>

        <div v-if="writeTab==='trans'" class="sub">
          <div class="widget"><div class="widget-title">🌐 示例文本</div>
            <div class="chip-row"><button class="chip" @click="transText=transPreset">{{ transPreset.slice(0,30) }}…</button></div>
          </div>
          <textarea v-model="transText" class="txt big" placeholder="输入中文摘要或全文"></textarea>
          <button class="btn primary" :disabled="!transText" @click="doTranslate">{{ translating ? "翻译中…" : "翻译为学术英文" }}</button>
          <div v-if="translated" class="out-wrap"><pre class="out">{{ translated }}</pre><button class="copy-btn" @click="copyText(translated)">📋 复制</button></div>
        </div>
      </section>
    </main>

    <!-- ===== Agent 桌宠（可拖动 · 简单问答 · 快捷指令） ===== -->
    <div class="pet" :style="{ left: petX + 'px', top: petY + 'px' }">
      <div v-if="petOpen" class="pet-card">
        <div class="pet-head">
          <span class="pet-avatar"><svg class="pet-logo" viewBox="0 0 640 512" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M623.1 136.9l-282.7-101.2c-13.73-4.91-28.7-4.91-42.43 0L16.05 136.9C6.438 140.4 0 149.6 0 160s6.438 19.65 16.05 23.09l76.63 27.39v107.1c0 26.63 40.75 49.21 91.32 61.43C238.5 400.3 276.1 416 320 416s81.5-15.73 136-36.99c50.56-12.22 91.32-34.8 91.32-61.43v-107.1l73.68-26.35V288c0 17.69 14.31 32 32 32s32-14.31 32-32V160C640 149.6 633.6 140.4 623.1 136.9zM320 352c-79.25 0-144-29.76-144-64v-39.75l99.81 35.66c13.73 4.91 28.7 4.91 42.43 0l90.5-32.35V288C464 322.2 399.2 352 320 352z"/></svg></span>
          <div class="pet-hd-txt">
            <div class="pet-name">科研助手 · 桌宠</div>
            <div class="pet-sub">有问题问我 · 可拖动位置</div>
          </div>
          <button class="pet-close" title="收起" @click="petOpen=false">－</button>
        </div>

        <div class="pet-body" ref="petBody">
          <div class="pet-msg" :class="m.role" v-for="(m,i) in petMsgs" :key="i">
            <div class="pet-bubble">{{ m.text }}</div>
          </div>
          <div v-if="petBusy" class="pet-msg assistant"><div class="pet-bubble pet-typing">思考中…</div></div>
        </div>

        <div class="pet-shortcuts">
          <button class="pet-chip" v-for="s in petShortcuts" :key="s.q" @click="petSend(s.q)">{{ s.l }}</button>
        </div>

        <div class="pet-input">
          <input v-model="petInput" placeholder="问我论文相关问题，例如：核心创新点？实验结论？" @keyup.enter="petSend()" />
          <button class="pet-send" :disabled="!petInput || petBusy" @click="petSend()">➤</button>
        </div>
      </div>

      <div class="pet-icon" @mousedown="onPetDown" title="科研助手桌宠">
        <svg class="pet-logo" viewBox="0 0 640 512" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M623.1 136.9l-282.7-101.2c-13.73-4.91-28.7-4.91-42.43 0L16.05 136.9C6.438 140.4 0 149.6 0 160s6.438 19.65 16.05 23.09l76.63 27.39v107.1c0 26.63 40.75 49.21 91.32 61.43C238.5 400.3 276.1 416 320 416s81.5-15.73 136-36.99c50.56-12.22 91.32-34.8 91.32-61.43v-107.1l73.68-26.35V288c0 17.69 14.31 32 32 32s32-14.31 32-32V160C640 149.6 633.6 140.4 623.1 136.9zM320 352c-79.25 0-144-29.76-144-64v-39.75l99.81 35.66c13.73 4.91 28.7 4.91 42.43 0l90.5-32.35V288C464 322.2 399.2 352 320 352z"/></svg>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "ResearchAssistant",
  data() {
    return {
      view: "home",
      nowTime: "",
      mods: [
        { key: "library", name: "文献库", ico: "📁" },
        { key: "qa", name: "智能问答", ico: "💬" },
        { key: "read", name: "双语阅读", ico: "📖" },
        { key: "search", name: "检索追踪", ico: "🔍" },
        { key: "graph", name: "引用图谱", ico: "🕸" },
        { key: "write", name: "写作Copilot", ico: "✍️" }
      ],
      modHint: {
        library: "上传 / OCR / 去重",
        qa: "RAG 溯源问答",
        read: "中英对照",
        search: "arXiv 检索",
        graph: "基石 / 综述",
        write: "框架 / 可视化"
      },
      capCards: [
        { key: "library", ico: "📁", title: "文献库", sub: "上传 · OCR · 去重" },
        { key: "qa", ico: "💬", title: "智能问答", sub: "RAG 溯源锚点" },
        { key: "read", ico: "📖", title: "双语阅读", sub: "中英对照翻译" },
        { key: "search", ico: "🔍", title: "论文检索", sub: "arXiv 文献追踪" },
        { key: "graph", ico: "🕸", title: "引用图谱", sub: "基石 · 综述" },
        { key: "write", ico: "✍️", title: "写作 Copilot", sub: "框架 · 可视化" }
      ],
      funcBtns: [
        { key: "summary", name: "一句话总结", ico: "📖" },
        { key: "roadmap", name: "研究路线图", ico: "💡" },
        { key: "review", name: "自动写综述", ico: "📝" },
        { key: "trans", name: "翻译标题", ico: "🌐" },
        { key: "arxiv", name: "arXiv最新", ico: "🔍" },
        { key: "graph", name: "引用图谱", ico: "🕸" }
      ],
      homeAction: "", homeResult: "", homeBusy: false, homeActionTitle: "", homeSelectedPid: "",
      homePresets: ["帮我解析这篇论文", "生成引用图谱", "写一篇综述", "对比 BERT 与 Transformer"],
      qaPresets: ["这篇论文的β_1/β_2超参数是多少？", "训练用了什么GPU、多少块？", "对比 BERT 与 Transformer-Encoder", "GPT 系列参数量如何增长？"],
      searchPresets: ["Transformer", "Large Language Model", "Retrieval Augmented Generation"],
      framePresets: ["基于检索增强的多文档长上下文理解模型", "面向科学文献的引用图谱与综述生成", "少样本跨语言学术翻译研究"],
      topoPresets: ["RAG检索增强生成流程图", "Transformer 编码器结构图", "多Agent协作架构图"],
      transPreset: "我们提出了一种基于注意力机制的新型神经网络架构，在多个机器翻译任务上取得了显著效果提升。",

      agentMsgs: [], agentInput: "", agentBusy: false, agentSession: "",

      petOpen: false, petBusy: false, petInput: "", petMsgs: [],
      petX: null, petY: null, petDrag: null,
      petShortcuts: [
        { l: "这篇论文讲了什么", q: "这篇论文的核心内容和方法是什么？" },
        { l: "主要创新点", q: "这篇论文的主要创新点是什么？" },
        { l: "实验结论", q: "这篇论文的主要实验结论是什么？" },
        { l: "局限性", q: "这篇论文有哪些局限性或不足？" },
        { l: "和BERT比", q: "这篇论文的方法和 BERT 相比有什么优势？" },
        { l: "帮我写综述", q: "基于已入库论文帮我写一段综述" }
      ],

      papers: [], dedupNotice: "", uploading: false, uploadTasks: [],
      parse: null, parseTab: "标题树", parseTabs: ["标题树", "公式", "表格", "参考文献"],
      qaQuery: "", qaAnswer: "", qaStreamText: "", qaSources: [], qaScope: [], qaLoading: false, qaConfidence: "",
      readPaper: "", readData: null, readPage: 1, readCurrent: "", readTranslated: "", mode: "single", translating: false, fontSize: 14, readJump: 1,
      searchQuery: "", searchResults: [],
      graph: { nodes: [], links: [], cornerstone: [], derivative: [] },
      summaryText: "", futureText: "",
      writeTab: "frame", writeTabs: [
        { key: "frame", name: "论文框架", ico: "📝" },
        { key: "topo", name: "拓扑图脚本", ico: "🧩" },
        { key: "viz", name: "CSV可视化", ico: "📊" },
        { key: "trans", name: "学术翻译", ico: "🌐" }
      ],
      idea: "", framework: "", frameworkLoading: false, topoKind: "mermaid", topoPrompt: "", topologyScript: "",
      vizKind: "line", vizResult: {}, vizError: "",
      transText: "", translated: "",
      toolToView: { rag_qa: "qa", dedup: "library", read_translate: "read", arxiv_search: "search", graph_review: "graph", writing_copilot: "write" }
    };
  },
  computed: {
    totalPages() { return this.papers.reduce((s, p) => s + (p.page_count || 0), 0); },
    ocrCount() { return this.papers.filter(p => p.used_ocr).length; },
    dedupCount() { return this.dedupNotice ? 1 : 0; },
    maxPages() { return this.papers.reduce((m, p) => Math.max(m, p.page_count || 0), 0); },
    avgPages() { return this.papers.length ? Math.round(this.totalPages / this.papers.length) : 0; },
    filteredHeadings() {
      return ((this.readData && this.readData.headings) || []).filter(h => {
        const t = (h.title || "").trim();
        if (!t) return false;
        if (/^\d+([.:]\d+)*$/.test(t)) return false;     // 纯数字页码/小节号
        if (/^arxiv:/i.test(t) || /^\[stat\.ml/i.test(t) || /\d{1,2}\s+(jul|jan|feb|mar|apr|may|jun|aug|sep|oct|nov|dec)/i.test(t)) return false;  // arXiv 元信息
        if (t.length < 2) return false;
        return true;
      }).slice(0, 60);
    },
    activeToc() {
      const hs = this.filteredHeadings;
      let cur = "";
      for (const h of hs) { const rp = h.real_page || h.page; if (rp <= this.readPage) cur = h.title; else break; }
      return cur;
    },
    readProgress() {
      if (!this.readData || !this.readData.total_pages) return 0;
      return Math.round((this.readPage / this.readData.total_pages) * 100);
    }
  },
  methods: {
    switchView(k) { this.view = k; if (k === "graph") this.$nextTick(() => this.renderGraph()); },
    async runAction(key) {
      if (this.homeBusy) return;
      this.homeAction = key; this.homeResult = "…"; this.homeBusy = true;
      const titles = { summary:"📖 一句话总结", roadmap:"💡 研究路线图", review:"📝 自动写综述", trans:"🌐 标题翻译", arxiv:"🔍 arXiv 最新相关论文", graph:"🕸 引用图谱概览" };
      this.homeActionTitle = titles[key] || "";
      const pidList = this.homeSelectedPid ? [this.homeSelectedPid] : this.papers.map(p => p.id);
      try {
        if (key === "summary") {
          const r = await this.api("/qa", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ query:"用一句话总结这篇论文的核心贡献和方法", paper_ids: pidList, top_k: 4 }) });
          this.homeResult = (r.answer||"").replace(/\n/g,"<br/>");
        } else if (key === "roadmap") {
          const r = await this.api("/research/roadmap", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ scope: pidList }) });
          this.homeResult = (r.roadmap||r.msg||"出错").replace(/\n/g,"<br/>");
        } else if (key === "review") {
          const r = await this.api("/graph/summary", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ scope: pidList }) });
          this.homeResult = "<b>综述：</b><br/>"+(r.summary||"")+"<br/><br/><b>未来方向：</b><br/>"+(r.future||"").replace(/\n/g,"<br/>");
        } else if (key === "trans") {
          const p = this.papers.find(x => x.id === this.homeSelectedPid) || this.papers[0];
          const t = p ? p.title : "Layer Normalization";
          const r = await this.api("/translate", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ text: t }) });
          this.homeResult = "原文："+t+"<br/>译文："+(r.translated||"");
        } else if (key === "arxiv") {
          const p = this.papers.find(x => x.id === this.homeSelectedPid) || this.papers[0];
          const kw = p ? p.title.split(" ").slice(0,3).join(" ") : "layer normalization";
          const r = await this.api("/search/arxiv?q="+encodeURIComponent(kw)+"&max_results=5");
          this.homeResult = (r.items||[]).map((it,i)=>`<b>${i+1}. ${it.title}</b><br/><span style="color:#888">${(it.summary||"").slice(0,120)}…</span><br/><br/>`).join("") || "暂无结果";
        } else if (key === "graph") {
          const r = await this.api("/graph");
          if (r.empty) this.homeResult = "还没入库论文，先去文献库上传 PDF～";
          else this.homeResult = `节点：<b>${r.nodes.length}</b> 个论文<br/>引用关系：<b>${r.links.length}</b> 条边<br/>基石论文：<b>${(r.cornerstone||[]).map(n=>n.title).slice(0,3).join("、")||"无"}</b>`;
        }
      } catch(e) { this.homeResult = "调用失败："+e; }
      this.homeBusy = false;
    },
    async api(url, opts = {}) {
      const res = await fetch("/api" + url, opts);
      const text = await res.text();
      try { return JSON.parse(text); } catch { return { msg: text }; }
    },
    copyText(t) { if (navigator.clipboard) navigator.clipboard.writeText(t || ""); },
    triggerUpload() { this.$refs.fileInput.click(); },
    async onDrop(e) {
      const files = Array.from(e.dataTransfer.files || []).filter(f => f.name.toLowerCase().endsWith(".pdf"));
      if (!files.length) return;
      await this.startUpload(files);
    },
    async uploadFiles(e) {
      const files = Array.from(e.target.files || []);
      if (!files.length) return;
      await this.startUpload(files);
      e.target.value = "";
    },
    async startUpload(files) {
      this.uploading = true; this.dedupNotice = "";
      const fd = new FormData();
      files.forEach(f => fd.append("files", f));
      const r = await this.api("/upload", { method: "POST", body: fd });
      const results = r.results || [];
      for (const f of files) {
        const res = results.find(x => x.filename === f.name);
        if (res && res.ok) this.uploadTasks.push({ name: f.name, pid: res.id, progress: 0, status: "parsing" });
      }
      await this.pollUploads();
    },
    async reparse(id) {
      if (!confirm("将重新解析该论文（OCR 全页重扫，可能需要数十秒），继续？")) return;
      const p = this.papers.find(x => x.id === id);
      const r = await this.api("/papers/" + id + "/reparse", { method: "POST" });
      if (!r.ok) return alert(r.msg || "重新解析失败");
      this.uploadTasks.push({ name: (p && p.title) || "重新解析", pid: id, progress: 0, status: "parsing" });
      await this.pollUploads();
      if (this.readPaper === id) { this.readPage = 1; await this.fetchRead(); this.readTranslated = ""; }
    },
    async pollUploads() {
      const pending = () => this.uploadTasks.some(t => t.status === "parsing");
      while (pending()) {
        const active = this.uploadTasks.filter(t => t.status === "parsing");
        for (const t of active) {
          try {
            const st = await this.api("/parse/" + t.pid + "/status");
            t.progress = st.progress || 0;
            if (st.status === "done") { t.status = "done"; t.progress = 100; t.dedup = st.dedup; }
            else if (st.status === "error") { t.status = "error"; t.error = st.error || ""; }
          } catch {}
        }
        if (pending()) await new Promise(res => setTimeout(res, 700));
      }
      const dupTask = this.uploadTasks.find(t => t.dedup && t.dedup.notice);
      if (dupTask) this.dedupNotice = dupTask.dedup.notice;
      this.uploading = false;
      await this.loadPapers();
    },
    async loadPapers() { const r = await this.api("/papers"); this.papers = r.papers || []; },
    async delPaper(id) { if (!confirm("确认删除该论文？")) return; await this.api("/papers/" + id, { method: "DELETE" }); await this.loadPapers(); },
    async showParse(id) { this.parseTab = "标题树"; const r = await this.api("/papers/" + id + "/parse"); this.parse = r.ok ? r : null; },
    askThis(id, title) { this.view = "qa"; this.qaScope = [id]; this.qaQuery = "请解析这篇论文" + (title ? "《" + title + "》" : "") + "的核心贡献与创新点"; this.$nextTick(() => this.askQA()); },
    toggleQaScope(id) { this.qaScope.includes(id) ? (this.qaScope = this.qaScope.filter(x => x !== id)) : this.qaScope.push(id); },
    askPreset(q) { this.qaQuery = q; this.askQA(); },
    async askQA() {
      this.qaLoading = true; this.qaAnswer = ""; this.qaStreamText = ""; this.qaSources = []; this.qaConfidence = "";
      const scope = this.qaScope.length ? this.qaScope : this.papers.map(p => p.id);
      const body = { query: this.qaQuery, paper_ids: scope, top_k: 6 };
      try {
        const resp = await fetch("/api/qa/stream", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
        while (true) {
          const { done, value } = await reader.read(); if (done) break;
          buf += dec.decode(value, { stream: true });
          const parts = buf.split("\n\n"); buf = parts.pop();
          for (const p of parts) {
            if (!p.startsWith("data:")) continue;
            const data = p.slice(5).trim(); if (data === "[DONE]") continue;
            try { const j = JSON.parse(data); if (j.delta) this.qaStreamText += j.delta; if (j.sources) this.qaSources = j.sources; if (j.confidence) this.qaConfidence = j.confidence; } catch {}
          }
        }
      } catch {
        const r = await this.api("/qa", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        this.qaAnswer = r.answer || "出错"; this.qaSources = r.sources || []; this.qaConfidence = r.confidence || "";
      }
      this.qaLoading = false;
    },
    async loadRead() { if (!this.readPaper) return; this.readPage = 1; this.readJump = 1; await this.fetchRead(); },
    gotoReadPaper(id) { this.readPaper = id; this.loadRead(); },
    changeFont(d) { this.fontSize = Math.min(22, Math.max(12, this.fontSize + d)); },
    jumpToPage() { if (this.readData) this.gotoPage(this.readJump); },
    async fetchRead() {
      const r = await this.api(`/papers/${this.readPaper}/read?page=${this.readPage}&size=1`);
      if (!r.ok) return;
      this.readData = r; this.readCurrent = (r.pages[0] && r.pages[0].text) || "（无文本，可能为扫描页）";
    },
    prevPage() { if (this.readPage > 1) { this.readPage--; this.fetchRead(); this.readTranslated = ""; } },
    nextPage() { if (this.readPage < this.readData.total_pages) { this.readPage++; this.fetchRead(); this.readTranslated = ""; } },
    gotoPage(pg) { if (this.readData && pg >= 1 && pg <= this.readData.total_pages) { this.readPage = pg; this.fetchRead(); this.readTranslated = ""; } },
    gotoToc(h) { this.gotoPage(h.real_page || h.page); },
    async translatePage() {
      this.translating = true;
      const r = await this.api("/translate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: this.readCurrent.slice(0, 4000) }) });
      this.translating = false;
      if (r.ok) { this.readTranslated = r.translated; this.mode = "dual"; }
    },
    async doSearch() { const r = await this.api("/search/arxiv?q=" + encodeURIComponent(this.searchQuery) + "&max_results=8"); this.searchResults = r.items || []; },
    async loadGraph() { const r = await this.api("/graph"); this.graph = r; this.$nextTick(() => this.renderGraph()); },
    renderGraph() {
      if (!this.graph.nodes.length || !this.$refs.graphEl) return;
      if (this._graphChart) { this._graphChart.dispose(); }
      const chart = window.echarts.init(this.$refs.graphEl);
      const nodes = this.graph.nodes.map(n => ({ id: n.id, name: n.title.slice(0, 24), symbolSize: 22 }));
      const links = this.graph.links.map(l => ({ source: l.source, target: l.target }));
      chart.setOption({
        tooltip: { formatter: p => p.dataType === "node" ? (this.graph.nodes.find(x => x.id === p.data.id) || {}).title || p.data.name : "" },
        series: [{ type: "graph", layout: "force", roam: true, draggable: true, data: nodes, links,
          label: { show: true, fontSize: 10 }, force: { repulsion: 320, edgeLength: 90 },
          lineStyle: { color: "#99a", curveness: 0.2 }, emphasis: { focus: "adjacency" } }]
      });
      this._graphChart = chart;
    },
    async genSummary() {
      const r = await this.api("/graph/summary", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope: this.papers.map(p => p.id) }) });
      this.summaryText = r.summary || r.msg; this.futureText = r.future || "";
    },
    async genFramework() {
      if (!this.idea.trim() || this.frameworkLoading) return;
      this.frameworkLoading = true; this.framework = "";
      try {
        const r = await this.api("/writing/framework", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ idea: this.idea.trim() }) });
        this.framework = r.framework || r.msg || "生成失败，请重试";
      } catch (e) { this.framework = "请求出错：" + e; }
      this.frameworkLoading = false;
    },
    async genTopology() {
      const fd = new FormData(); fd.append("kind", this.topoKind); fd.append("prompt", this.topoPrompt);
      const r = await this.api("/writing/topology", { method: "POST", body: fd });
      this.topologyScript = r.script || r.msg;
    },
    async uploadViz(e) {
      const f = e.target.files[0]; if (!f) return;
      const fd = new FormData(); fd.append("file", f); fd.append("kind", this.vizKind);
      const r = await this.api("/viz/csv", { method: "POST", body: fd });
      this.vizResult = r.ok ? r : {}; this.vizError = r.msg || ""; e.target.value = "";
    },
    async doTranslate() {
      this.translating = true;
      const r = await this.api("/translate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: this.transText }) });
      this.translating = false; this.translated = r.translated || r.msg;
    },
    async agentSend() {
      const q = (this.agentInput || "").trim(); if (!q || this.agentBusy) return;
      this.agentMsgs.push({ role: "user", text: q });
      this.agentInput = ""; this.agentBusy = true; this.scrollChat();
      try {
        const r = await this.api("/agent/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: q, session_id: this.agentSession }) });
        const tool = (r.plan && r.plan[0] && r.plan[0].tool) || "";
        const res = r.result || {};
        const text = res.answer || res.note || res.msg || (res.title ? "已定位相关论文，请前往对应模块查看。" : "已理解你的需求，请前往对应模块使用。");
        const steps = (r.steps || []).map(s => ({ action: s.action, tool: s.tool }));
        this.agentMsgs.push({ role: "assistant", text, toolLabel: this.toolLabel(tool), jump: this.toolToView[tool] || "", steps });
      } catch (e) {
        this.agentMsgs.push({ role: "assistant", text: "服务暂不可用：" + e });
      }
      this.agentBusy = false; this.scrollChat();
    },
    toolLabel(t) {
      const map = { rag_qa: "知识问答", dedup: "文献去重", read_translate: "双语阅读", arxiv_search: "论文检索", graph_review: "引用图谱", writing_copilot: "写作Copilot", general: "通用" };
      return map[t] || "";
    },
    scrollChat() { this.$nextTick(() => { const el = this.$refs.chatBody; if (el) el.scrollTop = el.scrollHeight; }); },
    fmtText(t) {
      if (!t) return "";
      return t.split(/\n+/).map(s => s.replace(/\s+/g, " ").trim()).filter(Boolean).join("\n\n");
    },
    onPetDown(e) {
      if (this.petOpen && e.target.closest(".pet-card")) return;
      this.petDrag = { sx: e.clientX, sy: e.clientY, ox: this.petX, oy: this.petY, moved: false };
      this._petMove = (ev) => this.onPetMove(ev);
      this._petUp = () => this.onPetUp();
      window.addEventListener("mousemove", this._petMove);
      window.addEventListener("mouseup", this._petUp);
      e.preventDefault();
    },
    onPetMove(ev) {
      if (!this.petDrag) return;
      const dx = ev.clientX - this.petDrag.sx, dy = ev.clientY - this.petDrag.sy;
      if (!this.petDrag.moved && Math.hypot(dx, dy) > 6) this.petDrag.moved = true;
      this.petX = Math.max(6, Math.min(window.innerWidth - 96, this.petDrag.ox + dx));
      this.petY = Math.max(6, Math.min(window.innerHeight - 92, this.petDrag.oy + dy));
    },
    onPetUp() {
      const d = this.petDrag;
      this.petDrag = null;
      if (this._petMove) window.removeEventListener("mousemove", this._petMove);
      if (this._petUp) window.removeEventListener("mouseup", this._petUp);
      if (d && !d.moved) this.petOpen = !this.petOpen;  // 没拖动＝点击，切换开合
    },
    scrollPet() { this.$nextTick(() => { const el = this.$refs.petBody; if (el) el.scrollTop = el.scrollHeight; }); },
    petSend(q) {
      const text = (q || this.petInput).trim();
      if (!text || this.petBusy) return;
      this.petInput = "";
      this.petMsgs.push({ role: "user", text });
      this.scrollPet();
      const local = this.petLocal(text);
      if (local) {
        setTimeout(() => {
          this.petMsgs.push({ role: "assistant", text: local.text });
          if (local.jump) {
            this.view = local.jump;
            this.petMsgs.push({ role: "assistant", text: "已带你到「" + local.jumpName + "」模块 →" });
          }
          this.scrollPet();
        }, 300);
        return;
      }
      this.petBusy = true;
      // 学术问题走 RAG 问答（基于已入库论文），带溯源
      const paperIds = this.papers.length ? this.papers.map(p => p.id) : [];
      if (!paperIds.length) {
        this.petMsgs.push({ role: "assistant", text: "还没有已入库的论文哦～先去文献库上传一篇 PDF 吧，我就能基于论文内容回答你了。" });
        this.petBusy = false; this.scrollPet();
        return;
      }
      this.api("/qa", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, paper_ids: paperIds, top_k: 6 }) })
        .then(r => {
          const ans = r.answer || "抱歉，我在已入库论文里没找到相关内容。";
          let out = ans;
          if (r.sources && r.sources.length) {
            const cites = r.sources.slice(0, 3).map(s => `[p.${s.page}]`).join(" ");
            out += "\n\n📚 引用来源：" + cites;
          }
          if (r.confidence) out += "\n置信度：" + r.confidence;
          this.petMsgs.push({ role: "assistant", text: out });
        })
        .catch(() => this.petMsgs.push({ role: "assistant", text: "回答时出错了，稍后再试～" }))
        .finally(() => { this.petBusy = false; this.scrollPet(); });
    },
    petLocal(t) {
      const q = t.toLowerCase();
      if (/(你好|hi|hello|嗨|在吗|早上好|下午好|晚上好)/.test(q))
        return { text: "你好呀！我是科研助手桌宠 🎓\n我现在能基于你已入库的论文回答问题——试试问：这篇论文讲了什么/主要创新点/实验结论/局限性？" };
      if (/(你会|能做什么|功能|干什么|介绍一下|who are)/.test(q))
        return { text: "我能：\n📚 基于已入库论文回答问题（带引用页码）\n📖 帮你跳转到双语阅读/翻译\n🔍 跳转到论文检索\n🕸 跳转到引用图谱\n✍️ 跳转到写作Copilot\n\n点下方快捷按钮试试，或直接问我论文相关问题～" };
      if (/(几点|现在.*时|几点钟|时间)/.test(q))
        return { text: "现在是 " + new Date().toLocaleTimeString("zh-CN", { hour12: false }) };
      if (/(星期|周几|日期|今天.*号)/.test(q))
        return { text: "今天是 " + new Date().toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" }) };
      if (/(谢谢|感谢|thank)/.test(q))
        return { text: "不客气，随时找我 😊" };
      if (/(解析|上传|入库|导入|文献库)/.test(q))
        return { text: "好的，带你去文献库上传/解析 PDF~", jump: "library", jumpName: "文献库" };
      if (/(图谱|引用关系|基石|综述)/.test(q))
        return { text: "带你去引用图谱模块~", jump: "graph", jumpName: "引用图谱" };
      if (/(问答|提问|知识问答)/.test(q))
        return { text: "带你去知识问答模块~", jump: "qa", jumpName: "智能问答" };
      if (/(检索|搜索|找.*论文|查.*论文)/.test(q))
        return { text: "带你去论文检索模块~", jump: "search", jumpName: "论文检索" };
      if (/(阅读|翻译|对照)/.test(q))
        return { text: "带你去双语阅读模块~", jump: "read", jumpName: "双语阅读" };
      if (/(写作|框架|写.*综述|写.*论文|拓扑|可视化|图表|CSV)/.test(q))
        return { text: "带你去写作Copilot模块~", jump: "write", jumpName: "写作Copilot" };
      return null;  // 其余交给后端大模型
    }
  },
  mounted() {
    this.agentSession = "s" + Date.now().toString(36);
    this.petX = window.innerWidth - 96;
    this.petY = window.innerHeight - 250;
    this.petMsgs.push({ role: "assistant", text: "你好呀 🎓 我是科研助手桌宠～\n我能基于你已入库的论文回答问题，试试点下面快捷按钮，或直接问我：这篇论文讲了什么？" });
    this.loadPapers();
    const tick = () => { const d = new Date(); this.nowTime = d.toTimeString().slice(0, 8); };
    tick(); this._timer = setInterval(tick, 1000);
  }
};
</script>

<style>
:root {
  --c1: #4a5bd8; --c2: #7a4bd8; --c3: #3aa7d8;
  --bg: #f0f2fb; --card: #ffffff; --line: #e6eaf6;
  --txt: #223; --sub: #7a809c;
  --shadow: 0 8px 24px rgba(50,70,160,.08);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body, #app { height: 100%; }
body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background: var(--bg); color: var(--txt); }
.app { display: flex; height: 100vh; }

/* ===== 侧边栏 ===== */
.sidebar { width: 252px; flex-shrink: 0; background: linear-gradient(180deg,#f3f5fd,#e9ecfa 70%,#efe9fb); color: #3a3f55; padding: 22px 14px; display: flex; flex-direction: column; gap: 22px; overflow-y: auto; }
.brand { display: flex; align-items: center; gap: 13px; padding: 4px 6px 14px; border-bottom: 1px solid #dfe3f4; }
.logo { width: 40px; height: 40px; flex-shrink: 0; filter: drop-shadow(0 2px 6px rgba(74,91,216,.28)); }
.logo path { fill: var(--c1); }
.brand-name { font-size: 19px; font-weight: 800; letter-spacing: 1.5px; background: linear-gradient(90deg,#3a4a9a,#6a4bd8); -webkit-background-clip: text; background-clip: text; color: transparent; }
.brand-sub { font-size: 11px; color: #7a84ad; margin-top: 3px; letter-spacing: .5px; }
.side-block { }
.side-title { font-size: 11px; font-weight: 600; color: #8a94b8; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; padding: 0 8px; }
.nav-item { display: flex; align-items: center; gap: 10px; width: 100%; padding: 11px 12px; margin-bottom: 4px; border: none; border-radius: 11px; background: transparent; color: #3c4156; font-size: 14px; cursor: pointer; text-align: left; transition: .18s; position: relative; }
.nav-item:hover { background: rgba(74,91,216,.08); }
.nav-item.active { background: linear-gradient(120deg,var(--c1),var(--c2)); color: #fff; font-weight: 600; box-shadow: 0 4px 12px rgba(74,91,216,.35); }
.ni-name { flex: 1; }
.ni-hint { font-size: 10px; color: #8a94b8; }
.nav-item.active .ni-hint { color: #e3e7ff; }
.side-foot { margin-top: auto; font-size: 11px; color: #9aa3c4; text-align: center; line-height: 1.8; padding-top: 12px; border-top: 1px solid #dfe3f4; }

/* ===== 主区域 ===== */
.main { flex: 1; overflow-y: auto; padding: 24px 30px; background: radial-gradient(1200px 400px at 20% -5%, #e7ecff 0%, transparent 60%), var(--bg); }
.panel { max-width: 1280px; margin: 0 auto; background: var(--card); border-radius: 18px; padding: 26px; box-shadow: var(--shadow); border: 1px solid var(--line); }
.panel-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; flex-wrap: wrap; gap: 12px 16px; }
.panel-head h2 { font-size: 19px; color: #24305c; display: flex; align-items: center; gap: 8px; }
.m-ico { font-size: 17px; width: 36px; height: 36px; border-radius: 11px; display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(60,80,180,.12); flex-shrink: 0; }
.ni-ico { font-size: 15px; width: 30px; height: 30px; border-radius: 9px; display: inline-flex; align-items: center; justify-content: center; background: rgba(74,91,216,.10); flex-shrink: 0; transition: .18s; }
.nav-item.active .ni-ico { background: rgba(255,255,255,.28); box-shadow: 0 2px 8px rgba(0,0,0,.16); }
.head-right { display: flex; align-items: center; gap: 20px; }
.info { color: #7a809c; font-size: 13px; background: #f1f3fa; border: 1px solid #e6eaf6; border-radius: 20px; padding: 6px 14px; white-space: nowrap; }

/* 控制台 */
.home-panel { padding: 28px; }
.panel-banner { background: linear-gradient(120deg,#eef1ff,#f6f0ff); border: 1px solid var(--line); border-radius: 16px; padding: 32px 36px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; margin-bottom: 24px; }
.banner-title { font-size: 38px; font-weight: 800; line-height: 1.2; padding: 8px 0; background: linear-gradient(90deg,var(--c1),var(--c2)); -webkit-background-clip: text; background-clip: text; color: transparent; letter-spacing: 1px; }
.banner-sub { color: var(--sub); font-size: 15px; margin-top: 12px; }
.banner-pills { display: flex; gap: 10px; flex-wrap: wrap; }
.pill { background: #fff; border: 1px solid var(--line); border-radius: 20px; padding: 6px 14px; font-size: 12px; color: #445; box-shadow: 0 2px 6px rgba(50,70,160,.05); }

.cards-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 26px; }
.cap-card { display: flex; gap: 14px; align-items: flex-start; background: #fbfcff; border: 1px solid var(--line); border-radius: 15px; padding: 20px; cursor: pointer; transition: .2s; }
.cap-card:hover { border-color: var(--c1); box-shadow: 0 10px 24px rgba(74,91,216,.14); transform: translateY(-3px); }
.cap-ico { font-size: 26px; background: linear-gradient(135deg,#eef1ff,#f3edff); border-radius: 12px; width: 52px; height: 52px; display: flex; align-items: center; justify-content: center; }
.cap-title { font-size: 16px; font-weight: 700; color: #2a3568; margin-bottom: 6px; }
.cap-sub { font-size: 12px; color: var(--sub); line-height: 1.5; }

.section-label { font-size: 14px; font-weight: 700; color: #44506e; margin-bottom: 12px; }
.func-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 26px; }
.func-btn { display: flex; align-items: center; justify-content: flex-start; gap: 8px; width: 100%; padding: 13px 22px; border-radius: 12px; font-size: 14px; border: 1px solid #d4ddff; background: linear-gradient(135deg,#f2f5ff,#eef3ff); color: #3a4a9a; cursor: pointer; transition: .2s; box-shadow: 0 2px 6px rgba(74,91,216,.06); }
.func-btn:hover { background: linear-gradient(135deg,var(--c1),var(--c2)); color: #fff; border-color: transparent; transform: translateY(-1px); }
.func-btn.active { background: linear-gradient(135deg,var(--c1),var(--c2)); color: #fff; border-color: transparent; box-shadow: 0 6px 16px rgba(74,91,216,.25); }
.fb-ico { font-size: 15px; }
.home-result { margin: 4px 0 26px; border: 1px solid var(--line); border-radius: 14px; padding: 18px 22px; background: linear-gradient(160deg,#ffffff,#f8f9ff); }
.hr-head { font-size: 14px; font-weight: 800; color: var(--c1); margin-bottom: 10px; display: flex; align-items: center; gap: 10px; }
.hr-loading { font-size: 12px; font-weight: 500; color: #a78bfa; animation: pulse 1.2s infinite; }
.hr-body { font-size: 13.5px; color: #3a4678; line-height: 1.75; }
.hr-loading-body { color: #9aa3c4; }
.paper-picker { margin-left: 12px; padding: 5px 10px; border-radius: 8px; border: 1px solid #d4ddff; background: #fff; font-size: 12px; color: #3a4a9a; max-width: 280px; cursor: pointer; }
.paper-picker:focus { outline: none; border-color: var(--c1); }

/* 对话窗口 */
.chat-card { background: #fff; border: 1px solid var(--line); border-radius: 16px; overflow: hidden; box-shadow: var(--shadow); }
.chat-head { display: flex; justify-content: space-between; align-items: center; padding: 18px 22px; border-bottom: 1px solid var(--line); background: linear-gradient(120deg,#f4f6ff,#faf4ff); }
.chat-title { font-size: 17px; font-weight: 700; color: #2a3568; }
.chat-sub { font-size: 12.5px; color: var(--sub); margin-top: 5px; line-height: 1.6; }
.chat-time { color: #9aa0b5; font-size: 12px; font-variant-numeric: tabular-nums; }
.chat-presets { padding: 12px 22px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; border-bottom: 1px dashed var(--line); background: #fcfdff; }
.cp-label { font-size: 12px; color: var(--sub); }
.cp-btn { padding: 5px 14px; border-radius: 16px; border: 1px solid #d4ddff; background: #fff; color: #3a4a9a; font-size: 12px; cursor: pointer; }
.cp-btn:hover { background: #eef1ff; }
.chat-body { max-height: 320px; overflow-y: auto; padding: 18px 22px; display: flex; flex-direction: column; gap: 12px; }
.msg { max-width: 82%; }
.msg.user { align-self: flex-end; }
.msg.assistant { align-self: flex-start; }
.bubble { padding: 12px 15px; border-radius: 14px; font-size: 14px; line-height: 1.7; white-space: pre-wrap; }
.msg.user .bubble { background: linear-gradient(120deg,var(--c1),var(--c2)); color: #fff; border-bottom-right-radius: 4px; box-shadow: 0 4px 10px rgba(74,91,216,.25); }
.msg.assistant .bubble { background: #f1f3fa; color: #333; border-bottom-left-radius: 4px; }
.tool-tag { display: inline-block; background: linear-gradient(120deg,#e8eefc,#efe9fb); color: var(--c1); font-size: 11px; padding: 2px 9px; border-radius: 20px; margin-right: 8px; vertical-align: 1px; }
.jump-btn { margin-top: 6px; padding: 6px 14px; border: 1px solid #d4ddff; background: #fff; color: var(--c1); border-radius: 9px; font-size: 12px; cursor: pointer; }
.jump-btn:hover { background: #eef1ff; }
.chat-input { display: flex; gap: 12px; padding: 16px 22px; border-top: 1px solid var(--line); }
.chat-input input { flex: 1; padding: 12px 15px; border: 1px solid #ccd3e6; border-radius: 11px; font-size: 14px; font-family: inherit; }
.chat-input input:focus { outline: none; border-color: var(--c1); box-shadow: 0 0 0 3px rgba(74,91,216,.12); }

/* 通用按钮 */
.btn { padding: 8px 16px; border-radius: 10px; border: 1px solid #ccd3e6; background: #fff; color: #334; font-size: 14px; cursor: pointer; transition: .2s; }
.btn:hover { border-color: var(--c1); color: var(--c1); }
.btn.primary { background: linear-gradient(120deg,var(--c1),var(--c2)); border: none; color: #fff; box-shadow: 0 4px 12px rgba(74,91,216,.28); }
.btn.primary:hover { opacity: .92; color: #fff; }
.btn.primary:disabled { opacity: .5; cursor: not-allowed; box-shadow: none; }
.btn.danger { color: #d44; border-color: #f3c6c6; }
.btn.small { padding: 5px 12px; font-size: 13px; }
.btn.active { background: linear-gradient(120deg,var(--c1),var(--c2)); color: #fff; border-color: transparent; }

/* 小部件：统计 */
.mini-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 18px; }
.mini-stat { background: linear-gradient(135deg,#f7f9ff,#f2f5ff); border: 1px solid var(--line); border-radius: 13px; padding: 16px; text-align: center; }
.ms-num { font-size: 26px; font-weight: 800; color: var(--c1); }
.ms-label { font-size: 12px; color: var(--sub); margin-top: 4px; }

/* 小部件：widget 快捷 */
.widget { background: #fbfcff; border: 1px solid var(--line); border-radius: 13px; padding: 14px 16px; margin-bottom: 16px; }
.widget-title { font-size: 13px; font-weight: 700; color: #44506e; margin-bottom: 10px; }
.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { padding: 6px 14px; border-radius: 16px; border: 1px solid #d4ddff; background: #fff; color: #3a4a9a; font-size: 12.5px; cursor: pointer; transition: .15s; }
.chip:hover { background: linear-gradient(120deg,var(--c1),var(--c2)); color: #fff; border-color: transparent; }

/* 文献库 */
.drop-tip { border: 2px dashed #c8d2f5; border-radius: 12px; padding: 18px; text-align: center; color: #7a86b8; font-size: 13px; background: #f8faff; margin-bottom: 18px; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px,1fr)); gap: 14px; }
.paper-card { border: 1px solid var(--line); border-radius: 13px; padding: 15px; background: #fbfcff; transition: .2s; }
.paper-card:hover { border-color: #b8c6f5; box-shadow: 0 6px 16px rgba(50,70,160,.07); }
.pc-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.pc-title { font-weight: 600; flex: 1; color: #2a3568; line-height: 1.4; font-size: 14px; }
.pc-meta { display: flex; gap: 10px; font-size: 12px; color: var(--sub); align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.pc-actions { display: flex; gap: 8px; }
.badge { background: #e8eefc; color: var(--c1); font-size: 11px; padding: 2px 9px; border-radius: 20px; }
.badge.ocr { background: #fdeef0; color: #d44; }
.abs { font-size: 12px; color: #6a7089; margin: 8px 0; line-height: 1.5; }
.row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.reason { font-size: 12px; color: #b16b1f; margin-top: 8px; background: #fff6ea; padding: 6px 10px; border-radius: 8px; }
.empty { text-align: center; color: #a7adc4; padding: 50px 0; }
.notice { background: #fff7e6; border: 1px solid #f3d9a4; color: #a05a12; padding: 12px 16px; border-radius: 10px; margin-bottom: 16px; }

/* 解析 */
.parse-box { margin-top: 22px; border-top: 1px solid var(--line); padding-top: 18px; }
.parse-head { display: flex; justify-content: space-between; align-items: center; }
.parse-box h4 { color: #3a4a7a; margin: 16px 0 8px; font-size: 15px; }
.pmeta { background: #f6f8ff; padding: 12px; border-radius: 10px; font-size: 13px; line-height: 1.9; }
.ptabs { display: flex; gap: 8px; margin: 14px 0; }
.tree { list-style: none; }
.tree li { padding: 4px 0; font-size: 13px; color: #334; }
.tree li.lv1 { font-weight: 700; font-size: 14px; }
.tree li.lv2 { padding-left: 22px; }
.tree .lv-tag { background: #eef; font-size: 11px; padding: 1px 6px; border-radius: 4px; margin-right: 6px; color: #6a6fd0; }
.tree em { color: #aab; font-style: normal; font-size: 11px; }
.formula { background: #1e1e2e; color: #e6edf3; padding: 12px; border-radius: 10px; font-size: 12px; white-space: pre-wrap; }
.tbl { border-collapse: collapse; width: 100%; font-size: 12px; margin: 4px 0 10px; }
.tbl td { border: 1px solid #ddd; padding: 4px 8px; }
.tbl-caption { color: var(--sub); font-size: 12px; }
.refs { font-size: 12px; color: #445; padding-left: 20px; line-height: 1.8; }

/* 问答 */
.qa-scope { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 14px; font-size: 13px; color: #667; }
.qa-input { display: flex; gap: 12px; align-items: flex-end; margin-bottom: 14px; }
.qa-input textarea, .qa-input .txt { flex: 1; padding: 12px; border: 1px solid #ccd3e6; border-radius: 10px; font-size: 14px; resize: vertical; font-family: inherit; }
.qa-input textarea:focus, .qa-input .txt:focus { outline: none; border-color: var(--c1); }
.chat .bubble { background: #f3f6ff; border-left: 4px solid var(--c1); padding: 16px; border-radius: 10px; white-space: pre-wrap; line-height: 1.8; font-size: 14px; position: relative; }
.bubble-tools { position: absolute; top: 8px; right: 10px; }
.copy-btn { border: 1px solid #ccd3e6; background: #fff; border-radius: 7px; font-size: 11px; padding: 3px 9px; color: #667; cursor: pointer; }
.copy-btn:hover { color: var(--c1); border-color: var(--c1); }
.copy-btn.inline { position: static; margin-left: 8px; }
.sources { margin-top: 14px; }
.src-title { font-size: 14px; font-weight: 700; color: #3a4a7a; margin-bottom: 8px; }
.src { background: #fafbff; border: 1px solid var(--line); border-radius: 9px; padding: 10px; margin-bottom: 8px; font-size: 13px; }
.src-snip { display: block; color: #778; margin-top: 4px; }

/* 阅读 */
.paper-pick { display: flex; align-items: center; gap: 8px; background: #f1f3fa; border: 1px solid #e6eaf6; border-radius: 10px; padding: 5px 8px; }
.pick-ico { font-size: 15px; }
.paper-pick .sel { border: none; background: transparent; padding: 4px 6px; font-size: 14px; cursor: pointer; }
.paper-pick .sel:focus { outline: none; }

.read-welcome { }
.rw-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px; }
.rw-features { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }
.rwf-card { background: linear-gradient(135deg,#f4f8ff,#eef3ff); border: 1px solid var(--line); border-radius: 13px; padding: 18px 16px; text-align: center; }
.rwf-ico { font-size: 26px; }
.rwf-t { font-size: 14px; font-weight: 700; color: #2a3568; margin: 8px 0 4px; }
.rwf-s { font-size: 11.5px; color: var(--sub); line-height: 1.5; }
.rw-list-title { font-size: 14px; font-weight: 700; color: #44506e; margin-bottom: 12px; }
.rw-list { display: flex; flex-direction: column; gap: 10px; }
.rw-item { display: flex; align-items: center; gap: 14px; background: #fbfcff; border: 1px solid var(--line); border-radius: 12px; padding: 13px 16px; cursor: pointer; transition: .18s; flex-wrap: wrap; }
.rw-item:hover { border-color: #b8c6f5; box-shadow: 0 6px 16px rgba(50,70,160,.08); transform: translateY(-1px); }
.rw-file { font-family: Consolas,monospace; font-size: 12px; color: #7a84ad; background: #eef1fb; padding: 3px 9px; border-radius: 7px; }
.rw-name { flex: 1; font-size: 14px; font-weight: 600; color: #2a3568; min-width: 180px; }
.rw-meta { font-size: 12px; color: var(--sub); }
.rw-go { font-size: 13px; color: var(--c1); font-weight: 600; }

.paper-info-bar { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; background: linear-gradient(120deg,#f4f7ff,#f2f4ff); border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px; margin-bottom: 14px; }
.pi-title { font-size: 15px; font-weight: 700; color: #2a3568; }
.pi-meta { font-size: 12px; color: var(--sub); margin-top: 4px; }
.pi-tools { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
.font-ctl, .jump-ctl { display: flex; align-items: center; gap: 6px; }
.font-val { font-size: 12px; color: var(--sub); min-width: 38px; text-align: center; }
.jump-in { width: 64px; padding: 6px 8px; border: 1px solid #ccd3e6; border-radius: 8px; font-size: 13px; }
.jump-in:focus { outline: none; border-color: var(--c1); }

.progress-wrap { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.progress-bar { flex: 1; height: 8px; background: #e7ebf7; border-radius: 6px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg,var(--c1),var(--c3)); border-radius: 6px; transition: width .3s; }
.progress-txt { font-size: 12px; color: var(--sub); white-space: nowrap; }
.read-layout { display: grid; grid-template-columns: 220px 1fr; gap: 16px; }
.read-toc { border: 1px solid var(--line); border-radius: 14px; padding: 14px; background: linear-gradient(160deg,#ffffff,#f8f9ff); max-height: 70vh; overflow-y: auto; text-align: left; }
.toc-title { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 800; color: var(--c1); margin-bottom: 10px; padding-bottom: 10px; border-bottom: 2px solid #eef1fb; letter-spacing: 1px; }
.toc-title::after { content: ""; flex: 1; height: 2px; border-radius: 2px; background: linear-gradient(90deg,#eef1fb,#ffffff); }
.toc-item { display: flex; align-items: center; gap: 8px; text-align: left; font-size: 12.5px; padding: 5px 10px; margin: 1px 0; border-radius: 8px; cursor: pointer; color: #4a5a8a; line-height: 1.5; transition: all .15s ease; position: relative; }
.toc-idx { flex-shrink: 0; width: 18px; height: 18px; border-radius: 6px; background: #eef1fb; color: var(--c1); font-size: 10.5px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.toc-t { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.toc-p { flex-shrink: 0; font-size: 10.5px; color: #9aa3c4; font-weight: 500; }
.toc-item.cur .toc-idx { background: linear-gradient(135deg,var(--c1),var(--c2)); color: #fff; }
.toc-item.cur .toc-p { color: var(--c1); }
.tlv1 { font-weight: 650; color: #2f3b66; margin-top: 8px; }
.tlv2 { margin-left: 16px; font-weight: 500; color: #4a5a8a; }
.tlv3 { margin-left: 28px; font-size: 12px; color: #6a76a2; }
.toc-item:hover { background: #eef1ff; transform: translateX(2px); }
.toc-item.cur { background: linear-gradient(120deg,#e8eefc,#f0eafc); color: var(--c1); font-weight: 700; }
.toc-item.cur::before { content: ""; position: absolute; left: 0; top: 6px; bottom: 6px; width: 3px; border-radius: 3px; background: linear-gradient(180deg,var(--c1),var(--c2)); }
.toc-empty { font-size: 12px; color: #a7adc4; padding: 12px 0; text-align: center; }
.tlv1 { font-weight: 700; }
.tlv2 { padding-left: 16px; }
.tlv3 { padding-left: 28px; }
.read-toolbar { display: flex; align-items: center; gap: 12px; margin: 12px 0; color: #667; font-size: 13px; flex-wrap: wrap; }
.mode-toggle { margin-left: auto; display: flex; gap: 6px; }
.dual { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.col { background: #fafbff; border: 1px solid var(--line); border-radius: 11px; overflow: hidden; }
.col-label { background: linear-gradient(120deg,#eef1fb,#efeafb); padding: 8px 12px; font-size: 12px; color: var(--c1); font-weight: 600; letter-spacing: 1px; }
.col-body { padding: 16px 18px; font-size: 13px; line-height: 2; white-space: pre-wrap; max-height: 60vh; overflow: auto; }
.paper-text { font-family: Georgia, "Times New Roman", "Songti SC", "SimSun", serif; color: #2b2b3a; }
.paper-text .translate-inline { font-family: inherit; }
.single-body .col-body { max-height: 70vh; }
.translate-inline { display: inline-flex; align-items: center; gap: 4px; margin-top: 8px; padding: 7px 14px; }

/* 图谱 */
.graph-wrap { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }
.graph-box { height: 460px; border: 1px solid var(--line); border-radius: 12px; background: #fbfcff; }
.graph-side h4 { color: #3a4a7a; font-size: 14px; margin: 12px 0 6px; }
.graph-side li { font-size: 13px; padding: 4px 0; color: #445; }
.graph-side em { color: #a05a12; font-style: normal; font-size: 11px; }
.legend { font-size: 12px; color: var(--sub); line-height: 1.7; background: #f6f8ff; padding: 8px 10px; border-radius: 8px; }
.gen-box { margin-top: 18px; border-top: 1px solid var(--line); padding-top: 16px; }
.gen-box h4 { color: #3a4a7a; margin-bottom: 6px; }
.gen-box p { font-size: 14px; line-height: 1.8; }
.gen-box pre { background: #f6f8ff; padding: 14px; border-radius: 10px; white-space: pre-wrap; font-size: 13px; position: relative; }

/* 写作 */
.tabs2 { display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; }
.sub { display: flex; flex-direction: column; gap: 12px; }
.row2 { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.txt { padding: 12px; border: 1px solid #ccd3e6; border-radius: 10px; font-size: 14px; font-family: inherit; }
.txt:focus { outline: none; border-color: var(--c1); }
.txt.big { min-height: 90px; }
.out { background: #f6f8ff; padding: 16px; border-radius: 10px; white-space: pre-wrap; font-size: 13px; line-height: 1.7; position: relative; }
.out-wrap { position: relative; display: flex; flex-direction: column; gap: 8px; }
.out-wrap .copy-btn { align-self: flex-end; }
.sel { padding: 8px 12px; border-radius: 9px; border: 1px solid #ccd3e6; font-size: 14px; }
.viz-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.viz-img { width: 100%; border: 1px solid var(--line); border-radius: 10px; }
.viz-info { font-size: 12px; display: flex; flex-direction: column; gap: 10px; }
.viz-info .viz-table { border-collapse: collapse; width: 100%; }
.viz-info .viz-table td { border: 1px solid #ddd; padding: 4px 6px; }
.caption { font-size: 13px; line-height: 1.6; background: #f6f8ff; padding: 10px; border-radius: 8px; }

/* 模块增强小组件 */
.lib-steps { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; background: linear-gradient(135deg,#fdf9ef,#fbf3e3); border: 1px solid #f0e3c4; border-radius: 12px; padding: 12px 16px; margin-bottom: 18px; }
.lst-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #6a5b3c; font-weight: 600; }
.lst-n { width: 22px; height: 22px; border-radius: 50%; background: linear-gradient(120deg,var(--c1),var(--c2)); color: #fff; font-size: 12px; display: inline-flex; align-items: center; justify-content: center; }
.lst-arrow { color: #c9a45c; font-weight: 700; }

.qa-tips { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 14px; }
.qt { background: #fbfcff; border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; font-size: 12.5px; color: #5a5f7a; line-height: 1.6; }
.qt b { color: #2a3568; margin-right: 4px; }
.qt-ico { margin-right: 6px; }

.search-stat { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; background: #f4f8ff; border: 1px solid var(--line); border-radius: 10px; padding: 10px 16px; margin-bottom: 14px; font-size: 13px; color: #5a5f7a; }
.ss-item b { font-size: 18px; color: var(--c1); margin-right: 4px; }
.ss-bar { flex: 1; min-width: 120px; height: 8px; background: #e4e9f7; border-radius: 6px; overflow: hidden; }
.ss-bar span { display: block; height: 100%; background: linear-gradient(90deg,#3aa7d8,#4a5bd8); border-radius: 6px; }

.pr-block { background: #fbf4f8; border: 1px solid #f0d9e6; border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; }
.pr-block h4 { margin-top: 0 !important; color: #a34a7a; }
.pr-item { display: flex; align-items: center; gap: 8px; margin: 7px 0; font-size: 12px; }
.pr-name { width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #445; }
.pr-track { flex: 1; height: 7px; background: #f0e2ec; border-radius: 5px; overflow: hidden; }
.pr-fill { display: block; height: 100%; background: linear-gradient(90deg,#d86aa8,#7a4bd8); border-radius: 5px; }
.pr-val { color: #a34a7a; font-weight: 700; min-width: 34px; text-align: right; }

.write-hint { background: #f6f9ff; border: 1px dashed #bcd0f5; border-radius: 10px; padding: 10px 14px; font-size: 12.5px; color: #5a6a9a; line-height: 1.7; margin-bottom: 14px; }

/* 上传解析进度 */
.upload-progress { background: #fbfcff; border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px; margin-bottom: 16px; }
.up-title { font-size: 13px; font-weight: 700; color: #44506e; margin-bottom: 10px; }
.up-item { display: flex; align-items: center; gap: 12px; margin: 8px 0; font-size: 13px; }
.up-name { width: 180px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #445; }
.up-track { flex: 1; height: 8px; background: #e7ebf7; border-radius: 6px; overflow: hidden; }
.up-fill { display: block; height: 100%; background: linear-gradient(90deg,var(--c3),var(--c1)); border-radius: 6px; transition: width .3s; }
.up-fill.stdone { background: linear-gradient(90deg,#3aa75a,#2f9e44); }
.up-fill.sterror { background: linear-gradient(90deg,#e05a5a,#d44); }
.up-pct { min-width: 40px; text-align: right; font-variant-numeric: tabular-nums; color: #5a5f7a; }
.up-st { min-width: 62px; text-align: center; font-size: 12px; color: var(--c1); }
.up-st.done { color: #2f9e44; }
.up-st.error { color: #d44; }

/* 问答置信度 */
.qa-conf { font-size: 12.5px; color: #667; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
.conf { display: inline-block; padding: 1px 9px; border-radius: 12px; font-size: 11px; font-weight: 600; margin-left: 4px; vertical-align: 1px; }
.conf.chigh { background: #e6f7ec; color: #2f9e44; }
.conf.c中 { background: #fff3e0; color: #e8890c; }
.conf.clow { background: #fdeef0; color: #d44; }
.src-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

/* Agent 步骤条 */
.agent-steps { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; background: #f6f9ff; border: 1px solid #dfe7fb; border-radius: 9px; padding: 7px 11px; margin-bottom: 8px; }
.astp { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: #4a5a8a; }
.astp-n { width: 19px; height: 19px; border-radius: 50%; background: linear-gradient(120deg,var(--c1),var(--c2)); color: #fff; font-size: 11px; display: inline-flex; align-items: center; justify-content: center; }
.astp-arrow { color: #9aa3c4; font-weight: 700; }

/* 滚动条 */
.main::-webkit-scrollbar, .chat-body::-webkit-scrollbar, .read-toc::-webkit-scrollbar, .col-body::-webkit-scrollbar { width: 8px; }
.main::-webkit-scrollbar-thumb, .chat-body::-webkit-scrollbar-thumb, .read-toc::-webkit-scrollbar-thumb, .col-body::-webkit-scrollbar-thumb { background: #ccd3e6; border-radius: 6px; }

/* Agent 桌宠 */
.pet { position: fixed; z-index: 999; }
.pet-icon { width: 64px; height: 64px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: grab; user-select: none; transition: transform .15s; }
.pet-icon:hover { transform: scale(1.08); }
.pet-icon:active { cursor: grabbing; }
.pet-icon .pet-logo { width: 40px; height: 40px; color: var(--c1); filter: drop-shadow(0 3px 8px rgba(74,91,216,.32)); }
.pet-card { position: absolute; right: 0; bottom: 76px; width: 272px; background: #fff; border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 12px 32px rgba(50,70,160,.16); overflow: hidden; display: flex; flex-direction: column; }
.pet-head { display: flex; align-items: center; gap: 10px; padding: 12px 14px; background: linear-gradient(120deg,#eef1ff,#f6f0ff); }
.pet-avatar { width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.pet-avatar .pet-logo { width: 24px; height: 24px; color: var(--c1); }
.pet-name { font-weight: 700; color: #2a3568; font-size: 14px; }
.pet-sub { font-size: 11px; color: var(--sub); }
.pet-close { margin-left: auto; border: none; background: #fff; border-radius: 8px; width: 26px; height: 26px; cursor: pointer; color: #667; font-size: 16px; line-height: 1; }
.pet-close:hover { background: #eef1ff; }
.pet-body { height: 230px; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; background: #fafbff; }
.pet-msg { max-width: 92%; }
.pet-msg.user { align-self: flex-end; }
.pet-msg.assistant { align-self: flex-start; }
.pet-bubble { padding: 9px 11px; border-radius: 11px; font-size: 12.5px; line-height: 1.6; white-space: pre-wrap; }
.pet-msg.user .pet-bubble { background: linear-gradient(120deg,var(--c1),var(--c2)); color: #fff; border-bottom-right-radius: 3px; }
.pet-msg.assistant .pet-bubble { background: #eef1fb; color: #334; border-bottom-left-radius: 3px; }
.pet-typing { color: #7a86b8; font-style: italic; }
.pet-shortcuts { display: flex; flex-wrap: wrap; gap: 6px; padding: 10px 12px; border-top: 1px solid var(--line); background: #fcfdff; }
.pet-chip { border: 1px solid #d4ddff; background: #fff; color: #3a4a9a; font-size: 11px; padding: 4px 10px; border-radius: 13px; cursor: pointer; transition: .15s; }
.pet-chip:hover { background: linear-gradient(120deg,var(--c1),var(--c2)); color: #fff; border-color: transparent; }
.pet-input { display: flex; gap: 8px; padding: 10px 12px; border-top: 1px solid var(--line); }
.pet-input input { flex: 1; padding: 8px 11px; border: 1px solid #ccd3e6; border-radius: 9px; font-size: 12.5px; font-family: inherit; }
.pet-input input:focus { outline: none; border-color: var(--c1); box-shadow: 0 0 0 2px rgba(74,91,216,.12); }
.pet-send { border: none; background: linear-gradient(120deg,var(--c1),var(--c2)); color: #fff; border-radius: 9px; width: 38px; font-size: 15px; cursor: pointer; flex-shrink: 0; }
.pet-send:disabled { opacity: .5; cursor: not-allowed; }
.pet-body::-webkit-scrollbar { width: 6px; }
.pet-body::-webkit-scrollbar-thumb { background: #ccd3e6; border-radius: 4px; }

@media (max-width: 1000px) {
  .cards-row { grid-template-columns: repeat(2, 1fr); }
  .mini-stats { grid-template-columns: repeat(2, 1fr); }
  .dual, .graph-wrap, .read-layout { grid-template-columns: 1fr; }
  .read-toc { max-height: 160px; }
}
@media (max-width: 720px) {
  .app { flex-direction: column; }
  .sidebar { width: 100%; flex-direction: row; flex-wrap: wrap; gap: 6px; padding: 12px; }
  .side-block, .brand { border-bottom: none; }
  .side-title, .side-foot, .ni-hint { display: none; }
  .cards-row { grid-template-columns: 1fr; }
}
</style>
