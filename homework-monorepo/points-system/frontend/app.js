"use strict";

const API = "";
let currentUser = null;

/* ===== 通用工具 ===== */
function toast(msg, isErr) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = "toast show" + (isErr ? " err" : "");
  setTimeout(() => { el.className = "toast"; }, 2400);
}

async function api(path, opts) {
  opts = opts || {};
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { const body = await res.json(); detail = body.detail || detail; } catch (e) {}
    throw new Error(detail);
  }
  return res.json();
}

function fmt(s) {
  const d = new Date(s);
  return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function lockBtn(btn, text) { btn.dataset._lbl = btn.textContent; btn.disabled = true; btn.textContent = text; }
function unlockBtn(btn) { btn.disabled = false; btn.textContent = btn.dataset._lbl || btn.textContent; }


/* ===== 转盘抽奖 ===== */

// 转盘状态
var _wheel = null;          // { canvas, ctx, sectors, currentAngle }
const SECTOR_COUNT = 11;    // 10 个随机奖品 + 1 个"谢谢惠顾"
const SECTOR_ANGLE = (2 * Math.PI) / SECTOR_COUNT; // ~32.727°

// 转盘扇区配色（交替暖色系）
var WHEEL_COLORS = [
  "#FF6B6B", "#4ECDC4", "#FFE66D", "#95E1D3",
  "#F38181", "#AA96DA", "#FCBAD3", "#A8D8EA",
  "#D4A5A5", "#F8B500", "#88D8B0"
];

/**
 * 从奖池中随机取 N 个奖品，补齐到 SECTOR_COUNT-1 个（末位固定为"谢谢惠顾"）
 * 返回 [{ name, isWin, color }, ...]
 */
function buildSectors(prizePool) {
  var pool = (prizePool || []).filter(function(p) { return p.name !== "谢谢参与" && p.name !== "谢谢惠顾"; });
  // 随机打乱并取前 10 个
  var shuffled = pool.slice().sort(function() { return Math.random() - 0.5; });
  var picked = shuffled.slice(0, SECTOR_COUNT - 1);

  var sectors = [];
  for (var i = 0; i < picked.length; i++) {
    sectors.push({
      name: picked[i].name,
      isWin: picked[i].is_win !== 0,   // 奖池中标记为中奖的奖品
      color: WHEEL_COLORS[i % WHEEL_COLORS.length],
      prizeId: picked[i].id
    });
  }
  // 最后一个扇区固定：谢谢惠顾
  sectors.push({
    name: "谢谢惠顾",
    isWin: false,
    color: WHEEL_COLORS[(SECTOR_COUNT - 1) % WHEEL_COLORS.length],
    prizeId: null
  });

  // 再打乱一次让"谢谢惠顾"不一定在最后
  // 但为了视觉美观，保持固定位置也可以——这里选择再随机洗一次
  // Fisher-Yates 洗牌（保留颜色绑定）
  for (var j = sectors.length - 1; j > 0; j--) {
    var r = Math.floor(Math.random() * (j + 1));
    var tmp = sectors[j]; sectors[j] = sectors[r]; sectors[r] = tmp;
    // 颜色也跟着换
    var tc = WHEEL_COLORS[j % WHEEL_COLORS.length];
    WHEEL_COLORS[j] = WHEEL_COLORS[r % WHEEL_COLORS.length];
    WHEEL_COLORS[r] = tc;
    sectors[j].color = WHEEL_COLORS[j % WHEEL_COLORS.length];
    sectors[r].color = WHEEL_COLORS[r % WHEEL_COLORS.length];
  }

  return sectors;
}

/**
 * 在 Canvas 上绘制转盘
 */
function drawWheel(sectors, currentAngle) {
  var canvas = document.getElementById("wheelCanvas");
  if (!canvas) return;
  var ctx = canvas.getContext("2d");
  var cx = 160, cy = 160, r = 150;

  ctx.clearRect(0, 0, 320, 320);
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(currentAngle || 0);

  for (var i = 0; i < sectors.length; i++) {
    var start = i * SECTOR_ANGLE;
    var end = start + SECTOR_ANGLE;

    // 扇形填充
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, r, start, end);
    ctx.closePath();
    ctx.fillStyle = sectors[i].color;
    ctx.fill();

    // 扇形边线
    ctx.strokeStyle = "rgba(255,255,255,.35)";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 文字标签（沿径向排列）
    ctx.save();
    ctx.rotate(start + SECTOR_ANGLE / 2); // 扇形中心角
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#fff";
    ctx.font = "bold 13px -apple-system, 'PingFang SC', sans-serif";

    // 文字沿半径方向偏移
    var label = sectors[i].name;
    if (label.length > 6) label = label.substring(0, 5) + "..";
    ctx.shadowColor = "rgba(0,0,0,.3)";
    ctx.shadowBlur = 3;
    ctx.fillText(label, r - 16, 0);
    ctx.restore();
  }

  // 中心圆装饰
  ctx.beginPath();
  ctx.arc(0, 0, 28, 0, 2 * Math.PI);
  ctx.fillStyle = "#fff";
  ctx.fill();
  ctx.strokeStyle = "rgba(31,42,68,.15)";
  ctx.lineWidth = 2;
  ctx.stroke();

  // 中心文字
  ctx.shadowColor = "transparent";
  ctx.fillStyle = "#1f2a44";
  ctx.font = "bold 13px -apple-system, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("抽奖", 0, 0);

  ctx.restore();
}

