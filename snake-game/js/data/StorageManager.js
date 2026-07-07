// ===== Storage Manager Module =====

const StorageManager = {
    /**
     * 获取本地存储数据
     * @returns {Object} 存储数据
     */
    getData() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                return JSON.parse(saved);
            } catch (e) {
                console.error('Failed to parse storage data:', e);
                return {};
            }
        }
        return {};
    },

    /**
     * 保存数据到本地存储
     * @param {Object} data - 要保存的数据
     */
    saveData(data) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        } catch (e) {
            console.error('Failed to save data:', e);
        }
    },

    /**
     * 获取设置
     * @returns {Object} 设置对象
     */
    getSettings() {
        const data = this.getData();
        return { ...DEFAULT_SETTINGS, ...data.settings };
    },

    /**
     * 保存设置
     * @param {Object} settings - 设置对象
     */
    saveSettings(settings) {
        const data = this.getData();
        data.settings = settings;
        this.saveData(data);
    },

    /**
     * 获取最高分
     * @param {string} mode - 游戏模式
     * @param {string} difficulty - 难度
     * @returns {number} 最高分
     */
    getHighScore(mode, difficulty) {
        const data = this.getData();
        if (data.highScores && data.highScores[mode] && data.highScores[mode][difficulty] !== undefined) {
            return data.highScores[mode][difficulty];
        }
        return 0;
    },

    /**
     * 保存最高分
     * @param {string} mode - 游戏模式
     * @param {string} difficulty - 难度
     * @param {number} score - 分数
     */
    saveHighScore(mode, difficulty, score) {
        const data = this.getData();
        if (!data.highScores) {
            data.highScores = {};
        }
        if (!data.highScores[mode]) {
            data.highScores[mode] = {};
        }
        if (!data.highScores[mode][difficulty] || score > data.highScores[mode][difficulty]) {
            data.highScores[mode][difficulty] = score;
            this.saveData(data);
            return true; // 返回是否刷新了最高分
        }
        return false;
    },

    /**
     * 获取所有最高分记录
     * @returns {Object} 所有最高分
     */
    getAllHighScores() {
        const data = this.getData();
        return data.highScores || {};
    },

    /**
     * 保存成就
     * @param {string} achievementId - 成就ID
     */
    saveAchievement(achievementId) {
        const data = this.getData();
        if (!data.achievements) {
            data.achievements = [];
        }
        if (!data.achievements.includes(achievementId)) {
            data.achievements.push(achievementId);
            this.saveData(data);
        }
    },

    /**
     * 获取所有成就
     * @returns {Array} 成就列表
     */
    getAchievements() {
        const data = this.getData();
        return data.achievements || [];
    },

    /**
     * 保存游戏统计
     * @param {Object} stats - 统计数据
     */
    saveStatistics(stats) {
        const data = this.getData();
        data.statistics = {
            ...data.statistics,
            ...stats
        };
        this.saveData(data);
    },

    /**
     * 获取游戏统计
     * @returns {Object} 统计数据
     */
    getStatistics() {
        const data = this.getData();
        return data.statistics || {
            totalGames: 0,
            totalPlayTime: 0,
            maxScore: 0,
            averageScore: 0
        };
    },

    /**
     * 清除所有数据
     */
    clearAll() {
        localStorage.removeItem(STORAGE_KEY);
    },

    /**
     * 获取存储使用情况
     * @returns {Object} 使用情况 { used, quota }
     */
    getStorageUsage() {
        let used = 0;
        for (let key in localStorage) {
            if (localStorage.hasOwnProperty(key)) {
                used += localStorage[key].length * 2; // 每个字符2字节
            }
        }
        const quota = 5 * 1024 * 1024; // LocalStorage 通常5MB
        return { used, quota, percentage: (used / quota * 100).toFixed(2) };
    }
};

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StorageManager;
}
