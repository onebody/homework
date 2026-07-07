// ===== Game Engine =====

class GameEngine {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');

        this.state = GAME_STATE.IDLE;
        this.previousState = null;

        this.difficulty = DIFFICULTY.EASY;
        this.gameMode = GAME_MODE.CLASSIC;
        this.gridSize = GRID_SIZE;
        this.gridWidth = GRID_WIDTH;
        this.gridHeight = GRID_HEIGHT;

        this.snake = new Snake(this.gridWidth, this.gridHeight);
        this.food = new Food(this.gridWidth, this.gridHeight);
        this.obstacles = [];

        this.score = 0;
        this.highScore = 0;

        this.gameTime = 0;
        this.timeLimit = 60;
        this.lastUpdateTime = 0;
        this.accumulator = 0;

        this.animationFrameId = null;
        this.isRunning = false;

        // 粒子效果系统
        this.particles = [];

        // 得分飘字效果系统
        this.floatingTexts = [];

        // 蛇死亡闪烁动画
        this.deathAnimation = { active: false, timer: 0, duration: 1.5, blinkCount: 0 };

        this.settings = this.loadSettings();

        // 延迟初始化，避免在隐藏容器中计算Canvas尺寸
        this._needsResize = true;

        this.init();
    }

    init() {
        // 不立即调用 resizeCanvas，因为游戏界面可能还不可见
        this.loadHighScore();

        if (this.gameMode === GAME_MODE.OBSTACLE) {
            this.generateObstacles();
        }

        window.addEventListener('resize', debounce(() => {
            this._needsResize = true;
            if (this.state !== GAME_STATE.IDLE) {
                this.resizeCanvas();
            }
        }, 250));

        globalEventBus.emit('game:initialized', this);
    }

    /**
     * 调整Canvas尺寸，使其适应容器并保持网格对齐
     */
    resizeCanvas() {
        const container = this.canvas.parentElement;
        if (!container) return;

        const containerWidth = container.clientWidth;
        const containerHeight = container.clientHeight;

        // 如果容器尺寸为0（界面隐藏中），延迟调整
        if (containerWidth <= 0 || containerHeight <= 0) {
            this._needsResize = true;
            return;
        }

        this._needsResize = false;

        const maxWidth = Math.min(containerWidth - 20, 600);
        const maxHeight = Math.min(containerHeight - 40, 600);
        const size = Math.max(Math.min(maxWidth, maxHeight), this.gridSize);

        const scaledSize = Math.floor(size / this.gridSize) * this.gridSize;

        this.canvas.width = scaledSize;
        this.canvas.height = scaledSize;
        this.canvas.style.width = scaledSize + 'px';
        this.canvas.style.height = scaledSize + 'px';
    }

    loadSettings() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                return { ...DEFAULT_SETTINGS, ...parsed.settings };
            } catch (e) {
                console.error('Failed to load settings:', e);
            }
        }
        return { ...DEFAULT_SETTINGS };
    }

    saveSettings() {
        const data = this.getStorageData();
        data.settings = this.settings;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    }

    getStorageData() {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                return JSON.parse(saved);
            } catch (e) {
                return {};
            }
        }
        return {};
    }

    loadHighScore() {
        const data = this.getStorageData();
        if (data.highScores) {
            const mode = this.gameMode;
            const diff = this.difficulty.name;

            if (data.highScores[mode] && data.highScores[mode][diff] !== undefined) {
                this.highScore = data.highScores[mode][diff];
            }
        }
    }

    saveHighScore() {
        const data = this.getStorageData();
        if (!data.highScores) {
            data.highScores = {};
        }

        const mode = this.gameMode;
        const diff = this.difficulty.name;

        if (!data.highScores[mode]) {
            data.highScores[mode] = {};
        }

        if (!data.highScores[mode][diff] || this.score > data.highScores[mode][diff]) {
            data.highScores[mode][diff] = this.score;
            this.highScore = this.score;

            globalEventBus.emit('game:highScore', { score: this.score });
        }

        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    }

    /**
     * 保存完整游戏记录到历史记录（用于排行榜P2）
     * @param {number} score - 本次得分
     */
    saveGameRecord(score) {
        const data = this.getStorageData();
        if (!data.gameRecords) {
            data.gameRecords = [];
        }

        data.gameRecords.push({
            score: score,
            mode: this.gameMode,
            difficulty: this.difficulty.name,
            timeLimit: this.gameMode === GAME_MODE.TIMED ? this.timeLimit : null,
            date: new Date().toISOString(),
            snakeLength: this.snake ? this.snake.getLength() : 0
        });

        // 只保留最近100条记录
        if (data.gameRecords.length > 100) {
            data.gameRecords = data.gameRecords.slice(-100);
        }

        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    }

    generateObstacles() {
        this.obstacles = [];
        const count = this.difficulty.obstacleCount || 0;

        for (let i = 0; i < count; i++) {
            let position;
            let attempts = 0;

            do {
                position = {
                    x: randomInt(0, this.gridWidth - 1),
                    y: randomInt(0, this.gridHeight - 1)
                };
                attempts++;
            } while (
                (position.x === Math.floor(this.gridWidth / 2) &&
                 position.y === Math.floor(this.gridHeight / 2)) ||
                (Math.abs(position.x - Math.floor(this.gridWidth / 2)) <= 2 &&
                 Math.abs(position.y - Math.floor(this.gridHeight / 2)) <= 2) ||
                this.snake.isOnSnake(position) ||
                isPositionInArray(position, this.obstacles) ||
                attempts > 100
            );

            if (attempts <= 100) {
                this.obstacles.push(position);
            }
        }
    }

    start() {
        if (this.state === GAME_STATE.PLAYING) return;

        // 确保Canvas在游戏界面可见后才调整尺寸
        if (this._needsResize) {
            // 使用 requestAnimationFrame 等待DOM渲染
            requestAnimationFrame(() => {
                this.resizeCanvas();
                this._doStart();
            });
        } else {
            this._doStart();
        }
    }

    /**
     * 实际开始游戏逻辑
     */
    _doStart() {
        this.reset();
        this.state = GAME_STATE.READY;
        this.showReadyCountdown();

        globalEventBus.emit('game:start', { mode: this.gameMode, difficulty: this.difficulty.name });
    }

    showReadyCountdown() {
        const readyOverlay = document.getElementById('ready-overlay');
        const readyText = readyOverlay.querySelector('.ready-text');

        readyOverlay.style.display = 'flex';

        let count = 3;
        readyText.textContent = count.toString();

        const countdownInterval = setInterval(() => {
            count--;

            if (count > 0) {
                readyText.textContent = count.toString();
            } else if (count === 0) {
                readyText.textContent = 'GO!';
            } else {
                clearInterval(countdownInterval);
                readyOverlay.style.display = 'none';

                this.state = GAME_STATE.PLAYING;
                this.isRunning = true;
                this.lastUpdateTime = performance.now();
                this.gameLoop();

                globalEventBus.emit('game:playing', null);
            }
        }, 1000);
    }

    gameLoop() {
        if (!this.isRunning) return;

        const now = performance.now();
        const deltaTime = now - this.lastUpdateTime;
        this.lastUpdateTime = now;

        this.accumulator += deltaTime;

        const updateInterval = 1000 / this.difficulty.speed;

        while (this.accumulator >= updateInterval) {
            this.update(updateInterval / 1000);
            this.accumulator -= updateInterval;
        }

        // 更新粒子和飘字效果
        this.updateEffects(deltaTime / 1000);

        this.render();

        this.animationFrameId = requestAnimationFrame(() => this.gameLoop());
    }

    update(deltaTime) {
        if (this.state !== GAME_STATE.PLAYING) return;

        this.gameTime += deltaTime;

        if (this.gameMode === GAME_MODE.TIMED) {
            const remainingTime = this.timeLimit - this.gameTime;

            if (remainingTime <= 0) {
                this.gameOver();
                return;
            }

            globalEventBus.emit('game:timeUpdate', { remaining: Math.ceil(remainingTime) });
        }

        const head = this.snake.move(this.difficulty.throughWall);

        const collision = Collision.checkAll(
            head,
            this.snake.getBodyWithoutHead(),
            this.gridWidth,
            this.gridHeight,
            this.difficulty.throughWall,
            this.obstacles
        );

        if (collision.wall || collision.self || collision.obstacle) {
            this.gameOver();
            return;
        }

        if (Collision.checkFoodCollision(head, this.food.position)) {
            this.eatFood();
        } else {
            this.snake.body.pop();
        }

        if (this.food.isExpired()) {
            this.food.spawn(this.snake.body, this.obstacles);
        }
    }

    eatFood() {
        const foodValue = this.food.getValue();
        const foodPosition = { ...this.food.position };

        this.score += foodValue;

        // grow()是空方法但有意义：蛇增长的逻辑是在update()中吃到食物时不执行body.pop()
        // 调用grow()是为了代码可读性，标明"蛇在增长"
        this.snake.grow();

        // 生成粒子效果
        this.spawnParticles(foodPosition, this.food.type.color, foodValue >= 3 ? 15 : 8);

        // 生成得分飘字
        this.spawnFloatingText(foodPosition, '+' + foodValue, this.food.type.color);

        this.food.spawn(this.snake.body, this.obstacles);

        if (this.settings.vibrationEnabled) {
            vibrate(50);
        }

        if (this.settings.soundEnabled) {
            globalEventBus.emit('audio:play', { sound: 'eat' });
        }

        globalEventBus.emit('game:eatFood', {
            score: this.score,
            foodType: this.food.type,
            position: foodPosition,
            value: foodValue
        });

        // 检查成就
        AchievementManager.checkOnEatFood(this.score);
    }

    /**
     * 生成粒子效果
     * @param {Object} position - 网格坐标 {x, y}
     * @param {string} color - 粒子颜色
     * @param {number} count - 粒子数量
     */
    spawnParticles(position, color, count) {
        const centerX = position.x * this.gridSize + this.gridSize / 2;
        const centerY = position.y * this.gridSize + this.gridSize / 2;

        for (let i = 0; i < count; i++) {
            const angle = (Math.PI * 2 * i) / count + Math.random() * 0.5;
            const speed = 50 + Math.random() * 100;

            this.particles.push({
                x: centerX,
                y: centerY,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                life: 1.0,
                decay: 1.5 + Math.random() * 0.5,
                size: 2 + Math.random() * 3,
                color: color
            });
        }
    }

    /**
     * 生成得分飘字
     * @param {Object} position - 网格坐标 {x, y}
     * @param {string} text - 飘字内容
     * @param {string} color - 飘字颜色
     */
    spawnFloatingText(position, text, color) {
        const x = position.x * this.gridSize + this.gridSize / 2;
        const y = position.y * this.gridSize;

        this.floatingTexts.push({
            x: x,
            y: y,
            text: text,
            color: color,
            life: 1.0,
            decay: 1.0,
            vy: -60
        });
    }

    /**
     * 更新所有视觉效果（粒子、飘字、死亡动画）
     * @param {number} deltaTime - 时间增量（秒）
     */
    updateEffects(deltaTime) {
        // 更新粒子
        this.particles = this.particles.filter(p => {
            p.x += p.vx * deltaTime;
            p.y += p.vy * deltaTime;
            p.vy += 80 * deltaTime; // 重力
            p.life -= p.decay * deltaTime;
            return p.life > 0;
        });

        // 更新飘字
        this.floatingTexts = this.floatingTexts.filter(ft => {
            ft.y += ft.vy * deltaTime;
            ft.life -= ft.decay * deltaTime;
            return ft.life > 0;
        });

        // 更新死亡闪烁动画
        if (this.deathAnimation.active) {
            this.deathAnimation.timer -= deltaTime;
            this.deathAnimation.blinkCount++;

            if (this.deathAnimation.timer <= 0) {
                this.deathAnimation.active = false;
            }
        }
    }

    gameOver() {
        this.isRunning = false;
        this.state = GAME_STATE.GAME_OVER;

        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }

        // 启动死亡闪烁动画
        this.deathAnimation = {
            active: true,
            timer: 1.5,
            duration: 1.5,
            blinkCount: 0
        };

        // 渲染死亡动画
        this.renderDeathAnimation();

        this.saveHighScore();
        this.saveGameRecord(this.score);

        // 更新游戏统计
        this.updateStatistics();

        if (this.settings.soundEnabled) {
            globalEventBus.emit('audio:play', { sound: 'gameover' });
        }

        if (this.settings.vibrationEnabled) {
            vibrate([100, 50, 100]);
        }

        // 检查成就
        AchievementManager.checkOnGameOver(this.score);

        // 延迟显示游戏结束界面，让死亡动画播放
        setTimeout(() => {
            globalEventBus.emit('game:over', {
                score: this.score,
                highScore: this.highScore,
                mode: this.gameMode,
                difficulty: this.difficulty.name
            });
        }, 1500);
    }

    /**
     * 渲染蛇死亡闪烁动画
     */
    renderDeathAnimation() {
        if (!this.deathAnimation.active) return;

        const animate = () => {
            if (!this.deathAnimation.active) return;

            const ctx = this.ctx;
            const gridSize = this.gridSize;
            const canvasWidth = this.canvas.width;
            const canvasHeight = this.canvas.height;

            // 清空画布
            ctx.fillStyle = '#FAFAFA';
            ctx.fillRect(0, 0, canvasWidth, canvasHeight);

            // 绘制网格
            this.drawGrid(ctx, gridSize, canvasWidth, canvasHeight);

            // 绘制障碍物
            if (this.gameMode === GAME_MODE.OBSTACLE) {
                this.drawObstacles(ctx, gridSize);
            }

            // 绘制食物
            this.food.draw(ctx, gridSize);

            // 蛇闪烁效果：奇偶帧交替显示
            const showSnake = Math.floor(this.deathAnimation.blinkCount / 4) % 2 === 0;
            if (showSnake && this.snake) {
                const colors = SKIN_COLORS[this.snake.skin] || SKIN_COLORS.classic;
                for (let i = this.snake.body.length - 1; i >= 0; i--) {
                    const segment = this.snake.body[i];
                    const x = segment.x * gridSize;
                    const y = segment.y * gridSize;

                    // 死亡时蛇变红
                    ctx.fillStyle = i === 0 ? '#F44336' : '#FF8A80';
                    ctx.fillRect(x + 1, y + 1, gridSize - 2, gridSize - 2);
                }
            }

            requestAnimationFrame(() => {
                const now = performance.now();
                const dt = 1 / 60;
                this.deathAnimation.timer -= dt;
                this.deathAnimation.blinkCount++;
                if (this.deathAnimation.timer > 0) {
                    animate();
                } else {
                    this.deathAnimation.active = false;
                }
            });
        };

        animate();
    }

    /**
     * 更新游戏统计信息
     */
    updateStatistics() {
        const data = this.getStorageData();
        if (!data.statistics) {
            data.statistics = {
                totalGames: 0,
                totalPlayTime: 0,
                maxScore: 0,
                totalScore: 0
            };
        }

        data.statistics.totalGames++;
        data.statistics.totalPlayTime += this.gameTime;
        data.statistics.totalScore = (data.statistics.totalScore || 0) + this.score;
        if (this.score > data.statistics.maxScore) {
            data.statistics.maxScore = this.score;
        }

        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    }

    pause() {
        if (this.state !== GAME_STATE.PLAYING) return;

        this.previousState = this.state;
        this.state = GAME_STATE.PAUSED;
        this.isRunning = false;

        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }

        document.getElementById('pause-overlay').style.display = 'flex';

        globalEventBus.emit('game:paused', null);
    }

    resume() {
        if (this.state !== GAME_STATE.PAUSED) return;

        this.state = GAME_STATE.PLAYING;

        document.getElementById('pause-overlay').style.display = 'none';

        this.isRunning = true;
        this.lastUpdateTime = performance.now();
        this.gameLoop();

        globalEventBus.emit('game:resumed', null);
    }

    reset() {
        // 如果蛇或食物已被销毁（destroy后），需要重新创建
        if (!this.snake) {
            this.snake = new Snake(this.gridWidth, this.gridHeight);
        } else {
            this.snake.reset();
            this.snake.setSkin(this.settings.selectedSkin || 'classic');
        }

        this.food = new Food(this.gridWidth, this.gridHeight);
        this.food.spawn(this.snake.body, this.obstacles);

        this.score = 0;
        this.gameTime = 0;
        this.accumulator = 0;
        this.isRunning = false;

        // 清空视觉效果
        this.particles = [];
        this.floatingTexts = [];
        this.deathAnimation = { active: false, timer: 0, duration: 1.5, blinkCount: 0 };

        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }

        if (this.gameMode === GAME_MODE.OBSTACLE) {
            this.generateObstacles();
        }

        globalEventBus.emit('game:reset', null);
    }

    render() {
        if (this.state === GAME_STATE.IDLE) return;

        const ctx = this.ctx;
        const gridSize = this.gridSize;
        const canvasWidth = this.canvas.width;
        const canvasHeight = this.canvas.height;

        ctx.fillStyle = '#FAFAFA';
        ctx.fillRect(0, 0, canvasWidth, canvasHeight);

        this.drawGrid(ctx, gridSize, canvasWidth, canvasHeight);

        if (this.gameMode === GAME_MODE.OBSTACLE) {
            this.drawObstacles(ctx, gridSize);
        }

        this.food.draw(ctx, gridSize);
        this.snake.draw(ctx, gridSize);

        // 绘制粒子效果
        this.drawParticles(ctx);

        // 绘制飘字效果
        this.drawFloatingTexts(ctx);

        this.drawScore(ctx, canvasWidth);
    }

    drawGrid(ctx, gridSize, canvasWidth, canvasHeight) {
        ctx.strokeStyle = '#E0E0E0';
        ctx.lineWidth = 0.5;

        for (let x = 0; x <= canvasWidth; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvasHeight);
            ctx.stroke();
        }

        for (let y = 0; y <= canvasHeight; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvasWidth, y);
            ctx.stroke();
        }
    }

    drawObstacles(ctx, gridSize) {
        if (!this.obstacles || this.obstacles.length === 0) return;

        ctx.fillStyle = '#9E9E9E';

        this.obstacles.forEach(obs => {
            const x = obs.x * gridSize;
            const y = obs.y * gridSize;

            ctx.fillRect(x + 1, y + 1, gridSize - 2, gridSize - 2);

            ctx.strokeStyle = '#F44336';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(x + 4, y + 4);
            ctx.lineTo(x + gridSize - 4, y + gridSize - 4);
            ctx.moveTo(x + gridSize - 4, y + 4);
            ctx.lineTo(x + 4, y + gridSize - 4);
            ctx.stroke();
        });
    }

    /**
     * 绘制粒子效果
     * @param {CanvasRenderingContext2D} ctx - Canvas上下文
     */
    drawParticles(ctx) {
        this.particles.forEach(p => {
            ctx.globalAlpha = Math.max(0, p.life);
            ctx.fillStyle = p.color;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2);
            ctx.fill();
        });
        ctx.globalAlpha = 1.0;
    }

    /**
     * 绘制飘字效果
     * @param {CanvasRenderingContext2D} ctx - Canvas上下文
     */
    drawFloatingTexts(ctx) {
        this.floatingTexts.forEach(ft => {
            ctx.globalAlpha = Math.max(0, ft.life);
            ctx.fillStyle = ft.color;
            ctx.font = 'bold 18px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(ft.text, ft.x, ft.y);
        });
        ctx.globalAlpha = 1.0;
    }

    drawScore(ctx, canvasWidth) {
        ctx.fillStyle = '#212121';
        ctx.font = '16px Arial';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText('分数: ' + this.score, 10, 10);

        ctx.textAlign = 'right';
        ctx.fillText('最高分: ' + this.highScore, canvasWidth - 10, 10);
    }

    handleInput(direction) {
        if (this.state !== GAME_STATE.PLAYING) return;
        this.snake.setDirection(direction);
    }

    setDifficulty(level) {
        if (DIFFICULTY[level.toUpperCase()]) {
            this.difficulty = DIFFICULTY[level.toUpperCase()];
            this.loadHighScore();
        }
    }

    setGameMode(mode) {
        if (GAME_MODE[mode.toUpperCase()]) {
            this.gameMode = GAME_MODE[mode.toUpperCase()];

            if (this.gameMode === GAME_MODE.OBSTACLE) {
                this.generateObstacles();
            } else {
                this.obstacles = [];
            }

            this.loadHighScore();
        }
    }

    setSkin(skinName) {
        this.settings.selectedSkin = skinName;
        if (this.snake) {
            this.snake.setSkin(skinName);
        }
        this.saveSettings();
    }

    toggleSound() {
        this.settings.soundEnabled = !this.settings.soundEnabled;
        this.saveSettings();
        return this.settings.soundEnabled;
    }

    toggleVibration() {
        this.settings.vibrationEnabled = !this.settings.vibrationEnabled;
        this.saveSettings();
        return this.settings.vibrationEnabled;
    }

    setTimeLimit(seconds) {
        this.timeLimit = seconds;
    }

    getScore() {
        return this.score;
    }

    getHighScore() {
        return this.highScore;
    }

    getState() {
        return this.state;
    }

    getSnakeLength() {
        return this.snake ? this.snake.getLength() : 0;
    }

    /**
     * 停止游戏但保留引擎实例可重用（用于返回菜单）
     * 与 destroy() 不同，stop() 不会将 snake/food 设为 null
     */
    stop() {
        this.isRunning = false;
        this.state = GAME_STATE.IDLE;

        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }

        // 清空视觉效果
        this.particles = [];
        this.floatingTexts = [];
        this.deathAnimation.active = false;

        if (this.ctx) {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }

        globalEventBus.emit('game:stopped', null);
    }

    destroy() {
        this.isRunning = false;

        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }

        this.snake = null;
        this.food = null;
        this.obstacles = [];

        // 清空视觉效果
        this.particles = [];
        this.floatingTexts = [];
        this.deathAnimation.active = false;

        if (this.ctx) {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }

        globalEventBus.emit('game:destroyed', null);
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = GameEngine;
}
