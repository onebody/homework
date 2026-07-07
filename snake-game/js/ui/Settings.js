// ===== Settings UI Module =====

const Settings = {
    /**
     * 初始化设置界面
     * @param {GameEngine} gameEngine - 游戏引擎实例
     */
    init(gameEngine) {
        this.gameEngine = gameEngine;
        this.bindEvents();
        this.loadSettings();
    },

    /**
     * 绑定设置事件
     */
    bindEvents() {
        // 返回按钮
        document.getElementById('btn-settings-back').addEventListener('click', () => {
            this.hide();
            Menu.show();
        });

        // 音效开关
        document.getElementById('setting-sound').addEventListener('change', (e) => {
            const enabled = this.gameEngine.toggleSound();
            e.target.checked = enabled;
            this.saveSetting('soundEnabled', enabled);
        });

        // 震动反馈开关
        document.getElementById('setting-vibration').addEventListener('change', (e) => {
            const enabled = this.gameEngine.toggleVibration();
            e.target.checked = enabled;
            this.saveSetting('vibrationEnabled', enabled);
        });

        // 皮肤选择
        document.getElementById('setting-skin').addEventListener('change', (e) => {
            const skin = e.target.value;
            this.gameEngine.setSkin(skin);
            this.saveSetting('selectedSkin', skin);
        });

        // 语言选择
        document.getElementById('setting-language').addEventListener('change', (e) => {
            const language = e.target.value;
            this.saveSetting('language', language);
            // 这里可以触发语言切换逻辑
            console.log('Language changed to:', language);
        });

        // 大字体模式
        document.getElementById('setting-large-font').addEventListener('change', (e) => {
            const enabled = e.target.checked;
            this.toggleLargeFont(enabled);
            this.saveSetting('fontSize', enabled ? 'large' : 'normal');
        });

        // 护眼模式
        document.getElementById('setting-eye-care').addEventListener('change', (e) => {
            const enabled = e.target.checked;
            this.toggleEyeCare(enabled);
            this.saveSetting('eyeCareMode', enabled);
        });
    },

    /**
     * 加载设置到UI
     */
    loadSettings() {
        const settings = this.gameEngine.settings;

        // 音效
        document.getElementById('setting-sound').checked = settings.soundEnabled;

        // 震动
        document.getElementById('setting-vibration').checked = settings.vibrationEnabled;

        // 皮肤
        document.getElementById('setting-skin').value = settings.selectedSkin;

        // 语言
        document.getElementById('setting-language').value = settings.language;

        // 大字体
        const isLargeFont = settings.fontSize === 'large';
        document.getElementById('setting-large-font').checked = isLargeFont;
        this.toggleLargeFont(isLargeFont);

        // 护眼模式
        const isEyeCare = settings.eyeCareMode;
        document.getElementById('setting-eye-care').checked = isEyeCare;
        this.toggleEyeCare(isEyeCare);
    },

    /**
     * 切换大字体模式
     * @param {boolean} enabled - 是否启用
     */
    toggleLargeFont(enabled) {
        if (enabled) {
            document.body.setAttribute('data-large-font', 'true');
        } else {
            document.body.removeAttribute('data-large-font');
        }
    },

    /**
     * 切换护眼模式
     * @param {boolean} enabled - 是否启用
     */
    toggleEyeCare(enabled) {
        if (enabled) {
            document.body.setAttribute('data-eye-care', 'true');
        } else {
            document.body.removeAttribute('data-eye-care');
        }
    },

    /**
     * 保存设置到本地存储
     * @param {string} key - 设置键
     * @param {*} value - 设置值
     */
    saveSetting(key, value) {
        const data = this.gameEngine.getStorageData();
        if (!data.settings) {
            data.settings = {};
        }
        data.settings[key] = value;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    },

    /**
     * 显示设置界面
     */
    show() {
        document.getElementById('settings-screen').classList.add('active');
    },

    /**
     * 隐藏设置界面
     */
    hide() {
        document.getElementById('settings-screen').classList.remove('active');
    }
};

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Settings;
}