/**
 * 初始化 / 刷新转盘数据
 */
function initWheel(prizePool) {
  var canvas = document.getElementById("wheelCanvas");
  if (!canvas) return;
  _wheel = {
    canvas: canvas,
    ctx: canvas.getContext("2d"),
    sectors: buildSectors(prizePool),
    currentAngle: (_wheel && _wheel.currentAngle) || 0,  // 保留上次停止角度
    spinning: false
  };
  drawWheel(_wheel.sectors, _wheel.currentAngle);
}

/**
 * 计算目标奖品在当前转盘上的扇区索引
 * 返回 0~10 的索引值
 */
function findSectorIndex(prizeName) {
  if (!_wheel) return 0;
  // 精确匹配名称；若不匹配则找"谢谢惠顾"兜底
  for (var i = 0; i < _wheel.sectors.length; i++) {
    if (_wheel.sectors[i].name === prizeName) return i;
  }
  // 兜底：找第一个非中奖的
  for (var j = 0; j < _wheel.sectors.length; j++) {
    if (!_wheel.sectors[j].isWin) return j;
  }
  return 0;
}

/**
 * 执行转盘旋转动画，停在目标扇区上
 * targetIndex: 目标扇区索引 (0 ~ SECTOR_COUNT-1)
 * callback: 动画结束回调
 */
function spinTo(targetIndex, callback) {
  if (!_wheel || _wheel.spinning) return;
  _wheel.spinning = true;

  var canvas = _wheel.canvas;
  canvas.classList.add("spinning");

  // 目标扇区的中心角度（相对于 12 点方向）
  // 指针在顶部（-PI/2 方向），需要计算转到什么角度时目标扇区中心对准指针
  var sectorCenter = targetIndex * SECTOR_ANGLE + SECTOR_ANGLE / 2;
  // 当前角度基础上，至少转 5 圈 + 目标偏移
  var extraSpins = 5 + Math.floor(Math.random() * 3); // 5~7 圈
  // 最终角度 = 当前角度 + extraSpins*2π + (使目标扇区对准顶部的补偿)
  // 指针在 -π/2（canvas 坐标系 12 点），所以：
  // 目标扇区中心应转到 -π/2（即 π*3/2）附近
  var targetRotation = _wheel.currentAngle
    + extraSpins * 2 * Math.PI
    + (-Math.PI / 2 - sectorCenter)
    - (_wheel.currentAngle % (2 * Math.PI));

  // 确保总是正向旋转足够多的圈
  if (targetRotation <= _wheel.currentAngle + 4 * Math.PI) {
    targetRotation += 2 * Math.PI * (5 + Math.random() * 3);
  }

  // 应用 CSS transform 触发 transition
  canvas.style.transform = "rotate(" + targetRotation + "rad)";

  // transitionend 回调（transition 时间由 CSS 控制，约 5s）
  var onEnd = function(e) {
    if (e.target !== canvas) return;
    canvas.removeEventListener("transitionend", onEnd);
    canvas.classList.remove("spinning");

    _wheel.currentAngle = targetRotation % (2 * Math.PI);
    // 归一化到 [0, 2π)
    if (_wheel.currentAngle < 0) _wheel.currentAngle += 2 * Math.PI;

    // 重绘以同步最终角度
    drawWheel(_wheel.sectors, _wheel.currentAngle);
    _wheel.spinning = false;

    if (callback) callback();
  };

  // 备用：如果 transitionend 未触发（某些浏览器问题），用 setTimeout 兜底
  var fallbackTimer = setTimeout(function() {
    canvas.removeEventListener("transitionend", onEnd);
    canvas.classList.remove("spinning");
    _wheel.currentAngle = targetRotation % (2 * Math.PI);
    if (_wheel.currentAngle < 0) _wheel.currentAngle += 2 * Math.PI;
    drawWheel(_wheel.sectors, _wheel.currentAngle);
    _wheel.spinning = false;
    if (callback) callback();
  }, 5500);

  var realEnd = function(e) {
    clearTimeout(fallbackTimer);
    onEnd(e);
  };
  canvas.addEventListener("transitionend", realEnd);
}


