const { createApp } = Vue;

// 自动检测基础路径（支持子路径部署如 /homework/）
const BASE_PATH = (() => {
  const path = window.location.pathname;
  const match = path.match(/^(\/homework)/);
  return match ? match[1] : '';
})();

createApp({
  data() {
    return {
      token: localStorage.getItem("admin_token") || "",
      loginForm: { username: "", password: "" },
      showPwdForm: false,
      passwordForm: { old_password: "", new_password: "", confirm_password: "" },
      pwdBusy: false,
      view: "dashboard",
      stats: null, prizes: [], users: [], checkins: [], redeems: [],
      dash: null, dashLoading: false,
      challengeTasks: [], challengeCheckins: [], viewingCheckinsTask: null,
      editing: null, reviewing: null, reviewingRedeem: null, reviewingChallenge: null,
      challengeEditing: null,
      checkinFilter: "pending", redeemFilter: "all", challengeCheckinFilter: "pending",
      pendingCount: 0, redeemPendingCount: 0, challengePendingCount: 0,
      toast: "", toastTimer: null,

      // ========== 图片查看器 ==========
      viewer: {
        visible: false,          // 弹窗是否显示
        images: [],              // [{src, thumb?, caption?}] 图片列表
        index: 0,                // 当前索引
        zoom: 1,                 // 缩放比例
        rotate: 0,               // 旋转角度
        loading: false,          // 大图加载中
        showUpload: false,       // 是否展示上传面板
        uploadList: [],          // 待上传文件列表
        uploading: false,        // 上传中
        // 触摸滑动
        touchStartX: 0,
        touchStartY: 0,
        swiping: false,
      },
    };
  },
  mounted() { if (this.token) this.bootstrap(); },
  computed: {
    // 当前图片
    currentImage() {
      const v = this.viewer;
      return v.images[v.index] || null;
    },
    // 当前图片 URL（优先大图 src，降级 thumb）
    currentSrc() {
      return this.currentImage?.src || this.currentImage?.thumb || "";
    },
    // 总图片数
    imageCount() {
      return this.viewer.images.length;
    },
    // 是否第一张 / 最后一张
    isFirst() { return this.viewer.index <= 0; },
    isLast() { return this.viewer.index >= this.imageCount - 1; },
    // 手机端顶栏：当前模块中文名
    currentViewName() {
      return {
        dashboard: "数据概览",
        prizes: "奖品管理",
        users: "用户管理",
        redeems: "兑换审核",
        checkins: "打卡审核",
        challenges: "闯关任务",
      }[this.view] || "";
    },
  },
  methods: {
    /* ==================== 基础 API ==================== */
    async api(path, opts = {}) {
      const headers = { ...(opts.headers || {}) };
      if (this.token) headers["Authorization"] = "Bearer " + this.token;
      const res = await fetch(BASE_PATH + path, { ...opts, headers });
      if (res.status === 401) { this.logout(); throw new Error("登录失效"); }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "请求失败");
      return data;
    },
    showToast(m) { this.toast = m; clearTimeout(this.toastTimer); this.toastTimer = setTimeout(() => (this.toast = ""), 2200); },
    // 卡片缩略图地址补全（模板中无法调用全局 fixUrl，这里暴露为实例方法）
    thumbUrl(url) { return fixUrl(url); },
    async bootstrap() {
      try { await this.loadAll(); }
      catch (e) { this.logout(); }
    },
    async login() {
      try {
        const d = await this.api("/api/auth/login", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.loginForm),
        });
        if (d.user.role !== "admin") throw new Error("该账号不是管理员");
        this.token = d.access_token; localStorage.setItem("admin_token", this.token);
        await this.loadAll();
      } catch (e) { this.showToast(e.message); }
    },
    logout() { this.token = ""; localStorage.removeItem("admin_token"); },
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
    async loadAll() {
      this.stats = await this.api("/api/admin/stats");
      this.prizes = await this.api("/api/admin/prizes");
      this.users = await this.api("/api/admin/users");
      await this.loadCheckins();
      await this.loadChallengeTasks();
      await this.refreshDashboard();
    },
    async refreshDashboard() {
      this.dashLoading = true;
      try {
        this.dash = await this.api("/api/admin/dashboard");
        this.stats = this.dash; // 兼容原有引用
        this.$nextTick(() => this.renderCharts());
      } catch (e) { /* 静默失败 */ }
      finally { this.dashLoading = false; }
    },
    renderCharts() {
      if (!this.dash || typeof Chart === 'undefined') return;
      // 销毁旧图表
      if (this._trendChart) { this._trendChart.destroy(); this._trendChart = null; }
      if (this._pieChart) { this._pieChart.destroy(); this._pieChart = null; }
      if (this._barChart) { this._barChart.destroy(); this._barChart = null; }

      const trendEl = this.$refs.trendChart;
      const pieEl = this.$refs.pieChart;
      const barEl = this.$refs.barChart;

      // 近 30 天打卡趋势折线图
      if (trendEl && this.dash.trend_30d) {
        this._trendChart = new Chart(trendEl, {
          type: 'line',
          data: {
            labels: this.dash.trend_30d.map(t => t.date.slice(5)),
            datasets: [{
              label: '打卡次数',
              data: this.dash.trend_30d.map(t => t.count),
              borderColor: '#2f80ed',
              backgroundColor: 'rgba(47,128,237,0.1)',
              fill: true, tension: 0.3, pointRadius: 2,
            }]
          },
          options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
        });
      }

      // 用户类型分布饼图
      if (pieEl && this.dash.user_distribution) {
        const ud = this.dash.user_distribution;
        this._pieChart = new Chart(pieEl, {
          type: 'doughnut',
          data: {
            labels: ['学生', '家长', '管理员'],
            datasets: [{ data: [ud.student, ud.parent, ud.admin], backgroundColor: ['#2f80ed', '#27ae60', '#e67e22'] }]
          },
          options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
      }

      // 奖品兑换类别分布柱状图
      if (barEl && this.dash.prize_distribution) {
        const pd = this.dash.prize_distribution;
        const catMap = { stationery: '文具', outdoor: '户外', interest: '兴趣' };
        const labels = Object.keys(pd).map(k => catMap[k] || k);
        const values = Object.values(pd);
        this._barChart = new Chart(barEl, {
          type: 'bar',
          data: {
            labels,
            datasets: [{ label: '兑换次数', data: values, backgroundColor: ['#9b59b6', '#1abc9c', '#f39c12'] }]
          },
          options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
        });
      }
    },
    formatUptime(sec) {
      if (!sec) return '-';
      const d = Math.floor(sec / 86400);
      const h = Math.floor((sec % 86400) / 3600);
      const m = Math.floor((sec % 3600) / 60);
      if (d > 0) return `${d}天${h}小时`;
      if (h > 0) return `${h}小时${m}分`;
      return `${m}分钟`;
    },
    exportStats() {
      if (!this.dash) { this.showToast('无数据可导出'); return; }
      const d = this.dash;
      const lines = [
        '暑假作业打卡系统 - 统计报表',
        `导出时间: ${new Date().toLocaleString()}`,
        '---',
        `总注册用户: ${d.total_users} (学生 ${d.total_students} / 家长 ${d.total_parents})`,
        `本月活跃用户: ${d.monthly_active}`,
        `今日新增打卡: ${d.today_checkins}`,
        `本月积分发放: ${d.monthly_points_issued}`,
        `待审核打卡: ${d.pending_checkins}`,
        `待处理兑换: ${d.pending_redemptions}`,
        `最高连续打卡: ${d.max_streak_month} 天`,
        `日均打卡次数: ${d.avg_daily_checkins}`,
        `有效打卡总数: ${d.effective_checkins}`,
        `绑定关系: ${d.bindings}`,
        `位置异常: ${d.geo_risk_checkins}`,
        `统计窗口: ${d.summer_window}`,
      ];
      const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `打卡统计_${new Date().toISOString().slice(0,10)}.txt`;
      a.click();
      this.showToast('已导出统计报表');
    },
    async loadPendingCount() {
      try {
        const d = await this.api("/api/admin/checkins/pending-count");
        this.pendingCount = d.count || 0;
      } catch (e) { this.pendingCount = 0; }
    },
    async loadCheckins() {
      try {
        const all = await this.api("/api/admin/checkins");
        if (this.checkinFilter === "pending") {
          this.checkins = all.filter(c => c.review_status === "pending");
        } else {
          this.checkins = all;
        }
        this.pendingCount = all.filter(c => c.review_status === "pending").length;
      } catch (e) { this.checkins = []; }
    },
    async loadRedeems() {
      try {
        const qs = this.redeemFilter !== 'all' ? `?status=${this.redeemFilter}` : '';
        const items = await this.api("/api/admin/redemptions" + qs);
        this.redeems = items;
        // 计算待核实数量
        this.redeemPendingCount = items.filter(r => r.status === 'pending').length;
      }
      catch (e) { this.redeems = []; this.redeemPendingCount = 0; }
      this.view = "redeems";
    },
    openRedeemReview(record, status) {
      this.reviewingRedeem = { record, status, note: "" };
    },
    async submitRedeemReview() {
      if (!this.reviewingRedeem) return;
      const { record, status, note } = this.reviewingRedeem;
      try {
        await this.api(`/api/admin/redemptions/${record.id}/review`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status, note }),
        });
        this.showToast(status === 'approved' ? "已兑现" : "已拒绝");
        this.reviewingRedeem = null;
        await this.loadRedeems();
        this.stats = await this.api("/api/admin/stats");
      } catch (e) {
        this.showToast(e.message || "操作失败");
      }
    },

    /* ==================== 奖品 CRUD ==================== */
    openAdd() { this.editing = { name: "", description: "", category: "stationery", probability: 0.1, stock: -1, status: "on", cost_points: 0, is_lottery_ticket: false, ticket_qty: 1 }; },
    openEdit(p) { this.editing = { ...p, cost_points: p.cost_points || 0, is_lottery_ticket: !!p.is_lottery_ticket, ticket_qty: p.ticket_qty || 1 }; },
    async savePrize() {
      try {
        if (this.editing.id) {
          await this.api("/api/admin/prizes/" + this.editing.id, {
            method: "PUT", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(this.editing),
          });
        } else {
          await this.api("/api/admin/prizes", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(this.editing),
          });
        }
        this.editing = null; await this.loadAll(); this.showToast("已保存");
      } catch (e) { this.showToast(e.message); }
    },
    async del(p) {
      if (!confirm("确认删除奖品【" + p.name + "】？")) return;
      try { await this.api("/api/admin/prizes/" + p.id, { method: "DELETE" }); await this.loadAll(); }
      catch (e) { this.showToast(e.message); }
    },
    catName(c) { return { stationery: "文具", outdoor: "户外", interest: "兴趣" }[c] || c; },
    roleName(r) { return { student: "学生", parent: "家长", admin: "管理员" }[r] || r; },
    sceneName(s) { return { pass: "通过", warn: "需复核", pending: "待审" }[s] || s; },

    openReview(checkin, status) {
      this.reviewing = { checkin, status, note: "" };
    },
    async submitReview() {
      if (!this.reviewing) return;
      try {
        await this.api(`/api/admin/checkins/${this.reviewing.checkin.id}/review`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            status: this.reviewing.status,
            note: this.reviewing.note,
          }),
        });
        this.showToast(this.reviewing.status === "approved" ? "已通过" : "已拒绝");
        this.reviewing = null;
        await this.loadCheckins();
        this.stats = await this.api("/api/admin/stats");
      } catch (e) {
        this.showToast(e.message || "操作失败");
      }
    },

    /* ==================== 图片查看器核心方法 ==================== */

    /**
     * 打开查看器 — 从单张图片开始
     * @param {string|object} img - 图片 URL 或 {src, thumb, caption} 对象
     * @param {Array} [allImages] - 同组所有图片列表（用于翻页）
     * @param {number} [startIdx=0] - 起始索引
     */
    openViewer(img, allImages, startIdx) {
      const v = this.viewer;
      // 构建标准化图片列表
      let images = [];
      if (allImages && allImages.length > 0) {
        images = allImages.map(normalizeImg);
      } else {
        images = [normalizeImg(img)];
      }
      // 确定起始位置
      let idx = startIdx || 0;
      if (allImages && allImages.length === 0 && img) idx = 0;
      if (typeof img === "string" && allImages) {
        const found = allImages.findIndex(i =>
          (typeof i === "string" && i === img) || i?.src === img || i?.thumb === img);
        if (found >= 0) idx = found;
      }

      v.visible = true;
      v.images = images;
      v.index = Math.min(idx, images.length - 1);
      v.zoom = 1;
      v.rotate = 0;
      v.loading = false;
      v.showUpload = false;
      document.body.style.overflow = "hidden";
      this.$nextTick(() => {
        const el = document.querySelector(".viewer-overlay");
        if (el) el.focus();
      });
    },

    /** 关闭查看器 */
    closeViewer() {
      this.viewer.visible = false;
      this.viewer.images = [];
      this.viewer.index = 0;
      this.viewer.zoom = 1;
      this.viewer.rotate = 0;
      this.viewer.showUpload = false;
      this.viewer.uploadList = [];
      document.body.style.overflow = "";
    },

    /** 上一张 */
    prevImage() {
      if (this.isFirst) return;
      this.viewer.index--;
      this.resetTransform();
    },

    /** 下一张 */
    nextImage() {
      if (this.isLast) return;
      this.viewer.index++;
      this.resetTransform();
    },

    /** 重置缩放/旋转 */
    resetTransform() {
      this.viewer.zoom = 1;
      this.viewer.rotate = 0;
    },

    /** 放大 */
    zoomIn() {
      this.viewer.zoom = Math.min(this.viewer.zoom + 0.5, 5);
    },

    /** 缩小 */
    zoomOut() {
      this.viewer.zoom = Math.max(this.viewer.zoom - 0.5, 0.25);
    },

    /** 左旋 90° */
    rotateLeft() {
      this.viewer.rotate -= 90;
    },

    /** 右旋 90° */
    rotateRight() {
      this.viewer.rotate += 90;
    },

    /** 重置视图（缩放+旋转归零） */
    resetView() {
      this.viewer.zoom = 1;
      this.viewer.rotate = 0;
    },

    /** 键盘事件处理 */
    onViewerKeydown(e) {
      switch (e.key) {
        case "Escape": this.closeViewer(); break;
        case "ArrowLeft": this.prevImage(); break;
        case "ArrowRight": this.nextImage(); break;
        case "+": case "=": this.zoomIn(); break;
        case "-": this.zoomOut(); break;
        case "r": case "R": this.rotateRight(); break;
      }
    },

    /* ---- 触摸滑动 ---- */

    onTouchStart(e) {
      const t = e.touches[0];
      this.viewer.touchStartX = t.clientX;
      this.viewer.touchStartY = t.clientY;
      this.viewer.swiping = false;
    },

    onTouchMove(e) {
      if (e.touches.length !== 1) return;
      const dx = e.touches[0].clientX - this.viewer.touchStartX;
      const dy = Math.abs(e.touches[0].clientY - this.viewer.touchStartY);
      if (Math.abs(dx) > 30 && dy < 50) {
        this.viewer.swiping = true;
      }
    },

    onTouchEnd(e) {
      if (!this.viewer.swiping) return;
      const dx = e.changedTouches[0].clientX - this.viewer.touchStartX;
      if (dx < -60) this.nextImage();
      else if (dx > 60) this.prevImage();
      this.viewer.swiping = false;
    },

    /* ---- 图片加载 ---- */

    onImgLoad() {
      this.viewer.loading = false;
    },

    onImgError() {
      this.viewer.loading = false;
    },

    onIndexChanged() {
      this.viewer.loading = true;
      this.resetTransform();
      // 自动聚焦以支持键盘事件
      this.$nextTick(() => {
        const el = document.querySelector(".viewer-overlay");
        if (el) el.focus();
      });
    },

    /** 鼠标滚轮缩放 */
    onWheel(e) {
      e.preventDefault();
      if (e.deltaY < 0) this.zoomIn();
      else if (e.deltaY > 0) this.zoomOut();
    },

    /* ---- 上传功能 ---- */

    toggleUpload() {
      this.viewer.showUpload = !this.viewer.showUpload;
      this.viewer.uploadList = [];
    },

    onUploadFiles(e) {
      const files = Array.from(e.target.files || []);
      if (files.length === 0) return;
      // 过滤非图片
      const imgs = files.filter(f => f.type.startsWith("image/"));
      if (imgs.length < files.length) {
        this.showToast("已过滤非图片文件");
      }
      // 预览 + 存储原始 File
      imgs.forEach(f => {
        const reader = new FileReader();
        reader.onload = (ev) => {
          this.viewer.uploadList.push({
            file: f,
            name: f.name,
            preview: ev.target.result,
            size: formatSize(f.size),
          });
        };
        reader.readAsDataURL(f);
      });
      e.target.value = "";
    },

    removeUploadItem(idx) {
      this.viewer.uploadList.splice(idx, 1);
    },

    clearUploadList() {
      this.viewer.uploadList = [];
    },

    async doUpload() {
      const list = this.viewer.uploadList;
      if (list.length === 0) {
        this.showToast("请先选择图片"); return;
      }
      this.viewer.uploading = true;
      let okCount = 0;
      for (const item of list) {
        try {
          const fd = new FormData();
          fd.append("photo", item.file);
          const res = await fetch("/api/checkin/upload", {
            method: "POST",
            headers: { "Authorization": "Bearer " + this.token },
            body: fd,
          });
          if (res.ok) {
            const data = await res.json().catch(() => ({}));
            // 将上传成功的新图追加到当前查看列表
            const url = data.photo_url || data.photo_path || data.url;
            if (url) {
              this.viewer.images.push(normalizeImg(url));
            }
            okCount++;
          }
        } catch (err) {
          console.error("upload error:", err);
        }
      }
      this.viewer.uploading = false;
      this.viewer.showUpload = false;
      this.viewer.uploadList = [];
      this.showToast(`成功上传 ${okCount}/${list.length} 张图片`);
    },

    /**
     * 从打卡记录中提取该用户所有照片，打开查看器并定位到当前行
     */
    viewCheckinPhoto(checkin, allCheckins) {
      // 收集同用户的照片作为多图列表
      let images = [];
      let startIndex = 0;
      if (checkin.photo || checkin.photo_url) {
        images = (allCheckins || [checkin])
          .filter(c => c.photo || c.photo_url)
          .map(c => ({
            src: c.photo_url || fixUrl(c.photo),
            thumb: c.photo_url || fixUrl(c.photo),
            caption: `${c.check_date} ${c.check_type === "makeup" ? "补卡" : "正常"}打卡`,
          }));
        const targetSrc = checkin.photo_url || fixUrl(checkin.photo);
        startIndex = images.findIndex(i => i.src === targetSrc);
        if (startIndex < 0) startIndex = 0;
      }
      if (images.length === 0) {
        this.showToast("该记录无照片"); return;
      }
      this.openViewer(images[startIndex], images, startIndex);
    },

    /* ==================== 闯关任务管理 ==================== */
    async loadChallengeTasks() {
      try {
        this.challengeTasks = await this.api("/api/challenge/admin/tasks");
        this.challengePendingCount = this.challengeTasks.reduce((sum, t) => sum + (t.pending_reviews || 0), 0);
      } catch (e) {
        this.challengeTasks = [];
        this.showToast("加载闯关任务失败：" + e.message);
      }
    },

    openChallengeForm(task) {
      if (task) {
        this.challengeEditing = {
          id: task.id,
          name: task.name,
          description: task.description || "",
          sort_order: task.sort_order,
          reward_points: task.reward_points,
          status: task.status,
          unlock_at: task.unlock_at ? task.unlock_at.slice(0, 16) : "",
          unlock_condition: task.unlock_condition || ""
        };
      } else {
        this.challengeEditing = {
          name: "",
          description: "",
          sort_order: 0,
          reward_points: 10,
          status: "locked",
          unlock_at: "",
          unlock_condition: ""
        };
      }
    },

    async saveChallengeTask() {
      const data = new FormData();
      data.append("name", this.challengeEditing.name);
      data.append("description", this.challengeEditing.description || "");
      data.append("sort_order", this.challengeEditing.sort_order || 0);
      data.append("reward_points", this.challengeEditing.reward_points || 0);
      data.append("status", this.challengeEditing.status);
      if (this.challengeEditing.unlock_at) {
        data.append("unlock_at", this.challengeEditing.unlock_at);
      }
      data.append("unlock_condition", this.challengeEditing.unlock_condition || "");

      try {
        if (this.challengeEditing.id) {
          await this.api(`/api/challenge/admin/tasks/${this.challengeEditing.id}`, {
            method: "PUT",
            body: data
          });
          this.showToast("任务已更新");
        } else {
          await this.api("/api/challenge/admin/tasks", {
            method: "POST",
            body: data
          });
          this.showToast("任务已创建");
        }
        this.challengeEditing = null;
        await this.loadChallengeTasks();
      } catch (e) {
        this.showToast("保存失败：" + e.message);
      }
    },

    async unlockTask(task) {
      if (!confirm(`确认开放任务"${task.name}"？`)) return;
      try {
        await this.api(`/api/challenge/admin/tasks/${task.id}/unlock`, {
          method: "POST"
        });
        this.showToast("任务已开放");
        await this.loadChallengeTasks();
      } catch (e) {
        this.showToast("操作失败：" + e.message);
      }
    },

    async deleteTask(task) {
      if (!confirm(`确认删除任务"${task.name}"？此操作将同时删除所有打卡记录，不可恢复！`)) return;
      try {
        await this.api(`/api/challenge/admin/tasks/${task.id}`, {
          method: "DELETE"
        });
        this.showToast("任务已删除");
        await this.loadChallengeTasks();
      } catch (e) {
        this.showToast("删除失败：" + e.message);
      }
    },

    async viewChallengeCheckins(task) {
      this.viewingCheckinsTask = task;
      this.challengeCheckinFilter = "pending";
      await this.loadChallengeCheckins(task.id);
    },

    async loadChallengeCheckins(taskId) {
      try {
        const params = new URLSearchParams();
        params.append("task_id", taskId);
        if (this.challengeCheckinFilter === "pending") {
          params.append("status", "pending");
        }
        this.challengeCheckins = await this.api(`/api/challenge/admin/checkins?${params}`);
      } catch (e) {
        this.challengeCheckins = [];
        this.showToast("加载打卡记录失败：" + e.message);
      }
    },

    openChallengeReview(checkin, action) {
      this.reviewingChallenge = {
        checkin: checkin,
        action: action,
        note: ""
      };
    },

    async submitChallengeReview() {
      if (!this.reviewingChallenge) return;
      const { checkin, action, note } = this.reviewingChallenge;

      try {
        await this.api(`/api/challenge/admin/checkins/${checkin.id}/review`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action, note })
        });

        this.showToast(action === "approve" ? "已通过" : "已拒绝");
        this.reviewingChallenge = null;

        if (this.viewingCheckinsTask) {
          await this.loadChallengeCheckins(this.viewingCheckinsTask.id);
        }
        await this.loadChallengeTasks();
      } catch (e) {
        this.showToast("审核失败：" + e.message);
      }
    },

    viewChallengeAttachments(checkin) {
      if (!checkin.attachments || checkin.attachments.length === 0) {
        this.showToast("无附件");
        return;
      }
      const images = checkin.attachments.map(url => ({
        src: fixUrl(url),
        thumb: fixUrl(url),
        caption: `${checkin.user_nickname} 的打卡附件`
      }));
      this.openViewer(images[0], images, 0);
    },
  },
}).mount("#app");

/* ==================== 工具函数 ==================== */

/** 标准化图片对象 */
function normalizeImg(img) {
  if (typeof img === "string") return { src: fixUrl(img), thumb: fixUrl(img) };
  return {
    src: img.src ? fixUrl(img.src) : "",
    thumb: img.thumb ? fixUrl(img.thumb) : (img.src ? fixUrl(img.src) : ""),
    caption: img.caption || "",
  };
}

/** 补全相对路径为完整 URL */
function fixUrl(url) {
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) return url;
  // 相对路径补全（支持子路径部署）
  if (url.startsWith("/uploads/") || url.startsWith("/static/")) {
    return location.origin + BASE_PATH + url;
  }
  return location.origin + BASE_PATH + "/" + url.replace(/^\.\//, "");
}

/** 格式化文件大小 */
function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}
