// ===== Menu UI Module =====

const Menu = {
    /**
     * 初始化菜单界面
     * @param {GameEngine} gameEngine - 游戏引擎实例
     */
    init(gameEngine) {
        this.gameEngine = gameEngine;
        this.bindEvents();
        this.loadSettings();
    },

    /**
     * 绑定菜单事件
     */
    bindEvents() {
        // 开始游戏按钮
        document.getElementById('btn-start').addEventListener('click', () => {
            this.hide();
            document.getElementById('game-screen').classList.add('active');

            // 如果是限时模式，显示时间选择
            if (this.gameEngine.gameMode === GAME_MODE.TIMED) {
                this.showTimeSelection();
            } else {
                this.gameEngine.start();
            }
        });

        // 设置按钮
        document.getElementById('btn-settings').addEventListener('click', () => {
            this.hide();
            document.getElementById('settings-screen').classList.add('active');
        });

        // 排行榜按钮
        document.getElementById('btn-leaderboard').addEventListener('click', () => {
            this.hide();
            document.getElementById('leaderboard-screen').classList.add('active');
            Leaderboard.render();
        });

        // 帮助按钮
        document.getElementById('btn-help').addEventListener('click', () => {
            this.hide();
            document.getElementById('help-screen').classList.add('active');
        });

        // 难度选择
        document.querySelectorAll('.difficulty-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.difficulty-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.gameEngine.setDifficulty(e.target.dataset.difficulty);
            });
        });

        // 模式选择
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.gameEngine.setGameMode(e.target.dataset.mode);

                // 显示/隐藏时间选择
                const timeSelector = document.getElementById('time-selector');
                if (e.target.dataset.mode === 'timed') {
                    if (timeSelector) timeSelector.style.display = 'block';
                    document.querySelector('.game-timer').style.display = 'block';
                } else {
                    if (timeSelector) timeSelector.style.display = 'none';
                    document.querySelector('.game-timer').style.display = 'none';
                }
            });
        });

        // 限时模式时间选择按钮（如果已存在）
        this.bindTimeSelectionEvents();
    },

    /**
     * 绑定时间选择事件
     */
    bindTimeSelectionEvents() {
        document.querySelectorAll('.time-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                const seconds = parseInt(e.target.dataset.time, 10);
                this.gameEngine.setTimeLimit(seconds);
            });
        });
    },

    /**
     * 显示限时模式时间选择（在游戏界面上的弹窗）
     */
    showTimeSelection() {
        // 使用 ready-overlay 来显示时间选择
        const readyOverlay = document.getElementById('ready-overlay');
        const readyText = readyOverlay.querySelector('.ready-text');

        // 创建时间选择内容
        readyText.innerHTML = '选择时间';

        const timeOptions = document.createElement('div');
        timeOptions.className = 'time-selection-buttons';
        timeOptions.style.cssText = 'display: flex; gap: 15px; margin-top: 20px;';

        const times = [
            { label: '60秒', value: 60 },
            { label: '120秒', value: 120 },
            { label: '180秒', value: 180 }
        ];

        // 获取当前已选时间
        const currentTime = this.gameEngine.timeLimit;

        times.forEach(t => {
            const btn = document.createElement('button');
            btn.className = 'btn btn-primary' + (t.value === currentTime ? ' time-active' : '');
            btn.textContent = t.label;
            btn.style.cssText = 'min-width: 80px;';
            btn.addEventListener('click', () => {
                this.gameEngine.setTimeLimit(t.value);
                readyOverlay.style.display = 'none';
                // 恢复原始 readyText
                readyText.innerHTML = '';
                this.gameEngine.start();
            });
            timeOptions.appendChild(btn);
        });

        readyText.appendChild(timeOptions);
        readyOverlay.style.display = 'flex';
    },

    /**
     * 加载设置到UI
     */
    loadSettings() {
        const settings = this.gameEngine.settings;

        // 设置难度按钮
        document.querySelectorAll('.difficulty-btn').forEach(btn => {
            if (btn.dataset.difficulty === settings.selectedDifficulty) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // 设置模式按钮
        document.querySelectorAll('.mode-btn').forEach(btn => {
            if (btn.dataset.mode === settings.selectedMode) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    },

    /**
     * 显示菜单界面
     */
    show() {
        document.getElementById('menu-screen').classList.add('active');
    },

    /**
     * 隐藏菜单界面
     */
    hide() {
        document.getElementById('menu-screen').classList.remove('active');
    }
};

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Menu;
}
