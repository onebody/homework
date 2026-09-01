/* =========================================================
 * 学习成长计划 - 管理端模块（window.LearningAdminModule）
 * 经 app.mixin 注入（app.js mount 前），避免 app.js 继续膨胀。
 * 六子页：审核配置 / 学科 / 学期 / 班级 / 模板 / 审核队列
 * ========================================================= */
(function () {
  "use strict";

  function jsonBody(obj) {
    return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) };
  }
  function putBody(obj) {
    return { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) };
  }

  window.LearningAdminModule = {
    data() {
      return {
        laTab: "config",
        laBusy: false,
        // 审核配置
        laConfig: { mode: "summer", review_mode: "admin", current_semester_id: null },
        // 学科
        laSubjects: [],
        laSubjectEditing: null,   // null=关闭；{id?}=表单
        // 学期
        laSemesters: [],
        laSemesterEditing: null,
        // 班级
        laClasses: [],
        laClassEditing: null,
        laClassMembers: null,     // {cid, name, selected:[]}
        laStudents: [],
        // 模板
        laTemplates: [],
        laTemplateEditing: null,
        laTemplateDetail: null,   // {plan, tasks}
        laTaskEditing: null,
        laAssign: null,           // {tid, name, class_id, grade}
        // 审核队列
        laSubs: [],
        laSubFilter: "pending",
        laSubPg: { page: 1, pages: 1, total: 0 },
        laReviewing: null,        // 正在审核的提交（驳回时填理由）
        laReviewNote: "",
      };
    },
    methods: {
      /* ---------- 入口与子页切换 ---------- */
      openLearning() {
        this.view = "learning";
        this.loadLaConfig();
        this.loadLaSemesters();   // 配置页学期下拉依赖
      },
      switchLaTab(tab) {
        this.laTab = tab;
        if (tab === "config") this.loadLaConfig();
        if (tab === "subjects") this.loadLaSubjects();
        if (tab === "semesters") this.loadLaSemesters();
        if (tab === "classes") this.loadLaClasses();
        if (tab === "templates") this.loadLaTemplates();
        if (tab === "submissions") this.loadLaSubs(1);
      },

      /* ---------- 审核配置 ---------- */
      async loadLaConfig() {
        try { this.laConfig = await this.api("/api/admin/learning/config"); } catch (e) { /* 静默 */ }
      },
      async saveLaConfig() {
        this.laBusy = true;
        try {
          await this.api("/api/admin/learning/config", putBody(this.laConfig));
          this.showToast("配置已保存");
          await this.loadLaConfig();
        } catch (e) { this.showToast(e.message); }
        finally { this.laBusy = false; }
      },

      /* ---------- 学科 ---------- */
      async loadLaSubjects() {
        try { this.laSubjects = await this.api("/api/admin/learning/subjects"); } catch (e) { this.showToast(e.message); }
      },
      openSubjectEdit(s) {
        this.laSubjectEditing = s ? { ...s } : { name: "", emoji: "📚", grade_min: 1, grade_max: 6, sort_order: 0, status: "on" };
      },
      async saveSubject() {
        const f = this.laSubjectEditing;
        this.laBusy = true;
        try {
          const body = { name: f.name, emoji: f.emoji, grade_min: +f.grade_min, grade_max: +f.grade_max, sort_order: +f.sort_order, status: f.status };
          if (f.id) await this.api("/api/admin/learning/subjects/" + f.id, putBody(body));
          else await this.api("/api/admin/learning/subjects", jsonBody(body));
          this.laSubjectEditing = null;
          await this.loadLaSubjects();
        } catch (e) { this.showToast(e.message); }
        finally { this.laBusy = false; }
      },
      async deleteSubject(s) {
        if (!confirm(`删除学科「${s.name}」？（被任务引用时将改为下架）`)) return;
        try {
          const d = await this.api("/api/admin/learning/subjects/" + s.id, { method: "DELETE" });
          this.showToast(d.message || "已删除");
          await this.loadLaSubjects();
        } catch (e) { this.showToast(e.message); }
      },

      /* ---------- 学期 ---------- */
      async loadLaSemesters() {
        try { this.laSemesters = await this.api("/api/admin/learning/semesters"); } catch (e) { /* 静默 */ }
      },
      openSemesterEdit(s) {
        this.laSemesterEditing = s ? { ...s } : { name: "", type: "semester", start_date: "", end_date: "", status: "active" };
      },
      async saveSemester() {
        const f = this.laSemesterEditing;
        if (!f.name || !f.start_date || !f.end_date) { this.showToast("名称与起止日期必填"); return; }
        this.laBusy = true;
        try {
          const body = { name: f.name, type: f.type, start_date: f.start_date, end_date: f.end_date, status: f.status };
          if (f.id) await this.api("/api/admin/learning/semesters/" + f.id, putBody(body));
          else await this.api("/api/admin/learning/semesters", jsonBody(body));
          this.laSemesterEditing = null;
          await this.loadLaSemesters();
        } catch (e) { this.showToast(e.message); }
        finally { this.laBusy = false; }
      },
      async deleteSemester(s) {
        if (!confirm(`删除学期「${s.name}」？（已有计划引用时将改为归档）`)) return;
        try {
          const d = await this.api("/api/admin/learning/semesters/" + s.id, { method: "DELETE" });
          this.showToast(d.message || "已删除");
          await this.loadLaSemesters();
        } catch (e) { this.showToast(e.message); }
      },

      /* ---------- 班级 ---------- */
      async loadLaClasses() {
        try { this.laClasses = await this.api("/api/admin/learning/classes"); } catch (e) { this.showToast(e.message); }
      },
      openClassEdit(c) {
        this.laClassEditing = c ? { ...c } : { name: "", grade: 1 };
      },
      async saveClass() {
        const f = this.laClassEditing;
        if (!f.name) { this.showToast("班级名称必填"); return; }
        this.laBusy = true;
        try {
          const body = { name: f.name, grade: +f.grade };
          if (f.id) await this.api("/api/admin/learning/classes/" + f.id, putBody(body));
          else await this.api("/api/admin/learning/classes", jsonBody(body));
          this.laClassEditing = null;
          await this.loadLaClasses();
        } catch (e) { this.showToast(e.message); }
        finally { this.laBusy = false; }
      },
      async deleteClass(c) {
        if (!confirm(`删除班级「${c.name}」？（学生将解除归属，模板将改为全校可见）`)) return;
        try {
          await this.api("/api/admin/learning/classes/" + c.id, { method: "DELETE" });
          await this.loadLaClasses();
        } catch (e) { this.showToast(e.message); }
      },
      async openClassMembers(c) {
        this.laClassMembers = { cid: c.id, name: c.name, selected: [] };
        try {
          const d = await this.api("/api/admin/learning/students");
          this.laStudents = d.items || [];
        } catch (e) { this.showToast(e.message); }
      },
      async assignClassMembers() {
        const m = this.laClassMembers;
        if (!m.selected.length) { this.showToast("请勾选学生"); return; }
        this.laBusy = true;
        try {
          const d = await this.api(`/api/admin/learning/classes/${m.cid}/members`,
            jsonBody({ student_ids: m.selected }));
          this.showToast(`已分班 ${d.assigned} 人`);
          this.laClassMembers = null;
          await this.loadLaClasses();
        } catch (e) { this.showToast(e.message); }
        finally { this.laBusy = false; }
      },

      /* ---------- 模板 ---------- */
      async loadLaTemplates() {
        try {
          const d = await this.api("/api/admin/learning/templates");
          this.laTemplates = d.items || [];
        } catch (e) { this.showToast(e.message); }
      },
      openTemplateEdit(t) {
        this.laTemplateEditing = t
          ? { id: t.id, name: t.name, description: t.description || "", semester_id: t.semester_id, grade: t.grade, class_id: t.class_id, period_type: t.period_type }
          : { name: "", description: "", semester_id: null, grade: null, class_id: null, period_type: "week" };
      },
      async saveTemplate() {
        const f = this.laTemplateEditing;
        if (!f.name) { this.showToast("模板名称必填"); return; }
        this.laBusy = true;
        try {
          const body = {
            name: f.name, description: f.description || null,
            semester_id: f.semester_id || null, grade: f.grade || null,
            class_id: f.class_id || null, period_type: f.period_type,
          };
          if (f.id) await this.api("/api/admin/learning/templates/" + f.id, putBody(body));
          else await this.api("/api/admin/learning/templates", jsonBody(body));
          this.laTemplateEditing = null;
          await this.loadLaTemplates();
        } catch (e) { this.showToast(e.message); }
        finally { this.laBusy = false; }
      },
      async deleteTemplate(t) {
        if (!confirm(`删除模板「${t.name}」？（已有学生实例时将改为归档）`)) return;
        try {
          const d = await this.api("/api/admin/learning/templates/" + t.id, { method: "DELETE" });
          this.showToast(d.message || "已删除");
          await this.loadLaTemplates();
        } catch (e) { this.showToast(e.message); }
      },
      async openTemplateDetail(t) {
        try {
          this.laTemplateDetail = await this.api("/api/admin/learning/templates/" + t.id);
        } catch (e) { this.showToast(e.message); }
      },
      openTaskEdit(task) {
        this.laTaskEditing = task ? { ...task } : {
          title: "", subject_id: null, completion_criteria: "",
          est_minutes: 30, due_date: null, reward_points: 10, reward_xp: 10, sort_order: 0,
        };
      },
      async saveTemplateTask() {
        const f = this.laTaskEditing;
        if (!f.title) { this.showToast("任务标题必填"); return; }
        this.laBusy = true;
        try {
          const body = {
            title: f.title, subject_id: f.subject_id || null,
            completion_criteria: f.completion_criteria || null,
            est_minutes: +f.est_minutes || 30, due_date: f.due_date || null,
            reward_points: +f.reward_points || 0, reward_xp: +f.reward_xp || 0,
            sort_order: +f.sort_order || 0,
          };
          if (f.id) await this.api("/api/admin/learning/tasks/" + f.id, putBody(body));
          else await this.api(`/api/admin/learning/templates/${this.laTemplateDetail.plan.id}/tasks`, jsonBody(body));
          this.laTaskEditing = null;
          await this.openTemplateDetail(this.laTemplateDetail.plan);
          await this.loadLaTemplates();
        } catch (e) { this.showToast(e.message); }
        finally { this.laBusy = false; }
      },
      async deleteTemplateTask(task) {
        if (!confirm(`删除任务「${task.title}」？`)) return;
        try {
          await this.api("/api/admin/learning/tasks/" + task.id, { method: "DELETE" });
          await this.openTemplateDetail(this.laTemplateDetail.plan);
          await this.loadLaTemplates();
        } catch (e) { this.showToast(e.message); }
      },
      async publishTemplate(t) {
        try {
          const d = await this.api(`/api/admin/learning/templates/${t.id}/publish`, { method: "POST" });
          this.showToast(d.message || "已发布");
          await this.loadLaTemplates();
          if (this.laTemplateDetail && this.laTemplateDetail.plan.id === t.id) {
            await this.openTemplateDetail(t);
          }
        } catch (e) { this.showToast(e.message); }
      },
      openAssign(t) { this.laAssign = { tid: t.id, name: t.name, class_id: null, grade: null }; },
      async assignTemplate() {
        const a = this.laAssign;
        const body = {};
        if (a.class_id) body.class_id = +a.class_id;
        else if (a.grade) body.grade = +a.grade;
        else { this.showToast("请选择班级或年级"); return; }
        this.laBusy = true;
        try {
          const d = await this.api(`/api/admin/learning/templates/${a.tid}/assign`, jsonBody(body));
          this.showToast(`已指派 ${d.assigned} 人，跳过 ${d.skipped} 人`);
          this.laAssign = null;
        } catch (e) { this.showToast(e.message); }
        finally { this.laBusy = false; }
      },

      /* ---------- 审核队列 ---------- */
      async loadLaSubs(page) {
        const p = Number(page) >= 1 ? Number(page) : this.laSubPg.page;
        try {
          const d = await this.api(`/api/admin/learning/submissions?status=${this.laSubFilter}&page=${p}&size=20`);
          this.laSubs = d.items || [];
          this.laSubPg = { page: d.page || 1, pages: d.pages || 1, total: d.total || 0 };
        } catch (e) { this.showToast(e.message); }
      },
      async laReview(s, approved) {
        if (!approved) { this.laReviewing = s; this.laReviewNote = ""; return; }
        this.laBusy = true;
        try {
          await this.api(`/api/admin/learning/submissions/${s.id}/review`, putBody({ approved: true }));
          this.showToast("已通过，奖励已发放");
          await this.loadLaSubs();
        } catch (e) { this.showToast(e.message); }
        finally { this.laBusy = false; }
      },
      async laRejectConfirm() {
        this.laBusy = true;
        try {
          await this.api(`/api/admin/learning/submissions/${this.laReviewing.id}/review`,
            putBody({ approved: false, note: this.laReviewNote || "不符合完成标准" }));
          this.showToast("已驳回");
          this.laReviewing = null;
          await this.loadLaSubs();
        } catch (e) { this.showToast(e.message); }
        finally { this.laBusy = false; }
      },
    },
  };
})();
