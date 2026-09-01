/* =========================================================
 * 学习成长计划模块（学生端）——独立文件，经 mixin 注入根实例
 * app.js 仅在 app.mount 前追加：app.mixin(window.PlanModule)
 * 依赖 app.js 的 api()/showToast()/compressImage()/blobToFile()，
 * 均为运行时调用（本文件先加载、后执行），无加载顺序问题。
 * ========================================================= */
(function () {
  "use strict";

  function todayStr() {
    var d = new Date();
    var m = String(d.getMonth() + 1).padStart(2, "0");
    var day = String(d.getDate()).padStart(2, "0");
    return d.getFullYear() + "-" + m + "-" + day;
  }

  /* ---------- ring-progress：SVG stroke-dasharray 环形条 ----------
     不用 conic-gradient，兼容微信 X5 / 旧 WebView */
  var RingProgress = {
    props: {
      percent: { type: Number, default: 0 },
      size: { type: Number, default: 76 },
      stroke: { type: Number, default: 8 },
    },
    computed: {
      r() { return (this.size - this.stroke) / 2; },
      circumference() { return 2 * Math.PI * this.r; },
      dash() {
        var p = Math.min(100, Math.max(0, this.percent || 0));
        return (this.circumference * p) / 100;
      },
    },
    template: `
      <svg class="ring-progress" :width="size" :height="size" :viewBox="'0 0 ' + size + ' ' + size">
        <circle class="ring-track" :cx="size/2" :cy="size/2" :r="r" fill="none" :stroke-width="stroke" />
        <circle class="ring-bar" :cx="size/2" :cy="size/2" :r="r" fill="none" :stroke-width="stroke"
          stroke-linecap="round" :stroke-dasharray="dash + ' ' + circumference"
          :transform="'rotate(-90 ' + size/2 + ' ' + size/2 + ')'" />
        <text class="ring-text" :x="size/2" :y="size/2" text-anchor="middle" dominant-baseline="central">{{ percent || 0 }}%</text>
      </svg>`,
  };

  /* ---------- task-card：四态 ⬜待开始 / 🔵进行中 / ✅已完成 / 🔴已逾期 ---------- */
  var TaskCard = {
    props: { task: { type: Object, required: true } },
    emits: ["open"],
    computed: {
      meta() {
        return ({
          todo: { icon: "⬜", text: "待开始" },
          doing: { icon: "🔵", text: "进行中" },
          done: { icon: "✅", text: "已完成" },
          overdue: { icon: "🔴", text: "已逾期" },
        })[this.task.computed_status] || { icon: "⬜", text: "待开始" };
      },
    },
    template: `
      <div class="task-card" :class="'st-' + task.computed_status" @click="$emit('open', task)">
        <div class="tc-icon">{{ meta.icon }}</div>
        <div class="tc-body">
          <div class="tc-title">{{ task.subject_emoji || '📖' }} {{ task.title }}</div>
          <div class="tc-sub">
            <span>{{ task.subject_name || '综合' }}</span>
            <span v-if="task.due_date">📅 {{ task.due_date }}</span>
            <span>⏱ {{ task.est_minutes }}分钟</span>
            <span v-if="task.reward_points">⭐ +{{ task.reward_points }}</span>
          </div>
          <div class="tc-sub" v-if="task.submission">
            <span :class="'sub-' + task.submission.review_status">
              {{ task.submission.review_status === 'approved' ? '✅ 审核已通过'
                : (task.submission.review_status === 'rejected' ? '❌ 未通过，请修改后重新提交' : '⏳ 成果审核中') }}
            </span>
          </div>
          <div class="tc-sub" v-else-if="task.progress_percent > 0">
            <span class="tc-percent">📈 进度 {{ task.progress_percent }}%</span>
          </div>
        </div>
        <div class="tc-status">{{ meta.text }}</div>
      </div>`,
  };

  /* ---------- badge-wall：勋章墙（全量定义 + 是否已获得） ---------- */
  var BadgeWall = {
    props: { items: { type: Array, default: () => [] } },
    template: `
      <div class="badge-wall">
        <p class="muted" v-if="!items.length">暂无勋章数据</p>
        <div class="bw-item" v-for="b in items" :key="b.key" :class="{earned: b.earned}">
          <div class="bw-icon">{{ b.earned ? '🏅' : '🔒' }}</div>
          <div class="bw-name">{{ b.name }}</div>
          <div class="bw-desc">{{ b.description }}</div>
        </div>
      </div>`,
  };

  /* ==================== PlanModule：mixin 主体 ==================== */
  window.PlanModule = {
    components: {
      "ring-progress": RingProgress,
      "task-card": TaskCard,
      "badge-wall": BadgeWall,
    },
    data() {
      return {
        planBootstrapped: false,   // 本轮登录后是否已做过模式探测
        planConfig: { mode: "summer", review_mode: "admin", semester_name: null, class_name: null },
        planSummary: {},           // /api/learning/summary 首页卡片数据
        planList: [],              // 我的计划实例（含进度汇总）
        planTemplates: { items: [], instantiated: [] },
        planBadges: [],
        planTab: "my",             // my | templates | badges
        currentPlan: null,         // 当前打开的计划详情
        currentTasks: [],
        selectedPlanTask: null,    // 任务详情弹窗
        planProgressForm: { note: "", minutes_spent: null, percent: null },
        planSubmitForm: { content: "", photoData: "", photoFile: null },
        planBusy: false,
        // 实时通知（WS 主通道 + 30s 轮询降级）
        notifUnread: 0,
        notifItems: [],
        showNotifPanel: false,
        // 家长监督视图
        parentLearning: { summary: null, plans: [], pending: [] },
        parentReviewBusy: false,
      };
    },
    computed: {
      // 学期/假期模式（summer 保持现状）
      isPlanMode() { return !!this.planConfig.mode && this.planConfig.mode !== "summer"; },
      // 计划详情内的今日待办：截止日为今天且未完成
      todayTodoTasks() {
        var t = todayStr();
        return this.currentTasks.filter(function (x) {
          return x.due_date === t && x.computed_status !== "done";
        });
      },
    },
    watch: {
      // bootstrap()/login() 落地 home 后探测一次学习计划模式（不侵入 app.js 的 bootstrap）
      view(v) {
        if (v === "home" && this.token && !this.planBootstrapped) {
          this.planBootstrapped = true;
          this.applyPlanMode();
        }
        if ((v === "home" || v === "plan") && this.token && !this._wsStarted) {
          this.initNotifySocket();
        }
      },
      // 退出登录时复位，保证重新登录后重新探测
      token(v) {
        if (!v) {
          this.planBootstrapped = false;
          this.stopNotifySocket();
          this.parentLearning = { summary: null, plans: [], pending: [] };
          this.planConfig = { mode: "summer", review_mode: "admin", semester_name: null, class_name: null };
          this.planSummary = {};
          this.planList = [];
          this.currentPlan = null;
          this.currentTasks = [];
          this.selectedPlanTask = null;
        }
      },
    },
    created() {
      // 非响应式句柄：WS 连接/退避/轮询定时器
      this._ws = null;
      this._wsStarted = false;
      this._wsFails = 0;
      this._retryTimer = null;
      this._pollTimer = null;
    },
    methods: {
      /* ---------- 模式探测与入口 ---------- */
      async applyPlanMode() {
        // 家长监督视图为后续版本能力，家长态暂不加载学习计划数据
        if (this.isParent) return;
        try {
          this.planConfig = await this.api("/api/learning/config");
        } catch (e) { return; }
        // 学期/假期模式：默认落地计划视图
        if (this.isPlanMode && this.view === "home") this.goPlan();
      },
      async goPlan() {
        this.view = "plan";
        if (this.isParent) {
          await this.loadParentLearning();
          return;
        }
        await this.loadPlanHome();
      },

      /* ---------- 数据加载 ---------- */
      async loadPlanHome() {
        await this.loadPlanConfig();
        await Promise.all([this.loadPlanSummary(), this.loadMyPlans()]);
      },
      async loadPlanConfig() {
        try { this.planConfig = await this.api("/api/learning/config"); } catch (e) { /* 保持默认 */ }
      },
      async loadPlanSummary() {
        try { this.planSummary = await this.api("/api/learning/summary"); } catch (e) { this.planSummary = {}; }
      },
      async loadMyPlans() {
        try {
          var d = await this.api("/api/learning/plans");
          this.planList = d.items || [];
        } catch (e) { this.planList = []; }
      },
      async loadTemplates() {
        try { this.planTemplates = await this.api("/api/learning/templates"); }
        catch (e) { this.planTemplates = { items: [], instantiated: [] }; }
      },
      async loadBadges() {
        try {
          var d = await this.api("/api/learning/badges");
          this.planBadges = d.items || [];
        } catch (e) { this.planBadges = []; }
      },
      async switchPlanTab(tab) {
        this.planTab = tab;
        if (tab === "templates" && !this.planTemplates.items.length) await this.loadTemplates();
        if (tab === "badges" && !this.planBadges.length) await this.loadBadges();
      },

      /* ---------- 计划详情 ---------- */
      async openPlan(p) {
        try {
          var d = await this.api("/api/learning/plans/" + p.id);
          this.currentPlan = d.plan;
          this.currentTasks = d.tasks || [];
        } catch (e) { this.showToast(e.message); }
      },
      closePlanDetail() {
        this.currentPlan = null;
        this.currentTasks = [];
        this.loadMyPlans();   // 回列表时刷新进度汇总
      },
      async refreshPlanDetail() {
        if (!this.currentPlan) return;
        try {
          var d = await this.api("/api/learning/plans/" + this.currentPlan.id);
          this.currentPlan = d.plan;
          this.currentTasks = d.tasks || [];
          // 弹窗中的任务对象同步为最新（避免进度/状态显示旧值）
          if (this.selectedPlanTask) {
            var sid = this.selectedPlanTask.id;
            var fresh = this.currentTasks.find(function (x) { return x.id === sid; });
            if (fresh) this.selectedPlanTask = fresh;
          }
        } catch (e) { /* 静默 */ }
      },
      openPlanTask(t) {
        this.selectedPlanTask = t;
        this.planProgressForm = { note: "", minutes_spent: null, percent: null };
        this.planSubmitForm = { content: "", photoData: "", photoFile: null };
      },

      /* ---------- 模板实例化 ---------- */
      async instantiateTemplate(t) {
        if (this.planBusy) return;
        this.planBusy = true;
        try {
          var d = await this.api("/api/learning/plans/instantiate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ template_id: t.id }),
          });
          this.showToast(d.message || "计划已激活");
          await this.loadTemplates();
          await this.loadMyPlans();
          this.planTab = "my";
        } catch (e) { this.showToast(e.message); }
        finally { this.planBusy = false; }
      },

      /* ---------- 进展记录 ---------- */
      async saveProgress() {
        var t = this.selectedPlanTask;
        if (!t || this.planBusy) return;
        var f = this.planProgressForm;
        if (!f.note && !f.minutes_spent && f.percent == null) {
          this.showToast("请填写进展内容");
          return;
        }
        this.planBusy = true;
        try {
          await this.api("/api/learning/tasks/" + t.id + "/progress", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              note: f.note || null,
              minutes_spent: f.minutes_spent || 0,
              percent: f.percent != null ? f.percent : 0,
            }),
          });
          this.showToast("进展已记录 📝");
          this.planProgressForm = { note: "", minutes_spent: null, percent: null };
          await this.refreshPlanDetail();
        } catch (e) { this.showToast(e.message); }
        finally { this.planBusy = false; }
      },

      /* ---------- 成果提交（复用打卡的压缩链路） ---------- */
      onPlanPhoto(e) {
        var f = e.target.files[0];
        if (!f) return;
        this.showToast("正在压缩图片…");
        var self = this;
        compressImage(f).then(function (result) {
          self.planSubmitForm.photoFile = blobToFile(result.blob, result.name);
          var r = new FileReader();
          r.onload = function (x) { self.planSubmitForm.photoData = x.target.result; };
          r.readAsDataURL(self.planSubmitForm.photoFile);
        }).catch(function (err) { self.showToast(err.message || "图片处理失败"); });
      },
      async submitTaskResult() {
        var t = this.selectedPlanTask;
        if (!t || this.planBusy) return;
        var f = this.planSubmitForm;
        if (!f.content.trim() && !f.photoFile) {
          this.showToast("请填写完成说明或上传成果照片");
          return;
        }
        this.planBusy = true;
        try {
          var fd = new FormData();
          fd.append("content", f.content.trim());
          if (f.photoFile) {
            fd.append("photo", f.photoFile, (f.photoFile && f.photoFile.name) || "photo.jpg");
          }
          var d = await this.api("/api/learning/tasks/" + t.id + "/submit", {
            method: "POST",
            body: fd,
          });
          this.showToast(d.message || "已提交");
          this.selectedPlanTask = null;
          await this.refreshPlanDetail();
          await this.loadPlanSummary();
          // 自动审核模式下提交即得积分/经验，刷新顶部实时积分
          try { this.user = await this.api("/api/auth/me"); } catch (e) { /* 不阻断主流程 */ }
        } catch (e) { this.showToast(e.message); }
        finally { this.planBusy = false; }
      },

      /* ---------- 实时通知：WS 主通道 + 指数退避 + 30s 轮询降级 ---------- */
      initNotifySocket() {
        if (!this.token || this._wsStarted) return;
        this._wsStarted = true;
        if (typeof WebSocket === "undefined") { this.startNotifPolling(); return; }
        this._connectWs();
      },
      _connectWs() {
        var self = this;
        var proto = location.protocol === "https:" ? "wss://" : "ws://";
        // BASE_PATH 为 app.js 顶层 const（全局词法作用域，运行时可访问）
        var url = proto + location.host + BASE_PATH + "/api/ws/notifications?token=" + encodeURIComponent(this.token);
        var ws;
        try { ws = new WebSocket(url); } catch (e) { this._wsFail(); return; }
        this._ws = ws;
        ws.onopen = function () {
          self._wsFails = 0;
          self.stopNotifPolling();   // WS 恢复后停掉降级轮询
          self.refreshUnread();
        };
        ws.onmessage = function (ev) {
          try {
            var msg = JSON.parse(ev.data);
            if (msg.type === "notification") self.onNotifyMessage(msg);
          } catch (e) { /* 忽略非 JSON 帧（ping 等） */ }
        };
        ws.onclose = function () { self._ws = null; self._wsFail(); };
        ws.onerror = function () { try { ws.close(); } catch (e) {} };
      },
      _wsFail() {
        var self = this;
        this._wsFails += 1;
        // 连续失败 3 次降级 30s 轮询，保证通知不丢
        if (this._wsFails >= 3) this.startNotifPolling();
        // 指数退避重连：1/2/4s…上限 30s
        var delay = Math.min(30, Math.pow(2, this._wsFails - 1)) * 1000;
        clearTimeout(this._retryTimer);
        this._retryTimer = setTimeout(function () { self._connectWs(); }, delay);
      },
      startNotifPolling() {
        if (this._pollTimer) return;
        var self = this;
        this.refreshUnread();
        this._pollTimer = setInterval(function () { self.refreshUnread(); }, 30000);
      },
      stopNotifPolling() {
        if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null; }
      },
      stopNotifySocket() {
        this._wsStarted = false;
        clearTimeout(this._retryTimer);
        this.stopNotifPolling();
        if (this._ws) { try { this._ws.onclose = null; this._ws.close(); } catch (e) {} this._ws = null; }
        this.notifUnread = 0;
        this.notifItems = [];
        this.showNotifPanel = false;
      },
      onNotifyMessage(msg) {
        this.notifUnread += 1;
        this.showToast("🔔 " + (msg.title || "新通知"));
        // 审核联动会加积分：任何视图都同步顶栏用户信息（积分/抽奖券等）
        this.api("/api/auth/me").then((u) => { this.user = u; }).catch(() => {});
        // 消息到达刷新当前视图（审核结果联动积分/进度）
        if (this.view === "plan") {
          if (this.isParent) this.loadParentLearning();
          else { this.loadPlanHome(); this.refreshPlanDetail(); }
        } else if (this.view === "home") {
          if (this.isParent) this.loadChildHome();
          else this.loadHome();
        }
      },
      async refreshUnread() {
        try {
          var d = await this.api("/api/learning/notifications/unread");
          this.notifUnread = d.unread || 0;
          if (this.showNotifPanel) this.notifItems = d.items || [];
        } catch (e) { /* 轮询失败静默 */ }
      },
      async openNotifPanel() {
        this.showNotifPanel = true;
        try {
          var d = await this.api("/api/learning/notifications/unread");
          this.notifUnread = d.unread || 0;
          this.notifItems = d.items || [];
        } catch (e) { this.notifItems = []; }
      },
      async markNotifRead(n) {
        if (n.read) return;
        try {
          await this.api("/api/learning/notifications/" + n.id + "/read", { method: "PATCH" });
          n.read = true;
          this.notifUnread = Math.max(0, this.notifUnread - 1);
        } catch (e) { /* 静默 */ }
      },

      /* ---------- 家长监督视图 ---------- */
      async loadParentLearning() {
        if (!this.actingChildId) return;
        await this.loadPlanConfig();
        try {
          var s = await this.api("/api/parent/learning/summary/" + this.actingChildId);
          this.parentLearning.summary = s;
        } catch (e) { this.parentLearning.summary = null; }
        try {
          var d = await this.api("/api/parent/learning/plans/" + this.actingChildId);
          this.parentLearning.plans = d.items || [];
        } catch (e) { this.parentLearning.plans = []; }
        if (this.planConfig.review_mode === "parent") {
          try {
            var p = await this.api("/api/parent/learning/submissions/pending");
            this.parentLearning.pending = p.items || [];
          } catch (e) { this.parentLearning.pending = []; }
        }
      },
      async parentReview(s, approved) {
        if (this.parentReviewBusy) return;
        this.parentReviewBusy = true;
        try {
          await this.api("/api/parent/learning/submissions/" + s.id + "/review", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ approved: approved, note: approved ? "家长确认完成" : "家长驳回，请修改后重新提交" }),
          });
          this.showToast(approved ? "已通过，孩子将获得奖励 🎉" : "已驳回");
          await this.loadParentLearning();
        } catch (e) { this.showToast(e.message); }
        finally { this.parentReviewBusy = false; }
      },
    },
  };
})();
