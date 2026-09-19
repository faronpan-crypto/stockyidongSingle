const OPTS = ["太阳", "晴天", "阴天", "下雨", "大雨", "暴雨", "飓风"];

const STUB_FOOT =
  "依赖 Tkinter 弹窗、本机 OCR、同花顺数据窗口或与 stockyidong.py 深度耦合的线程/状态。请运行桌面版：stockyidong_project/src/stockyidong.py 获得完整能力。";

function el(id) {
  return document.getElementById(id);
}

async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("application/json")) return r.json();
  return r.text();
}

let prevThreeDim = null;
let holdingsState = null;
let currentGroup = "1";
let editCell = { group: "1", index: 0 };

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showStub(title, detail) {
  el("stubTitle").textContent = title || "说明";
  el("stubBody").textContent = (detail || "") + "\n\n" + STUB_FOOT;
  el("stubModal").classList.add("show");
}

function hideStub() {
  el("stubModal").classList.remove("show");
}

function showView(name) {
  document.querySelectorAll(".view-panel").forEach((p) => p.classList.remove("visible"));
  const panel = document.getElementById("view-" + name);
  if (panel) panel.classList.add("visible");
  document.querySelectorAll(".sidebar .nav-btn[data-view]").forEach((b) => {
    if (b.classList.contains("nav-hold-group")) return;
    b.classList.toggle("active", b.dataset.view === name);
  });
}

function initNav() {
  document.querySelectorAll(".sidebar .nav-btn[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const v = btn.dataset.view;
      showView(v);
      if (v === "holdings") renderHoldingsAll();
    });
  });
  document.querySelectorAll(".nav-stub").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const t = e.currentTarget.dataset.stub || e.currentTarget.textContent.trim();
      showStub(e.currentTarget.textContent.trim(), t);
    });
  });
  el("stubClose").addEventListener("click", hideStub);
  el("stubModal").addEventListener("click", (ev) => {
    if (ev.target === el("stubModal")) hideStub();
  });

  const gh = el("navHoldingsGroups");
  for (let i = 1; i <= 14; i++) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "nav-btn nav-sub nav-hold-group";
    b.dataset.group = String(i);
    b.textContent = `${i} · …`;
    b.addEventListener("click", () => {
      currentGroup = String(i);
      document.querySelectorAll(".nav-hold-group").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      showView("holdings");
      renderHoldingsAll();
    });
    gh.appendChild(b);
  }
}

function updateSidebarHoldingLabels() {
  if (!holdingsState) return;
  const titles = holdingsState.tab_titles || {};
  const gl = holdingsState.group_labels || {};
  document.querySelectorAll("#navHoldingsGroups .nav-btn").forEach((b, idx) => {
    const gid = String(idx + 1);
    const label = titles[gid] || gl[gid] || gid;
    b.textContent = `${gid} · ${label}`;
  });
  document.querySelectorAll(".nav-hold-group").forEach((b) => {
    b.classList.toggle("active", b.dataset.group === currentGroup);
  });
}

function initPosition() {
  ["emotion", "vJudge", "yesterday"].forEach((id) => {
    const s = el(id);
    s.innerHTML = OPTS.map((o) => `<option>${o}</option>`).join("");
  });
  el("emotion").value = "阴天";
  el("vJudge").value = "阴天";
  el("yesterday").value = "阴天";

  el("btnPosition").addEventListener("click", async () => {
    const body = {
      emotion: el("emotion").value,
      v_judge: el("vJudge").value,
      yesterday: el("yesterday").value,
      fundamental: Number(el("fundamental").value),
      technical: Number(el("technical").value),
      sentiment_dim: Number(el("sentimentDim").value),
      prev_three_dimension_total: prevThreeDim,
    };
    const r = await api("/api/position/compute", {
      method: "POST",
      body: JSON.stringify(body),
    });
    prevThreeDim = r.three_dimension_total;
    el("posPct").textContent = `+${r.position_percent}%`;
    const [rr, gg, bb] = r.indicator_rgb;
    el("posIndicator").style.background = `rgb(${rr},${gg},${bb})`;
    el("posHint").textContent = `三维总分 ${r.three_dimension_total} · ${r.t_trading_hint} · ${
      r.new_position_allowed ? "可探讨开新仓条件" : "禁止开新仓（阈值对齐桌面）"
    }`;
    el("tTradingRo").textContent = r.t_trading_hint;
  });

  el("btnKelly").addEventListener("click", async () => {
    const body = {
      odds_b: Number(el("kellyB").value),
      win_prob_p: Number(el("kellyP").value),
    };
    const r = await api("/api/kelly", { method: "POST", body: JSON.stringify(body) });
    el("kellyOut").textContent = `f=${r.kelly_ratio}（约 ${r.kelly_percent}%）`;
  });
}

