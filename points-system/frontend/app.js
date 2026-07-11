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
var _wheel = null;          // { canvas, ctx, sectors, currentAngle, sectorCount, sectorAngle }

// 转盘扇区配色（交替暖色系，11 色循环）
var WHEEL_COLORS = [
  "#FF6B6B", "#4ECDC4", "#FFE66D", "#95E1D3",
  "#F38181", "#AA96DA", "#FCBAD3", "#A8D8EA",
  "#D4A5A5", "#F8B500", "#88D8B0"
];

/**
 * 在 Canvas 上绘制转盘（支持动态扇区数量 18~20）
 */
function drawWheel(sectors, currentAngle) {
  var canvas = document.getElementById("wheelCanvas");
  if (!canvas) return;
  var ctx = canvas.getContext("2d");
  var size = canvas.width;  // 360
  var cx = size / 2, cy = size / 2, r = cx - 10;
  var sectorCount = sectors.length;
  var sectorAngle = (2 * Math.PI) / sectorCount;

  ctx.clearRect(0, 0, size, size);
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(currentAngle || 0);

  for (var i = 0; i < sectorCount; i++) {
    var start = i * sectorAngle;
    var end = start + sectorAngle;

    // 扇形填充
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.arc(0, 0, r, start, end);
    ctx.closePath();
    ctx.fillStyle = sectors[i].color || WHEEL_COLORS[i % WHEEL_COLORS.length];
    ctx.fill();

    // 扇形边线
    ctx.strokeStyle = "rgba(255,255,255,.35)";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 文字标签（沿径向排列）
    ctx.save();
    ctx.rotate(start + sectorAngle / 2); // 扇形中心角
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#fff";
    // 扇区多时字号缩小
    var fontSize = sectorCount > 16 ? 10 : 12;
    ctx.font = "bold " + fontSize + "px -apple-system, 'PingFang SC', sans-serif";

    // 文字沿半径方向偏移
    var label = sectors[i].name;
    var maxLen = sectorCount > 16 ? 4 : 6;
    if (label.length > maxLen) label = label.substring(0, maxLen - 1) + "..";
    ctx.shadowColor = "rgba(0,0,0,.3)";
    ctx.shadowBlur = 3;
    ctx.fillText(label, r - 14, 0);
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
 * 用后端返回的扇区数据初始化/刷新转盘
 */
function initWheel(sectorsData) {
  var canvas = document.getElementById("wheelCanvas");
  if (!canvas) return;

  // 为每个扇区分配颜色
  var sectors = (sectorsData || []).map(function(s, i) {
    return {
      id: s.id,
      name: s.name,
      isWin: s.is_win,
      weight: s.weight,
      color: WHEEL_COLORS[i % WHEEL_COLORS.length],
    };
  });

  _wheel = {
    canvas: canvas,
    ctx: canvas.getContext("2d"),
    sectors: sectors,
    sectorCount: sectors.length,
    sectorAngle: (2 * Math.PI) / sectors.length,
    currentAngle: (_wheel && _wheel.currentAngle) || 0,
    spinning: false
  };
  drawWheel(_wheel.sectors, _wheel.currentAngle);
}

/**
 * 计算目标扇区在当前转盘上的中心角度
 */
function getSectorCenterAngle(targetIndex) {
  if (!_wheel) return 0;
  return targetIndex * _wheel.sectorAngle + _wheel.sectorAngle / 2;
}

/**
 * 执行转盘旋转动画，停在目标扇区上
 * targetIndex: 目标扇区索引
 * callback: 动画结束回调
 */
function spinTo(targetIndex, callback) {
  if (!_wheel || _wheel.spinning) return;
  _wheel.spinning = true;

  var canvas = _wheel.canvas;
  canvas.classList.add("spinning");

  // 目标扇区的中心角度
  var sectorCenter = getSectorCenterAngle(targetIndex);
  // 至少转 5~7 圈
  var extraSpins = 5 + Math.floor(Math.random() * 3);
  // 指针在顶部（-PI/2 方向），计算目标旋转角度
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

  // transitionend 回调
  var onEnd = function(e) {
    if (e.target !== canvas) return;
    canvas.removeEventListener("transitionend", onEnd);
    canvas.classList.remove("spinning");

    _wheel.currentAngle = targetRotation % (2 * Math.PI);
    if (_wheel.currentAngle < 0) _wheel.currentAngle += 2 * Math.PI;

    drawWheel(_wheel.sectors, _wheel.currentAngle);
    _wheel.spinning = false;

    if (callback) callback();
  };

  // 备用兜底
  var fallbackTimer = setTimeout(function() {
    canvas.removeEventListener("transitionend", onEnd);
    canvas.classList.remove("spinning");
    _wheel.currentAngle = targetRotation % (2 * Math.PI);
    if (_wheel.currentAngle < 0) _wheel.currentAngle += 2 * Math.PI;
    drawWheel(_wheel.sectors, _wheel.currentAngle);
    _wheel.spinning = false;
    if (callback) callback();
  }, 6500);

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
 * 抽奖面板 UI 更新
 */
function updateLotteryUI(d) {
  var state = document.getElementById("lotteryState");
  var btn = document.getElementById("drawBtn");
  var hint = document.getElementById("drawHint");

  // 初始化占位转盘（首次加载时画一个空转盘，实际扇区在抽奖时由后端返回）
  if (!_wheel) {
    initWheel([]);
  }

  if (d.can_lottery) {
    state.textContent = "抽奖已解锁！当前持有 " + d.lottery_tickets + " 张，每次消耗 1 张";
    state.className = "lottery-state unlocked";
    btn.disabled = false;
    hint.textContent = "点击下方按钮转动转盘 ";
  } else {
    state.textContent = "获取抽奖券即可参与抽奖";
    state.className = "lottery-state";
    btn.disabled = true;
    hint.textContent = "可用积分兑换抽奖券后解锁抽奖功能";
  }
}

/**
 * 抽奖主流程：
 * 1. 调用后端 API 获取转盘扇区 + 中奖结果
 * 2. 用返回的扇区数据绘制转盘
 * 3. 转盘旋转动画停在目标扇区
 * 4. 弹出中奖结果
 */
async function doDraw() {
  var btn = document.getElementById("drawBtn");
  if (btn.disabled || !_wheel || _wheel.spinning) return;

  lockBtn(btn, "抽奖中...");
  try {
    // 调用后端获取转盘扇区 + 抽奖结果
    var r = await api("/api/lottery/draw", {
      method: "POST",
      body: JSON.stringify({ user_id: currentUser }),
    });

    var sectorsData = r.sectors || [];
    var winningIndex = r.winning_index != null ? r.winning_index : 0;
    var prizeName = r.draw.prize_name;
    var isWin = r.draw.is_win;

    // 用后端返回的扇区数据重新绘制转盘
    initWheel(sectorsData);

    // 旋转动画完成后显示结果
    spinTo(winningIndex, function() {
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