/* ===== 数据加载与渲染 ===== */

async function loadUsers() {
  var users = await api("/api/users");
  var sel = document.getElementById("userSelect");
  sel.innerHTML = users.map(function(u) {
    return '<option value="' + u.id + '">' + u.display_name + '（' + u.username + '）</option>';
  }).join("");
  if (users.length) {
    currentUser = users[0].id;
    sel.value = String(currentUser);
  }
  sel.onchange = function() {
    currentUser = parseInt(sel.value, 10);
    refresh();
  };
}

async function refresh() {
  if (!currentUser) return;
  var d = await api("/api/dashboard?user_id=" + currentUser);
  window._dash = d;
  renderDashboard(d);
  renderPrizes(d.prizes);
  renderRedemptions(d.redemptions);
  renderTicketLedger(d.ticket_ledger);
  renderDraws(d.lottery_draws);
  updateConvertUI(d);
  updateLotteryUI(d);
}

function renderDashboard(d) {
  document.getElementById("balance").textContent = d.balance;
  document.getElementById("earned").textContent = d.total_earned;
  document.getElementById("spent").textContent = d.total_spent;
  document.getElementById("tickets").textContent = d.lottery_tickets;
  document.getElementById("pointsPerTicket").textContent = d.points_per_ticket;
  document.getElementById("streak").textContent = d.current_streak;

  var pill = document.getElementById("lotteryStatus");
  if (d.can_lottery) {
    pill.textContent = "已解锁";
    pill.className = "status-pill unlocked";
  } else {
    pill.textContent = "未解锁";
    pill.className = "status-pill locked";
  }

  var btn = document.getElementById("checkinBtn");
  var hint = document.getElementById("checkinHint");
  if (d.today_checked_in) {
    btn.disabled = true;
    btn.textContent = "今日已打卡 ✓";
    hint.textContent = "明天再来，连续打卡满 7 天可额外 +20 分";
  } else {
    btn.disabled = false;
    btn.textContent = "今日打卡 +10";
    var left = 7 - (d.current_streak % 7);
    hint.textContent = d.current_streak > 0
      ? "已连续 " + d.current_streak + " 天，再坚持 " + left + " 天得奖励"
      : "连续打卡 7 天可额外获得 20 分";
  }
}

function updateConvertUI(d) {
  var rate = document.getElementById("convertRate");
  var hint = document.getElementById("convertHint");
  var btn = document.getElementById("convertBtn");
  var qtyInput = document.getElementById("convertQty");
  var qty = Math.max(1, parseInt(qtyInput.value, 10) || 1);
  var need = qty * d.points_per_ticket;

  rate.textContent = "每 " + d.points_per_ticket + " 积分可兑换 1 张抽奖券";
  if (d.balance < d.points_per_ticket) {
    btn.disabled = true;
    hint.textContent = "积分不足：至少需 " + d.points_per_ticket + " 分才能换 1 张（当前 " + d.balance + " 分）";
  } else if (d.balance < need) {
    btn.disabled = true;
    hint.textContent = "兑换 " + qty + " 张需 " + need + " 分，当前仅 " + d.balance + " 分，请减少数量";
  } else {
    btn.disabled = false;
    hint.textContent = "兑换 " + qty + " 张将消耗 " + need + " 分，兑换后剩余 " + (d.balance - need) + " 分";
  }
}

/**
 * 抽奖面板 UI 更新：含转盘初始化
 */