const ALERT_KEYS = [
  ["amp", "振幅预警"],
  ["ma", "均线预警"],
  ["b1", "破1日预警"],
  ["b5", "破5日预警"],
  ["b20", "破20日预警"],
  ["sector", "板块情绪监测"],
  ["hmon", "Main持仓股监测"],
  ["hot15", "日K热门股监测"],
  ["auto", "自动化采集"],
];

function initAlertSwitches() {
  const box = el("alertSwitches");
  const saved = JSON.parse(localStorage.getItem("sy_web_alerts") || "{}");
  ALERT_KEYS.forEach(([k, label]) => {
    const id = `sw_${k}`;
    const wrap = document.createElement("label");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = id;
    cb.checked = !!saved[k];
    cb.addEventListener("change", () => {
      const o = JSON.parse(localStorage.getItem("sy_web_alerts") || "{}");
      o[k] = cb.checked;
      localStorage.setItem("sy_web_alerts", JSON.stringify(o));
    });
    wrap.appendChild(cb);
    wrap.appendChild(document.createTextNode(label));
    box.appendChild(wrap);
  });
}

function tabTitle(gid) {
  if (!holdingsState) return gid;
  const tt = holdingsState.tab_titles || {};
  if (tt[gid]) return tt[gid];
  const gl = holdingsState.group_labels || {};
  return gl[gid] || gid;
}

function renderHoldingSubTabs() {
  const box = el("holdingSubTabs");
  box.innerHTML = "";
  for (let i = 1; i <= 14; i++) {
    const gid = String(i);
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = `${gid} ${tabTitle(gid)}`;
    b.className = gid === currentGroup ? "active" : "";
    b.addEventListener("click", () => {
      currentGroup = gid;
      renderHoldingsAll();
    });
    box.appendChild(b);
  }
}

function renderHoldingToolbar() {
  const g = currentGroup;
  const gi = parseInt(g, 10);
  const frame = el("holdingToolbar");
  frame.innerHTML = "";

  const add = (text, stub) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "secondary nav-stub";
    b.textContent = text;
    b.dataset.stub = stub;
    b.addEventListener("click", () => showStub(text, stub));
    frame.appendChild(b);
  };

  add("打开管理界面", "_open_history_holdings_window");
  add("导入持仓", "_import_holdings");
  add("持仓股管理", "_manage_holdings");
  add("持仓检测", "_check_holdings");
  add("凯利设定", "_show_kelly_config");
  add("持仓计算", "_open_holding_calculator");
  add("5日最低点", "_calculate_5day_low_diff");

  if (gi === 6) add("爬取同花顺热榜", "_crawl_ths_hot_stocks");
  if (gi === 2) add("爬取选股通", "_crawl_xuangutong_leaders");
  if (gi === 3) add("爬取问财15Min", "_crawl_iwencai_15min_stocks");
  if (gi === 7) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "warn";
    b.textContent = "从资讯刷新";
    b.addEventListener("click", refreshHoldingsFromNews);
    frame.appendChild(b);
  }
}

