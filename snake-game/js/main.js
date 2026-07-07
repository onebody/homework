// ===== Main Entry Point =====

// 等待DOM加载完成
document.addEventListener('DOMContentLoaded', () => {
    console.log('Snake Adventure - Initializing...');

    // 创建游戏引擎实例
    const gameEngine = new GameEngine('game-canvas');

    // 存储全局引用（供成就系统等使用）
    window._gameEngine = gameEngine;

    // 初始化各模块
    AchievementManager.init();
    Menu.init(gameEngine);
    HUD.init(gameEngine);
    Settings.init(gameEngine);
    Leaderboard.init(gameEngine);
    AudioManager.init();

    // 设置初始界面
    document.getElementById('menu-screen').classList.add('active');

    // 绑定成就界面按钮
    document.getElementById('btn-achievements').addEventListener('click', () => {
        document.getElementById('menu-screen').classList.remove('active');
        document.getElementById('achievements-screen').classList.add('active');
        renderAchievementsScreen();
    });

    document.getElementById('btn-achievements-back').addEventListener('click', () => {
        document.getElementById('achievements-screen').classList.remove('active');
        document.getElementById('menu-screen').classList.add('active');
    });

    // 绑定全局键盘事件
    document.addEventListener('keydown', (e) => {
        // 防止方向键滚动页面
        if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {
            e.preventDefault();
        }

        // 只在游戏进行中时处理方向键
        if (gameEngine.getState() === GAME_STATE.PLAYING) {
            switch (e.key) {
                case 'ArrowUp':
                case 'w':
                case 'W':
                    gameEngine.handleInput(DIRECTION.UP);
                    break;
                case 'ArrowDown':
                case 's':
                case 'S':
                    gameEngine.handleInput(DIRECTION.DOWN);
                    break;
                case 'ArrowLeft':
                case 'a':
                case 'A':
                    gameEngine.handleInput(DIRECTION.LEFT);
                    break;
                case 'ArrowRight':
                case 'd':
                case 'D':
                    gameEngine.handleInput(DIRECTION.RIGHT);
                    break;
                case 'Escape':
                    gameEngine.pause();
                    break;
            }
        } else if (gameEngine.getState() === GAME_STATE.PAUSED) {
            // 暂停时按ESC或空格恢复
            if (e.key === 'Escape' || e.key === ' ') {
                gameEngine.resume();
            }
        }
    });

    // 绑定移动端滑动操作
    let touchStartX = 0;
    let touchStartY = 0;

    document.addEventListener('touchstart', (e) => {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
        if (gameEngine.getState() !== GAME_STATE.PLAYING) return;

        const touchEndX = e.changedTouches[0].clientX;
        const touchEndY = e.changedTouches[0].clientY;

        const deltaX = touchEndX - touchStartX;
        const deltaY = touchEndY - touchStartY;

        // 判断滑动方向（需要最小滑动距离）
        const minSwipeDistance = 30;

        if (Math.abs(deltaX) > Math.abs(deltaY)) {
            // 水平滑动
            if (Math.abs(deltaX) > minSwipeDistance) {
                if (deltaX > 0) {
                    gameEngine.handleInput(DIRECTION.RIGHT);
                } else {
                    gameEngine.handleInput(DIRECTION.LEFT);
                }
            }
        } else {
            // 垂直滑动
            if (Math.abs(deltaY) > minSwipeDistance) {
                if (deltaY > 0) {
                    gameEngine.handleInput(DIRECTION.DOWN);
                } else {
                    gameEngine.handleInput(DIRECTION.UP);
                }
            }
        }
    }, { passive: true });

    // 绑定虚拟方向键
    document.querySelectorAll('.d-pad-btn[data-direction]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            if (gameEngine.getState() !== GAME_STATE.PLAYING) return;

            const direction = e.target.dataset.direction;
            switch (direction) {
                case 'up':
                    gameEngine.handleInput(DIRECTION.UP);
                    break;
                case 'down':
                    gameEngine.handleInput(DIRECTION.DOWN);
                    break;
                case 'left':
                    gameEngine.handleInput(DIRECTION.LEFT);
                    break;
                case 'right':
                    gameEngine.handleInput(DIRECTION.RIGHT);
                    break;
            }
        });

        // 移动端触摸事件优化：防止长按弹出菜单
        btn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            if (gameEngine.getState() !== GAME_STATE.PLAYING) return;

            const direction = e.target.dataset.direction;
            switch (direction) {
                case 'up':
                    gameEngine.handleInput(DIRECTION.UP);
                    break;
                case 'down':
                    gameEngine.handleInput(DIRECTION.DOWN);
                    break;
                case 'left':
                    gameEngine.handleInput(DIRECTION.LEFT);
                    break;
                case 'right':
                    gameEngine.handleInput(DIRECTION.RIGHT);
                    break;
            }
        });
    });

    // 监听页面可见性变化（自动暂停）
    document.addEventListener('visibilitychange', () => {
        if (document.hidden && gameEngine.getState() === GAME_STATE.PLAYING) {
            gameEngine.pause();
        }
    });

    // 监听音频事件
    globalEventBus.on('audio:play', (data) => {
        AudioManager.play(data.sound);
    });

    // 显示初始化完成
    console.log('Snake Adventure - Ready to play!');
    console.log('Game Engine:', gameEngine);
});

/**
 * 渲染成就界面
 */
function renderAchievementsScreen() {
    const listContainer = document.getElementById('achievements-list');
    const progressElement = document.getElementById('achievements-progress');

    // 更新进度
    const unlocked = AchievementManager.getUnlockedCount();
    const total = AchievementManager.getTotalCount();
    progressElement.textContent = `${unlocked} / ${total} 已解锁`;

    // 清空列表
    listContainer.innerHTML = '';

    // 渲染每个成就
    AchievementManager.getAllAchievements().forEach(achievement => {
        const item = document.createElement('div');
        item.className = 'achievement-item ' + (achievement.unlocked ? 'unlocked' : 'locked');

        item.innerHTML = `
            <span class="achievement-icon">${achievement.icon}</span>
            <div class="achievement-info">
                <div class="achievement-name">${achievement.name}</div>
                <div class="achievement-desc">${achievement.description}</div>
                <div class="achievement-status ${achievement.unlocked ? 'unlocked' : 'locked'}">
                    ${achievement.unlocked ? '✅ 已解锁' : '🔒 未解锁'}
                </div>
            </div>
        `;

        listContainer.appendChild(item);
    });
}
