// ===== Achievement Manager Module =====

/**
 * 成就系统管理器
 * 管理游戏内所有成就的解锁逻辑和通知
 */
const AchievementManager = {
    /**
     * 成就定义列表
     * 每个成就包含: id, name, description, icon, checkFn
     */
    achievements: [
        {
            id: 'first_score',
            name: '初次得分',
            description: '第一次吃到食物',
            icon: '🎯',
            unlocked: false
        },
        {
            id: 'score_10',
            name: '十连击',
            description: '单局得分达到10',
            icon: '🔥',
            unlocked: false
        },
        {
            id: 'score_50',
            name: '半百',
            description: '单局得分达到50',
            icon: '⭐',
            unlocked: false
        },
        {
            id: 'score_100',
            name: '百发百中',
            description: '单局得分达到100',
            icon: '💎',
            unlocked: false
        },
        {
            id: 'persistent_player',
            name: '执着玩家',
            description: '总共玩了10局',
            icon: '🏆',
            unlocked: false
        },
        {
            id: 'speed_demon',
            name: '速度恶魔',
            description: '在困难模式下得分超过30',
            icon: '⚡',
            unlocked: false
        },
        {
            id: 'obstacle_master',
            name: '障碍大师',
            description: '在障碍模式下得分超过20',
            icon: '🧱',
            unlocked: false
        },
        {
            id: 'time_urgent',
            name: '争分夺秒',
            description: '在限时模式下得分超过50',
            icon: '⏱️',
            unlocked: false
        },
        {
            id: 'snake_long',
            name: '长蛇阵',
            description: '蛇身长度达到30节',
            icon: '🐍',
            unlocked: false
        },
        {
            id: 'wall_through',
            name: '穿墙术',
            description: '在简单模式穿墙10次以上并得分超过20',
            icon: '🌀',
            unlocked: false
        }
    ],

    /**
     * 初始化成就系统
     */
    init() {
        // 从本地存储加载已解锁的成就
        this.loadUnlockedAchievements();
    },

    /**
     * 从本地存储加载已解锁成就
     */
    loadUnlockedAchievements() {
        const data = StorageManager.getData();
        const unlockedIds = data.achievements || [];

        this.achievements.forEach(achievement => {
            achievement.unlocked = unlockedIds.includes(achievement.id);
        });
    },

    /**
     * 解锁成就
     * @param {string} achievementId - 成就ID
     */
    unlock(achievementId) {
        const achievement = this.achievements.find(a => a.id === achievementId);
        if (!achievement || achievement.unlocked) return;

        achievement.unlocked = true;
        StorageManager.saveAchievement(achievementId);

        // 显示成就通知
        this.showAchievementNotification(achievement);

        globalEventBus.emit('achievement:unlock', achievement);
    },

    /**
     * 显示成就解锁通知
     * @param {Object} achievement - 成就对象
     */
    showAchievementNotification(achievement) {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = 'achievement-notification';
        notification.innerHTML = `
            <span class="achievement-notification-icon">${achievement.icon}</span>
            <div class="achievement-notification-content">
                <div class="achievement-notification-title">成就解锁！</div>
                <div class="achievement-notification-name">${achievement.name}</div>
                <div class="achievement-notification-desc">${achievement.description}</div>
            </div>
        `;

        document.body.appendChild(notification);

        // 触发动画
        requestAnimationFrame(() => {
            notification.classList.add('show');
        });

        // 3秒后移除
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 500);
        }, 3000);
    },

    /**
     * 吃到食物时检查成就
     * @param {number} score - 当前分数
     */
    checkOnEatFood(score) {
        // 初次得分
        if (score >= 1) {
            this.unlock('first_score');
        }

        // 十连击
        if (score >= 10) {
            this.unlock('score_10');
        }

        // 半百
        if (score >= 50) {
            this.unlock('score_50');
        }

        // 百发百中
        if (score >= 100) {
            this.unlock('score_100');
        }
    },

    /**
     * 游戏结束时检查成就
     * @param {number} score - 最终得分
     */
    checkOnGameOver(score) {
        // 检查总游戏局数
        const stats = StorageManager.getStatistics();
        if (stats.totalGames >= 10) {
            this.unlock('persistent_player');
        }

        // 速度恶魔：困难模式得分超过30
        const gameEngine = window._gameEngine;
        if (gameEngine) {
            if (gameEngine.difficulty.name === 'hard' && score >= 30) {
                this.unlock('speed_demon');
            }

            // 障碍大师
            if (gameEngine.gameMode === GAME_MODE.OBSTACLE && score >= 20) {
                this.unlock('obstacle_master');
            }

            // 争分夺秒
            if (gameEngine.gameMode === GAME_MODE.TIMED && score >= 50) {
                this.unlock('time_urgent');
            }

            // 长蛇阵
            if (gameEngine.snake && gameEngine.snake.getLength() >= 30) {
                this.unlock('snake_long');
            }

            // 穿墙术
            if (gameEngine.difficulty.name === 'easy' && gameEngine.difficulty.throughWall && score >= 20) {
                this.unlock('wall_through');
            }
        }
    },

    /**
     * 获取所有成就状态
     * @returns {Array} 成就列表
     */
    getAllAchievements() {
        return this.achievements.map(a => ({ ...a }));
    },

    /**
     * 获取已解锁成就数量
     * @returns {number} 已解锁数量
     */
    getUnlockedCount() {
        return this.achievements.filter(a => a.unlocked).length;
    },

    /**
     * 获取成就总数
     * @returns {number} 成就总数
     */
    getTotalCount() {
        return this.achievements.length;
    }
};

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AchievementManager;
}
