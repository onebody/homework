const { createApp } = Vue;

// 自动检测基础路径（支持子路径部署如 /homework/）
const BASE_PATH = (() => {
  const path = window.location.pathname;
  // 如果路径包含 /homework，则使用 /homework 作为基础路径
  const match = path.match(/^(\/homework)/);
  return match ? match[1] : '';
})();

// ---------- 认证图片渲染 ----------
// 上传目录已改为需 Bearer token 的 /api/uploads，而 <img src> 无法携带请求头，
// 因此统一改用 fetch 取 blob 再通过 objectURL 渲染。
function _revokeAuthSrc(el) {
  if (el._authObjectUrl) {
    URL.revokeObjectURL(el._authObjectUrl);
    el._authObjectUrl = null;
  }
}

async function _applyAuthSrc(el, raw) {
  _revokeAuthSrc(el);
  el._authSrcValue = raw;
  if (!raw) { el.removeAttribute("src"); return; }
  // 本地预览（data:/blob:）与普通静态资源无需鉴权，直接赋值
  if (raw.indexOf("/api/uploads/") === -1) { el.src = raw; return; }
  const target = /^https?:/.test(raw) ? raw : BASE_PATH + raw;
  const token = localStorage.getItem("token") || "";
  try {
    const res = await fetch(target, {
      headers: token ? { Authorization: "Bearer " + token } : {},
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const blob = await res.blob();
    if (el._authSrcValue !== raw) return;   // 期间绑定值已变化，丢弃本次结果
    el._authObjectUrl = URL.createObjectURL(blob);
    el.src = el._authObjectUrl;
  } catch (e) {
    // 加载失败时不抛出，避免打断渲染；手动派发 error 以触发可能的 @error 收尾
    el.removeAttribute("src");
    el.alt = "图片加载失败";
    el.dispatchEvent(new Event("error"));
  }
}

const authSrcDirective = {
  mounted(el, binding) { _applyAuthSrc(el, binding.value || ""); },
  updated(el, binding) {
    if (binding.value === binding.oldValue) return;
    _applyAuthSrc(el, binding.value || "");
  },
  unmounted(el) { _revokeAuthSrc(el); },
};

// ---------- 分页 ----------
const PAGE_SIZE = 5;   // 学生/家长端记录列表每页条数

// 分页控件：上一页/下一页 + 折叠页码 + “第 X/Y 页 · 共 N 条”，桌面与移动端共用
const Pager = {
  props: {
    page: { type: Number, default: 1 },
    pages: { type: Number, default: 1 },
    total: { type: Number, default: 0 },
  },
  emits: ["go"],
  computed: {
    // 页码窗口：总页数少时全部列出；多时保留首末页并在当前页附近展开，其余折叠为 …
    numbers() {
      const p = this.page, n = this.pages, out = [];
      const push = v => { if (out[out.length - 1] !== v) out.push(v); };
      if (n <= 5) { for (let i = 1; i <= n; i++) out.push(i); return out; }
      push(1);
      if (p > 3) push("…");
      for (let i = Math.max(2, p - 1); i <= Math.min(n - 1, p + 1); i++) push(i);
      if (p < n - 2) push("…");
      push(n);
      return out;
    },
  },
  methods: {
    go(p) {
      if (p === "…" || p < 1 || p > this.pages || p === this.page) return;
      this.$emit("go", p);
    },
  },
  template: `
    <div class="pager" v-if="total > 0">
      <button class="pg-btn" :disabled="page<=1" @click="go(page-1)">上一页</button>
      <button v-for="(n,i) in numbers" :key="i" class="pg-num"
              :class="{on: n===page, gap: n==='…'}" :disabled="n==='…'" @click="go(n)">{{ n }}</button>
      <button class="pg-btn" :disabled="page>=pages" @click="go(page+1)">下一页</button>
      <span class="pg-info">第 {{ page }}/{{ pages }} 页 · 共 {{ total }} 条</span>
    </div>`,
};

const app = createApp({
  data() {
    return {
      view: "login",
      siteTitle: "暑假作业打卡平台",   // 页面标题（后台可配置，未配置时用默认值）
      siteSlogan: "每天进步一点点，打卡赢好礼！",   // 登录页欢迎标语（同上）
      pointsRule: { normal: 10, makeup: 5 },   // 打卡分值（后台可配置，未配置时用默认值）
      authMode: "login",
      regRole: "student",
      form: { username: "", nickname: "", password: "" },
      bindForm: { child_username: "", bind_code: "" },
      bindBusy: false,
      token: localStorage.getItem("token") || "",
      user: {},

      // 双角色：家长登录后关联孩子账号
      children: [],
      actingChildId: null,        // 当前操作的孩子 id（家长态）

      streak: { current_streak: 0, longest_streak: 0, effective_checkins: 0, lottery_tickets: 0, today_checked: false, can_makeup_this_month: 3, points: 0 },
      today: { today_checked: false, can_makeup_this_month: 3 },
      photoData: "", photoFile: null,
      proofData: "", proofFile: null,
      faceData: "", faceFile: null, faceIdUrl: null, faceEnrolled: false, faceBusy: false,
      isMakeup: false, makeupDate: "", makeupReason: "",
      lat: null, lng: null, locText: "📍 获取当前位置",
      submitting: false,
      showPwdForm: false,
      passwordForm: { old_password: "", new_password: "", confirm_password: "" },
      pwdBusy: false,
      drawing: false, drawResult: null,
      // 抽奖转盘
      wheelSpinning: false, wheelRotation: 0,
      // 打卡闯关合并页子 tab
      ccTab: "checkin",
      mall: { points: 0, lottery_tickets: 0, prizes: [], redemptions: [], lottery_records: [] },
      redeemBusy: false, replaceTarget: null,   // replaceTarget: 正在为其选择替换奖品的兑换记录
      history: [],
      // 各记录列表的分页状态（每页 PAGE_SIZE 条，由后端返回 page/pages/total 回填）
      pg: {
        history: { page: 1, pages: 1, total: 0 },
        redemptions: { page: 1, pages: 1, total: 0 },
        lotteryRecords: { page: 1, pages: 1, total: 0 },
      },
      summerStart: "2026-07-01", summerEnd: "2026-08-31",
      toast: "", toastTimer: null,
      // 闯关任务
      challengeTasks: [],
      myChallengeCheckins: [],
      selectedTask: null,
      challengeCheckinContent: "",
      challengePhotoData: "",
      challengePhotoFile: null,
      challengeSubmitting: false,
    };
  },
  computed: {
    isParent() { return this.user.role === "parent"; },
    // 当前操作主体（学生=自己；家长=选中的孩子）
    subjectId() {
      return this.isParent ? this.actingChildId : this.user.id;
    },
    subjectName() {
      if (!this.isParent) return this.user.nickname;
      const c = this.children.find(x => x.student_id === this.actingChildId);
      return c ? c.nickname : "孩子";
    },
    points() { return this.mall.points != null ? this.mall.points : (this.streak.points || 0); },
    // 抽奖转盘分区：由商城奖品（非抽奖券）生成 + 一个“谢谢参与”分区
    wheelSegments() {
      const prizes = (this.mall.prizes || [])
        .filter(p => !p.is_lottery_ticket)
        .slice(0, 7)
        .map(p => ({ name: p.name, short: this.shortName(p.name), win: true }));
      const segs = prizes.slice();
      segs.push({ name: "谢谢参与", short: "谢谢参与", win: false });
      // 至少 4 个分区，转盘更好看
      while (segs.length < 4) segs.splice(segs.length - 1, 0, { name: "神秘奖励", short: "神秘奖励", win: true });
      return segs;
    },
    wheelStyle() {
      const n = this.wheelSegments.length;
      const seg = 360 / n;
      const colors = ["#ffd06b", "#7eb6ff", "#a5e3c0", "#ffb3ba", "#c3a5ff", "#ffd9a0", "#8fd6ff", "#ffc2e2"];
      const stops = [];
      for (let i = 0; i < n; i++) {
        stops.push(`${colors[i % colors.length]} ${i * seg}deg ${(i + 1) * seg}deg`);
      }
      return {
        background: `conic-gradient(${stops.join(",")})`,
        transform: `rotate(${this.wheelRotation}deg)`,
        transition: this.wheelSpinning ? "transform 4s cubic-bezier(0.2,0.8,0.25,1)" : "none",
      };
    },
  },
  mounted() {
    this.loadSiteTitle();
    if (this.token) this.bootstrap();
  },
  methods: {
    async loadSiteTitle() {
      // 公开接口无需登录；no-store 保证后台改标题后刷新即生效
      try {
        const res = await fetch(BASE_PATH + "/api/site-config", { cache: "no-store" });
        const d = await res.json();
        if (d && d.student_title) {
          this.siteTitle = d.student_title;
          document.title = d.student_title;
        }
        if (d && d.student_slogan) this.siteSlogan = d.student_slogan;
        if (d && typeof d.checkin_points === "number") this.pointsRule.normal = d.checkin_points;
        if (d && typeof d.makeup_points === "number") this.pointsRule.makeup = d.makeup_points;
      } catch (e) { /* 取不到时保持默认标题 */ }
    },
    fixUrl(url) {
      if (!url) return "";
      if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) return url;
      if (url.startsWith("/api/uploads/") || url.startsWith("/uploads/") || url.startsWith("/static/")) {
        return window.location.origin + BASE_PATH + url;
      }
      return window.location.origin + BASE_PATH + "/" + url.replace(/^\.\//, "");
    },
    async api(path, opts = {}) {
      const headers = { ...(opts.headers || {}) };
      if (this.token) headers["Authorization"] = "Bearer " + this.token;
      // no-store：切换界面时强制走网络，避免微信/iOS Safari 命中 GET 缓存显示旧数据
      const res = await fetch(BASE_PATH + path, { cache: "no-store", ...opts, headers });
      if (res.status === 401) { this.logout(); throw new Error("登录失效"); }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "请求失败");
      return data;
    },
    showToast(msg) {
      this.toast = msg;
      clearTimeout(this.toastTimer);
      this.toastTimer = setTimeout(() => (this.toast = ""), 2200);
    },
    async bootstrap() {
      try {
        this.user = await this.api("/api/auth/me");
        this.view = "home";
        if (this.isParent) {
          await this.loadChildren();
        } else {
          await this.loadHome();
        }
      } catch (e) { this.view = "login"; }
    },
    async login() {
      try {
        const d = await this.api("/api/auth/login", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: this.form.username, password: this.form.password }),
        });
        this.token = d.access_token; localStorage.setItem("token", this.token);
        this.user = d.user; this.view = "home";
        if (this.isParent) await this.loadChildren();
        else await this.loadHome();
      } catch (e) { this.showToast(e.message); }
    },
    async register() {
      try {
        const d = await this.api("/api/auth/register", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: this.form.username, nickname: this.form.nickname,
            password: this.form.password, role: this.regRole,
          }),
        });
        this.token = d.access_token; localStorage.setItem("token", this.token);
        this.user = d.user; this.view = "home";
        if (this.isParent) await this.loadChildren();
        else await this.loadHome();
      } catch (e) { this.showToast(e.message); }
    },
    async doBind() {
      if (!this.bindForm.child_username.trim() || !this.bindForm.bind_code.trim()) {
        this.showToast("请填写孩子的用户名和绑定码");
        return;
      }
      this.bindBusy = true;
      try {
        const d = await this.api("/api/parent/bind", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            child_username: this.bindForm.child_username.trim(),
            bind_code: this.bindForm.bind_code.trim(),
          }),
        });
        this.showToast(d.message || "绑定成功");
        this.bindForm = { child_username: "", bind_code: "" };
        await this.loadChildren();
        // 如果刚绑定第一个孩子，切换到首页
        if (this.children.length === 1) this.view = "home";
      } catch (e) { this.showToast(e.message); }
      finally { this.bindBusy = false; }
    },
    async unbindChild(studentId) {
      if (!confirm("确定解绑该孩子吗？解绑后需重新绑定才能代操作。")) return;
      try {
        const d = await this.api("/api/parent/unbind/" + studentId, { method: "DELETE" });
        this.showToast(d.message || "解绑成功");
        await this.loadChildren();
        if (this.children.length === 0) this.view = "home";
      } catch (e) { this.showToast(e.message); }
    },
    logout() {
      this.token = ""; localStorage.removeItem("token"); this.view = "login";
      this.form = { username: "", nickname: "", password: "" };
    },
    async changePassword() {
      const f = this.passwordForm;
      if (!f.old_password) { this.showToast("请输入原密码"); return; }
      if (f.new_password.length < 4) { this.showToast("新密码至少 4 位"); return; }
      if (f.new_password !== f.confirm_password) { this.showToast("两次密码输入不一致"); return; }
      if (f.old_password === f.new_password) { this.showToast("新密码不能与原密码相同"); return; }
      this.pwdBusy = true;
      try {
        const d = await this.api("/api/auth/password", {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ old_password: f.old_password, new_password: f.new_password }),
        });
        this.showToast(d.message || "密码修改成功");
        this.showPwdForm = false;
        this.passwordForm = { old_password: "", new_password: "", confirm_password: "" };
      } catch (e) { this.showToast(e.message); }
      finally { this.pwdBusy = false; }
    },
    async loadChildren() {
      this.children = await this.api("/api/parent/children");
      if (this.children.length === 0) {
        this.actingChildId = null;
        this.streak = { current_streak: 0, longest_streak: 0, effective_checkins: 0, lottery_tickets: 0, today_checked: false, can_makeup_this_month: 3, points: 0 };
        this.today = { today_checked: false, today_pending: false, pending_count: 0, can_makeup_this_month: 3 };
        this.mall = { points: 0, lottery_tickets: 0, prizes: [], redemptions: [], lottery_records: [] };
        this.resetPg();
        return;
      }
      this.actingChildId = this.children[0].student_id;
      await this.loadChildHome();
    },
    async selectChild(id) {
      this.actingChildId = id;
      this.resetPg();   // 切孩子后记录列表回到第 1 页
      await this.loadChildHome();
      if (this.view === "mall") await this.loadMall();
      if (this.view === "me") await this.loadHistory();
    },
    async go(v) {
      this.view = v;
      if (v === "lottery") await this.loadMall();
      if (v === "mall") await this.loadMall();
      if (v === "me") { await this.loadHistory(); if (!this.isParent) await this.loadFaceStatus(); }
      if (v === "home") {
        if (this.isParent) await this.loadChildHome();
        else await this.loadHome();
      }
      if (v === "checkin-challenge") {
        this.ccTab = "checkin";
        if (this.isParent) await this.loadChildHome();
        else await this.loadHome();
        await this.loadChallengeTasks();
      }
    },
    // 切换到闯关子 tab（数据已在 go() 中预加载，缺失时补加载）
    async switchToChallenge() {
      this.ccTab = "challenge";
      if (!this.challengeTasks.length) await this.loadChallengeTasks();
    },
    shortName(name) {
      const s = (name || "").toString();
      return s.length > 4 ? s.slice(0, 4) : s;
    },
    segLabelStyle(i) {
      const n = this.wheelSegments.length;
      const seg = 360 / n;
      const angle = (i + 0.5) * seg;
      return { transform: `translateX(-50%) rotate(${angle}deg)` };
    },
    async loadHome() {
      this.streak = await this.api("/api/checkin/streak");
      this.today = await this.api("/api/checkin/today");
    },
    async loadChildHome() {
      if (!this.actingChildId) return;
      const cs = await this.api("/api/parent/child-streak/" + this.actingChildId);
      this.streak = {
        current_streak: cs.current_streak, longest_streak: cs.longest_streak,
        effective_checkins: cs.effective_checkins, lottery_tickets: cs.lottery_tickets,
        points: cs.points, today_checked: cs.today_checked, can_makeup_this_month: 3,
      };
      this.today = { today_checked: cs.today_checked, today_pending: cs.today_pending || false, pending_count: 0, can_makeup_this_month: 3 };
    },
    onPhoto(e) {
      const f = e.target.files[0]; if (!f) return;
      this.photoFile = f;
      const r = new FileReader(); r.onload = (x) => (this.photoData = x.target.result); r.readAsDataURL(f);
    },
    onProof(e) {
      const f = e.target.files[0]; if (!f) return;
      this.proofFile = f;
      const r = new FileReader(); r.onload = (x) => (this.proofData = x.target.result); r.readAsDataURL(f);
    },
    onFaceFile(e) {
      const f = e.target.files[0]; if (!f) return;
      this.faceFile = f;
      const r = new FileReader(); r.onload = (x) => (this.faceData = x.target.result); r.readAsDataURL(f);
    },
    async loadFaceStatus() {
      try {
        const d = await this.api("/api/face/status");
        this.faceEnrolled = d.face_enrolled;
        this.faceIdUrl = this.fixUrl(d.face_id_url);
      } catch (e) { /* 忽略 */ }
    },
    async enrollFace() {
      if (this.user.role !== "student") { this.showToast("仅学生可采集人脸底图"); return; }
      if (!this.faceFile) { this.showToast("请先拍摄/选择一张正脸照"); return; }
      this.faceBusy = true;
      try {
        const fd = new FormData();
        fd.append("photo", this.faceFile);
        const d = await this.api("/api/face/enroll", { method: "POST", body: fd });
        this.faceEnrolled = true;
        this.faceIdUrl = this.fixUrl(d.face_id_url) || this.faceIdUrl;
        this.showToast(d.message || "人脸底图采集成功");
        this.faceData = ""; this.faceFile = null;
        await this.loadFaceStatus();
      } catch (e) { this.showToast(e.message); }
      finally { this.faceBusy = false; }
    },
    async unenrollFace() {
      if (!confirm("确定撤销人脸底图吗？撤销后打卡将不再做人脸比对。")) return;
      this.faceBusy = true;
      try {
        await this.api("/api/face/enroll", { method: "DELETE" });
        this.faceEnrolled = false; this.faceIdUrl = null;
        this.showToast("已撤销人脸底图");
      } catch (e) { this.showToast(e.message); }
      finally { this.faceBusy = false; }
    },
    getLocation() {
      if (!navigator.geolocation) { this.locText = "设备不支持定位"; return; }
      navigator.geolocation.getCurrentPosition(
        (p) => { this.lat = p.coords.latitude; this.lng = p.coords.longitude; this.locText = "📍 已获取位置"; },
        () => { this.locText = "定位失败，仍可提交（将标记风险）"; }
      );
    },
    async submitCheckin() {
      if (!this.photoFile) { this.showToast("请先上传作业照片"); return; }
      if (this.isMakeup && !this.makeupDate) { this.showToast("请选择补卡日期"); return; }
      if (this.isMakeup && !this.proofFile) { this.showToast("补卡需上传补充凭证"); return; }
      this.submitting = true;
      try {
        const fd = new FormData();
        fd.append("photo", this.photoFile);
        if (this.proofFile) fd.append("proof", this.proofFile);
        if (this.lat != null) fd.append("location_lat", this.lat);
        if (this.lng != null) fd.append("location_lng", this.lng);
        fd.append("check_type", this.isMakeup ? "makeup" : "normal");
        if (this.isMakeup) {
          fd.append("makeup_for_date", this.makeupDate);
          if (this.makeupReason) fd.append("makeup_reason", this.makeupReason);
        }
        if (this.isParent) {
          fd.append("child_id", this.actingChildId);
          await this.api("/api/parent/checkin", { method: "POST", body: fd });
        } else {
          await this.api("/api/checkin", { method: "POST", body: fd });
        }
        this.showToast(this.isMakeup ? "补卡已提交，等待管理员审核" : (this.isParent ? "打卡已提交，等待管理员审核" : "打卡已提交，等待管理员审核 📝"));
        this.photoData = ""; this.photoFile = null; this.proofData = ""; this.proofFile = null;
        this.isMakeup = false; this.makeupDate = ""; this.makeupReason = "";
        if (this.isParent) await this.loadChildHome();
        else await this.loadHome();
        this.view = "home";
      } catch (e) { this.showToast(e.message); }
      finally { this.submitting = false; }
    },

    /* ==================== 分页辅助 ==================== */
    // 目标页码：显式传入优先（非法值如事件对象会被忽略），否则沿用当前页
    pageOf(key, page) {
      const p = Number(page);
      return Number.isInteger(p) && p >= 1 ? p : this.pg[key].page;
    },
    pgq(key, page) { return `page=${this.pageOf(key, page)}&size=${PAGE_SIZE}`; },
    applyPg(key, d) {
      this.pg[key] = { page: d.page || 1, pages: d.pages || 1, total: d.total || 0 };
    },
    resetPg() {
      this.pg.history = { page: 1, pages: 1, total: 0 };
      this.pg.redemptions = { page: 1, pages: 1, total: 0 };
      this.pg.lotteryRecords = { page: 1, pages: 1, total: 0 };
    },

    /* ============ 积分商城 ============ */
    async loadMall() {
      try {
        const d = this.isParent
          ? await this.api("/api/parent/mall/" + this.actingChildId)
          : await this.api("/api/mall");
        // 逐属性赋值，保持 Vue 3 响应式追踪嵌套数组的变更
        this.mall.points = d.points;
        this.mall.lottery_tickets = d.lottery_tickets;
        this.mall.prizes = d.prizes || [];
        this.streak.lottery_tickets = d.lottery_tickets;
        this.streak.points = d.points;
      } catch (e) { this.showToast(e.message); }
      // 两个记录列表各自分页拉取（沿用当前页码）
      await this.loadRedemptions();
      await this.loadLotteryRecords();
    },
    // 兑换记录（分页）
    async loadRedemptions(page) {
      if (this.isParent && !this.actingChildId) { this.mall.redemptions = []; return; }
      try {
        const url = this.isParent
          ? `/api/parent/redemptions/${this.actingChildId}?`
          : "/api/redemptions?";
        const d = await this.api(url + this.pgq("redemptions", page));
        this.mall.redemptions = d.items || [];
        this.applyPg("redemptions", d);
      } catch (e) { this.mall.redemptions = []; }
    },
    // 抽奖记录（分页）
    async loadLotteryRecords(page) {
      if (this.isParent && !this.actingChildId) { this.mall.lottery_records = []; return; }
      try {
        const url = this.isParent
          ? `/api/parent/lottery/${this.actingChildId}/records?`
          : "/api/lottery/records?";
        const d = await this.api(url + this.pgq("lotteryRecords", page));
        this.mall.lottery_records = d.items || [];
        this.applyPg("lotteryRecords", d);
      } catch (e) { this.mall.lottery_records = []; }
    },
    canRedeem(p) {
      if (p.is_lottery_ticket) return this.points >= p.cost_points;
      if (p.stock === 0) return false;
      return this.points >= p.cost_points;
    },
    async doRedeem(p) {
      if (this.redeemBusy) return;
      if (this.points < p.cost_points) { this.showToast("积分不足"); return; }
      if (!p.is_lottery_ticket && p.stock === 0) { this.showToast("该奖品已兑完"); return; }
      this.redeemBusy = true;
      try {
        const opts = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prize_id: p.id }) };
        const result = this.isParent
          ? await this.api("/api/parent/redeem?child_id=" + this.actingChildId, opts)
          : await this.api("/api/redeem", opts);
        if (result && result.is_lottery_ticket) {
          this.showToast(`兑换成功！获得 ${p.ticket_qty || 1} 张抽奖券 🎫`);
        } else {
          this.showToast("兑换成功！🎁");
        }
        await this.loadMall();
        await this.loadRedemptions(1);   // 新兑换记录在第 1 页
      } catch (e) { this.showToast(e.message); }
      finally { this.redeemBusy = false; }
    },
    openReplace(rec) {
      this.replaceTarget = rec;
    },
    cancelReplace() {
      this.replaceTarget = null;
    },
    async confirmReplace(newPrize) {
      if (!this.replaceTarget) return;
      try {
        const opts = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ new_prize_id: newPrize.id }) };
        if (this.isParent) {
          await this.api("/api/parent/redeem/" + this.replaceTarget.id + "/replace", opts);
        } else {
          await this.api("/api/redeem/" + this.replaceTarget.id + "/replace", opts);
        }
        this.showToast("已替换为「" + newPrize.name + "」");
        this.replaceTarget = null;
        await this.loadMall();
        await this.loadRedemptions(1);
      } catch (e) { this.showToast(e.message); }
    },

    /* ============ 抽奖（转盘） ============ */
    async loadLottery() { await this.loadMall(); },
    async draw() {
      if (this.wheelSpinning) return;
      if (this.mall.lottery_tickets <= 0) { this.showToast("暂无可用抽奖券，先去连续打卡攻资格吧"); return; }
      this.wheelSpinning = true; this.drawResult = null; this.drawing = true;
      try {
        const d = this.isParent
          ? await this.api("/api/parent/lottery/" + this.actingChildId + "/draw", { method: "POST" })
          : await this.api("/api/lottery/draw", { method: "POST" });
        // 定位目标分区：中奖时匹配奖品名，未中奖落在“谢谢参与”
        const segs = this.wheelSegments;
        const n = segs.length;
        const seg = 360 / n;
        let idx = d.is_win
          ? segs.findIndex(s => s.win && s.name === d.prize_name)
          : segs.findIndex(s => !s.win);
        if (idx < 0) idx = d.is_win ? segs.findIndex(s => s.win) : n - 1;
        if (idx < 0) idx = 0;
        // 目标旋转角度：5 圈 + 使目标分区中心对准顶部指针
        const target = 360 * 5 + (360 - (idx + 0.5) * seg);
        const base = this.wheelRotation - (this.wheelRotation % 360);
        this.wheelRotation = base + target;
        // 等待转盘动画结束
        await new Promise(r => setTimeout(r, 4100));
        this.drawResult = d;
        this.streak.lottery_tickets = d.tickets_left;
        await this.loadMall();
        await this.loadLotteryRecords(1);   // 新抽奖记录在第 1 页
        if (d.is_win) this.showToast("🎉 恭喜抽中 " + d.prize_name);
        else this.showToast("本次未中奖，再接再厉");
      } catch (e) { this.showToast(e.message); }
      finally { this.wheelSpinning = false; this.drawing = false; }
    },

    async loadHistory(page) {
      if (this.isParent) {
        this.history = [];
        this.pg.history = { page: 1, pages: 1, total: 0 };
      } else {
        const d = await this.api("/api/checkin/history?" + this.pgq("history", page));
        this.history = d.items || [];
        this.applyPg("history", d);
      }
    },
    async openReport() {
      const path = this.isParent
        ? "/api/parent/child-report/" + this.actingChildId + "/html"
        : "/api/report/me/html";
      // 报告 HTML 接口需 Bearer 认证，window.open 无法携带请求头，
      // 故先同步打开空窗口（规避弹窗拦截），再用带 token 的请求拉取后填充。
      const win = window.open("", "_blank");
      try {
        const res = await fetch(BASE_PATH + path, {
          cache: "no-store",
          headers: this.token ? { Authorization: "Bearer " + this.token } : {},
        });
        if (res.status === 401) { if (win) win.close(); this.logout(); return; }
        if (!res.ok) throw new Error("HTTP " + res.status);
        const html = await res.text();
        if (win) { win.document.open(); win.document.write(html); win.document.close(); }
      } catch (e) {
        if (win) win.close();
        this.showToast("报告加载失败");
      }
    },
    catName(c) { return { stationery: "文具", outdoor: "户外", interest: "兴趣" }[c] || c; },
    fmt(s) { return (s || "").replace("T", " ").slice(0, 16); },
    fmtDate(s) { return (s || "").replace("T", " ").slice(0, 10); },

    /* ============ 闯关任务 ============ */
    async loadChallengeTasks() {
      try {
        this.challengeTasks = await this.api("/api/challenge/tasks");
        // 同时加载我的打卡记录
        this.myChallengeCheckins = await this.api("/api/challenge/my-checkins");
      } catch (e) {
        console.error("加载闯关任务失败:", e);
      }
    },

    async openTaskDetail(task) {
      this.selectedTask = task;
      this.challengeCheckinContent = "";
      this.challengePhotoData = "";
      this.challengePhotoFile = null;
    },

    onChallengePhoto(e) {
      const file = e.target.files[0];
      if (!file) return;
      this.challengePhotoFile = file;
      const reader = new FileReader();
      reader.onload = (ev) => {
        this.challengePhotoData = ev.target.result;
      };
      reader.readAsDataURL(file);
    },

    async submitChallengeCheckin() {
      if (!this.selectedTask) return;
      if (!this.challengePhotoFile) {
        this.showToast("请上传完成照片");
        return;
      }
      this.challengeSubmitting = true;
      try {
        // 先上传附件
        const fd = new FormData();
        fd.append("file", this.challengePhotoFile);
        const uploadResult = await this.api("/api/challenge/upload", {
          method: "POST",
          body: fd
        });

        // 提交打卡
        const checkinData = new FormData();
        checkinData.append("content", this.challengeCheckinContent);
        checkinData.append("attachments", JSON.stringify([uploadResult.url]));
        
        await this.api(`/api/challenge/tasks/${this.selectedTask.id}/checkin-with-content`, {
          method: "POST",
          body: checkinData
        });

        this.showToast("打卡已提交，等待审核");
        this.selectedTask = null;
        await this.loadChallengeTasks();
      } catch (e) {
        this.showToast(e.message);
      } finally {
        this.challengeSubmitting = false;
      }
    },
  },
});

app.directive("auth-src", authSrcDirective);
app.component("pager", Pager);
app.mount("#app");
