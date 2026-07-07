// ===== Food Class =====

class Food {
    /**
     * 构造函数
     * @param {number} gridWidth - 网格宽度
     * @param {number} gridHeight - 网格高度
     * @param {number} duration - 存在时长（毫秒），-1表示不消失
     */
    constructor(gridWidth = GRID_WIDTH, gridHeight = GRID_HEIGHT, duration = -1) {
        this.gridWidth = gridWidth;
        this.gridHeight = gridHeight;
        this.position = { x: 0, y: 0 };
        this.type = FOOD_TYPE.NORMAL;
        this.spawnTime = Date.now();
        this.duration = duration; // -1 表示永不过期
        this.active = false;
        
        // 生成初始食物
        this.spawn([]);
    }

    /**
     * 在随机位置生成食物（避开蛇身）
     * @param {Array} snakeBody - 蛇身坐标数组
     * @param {Array} obstacles - 障碍物坐标数组（可选）
     */
    spawn(snakeBody = [], obstacles = []) {
        let attempts = 0;
        const maxAttempts = 1000;
        
        do {
            this.position = {
                x: randomInt(0, this.gridWidth - 1),
                y: randomInt(0, this.gridHeight - 1)
            };
            attempts++;
            
            if (attempts > maxAttempts) {
                console.warn('Could not find empty position for food');
                break;
            }
        } while (
            isPositionInArray(this.position, snakeBody) ||
            isPositionInArray(this.position, obstacles || [])
        );
        
        // 随机确定食物类型
        this.type = getRandomFoodType();
        this.spawnTime = Date.now();
        this.active = true;
    }

    /**
     * 检查食物是否过期
     * @returns {boolean} 是否过期
     */
    isExpired() {
        if (this.duration <= 0) return false; // 永不过期
        return (Date.now() - this.spawnTime) > this.duration;
    }

    /**
     * 获取食物分数价值
     * @returns {number} 分数
     */
    getValue() {
        return this.type.value;
    }

    /**
     * 绘制食物
     * @param {CanvasRenderingContext2D} ctx - Canvas上下文
     * @param {number} gridSize - 格子大小
     */
    draw(ctx, gridSize) {
        if (!this.active) return;
        
        const x = this.position.x * gridSize;
        const y = this.position.y * gridSize;
        const centerX = x + gridSize / 2;
        const centerY = y + gridSize / 2;
        const radius = gridSize / 2 - 2;
        
        // 绘制食物（圆形）
        ctx.fillStyle = this.type.color;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();
        
        // 添加高光效果
        ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.beginPath();
        ctx.arc(centerX - radius / 3, centerY - radius / 3, radius / 3, 0, Math.PI * 2);
        ctx.fill();
        
        // 特殊食物添加额外效果
        if (this.type === FOOD_TYPE.GOLDEN || this.type === FOOD_TYPE.RAINBOW) {
            // 金色或彩虹食物添加闪烁效果
            const pulse = Math.sin(Date.now() / 200) * 0.2 + 0.8;
            ctx.globalAlpha = pulse;
            ctx.fillStyle = this.type === FOOD_TYPE.RAINBOW ? '#FF69B4' : '#FFD700';
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius + 2, 0, Math.PI * 2);
            ctx.fill();
            ctx.globalAlpha = 1.0;
        }
    }

    /**
     * 检查某个位置是否是食物位置
     * @param {Object} position - 坐标 {x, y}
     * @returns {boolean} 是否是食物
     */
    isAtPosition(position) {
        return this.active && 
               this.position.x === position.x && 
               this.position.y === position.y;
    }

    /**
     * 使食物被吃掉（隐藏）
     */
    consume() {
        this.active = false;
    }

    /**
     * 重置食物
     * @param {Array} snakeBody - 蛇身坐标数组
     * @param {Array} obstacles - 障碍物坐标数组（可选）
     */
    reset(snakeBody = [], obstacles = []) {
        this.spawn(snakeBody, obstacles);
    }

    /**
     * 获取食物位置
     * @returns {Object} 坐标 {x, y}
     */
    getPosition() {
        return { ...this.position };
    }

    /**
     * 设置食物类型（用于测试）
     * @param {Object} type - 食物类型对象
     */
    setType(type) {
        if (Object.values(FOOD_TYPE).includes(type)) {
            this.type = type;
        }
    }

    /**
     * 设置存在时长
     * @param {number} duration - 时长（毫秒），-1表示永不过期
     */
    setDuration(duration) {
        this.duration = duration;
    }
}

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Food;
}