function updateLotteryUI(d) {
  var state = document.getElementById("lotteryState");
  var btn = document.getElementById("drawBtn");
  var hint = document.getElementById("drawHint");

  // 初始化或刷新转盘（使用奖池数据）
  initWheel(d.lottery_pool || d.prizes || []);

  if (d.can_lottery) {
    state.textContent = "抽奖已解锁！当前持有 " + d.lottery_tickets + " 张，每次消耗 1 张";
    state.className = "lottery-state unlocked";
    btn.disabled = false;
    hint.textContent = "点击下方按钮转动转盘 🎰";
  } else {
    state.textContent = "获取抽奖券即可参与抽奖";
    state.className = "lottery-state";
    btn.disabled = true;
    hint.textContent = "可用积分兑换抽奖券后解锁抽奖功能";
  }
}

/**
 * 抽奖主流程：
 * 1. 调用后端 API 获取真实结果
 * 2. 找到对应扇区索引
 * 3. 转盘旋转动画
 * 4. 弹出中奖结果
 */
async function doDraw() {
  var btn = document.getElementById("drawBtn");
  if (btn.disabled || !_wheel || _wheel.spinning) return;

  lockBtn(btn, "抽奖中...");
  try {
    // 先调用后端获取真实抽奖结果
    var r = await api("/api/lottery/draw", {
      method: "POST",
      body: JSON.stringify({ user_id: currentUser }),
    });
    var prizeName = r.draw.prize_name;
    var isWin = r.draw.is_win;

    // 找到目标扇区并旋转
    var targetIdx = findSectorIndex(prizeName);

    // 旋转动画完成后显示结果
    spinTo(targetIdx, function() {
      showResult(isWin, prizeName);
      refresh(); // 刷新数据
    });
  } catch (e) {
    toast(e.message, true);
    unlockBtn(btn);
  }
}

/**
 * 显示中奖结果弹窗
 */
function showResult(isWin, prizeName) {
  var modal = document.getElementById("resultModal");
  var icon = document.getElementById("resultIcon");
  var title = document.getElementById("resultTitle");
  var prizeEl = document.getElementById("resultPrize");

  if (isWin) {
    icon.textContent = "🎉";
    title.textContent = "恭喜中奖！";
    title.style.color = "var(--red)";
  } else {
    icon.textContent = "💫";
    title.textContent = "很遗憾";
    title.style.color = "var(--muted)";
  }

  prizeEl.textContent = prizeName;
  modal.classList.remove("hidden");

  unlockBtn(document.getElementById("drawBtn"));
}

// 关闭结果弹窗
document.addEventListener("DOMContentLoaded", function() {
  var closeBtn = document.getElementById("resultClose");
  if (closeBtn) closeBtn.onclick = function() {
    document.getElementById("resultModal").classList.add("hidden");
  };
});


/* ===== 积分兑换抽奖券 ===== */
async function doConvert() {
  var btn = document.getElementById("convertBtn");
  if (btn.disabled) return;
  var qty = Math.max(1, parseInt(document.getElementById("convertQty").value, 10) || 1);
  lockBtn(btn, "兑换中...");
  try {
    var r = await api("/api/convert", {
      method: "POST",
      body: JSON.stringify({ user_id: currentUser, qty: qty }),
    });
    toast("兑换成功，获得 " + r.conversion.qty + " 张抽奖券 \uD83C\uDFAB");
    await refresh();
  } catch (e) {
    toast(e.message, true);
  } finally {
    unlockBtn(btn);
  }
}


/* ===== 打卡 ===== */
async function doCheckin() {
  try {
    await api("/api/checkin", {
      method: "POST",
      body: JSON.stringify({ user_id: currentUser }),
    });
    toast("打卡成功，积分已到账 \u2705");
    await refresh();
  } catch (e) {
    toast(e.message, true);
  }
}


