/* =========================================================
 * 成长农场 - 管理端模块（window.FarmAdminModule）
 * 经 app.mixin 注入（app.js mount 前），避免 app.js 继续膨胀。
 * 三子页：数据概览 / 站点配置（默认乐园名） / 模板启停
 * ========================================================= */
(function () {
  "use strict";

  function putBody(obj) {
    return { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) };
  }

  window.FarmAdminModule = {
    data() {
      return {
        faTab: "overview",
        faBusy: false,
        faOverview: null,             // /api/admin/farm/overview
        faConfig: { farm_default_name: "" },
        faTemplates: [],
      };
    },
    methods: {
      /* ---------- 入口与子页切换 ---------- */
      openFarmAdmin() {
        this.view = "farm";
        this.loadFaOverview();
      },
      switchFaTab(tab) {
        this.faTab = tab;
        if (tab === "overview") this.loadFaOverview();
        if (tab === "config") this.loadFaConfig();
        if (tab === "templates") this.loadFaTemplates();
      },

      /* ---------- 数据概览 ---------- */
      async loadFaOverview() {
        try { this.faOverview = await this.api("/api/admin/farm/overview"); }
        catch (e) { this.showToast(e.message); }
      },

      /* ---------- 站点配置：默认乐园名 ---------- */
      async loadFaConfig() {
        try {
          const d = await this.api("/api/admin/farm/config");
          this.faConfig = { farm_default_name: d.farm_default_name || "" };
        } catch (e) { this.showToast(e.message); }
      },
      async saveFaConfig() {
        this.faBusy = true;
        try {
          await this.api("/api/admin/farm/config", putBody(this.faConfig));
          this.showToast("配置已保存");
          await this.loadFaConfig();
        } catch (e) { this.showToast(e.message); }
        finally { this.faBusy = false; }
      },

      /* ---------- 模板启停 ---------- */
      async loadFaTemplates() {
        try {
          const d = await this.api("/api/admin/farm/templates");
          this.faTemplates = d.items || [];
        } catch (e) { this.showToast(e.message); }
      },
      async toggleFaTemplate(t) {
        const next = t.status === "on" ? "off" : "on";
        if (next === "off" && t.farm_count > 0) {
          if (!confirm(`模板「${t.name}」已有 ${t.farm_count} 个农场使用，停用后新用户将无法选择。确认停用？`)) return;
        }
        this.faBusy = true;
        try {
          await this.api(`/api/admin/farm/templates/${t.id}`, putBody({ status: next }));
          this.showToast(next === "on" ? "模板已启用" : "模板已停用");
          await this.loadFaTemplates();
        } catch (e) { this.showToast(e.message); }
        finally { this.faBusy = false; }
      },
    },
  };
})();