function renderHoldingGrid() {
  const grid = el("holdingGrid");
  grid.innerHTML = "";
  const g = currentGroup;
  const cells = (holdingsState && holdingsState.groups && holdingsState.groups[g]) || [];
  for (let i = 0; i < 80; i++) {
    const d = document.createElement("div");
    d.className = "cell";
    const item = cells[i];
    if (item && (item.name || item.code)) {
      d.innerHTML =
        `<div class="c-name">${escapeHtml(item.name || "")}</div>` +
        `<div class="c-code">${escapeHtml(item.code || "")}</div>`;
    } else {
      d.innerHTML = `<span class="hint">#${i + 1}</span>`;
    }
    d.addEventListener("click", () => openCellDialog(g, i, item));
    grid.appendChild(d);
  }
}

function openCellDialog(group, index, item) {
  editCell = { group, index };
  el("cellIdx").textContent = `#${index + 1} · 组${group} · ${tabTitle(group)}`;
  el("cellName").value = item?.name || "";
  el("cellCode").value = item?.code || "";
  el("cellDialog").showModal();
}

async function loadHoldings() {
  holdingsState = await api("/api/holdings");
  updateSidebarHoldingLabels();
}

function renderHoldingsAll() {
  renderHoldingSubTabs();
  renderHoldingToolbar();
  renderHoldingGrid();
}

async function initHoldings() {
  el("cellCancel").addEventListener("click", () => el("cellDialog").close());

  async function saveCell(clear) {
    if (clear) {
      await api("/api/holdings/cell", {
        method: "POST",
        body: JSON.stringify({
          group_id: editCell.group,
          index: editCell.index,
          name: "",
          code: "",
        }),
      });
    } else {
      await api("/api/holdings/cell", {
        method: "POST",
        body: JSON.stringify({
          group_id: editCell.group,
          index: editCell.index,
          name: el("cellName").value,
          code: el("cellCode").value.replace(/\D/g, "").slice(0, 6),
        }),
      });
    }
    el("cellDialog").close();
    await loadHoldings();
    renderHoldingsAll();
  }
  el("cellSave").addEventListener("click", () => saveCell(false));
  el("cellClear").addEventListener("click", () => saveCell(true));
}

let activeNewsId = null;

async function loadNewsList(q = "") {
  const url = q ? `/api/news?q=${encodeURIComponent(q)}` : "/api/news";
  const data = await api(url);
  const box = el("newsList");
  box.innerHTML = "";
  for (const it of data.items) {
    const d = document.createElement("div");
    d.className = "news-item" + (activeNewsId === it.id ? " active" : "");
    d.textContent = `${it.tab_name} · ${it.created_at || ""}`;
    d.title = it.snippet || "";
    d.addEventListener("click", async () => {
      activeNewsId = it.id;
      const full = await api("/api/news/" + it.id);
      el("newTabName").value = full.tab_name;
      el("newsContent").value = full.content || "";
      el("newsDetailMeta").textContent = `id=${full.id} ${full.created_at || ""}`;
      await loadNewsList(el("newsSearch").value.trim());
    });
    box.appendChild(d);
  }
}

async function initNews() {
  el("btnNewsSearch").addEventListener("click", () => loadNewsList(el("newsSearch").value.trim()));
  el("btnSaveNews").addEventListener("click", async () => {
    const tab_name = el("newTabName").value.trim();
    if (!tab_name) {
      alert("填写 tab_name");
      return;
    }
    await api("/api/news", {
      method: "POST",
      body: JSON.stringify({ tab_name, content: el("newsContent").value }),
    });
    await loadNewsList(el("newsSearch").value.trim());
    el("newsDetailMeta").textContent = "已保存";
  });
}

async function refreshHoldingsFromNews() {
  const ndays = Number(
    (el("digestDays") && el("digestDays").value) || 8
  ) || 8;
  const r = await api(`/api/holdings/refresh-from-news?ndays=${ndays}`, { method: "POST" });
  if (!r.ok) {
    showStub("从资讯刷新失败", JSON.stringify(r.meta || {}, null, 2));
    return;
  }
  await loadHoldings();
  renderHoldingsAll();
  if (el("digestMeta")) el("digestMeta").textContent = "已从资讯刷新：组7–14 已写入，侧栏标签已更新为 MMDD。";
}

