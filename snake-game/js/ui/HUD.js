// ===== HUD (Head-Up Display) Module =====

const HUD = {
    /**
     * 初始化HUD
     * @param {GameEngine} gameEngine - 游戏引擎实例
     */
    init(gameEngine) {
        this.gameEngine = gameEngine;
        this.bindEvents();
        this.setupEventListeners();
    },

    /**
     * 绑定HUD事件
     */
    bindEvents() {
        // 暂停按钮
        document.getElementById('btn-pause').addEventListener('click', () => {
            if (this.gameEngine.state === GAME_STATE.PLAYING) {
                this.gameEngine.pause();
            }
        });

        // 重新开始按钮
        document.getElementById('btn-restart').addEventListener('click', () => {
            this.gameEngine.reset();
            this.gameEngine.start();
        });

        // 返回菜单按钮 - 修复：使用 stop() 代替 destroy()，保持引擎可重用
        document.getElementById('btn-menu').addEventListener('click', () => {
            if (this.gameEngine.getState() === GAME_STATE.PLAYING) {
                this.gameEngine.pause();
            }
            if (confirm('确定要返回菜单吗？当前游戏进度将丢失。')) {
                this.gameEngine.stop();
                document.getElementById('game-screen').classList.remove('active');
                Menu.show();
            } else {
                // 如果游戏还在暂停状态，恢复游戏
                if (this.gameEngine.getState() === GAME_STATE.PAUSED) {
                    this.gameEngine.resume();
                }
            }
        });

        // 暂停界面的继续按钮
        document.getElementById('btn-resume').addEventListener('click', () => {
            this.gameEngine.resume();
        });
    },

    /**
     * 设置事件监听
     */
    setupEventListeners() {
        // 监听分数变化
        globalEventBus.on('game:eatFood', (data) => {
            this.updateScore(data.score);
        });

        // 监听游戏结束
        globalEventBus.on('game:over', (data) => {
            this.showGameOver(data.score, data.highScore);
        });

        // 监听时间更新（限时模式）
        globalEventBus.on('game:timeUpdate', (data) => {
            this.updateTimer(data.remaining);
        });

        // 监听游戏开始
        globalEventBus.on('game:start', () => {
            this.resetHUD();
        });

        // 监听游戏重置
        globalEventBus.on('game:reset', () => {
            this.resetHUD();
        });

        // 监听最高分更新
        globalEventBus.on('game:highScore', (data) => {
            this.updateHighScore(data.score);
        });
    },

    /**
     * 更新分数显示
     * @param {number} score - 当前分数
     */
    updateScore(score) {
        const scoreElement = document.getElementById('current-score');
        scoreElement.textContent = score;

        // 分数增加动画
        scoreElement.style.transform = 'scale(1.3)';
        scoreElement.style.transition = 'transform 0.1s ease';
        setTimeout(() => {
            scoreElement.style.transform = 'scale(1)';
            scoreElement.style.transition = 'transform 0.2s ease';
        }, 100);
    },

    /**
     * 更新最高分显示
     * @param {number} highScore - 最高分
     */
    updateHighScore(highScore) {
        document.getElementById('high-score').textContent = highScore;
    },

    /**
     * 更新计时器显示
     * @param {number} remaining - 剩余时间（秒）
     */
    updateTimer(remaining) {
        const timerElement = document.getElementById('timer-value');
        timerElement.textContent = Math.ceil(remaining);

        // 时间不足时闪烁提醒
        if (remaining <= 10) {
            timerElement.style.color = '#F44336';
            timerElement.style.animation = 'pulse 1s infinite';
        } else {
            timerElement.style.color = '';
            timerElement.style.animation = '';
        }
    },

    /**
     * 显示游戏结束界面
     * @param {number} score - 本次得分
     * @param {number} highScore - 最高分
     */
    showGameOver(score, highScore) {
        document.getElementById('final-score').textContent = score;
        document.getElementById('final-high-score').textContent = highScore;

        document.getElementById('game-screen').classList.remove('active');
        document.getElementById('gameover-screen').classList.add('active');

        // 绑定游戏结束界面的按钮
        document.getElementById('btn-restart-game').onclick = () => {
            document.getElementById('gameover-screen').classList.remove('active');
            document.getElementById('game-screen').classList.add('active');
            this.gameEngine.reset();
            this.gameEngine.start();
        };

        // 修复：返回菜单使用 stop()，不用 destroy()
        document.getElementById('btn-back-to-menu').onclick = () => {
            this.gameEngine.stop();
            document.getElementById('gameover-screen').classList.remove('active');
            Menu.show();
        };
    },

    /**
     * 重置HUD
     */
    resetHUD() {
        this.updateScore(0);
        this.updateHighScore(this.gameEngine.highScore);

        const timerElement = document.getElementById('timer-value');
        timerElement.textContent = this.gameEngine.timeLimit;
        timerElement.style.color = '';
        timerElement.style.animation = '';
    }
};

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HUD;
}
