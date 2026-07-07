// ===== Leaderboard UI Module =====

const Leaderboard = {
    /**
     * 初始化排行榜界面
     * @param {GameEngine} gameEngine - 游戏引擎实例
     */
    init(gameEngine) {
        this.gameEngine = gameEngine;
        this.bindEvents();
    },

    /**
     * 绑定事件
     */
    bindEvents() {
        // 返回按钮
        document.getElementById('btn-leaderboard-back').addEventListener('click', () => {
            this.hide();
            Menu.show();
        });

        // Tab切换
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.render(e.target.dataset.tab);
            });
        });
    },

    /**
     * 渲染排行榜
     * @param {string} tab - 'local' | 'global'
     */
    render(tab = 'local') {
        const listContainer = document.getElementById('leaderboard-list');
        listContainer.innerHTML = '';

        if (tab === 'local') {
            this.renderLocalLeaderboard(listContainer);
        } else {
            this.renderGlobalLeaderboard(listContainer);
        }
    },

    /**
     * 渲染本地排行榜（使用完整游戏记录）
     * @param {HTMLElement} container - 列表容器
     */
    renderLocalLeaderboard(container) {
        const data = this.gameEngine.getStorageData();
        let records = [];

        // 优先使用完整游戏记录
        if (data.gameRecords && data.gameRecords.length > 0) {
            records = data.gameRecords.map(record => {
                const modeLabels = { classic: '经典', timed: '限时', obstacle: '障碍' };
                const diffLabels = { easy: '简单', medium: '中等', hard: '困难' };

                return {
                    score: record.score,
                    mode: record.mode,
                    difficulty: record.difficulty,
                    date: this.formatDate(record.date),
                    snakeLength: record.snakeLength || 0,
                    modeLabel: modeLabels[record.mode] || record.mode,
                    diffLabel: diffLabels[record.difficulty] || record.difficulty
                };
            });

            // 按分数降序排列
            records.sort((a, b) => b.score - a.score);
        }

        // 如果没有游戏记录，回退到最高分数据
        if (records.length === 0 && data.highScores) {
            Object.keys(data.highScores).forEach(mode => {
                Object.keys(data.highScores[mode]).forEach(diff => {
                    const score = data.highScores[mode][diff];
                    if (score > 0) {
                        const modeLabels = { classic: '经典', timed: '限时', obstacle: '障碍' };
                        const diffLabels = { easy: '简单', medium: '中等', hard: '困难' };
                        records.push({
                            score: score,
                            mode: mode,
                            difficulty: diff,
                            date: 'N/A',
                            modeLabel: modeLabels[mode] || mode,
                            diffLabel: diffLabels[diff] || diff
                        });
                    }
                });
            });
            records.sort((a, b) => b.score - a.score);
        }

        // 只取前20
        records = records.slice(0, 20);

        if (records.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #757575; margin-top: 40px;">暂无排行榜数据<br>开始游戏来创建记录吧！</p>';
            return;
        }

        // 渲染列表
        records.forEach((item, index) => {
            const rankLabel = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : (index + 1).toString();
            const itemElement = this.createLeaderboardItem(
                rankLabel,
                item.score,
                `${item.modeLabel} · ${item.diffLabel}`,
                item.date
            );
            container.appendChild(itemElement);
        });
    },

    /**
     * 渲染全球排行榜（模拟数据）
     * @param {HTMLElement} container - 列表容器
     */
    renderGlobalLeaderboard(container) {
        // 模拟全球排行榜数据
        const mockData = [
            { rank: '🥇', name: 'SnakeKing', score: 999, mode: '经典', difficulty: '困难' },
            { rank: '🥈', name: 'PythonPro', score: 856, mode: '经典', difficulty: '困难' },
            { rank: '🥉', name: 'SnakeMaster', score: 742, mode: '限时', difficulty: '中等' },
            { rank: '4', name: 'WormWarrior', score: 698, mode: '经典', difficulty: '中等' },
            { rank: '5', name: 'SlitherQueen', score: 654, mode: '障碍', difficulty: '困难' },
            { rank: '6', name: 'SnakeByte', score: 587, mode: '限时', difficulty: '困难' },
            { rank: '7', name: 'PixelPython', score: 534, mode: '经典', difficulty: '简单' },
            { rank: '8', name: 'RetroSnake', score: 498, mode: '限时', difficulty: '中等' },
            { rank: '9', name: 'SnakeEater', score: 456, mode: '障碍', difficulty: '中等' },
            { rank: '10', name: '你', score: this.gameEngine.getHighScore(), mode: '-', difficulty: '-' }
        ];

        mockData.forEach(item => {
            const itemElement = this.createLeaderboardItem(
                item.rank,
                item.score,
                `${item.name} · ${item.mode}`,
                ''
            );
            container.appendChild(itemElement);
        });
    },

    /**
     * 格式化日期
     * @param {string} isoString - ISO日期字符串
     * @returns {string} 格式化后的日期
     */
    formatDate(isoString) {
        if (!isoString || isoString === 'N/A') return 'N/A';
        try {
            const date = new Date(isoString);
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            const day = date.getDate().toString().padStart(2, '0');
            const hours = date.getHours().toString().padStart(2, '0');
            const minutes = date.getMinutes().toString().padStart(2, '0');
            return `${month}-${day} ${hours}:${minutes}`;
        } catch (e) {
            return 'N/A';
        }
    },

    /**
     * 创建排行榜条目
     * @param {string} rank - 排名
     * @param {number} score - 分数
     * @param {string} info - 附加信息
     * @param {string} date - 日期
     * @returns {HTMLElement} 条目元素
     */
    createLeaderboardItem(rank, score, info, date) {
        const item = document.createElement('div');
        item.className = 'leaderboard-item';

        const rankSpan = document.createElement('span');
        rankSpan.className = 'leaderboard-rank';
        rankSpan.textContent = rank;

        const infoDiv = document.createElement('div');
        infoDiv.className = 'leaderboard-info';

        const nameSpan = document.createElement('span');
        nameSpan.className = 'leaderboard-name';
        nameSpan.textContent = info;

        infoDiv.appendChild(nameSpan);

        if (date && date !== 'N/A') {
            const dateSpan = document.createElement('span');
            dateSpan.style.fontSize = '12px';
            dateSpan.style.color = '#757575';
            dateSpan.style.display = 'block';
            dateSpan.style.marginTop = '2px';
            dateSpan.textContent = date;
            infoDiv.appendChild(dateSpan);
        }

        const scoreSpan = document.createElement('span');
        scoreSpan.className = 'leaderboard-score';
        scoreSpan.textContent = score;

        item.appendChild(rankSpan);
        item.appendChild(infoDiv);
        item.appendChild(scoreSpan);

        return item;
    },

    /**
     * 显示排行榜界面
     */
    show() {
        document.getElementById('leaderboard-screen').classList.add('active');
    },

    /**
     * 隐藏排行榜界面
     */
    hide() {
        document.getElementById('leaderboard-screen').classList.remove('active');
    }
};

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Leaderboard;
}
