/* =========================================================
 * 成长农场模块（学生端）——独立文件，经 mixin 注入根实例
 * app.js 仅在 app.mount 前追加：app.mixin(window.FarmModule)
 * 依赖 app.js 的 api()/showToast()，均为运行时调用，无加载顺序问题。
 *
 * 能量来源：学习任务审核通过 / 打卡审核通过（历史成果在开通时一次性回填）
 * 能量用途：种菜、养殖、给成长树浇水；成长树育成大树后森林 +1 循环
 * ========================================================= */
(function () {
  "use strict";

  var SOURCE_TEXT = {
    task_approval: "任务审核通过",
    checkin_approval: "打卡审核通过",
    backfill: "历史成果转化",
    harvest: "收获奖励",
    plant: "种植消耗",
    adopt: "领养消耗",
    water: "浇树消耗",
  };

  window.FarmModule = {
    data() {
      return {
        farmStatus: null,          // /api/farm/status 原始返回
        farmTab: "scene",          // scene | log
        farmBusy: false,
        farmLog: { items: [], page: 1, pages: 1, total: 0 },
        // 开通引导
        farmInitForm: { name: "", template_key: "" },
        farmTplOptions: [],        // 切换模板弹窗的可选模板清单
        // 弹窗
        showFarmRename: false,
        farmRenameInput: "",
        showFarmTpl: false,
        showFarmPlant: null,       // null | 'crop' | 'animal'
      };
    },
    computed: {
      farmOpened() { return !!(this.farmStatus && this.farmStatus.has_farm); },
      farm() { return this.farmOpened ? this.farmStatus.farm : null; },
      farmTpl() { return this.farmOpened ? this.farmStatus.template : null; },
      farmPlots() { return this.farmOpened ? (this.farmStatus.plots || []) : []; },
      farmRules() { return (this.farmStatus && this.farmStatus.rules) || {}; },
      // 模板素材 key → {name, emoji} 映射（地块展示用）
      farmItemMap() {
        var map = {};
        if (!this.farmTpl) return map;
        (this.farmTpl.crop_items || []).concat(this.farmTpl.animal_items || []).forEach(function (it) {
          map[it.key] = it;
        });
        return map;
      },
      // 空地块数量（上限 - 在种地块）
      farmEmptyPlots() {
        if (!this.farmOpened) return 0;
        var used = this.farmPlots.filter(function (p) { return p.status !== "harvested"; }).length;
        return Math.max(0, (this.farm.max_plots || 4) - used);
      },
      // 待收获数量（场景角标提示）
      farmMatureCount() {
        return this.farmPlots.filter(function (p) { return p.is_mature; }).length;
      },
    },
    watch: {
      // 退出登录时复位
      token(v) {
        if (!v) {
          this.farmStatus = null;
          this.farmTab = "scene";
          this.farmLog = { items: [], page: 1, pages: 1, total: 0 };
          this.farmInitForm = { name: "", template_key: "" };
        }
      },
    },
    methods: {
      /* ---------- 入口与加载 ---------- */
      async goFarm() {
        if (this.isParent) { this.showToast("成长农场仅学生端可用"); return; }
        this.view = "farm";
        await this.loadFarm();
      },
      async loadFarm() {
        try {
          var d = await this.api("/api/farm/status");
          this.farmStatus = d;
          if (!d.has_farm && !this.farmInitForm.template_key && d.templates && d.templates.length) {
            this.farmInitForm.template_key = d.templates[0].key;   // 默认选中第一个模板
          }
          if (this.farmTab === "log" && !this.farmLog.items.length) this.loadFarmLog(1);
        } catch (e) { this.showToast(e.message); }
      },
      switchFarmTab(tab) {
        this.farmTab = tab;
        if (tab === "log" && !this.farmLog.items.length) this.loadFarmLog(1);
      },

      /* ---------- 开通引导 ---------- */
      async initFarm() {
        if (this.farmBusy) return;
        if (!this.farmInitForm.template_key) { this.showToast("请选择一个农场模板"); return; }
        this.farmBusy = true;
        try {
          await this.api("/api/farm/init", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: this.farmInitForm.name.trim() || null,
              template_key: this.farmInitForm.template_key,
            }),
          });
          this.showToast("🌱 成长农场已开通，历史学习成果已转化为成长能量！");
          await this.loadFarm();
        } catch (e) { this.showToast(e.message); }
        finally { this.farmBusy = false; }
      },

      /* ---------- 个性化命名 ---------- */
      openFarmRename() {
        this.farmRenameInput = this.farm ? this.farm.name : "";
        this.showFarmRename = true;
      },
      async saveFarmRename() {
        var name = (this.farmRenameInput || "").trim();
        if (!name) { this.showToast("请输入乐园名称"); return; }
        if (name.length > 32) { this.showToast("名称最长 32 个字符"); return; }
        this.farmBusy = true;
        try {
          await this.api("/api/farm/rename", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name }),
          });
          this.showToast("已改名 ✨");
          this.showFarmRename = false;
          await this.loadFarm();
        } catch (e) { this.showToast(e.message); }
        finally { this.farmBusy = false; }
      },

      /* ---------- 模板切换 ---------- */
      async loadFarmTemplates() {
        try {
          var d = await this.api("/api/farm/templates");
          // 复用开通引导的模板展示位；仅展示启用模板
          this.farmTplOptions = d.items || [];
        } catch (e) { this.farmTplOptions = []; }
        this.showFarmTpl = true;
      },
      async switchFarmTpl(key) {
        if (this.farmBusy) return;
        this.farmBusy = true;
        try {
          await this.api("/api/farm/template", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ template_key: key }),
          });
          this.showToast("模板已切换 🎨");
          this.showFarmTpl = false;
          await this.loadFarm();
        } catch (e) { this.showToast(e.message); }
        finally { this.farmBusy = false; }
      },

      /* ---------- 种植 / 养殖 ---------- */
      openFarmPlant(type) {
        if (!this.farmEmptyPlots) { this.showToast("地块已满，成长树升级可解锁更多地块"); return; }
        this.showFarmPlant = type;
      },
      async doFarmPlant(item) {
        if (this.farmBusy) return;
        this.farmBusy = true;
        try {
          await this.api("/api/farm/plant", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ plot_type: this.showFarmPlant, item_key: item.key }),
          });
          this.showToast((this.showFarmPlant === "animal" ? "领养成功" : "种植成功") + " " + item.emoji);
          this.showFarmPlant = null;
          await this.loadFarm();
        } catch (e) { this.showToast(e.message); }
        finally { this.farmBusy = false; }
      },
      async harvestPlot(p) {
        if (this.farmBusy) return;
        this.farmBusy = true;
        try {
          var d = await this.api("/api/farm/harvest/" + p.id, { method: "POST" });
          this.showToast("收获 ⚡+" + d.gained + "！");
          await this.loadFarm();
        } catch (e) { this.showToast(e.message); }
        finally { this.farmBusy = false; }
      },

      /* ---------- 成长树 ---------- */
      async waterTree() {
        if (this.farmBusy) return;
        this.farmBusy = true;
        try {
          var d = await this.api("/api/farm/water", { method: "POST" });
          if (d.forest_grown) this.showToast("🌲 成长树育成大树，森林 +1！新的树苗正在发芽…");
          else if (d.leveled) this.showToast("🌿 成长树升级啦！地块上限 +1");
          else this.showToast("浇水成功 💧");
          await this.loadFarm();
        } catch (e) { this.showToast(e.message); }
        finally { this.farmBusy = false; }
      },

      /* ---------- 能量流水 ---------- */
      async loadFarmLog(page) {
        try {
          var d = await this.api("/api/farm/energy-log?page=" + (page || 1) + "&size=20");
          this.farmLog = {
            items: d.items || [],
            page: d.page || 1,
            pages: Math.max(1, Math.ceil((d.total || 0) / (d.size || 20))),
            total: d.total || 0,
          };
        } catch (e) { this.showToast(e.message); }
      },

      /* ---------- 展示辅助 ---------- */
      farmSourceText(s) { return SOURCE_TEXT[s] || s; },
      farmPlotItem(p) {
        return this.farmItemMap[p.item_key] || { name: p.item_key, emoji: p.plot_type === "animal" ? "🐾" : "🌱" };
      },
      farmPlotCountdown(p) {
        if (!p.mature_at) return "";
        var ms = new Date(p.mature_at).getTime() - Date.now();
        if (ms <= 0) return "已成熟";
        var m = Math.ceil(ms / 60000);
        if (m >= 60) return Math.floor(m / 60) + "小时" + (m % 60 ? (m % 60) + "分" : "") + "后成熟";
        return m + "分钟后成熟";
      },
    },
  };
})();