async function runDigest() {
  const ndays = Number(el("digestDays").value) || 8;
  el("digestMeta").textContent = "加载中…";
  el("digestOut").innerHTML = "";
  const data = await api(`/api/news-digest?ndays=${ndays}`);
  const meta = data.meta || {};
  el("digestMeta").textContent = meta.hint || `rows=${meta.news_row_count ?? 0} reason=${meta.reason || "ok"}`;
  const out = el("digestOut");
  for (const day of data.days || []) {
    const wrap = document.createElement("div");
    wrap.className = "digest-day";
    wrap.innerHTML = `<div><span class="stag">${day.date_ymd}</span> ${day.date_mmdd} · ${day.stocks.length}</div>`;
    const pre = document.createElement("pre");
    pre.className = "log";
    pre.textContent = day.stocks.map((s) => `${s.code} ${s.name}`).join("\n");
    wrap.appendChild(pre);
    out.appendChild(wrap);
  }
}

async function initDigest() {
  el("btnDigest").addEventListener("click", runDigest);
  el("btnRefreshHoldingsFromNews").addEventListener("click", refreshHoldingsFromNews);
}

async function initCrawler() {
  el("btnRunCrawler").addEventListener("click", async () => {
    el("crawlerLog").textContent = "运行中…";
    const script = el("crawlerScript").value;
    try {
      const r = await api("/api/tasks/run-crawler", {
        method: "POST",
        body: JSON.stringify({ script, timeout_sec: 900 }),
      });
      el("crawlerLog").textContent =
        `rc=${r.returncode}\n--- out ---\n${r.stdout_tail || ""}\n--- err ---\n${r.stderr_tail || ""}`;
    } catch (e) {
      el("crawlerLog").textContent = String(e);
    }
  });
  el("btnReloadDict").addEventListener("click", async () => {
    await api("/api/stock-dict/reload", { method: "POST" });
    showStub("股票字典", "已清除内存缓存；下次 digest 会重新读盘或 akshare。");
  });
}

async function loadStats() {
  const s = await api("/api/stats");
  el("statsOut").textContent = JSON.stringify(s.counts, null, 2) + "\n" + s.db_path;

  const lg = await api("/api/stock-logic?limit=80");
  const tb = el("tblLogic").querySelector("tbody");
  tb.innerHTML = "";
  for (const r of lg.items || []) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${r.id}</td><td>${escapeHtml(r.stock_name)}</td><td>${escapeHtml(
      (r.logic || "").slice(0, 120)
    )}</td><td>${r.date || ""}</td>`;
    tb.appendChild(tr);
  }

  const kl = await api("/api/kelly-records?limit=40");
  const tk = el("tblKelly").querySelector("tbody");
  tk.innerHTML = "";
  for (const r of kl.items || []) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(r.stock_name)}</td><td>${r.calc_time || ""}</td><td>${r.odds}</td><td>${r.win_prob}</td><td>${r.kelly_ratio}</td>`;
    tk.appendChild(tr);
  }
}

async function boot() {
  initNav();
  initPosition();
  initAlertSwitches();
  await initHoldings();
  initNews();
  initDigest();
  initCrawler();

  el("btnReloadStats").addEventListener("click", loadStats);

  const cfg = await api("/api/config");
  el("dbPath").textContent = cfg.db_path;
  el("dbPath").title = cfg.db_path;

  await loadHoldings();
  renderHoldingsAll();

  await loadNewsList();
}

boot().catch((e) => {
  console.error(e);
  document.querySelector(".main-area")?.insertAdjacentHTML(
    "afterbegin",
    `<div class="panel error">加载失败：${escapeHtml(String(e))}</div>`
  );
});