/* ===== 奖品渲染 ===== */
function renderPrizes(prizes) {
  var el = document.getElementById("prizeList");
  if (!prizes.length) {
    el.innerHTML = '<div class="empty">暂无奖品</div>';
    return;
  }
  el.innerHTML = prizes.map(function(p) {
    return '<div class="prize ' + (p.can_redeem ? "" : "disabled") + '">'
      + '<div class="prize-name">' + escapeHtml(p.name) + '</div>'
      + '<div class="prize-desc">' + escapeHtml(p.description || "") + '</div>'
      + '<div class="prize-meta">'
        + '<span class="cost">' + p.cost_points + ' 分</span>'
        + '<span class="stock">库存 ' + p.stock + '</span>'
      + '</div>'
      + '<button class="btn" data-prize="' + p.id + '" ' + (p.can_redeem ? "" : "disabled") + '>'
        + (p.can_redeem ? "兑换" : "不可兑换")
      + '</button>'
    + '</div>';
  }).join("");

  el.querySelectorAll("button[data-prize]").forEach(function(b) {
    b.onclick = function() { redeem(parseInt(b.dataset.prize, 10)); };
  });
}

async function redeem(prizeId) {
  try {
    await api("/api/redeem", {
      method: "POST",
      body: JSON.stringify({ user_id: currentUser, prize_id: prizeId }),
    });
    toast("兑换成功 \uD83C\uDF89");
    await refresh();
  } catch (e) {
    toast(e.message, true);
  }
}


/* ===== 列表渲染 ===== */
function renderRedemptions(rows) {
  var el = document.getElementById("redemptionList");
  if (!rows.length) { el.innerHTML = '<div class="empty">暂无兑换记录</div>'; return; }
  el.innerHTML = rows.map(function(r) {
    return '<div class="row">'
      + '<span class="grow">' + escapeHtml(r.prize_name) + '</span>'
      + '<span class="muted">-' + r.cost_points + ' 分</span>'
      + '<span class="muted">' + fmt(r.created_at) + '</span>'
    + '</div>';
  }).join("");
}

function renderTicketLedger(rows) {
  var el = document.getElementById("ticketLedgerList");
  if (!rows || !rows.length) { el.innerHTML = '<div class="empty">暂无抽奖券流水</div>'; return; }
  el.innerHTML = rows.map(function(t) {
    return '<div class="row">'
      + '<span class="tag ' + (t.tx_type === "issue" ? "earn" : "spend") + '">'
        + (t.tx_type === "issue" ? "发放" : "消耗")
      + '</span>'
      + '<span class="grow">' + escapeHtml(t.note || "") + '</span>'
      + '<span class="' + (t.tx_type === "issue" ? "" : "muted") + '">'
        + (t.tx_type === "issue" ? "+" : "-") + t.amount
      + '</span>'
      + '<span class="muted">余 ' + t.balance_after + '</span>'
    + '</div>';
  }).join("");
}

function renderDraws(rows) {
  var el = document.getElementById("drawList");
  if (!rows || !rows.length) { el.innerHTML = '<div class="empty">暂无抽奖记录</div>'; return; }
  el.innerHTML = rows.map(function(r) {
    return '<div class="row">'
      + '<span class="tag ' + (r.is_win ? "earn" : "spend") + '">' + (r.is_win ? "中奖" : "未中") + '</span>'
      + '<span class="grow">' + escapeHtml(r.prize_name) + '</span>'
      + '<span class="muted">' + fmt(r.created_at) + '</span>'
    + '</div>';
  }).join("");
}

function renderLedger(rows) {
  var el = document.getElementById("ledgerList");
  if (!rows.length) { el.innerHTML = '<div class="empty">暂无流水</div>'; return; }
  el.innerHTML = rows.map(function(l) {
    return '<div class="row">'
      + '<span class="tag ' + l.tx_type + '">' + (l.tx_type === "earn" ? "收入" : "支出") + '</span>'
      + '<span class="grow">' + escapeHtml(l.note || "") + '</span>'
      + '<span class="' + (l.tx_type === "earn" ? "" : "muted") + '">'
        + (l.tx_type === "earn" ? "+" : "-") + l.amount
      + '</span>'
      + '<span class="muted">余 ' + l.balance_after + '</span>'
    + '</div>';
  }).join("");
}


/* ===== 事件绑定 & 启动 ===== */
document.getElementById("checkinBtn").onclick = doCheckin;
document.getElementById("convertBtn").onclick = doConvert;
document.getElementById("drawBtn").onclick = doDraw;
document.getElementById("convertQty").oninput = function() {
  if (window._dash) updateConvertUI(window._dash);
};

(async function() {
  try {
    await loadUsers();
    await refresh();
  } catch (e) {
    toast("初始化失败：" + e.message, true);
  }
})();
