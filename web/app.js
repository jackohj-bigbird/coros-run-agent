const KEY_API_BASE = "run_agent_api_base";

const el = {
  apiBase: document.getElementById("api-base"),
  apiStatus: document.getElementById("api-status"),
  planStatus: document.getElementById("plan-status"),
  toast: document.getElementById("toast"),
  runCount: document.getElementById("m-run-count"),
  distance: document.getElementById("m-distance"),
  pace: document.getElementById("m-pace"),
  completion: document.getElementById("m-completion"),
  recentBody: document.getElementById("recent-body"),
  planBody: document.getElementById("plan-body"),
  chatBox: document.getElementById("chat-box"),
  chatInput: document.getElementById("chat-input"),
  planStart: document.getElementById("plan-start"),
  planRace: document.getElementById("plan-race"),
  planTarget: document.getElementById("plan-target"),
  btnSaveApi: document.getElementById("btn-save-api"),
  btnRefresh: document.getElementById("btn-refresh"),
  btnSync: document.getElementById("btn-sync"),
  btnRecent: document.getElementById("btn-recent"),
  btnPlan: document.getElementById("btn-plan"),
  btnPlanSetup: document.getElementById("btn-plan-setup"),
  btnChat: document.getElementById("btn-chat"),
  btnChatClear: document.getElementById("btn-chat-clear"),
};

function defaultApiBase() {
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    return "http://127.0.0.1:8000";
  }
  return "";
}

function getApiBase() {
  return (localStorage.getItem(KEY_API_BASE) || defaultApiBase()).trim().replace(/\/$/, "");
}

function setApiBase(value) {
  localStorage.setItem(KEY_API_BASE, value.trim().replace(/\/$/, ""));
}

function showToast(msg) {
  el.toast.textContent = msg;
  el.toast.classList.add("show");
  setTimeout(() => el.toast.classList.remove("show"), 1800);
}

async function request(path, options = {}) {
  const base = getApiBase();
  if (!base) {
    throw new Error("请先填写后端 API 地址");
  }
  const response = await fetch(`${base}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `请求失败: ${response.status}`);
  }
  return data;
}

function row(cells) {
  return `<tr>${cells.map((c) => `<td>${escapeHtml(String(c))}</td>`).join("")}</tr>`;
}

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function pushMessage(text, type) {
  const div = document.createElement("div");
  div.className = `msg ${type}`;
  div.textContent = text;
  el.chatBox.appendChild(div);
  el.chatBox.scrollTop = el.chatBox.scrollHeight;
}

async function loadWeeklySummary() {
  const data = await request("/summary/weekly");
  el.runCount.textContent = String(data.run_count);
  el.distance.textContent = `${data.total_distance_km} km`;
  el.pace.textContent = data.avg_pace;
  el.completion.textContent = `${Math.round(Number(data.completion_rate) * 100)}%`;
}

async function loadRecentActivities() {
  const rows = await request("/activities/recent?limit=12");
  if (!rows.length) {
    el.recentBody.innerHTML = row(["-", "暂无活动", "-", "-"]);
    return;
  }
  el.recentBody.innerHTML = rows
    .map((item) =>
      row([
        new Date(item.start_date).toLocaleDateString("zh-CN"),
        item.name,
        `${item.distance_km} km`,
        item.avg_pace,
      ])
    )
    .join("");
}

async function loadPlan() {
  const rows = await request("/plan?limit=30");
  if (!rows.length) {
    el.planBody.innerHTML = row(["-", "暂无计划", "-", "-"]);
    return;
  }
  el.planBody.innerHTML = rows
    .map((item) => row([item.date, item.type, `${item.distance_km} km`, item.pace]))
    .join("");
}

async function loadAll() {
  await Promise.all([loadWeeklySummary(), loadRecentActivities(), loadPlan()]);
}

async function handleSync() {
  const data = await request("/sync/strava", { method: "POST" });
  showToast(`同步完成，新增 ${data.inserted} 条`);
  await loadAll();
}

async function handlePlanSetup() {
  const payload = {
    start_date: el.planStart.value,
    race_date: el.planRace.value,
    target_time_min: Number(el.planTarget.value || 100),
  };
  const data = await request("/plan/setup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  el.planStatus.textContent = `已生成 ${data.inserted} 条计划`;
  await loadPlan();
}

async function handleChat() {
  const question = el.chatInput.value.trim();
  if (!question) {
    return;
  }
  pushMessage(question, "user");
  el.chatInput.value = "";
  const data = await request("/chat", {
    method: "POST",
    body: JSON.stringify({ question }),
  });
  pushMessage(data.answer || "未收到回复", "bot");
}

function bindEvents() {
  el.btnSaveApi.addEventListener("click", async () => {
    const value = el.apiBase.value.trim();
    if (!value) {
      showToast("请填写后端 API 地址");
      return;
    }
    setApiBase(value);
    try {
      await request("/health");
      el.apiStatus.textContent = "连接成功";
      showToast("API 地址已保存");
      await loadAll();
    } catch (err) {
      el.apiStatus.textContent = String(err.message);
      showToast("保存了地址，但连通失败");
    }
  });

  el.btnRefresh.addEventListener("click", () => guarded(loadAll));
  el.btnSync.addEventListener("click", () => guarded(handleSync));
  el.btnRecent.addEventListener("click", () => guarded(loadRecentActivities));
  el.btnPlan.addEventListener("click", () => guarded(loadPlan));
  el.btnPlanSetup.addEventListener("click", () => guarded(handlePlanSetup));
  el.btnChat.addEventListener("click", () => guarded(handleChat));
  el.btnChatClear.addEventListener("click", () => {
    el.chatBox.innerHTML = "";
  });
  el.chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      guarded(handleChat);
    }
  });
}

async function guarded(fn) {
  try {
    await fn();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    showToast(msg);
  }
}

async function init() {
  el.apiBase.value = getApiBase();
  bindEvents();
  pushMessage("你可以问：我这周训练完成度如何？", "bot");
  if (!getApiBase()) {
    el.apiStatus.textContent = "请先填写后端 API 地址";
    return;
  }
  await guarded(loadAll);
}

init();
