// 主题预载脚本：在首帧渲染前应用已保存的「卡通成长」主题属性，避免默认主题闪烁（FOUC）。
// 注意：后端 CSP 为 script-src 'self' 'unsafe-eval'，禁止内联脚本，
// 因此该引导逻辑必须独立成外部文件，并在 <head> 中尽早加载。
(function () {
  try {
    var t = localStorage.getItem("student_theme");
    if (t === "cartoon") {
      document.documentElement.setAttribute("data-theme", "cartoon");
    }
  } catch (e) {
    // 隐私模式等场景下 localStorage 不可用时静默降级为默认主题
  }
})();
