const { createApp } = Vue;

// 自动检测基础路径（支持子路径部署如 /homework/）
const BASE_PATH = (() => {
  const path = window.location.pathname;
  // 如果路径包含 /homework，则使用 /homework 作为基础路径
  const match = path.match(/^(\/homework)/);
  return match ? match[1] : '';
})();

createApp({
  data() {
    return {
      view: "login",
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
      mall: { points: 0, lottery_tickets: 0, prizes: [], redemptions: [], lottery_records: [] },
      redeemBusy: false, replaceTarget: null,   // replaceTarget: 正在为其选择替换奖品的兑换记录
      history: [],
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
  },
  mounted() {
    if (this.token) this.bootstrap();
  },
  methods: {
    fixUrl(url) {
      if (!url) return "";
      if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) return url;
      if (url.startsWith("/uploads/") || url.startsWith("/static/")) {
        return window.location.origin + BASE_PATH + url;
      }
      return window.location.origin + BASE_PATH + "/" + url.replace(/^\.\//, "");
    },
    async api(path, opts = {}) {
      const headers = { ...(opts.headers || {}) };
      if (this.token) headers["Authorization"] = "Bearer " + this.token;
      const res = await fetch(BASE_PATH + path, { ...opts, headers });
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
        return;
      }
      this.actingChildId = this.children[0].student_id;
      await this.loadChildHome();
    },
    async selectChild(id) {
      this.actingChildId = id;
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
      if (v === "challenge") await this.loadChallengeTasks();
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
        this.mall.redemptions = d.redemptions || [];
        this.mall.lottery_records = d.lottery_records || [];
        this.streak.lottery_tickets = d.lottery_tickets;
        this.streak.points = d.points;
      } catch (e) { this.showToast(e.message); }
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
      } catch (e) { this.showToast(e.message); }
    },

    /* ============ 抽奖（与积分并存） ============ */
    async loadLottery() { await this.loadMall(); },
    async draw() {
      this.drawing = true; this.drawResult = null;
      try {
        const d = this.isParent
          ? await this.api("/api/parent/lottery/" + this.actingChildId + "/draw", { method: "POST" })
          : await this.api("/api/lottery/draw", { method: "POST" });
        this.drawResult = d;
        this.streak.lottery_tickets = d.tickets_left;
        await this.loadMall();
      } catch (e) { this.showToast(e.message); }
      finally { this.drawing = false; }
    },

    async loadHistory() {
      if (this.isParent) {
        this.history = [];
      } else {
        this.history = await this.api("/api/checkin/history");
      }
    },
    openReport() {
      if (this.isParent) {
        window.open("/api/parent/child-report/" + this.actingChildId + "/html", "_blank");
      } else {
        window.open("/api/report/me/html", "_blank");
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
}).mount("#app");
