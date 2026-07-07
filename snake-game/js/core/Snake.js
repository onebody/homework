// ===== Snake Class =====

class Snake {
    /**
     * 构造函数
     * @param {number} gridWidth - 网格宽度
     * @param {number} gridHeight - 网格高度
     * @param {string} skin - 皮肤名称
     */
    constructor(gridWidth = GRID_WIDTH, gridHeight = GRID_HEIGHT, skin = 'classic') {
        this.gridWidth = gridWidth;
        this.gridHeight = gridHeight;
        this.skin = skin;
        this.reset();
    }

    /**
     * 重置蛇到初始状态
     */
    reset() {
        // 初始位置在中间
        const startX = Math.floor(this.gridWidth / 2);
        const startY = Math.floor(this.gridHeight / 2);

        this.body = [
            { x: startX, y: startY },     // 头部
            { x: startX - 1, y: startY }, // 第1节
            { x: startX - 2, y: startY }  // 第2节
        ];

        this.direction = DIRECTION.RIGHT;
        this.nextDirection = DIRECTION.RIGHT;
        this.isAlive = true;
    }

    /**
     * 设置移动方向（防止180度转向）
     * @param {Object} newDirection - 新方向 {x, y}
     */
    setDirection(newDirection) {
        // 防止180度转向
        if (this.direction.x + newDirection.x === 0 &&
            this.direction.y + newDirection.y === 0) {
            return; // 忽略反向指令
        }
        this.nextDirection = newDirection;
    }

    /**
     * 更新方向（在移动前调用）
     */
    updateDirection() {
        this.direction = this.nextDirection;
    }

    /**
     * 移动蛇
     * @param {boolean} throughWall - 是否穿墙
     * @returns {Object|null} 新的头部坐标，如果死亡则返回null
     */
    move(throughWall = false) {
        if (!this.isAlive) return null;

        // 更新方向
        this.updateDirection();

        // 计算新头部位置
        const head = this.body[0];
        let newHead = {
            x: head.x + this.direction.x,
            y: head.y + this.direction.y
        };

        // 穿墙处理
        if (throughWall) {
            if (newHead.x < 0) newHead.x = this.gridWidth - 1;
            if (newHead.x >= this.gridWidth) newHead.x = 0;
            if (newHead.y < 0) newHead.y = this.gridHeight - 1;
            if (newHead.y >= this.gridHeight) newHead.y = 0;
        }

        // 添加新头部
        this.body.unshift(newHead);

        // 注意：移除尾部的逻辑在 GameEngine.update() 中处理
        // 如果蛇吃到食物，GameEngine 不执行 body.pop()，蛇就增长了
        return newHead;
    }

    /**
     * 增长蛇身（吃到食物时调用）
     *
     * 注意：此方法为语义方法，实际增长逻辑在 GameEngine.update() 中：
     *   - 吃到食物时，GameEngine 不调用 body.pop()，蛇就自然增长
     *   - 未吃到食物时，GameEngine 调用 body.pop() 移除尾部，蛇长度不变
     * 调用 grow() 是为了让代码可读，明确表达"蛇在增长"的语义。
     */
    grow() {
        // 蛇的增长逻辑由 GameEngine 控制：吃到食物时不执行 body.pop()
        // 此处无需额外操作
    }

    /**
     * 获取蛇头
     * @returns {Object} 头部坐标 {x, y}
     */
    getHead() {
        return this.body[0];
    }

    /**
     * 获取蛇身（不含头）
     * @returns {Array} 蛇身坐标数组
     */
    getBodyWithoutHead() {
        return this.body.slice(1);
    }

    /**
     * 检查是否撞到自己
     * @returns {boolean} 是否撞到自己
     */
    checkSelfCollision() {
        const head = this.getHead();
        return this.getBodyWithoutHead().some(segment =>
            segment.x === head.x && segment.y === head.y
        );
    }

    /**
     * 绘制蛇
     * @param {CanvasRenderingContext2D} ctx - Canvas上下文
     * @param {number} gridSize - 格子大小
     */
    draw(ctx, gridSize) {
        const colors = SKIN_COLORS[this.skin] || SKIN_COLORS.classic;

        // 绘制蛇身（从尾部到头部，这样头部在最上层）
        for (let i = this.body.length - 1; i >= 0; i--) {
            const segment = this.body[i];
            const x = segment.x * gridSize;
            const y = segment.y * gridSize;

            if (i === 0) {
                // 头部
                ctx.fillStyle = colors.head;
                ctx.fillRect(x + 1, y + 1, gridSize - 2, gridSize - 2);

                // 绘制眼睛
                ctx.fillStyle = colors.eye;
                const eyeSize = gridSize / 5;
                const eyeOffset = gridSize / 3;

                // 根据方向绘制眼睛
                if (this.direction === DIRECTION.RIGHT) {
                    ctx.fillRect(x + gridSize - eyeOffset, y + eyeOffset, eyeSize, eyeSize);
                    ctx.fillRect(x + gridSize - eyeOffset, y + gridSize - eyeOffset - eyeSize, eyeSize, eyeSize);
                } else if (this.direction === DIRECTION.LEFT) {
                    ctx.fillRect(x + eyeOffset - eyeSize, y + eyeOffset, eyeSize, eyeSize);
                    ctx.fillRect(x + eyeOffset - eyeSize, y + gridSize - eyeOffset - eyeSize, eyeSize, eyeSize);
                } else if (this.direction === DIRECTION.UP) {
                    ctx.fillRect(x + eyeOffset, y + eyeOffset - eyeSize, eyeSize, eyeSize);
                    ctx.fillRect(x + gridSize - eyeOffset - eyeSize, y + eyeOffset - eyeSize, eyeSize, eyeSize);
                } else if (this.direction === DIRECTION.DOWN) {
                    ctx.fillRect(x + eyeOffset, y + gridSize - eyeOffset, eyeSize, eyeSize);
                    ctx.fillRect(x + gridSize - eyeOffset - eyeSize, y + gridSize - eyeOffset, eyeSize, eyeSize);
                }
            } else {
                // 身体
                ctx.fillStyle = colors.body;
                ctx.fillRect(x + 2, y + 2, gridSize - 4, gridSize - 4);

                // 身体连接处的圆角效果
                ctx.fillStyle = colors.body;
                ctx.beginPath();
                ctx.arc(x + gridSize / 2, y + gridSize / 2, gridSize / 2 - 2, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    /**
     * 设置皮肤
     * @param {string} skinName - 皮肤名称
     */
    setSkin(skinName) {
        if (SKIN_COLORS[skinName]) {
            this.skin = skinName;
        }
    }

    /**
     * 获取蛇的长度
     * @returns {number} 长度
     */
    getLength() {
        return this.body.length;
    }

    /**
     * 检查某个位置是否在蛇身上
     * @param {Object} position - 坐标 {x, y}
     * @returns {boolean} 是否在蛇身上
     */
    isOnSnake(position) {
        return this.body.some(segment => segment.x === position.x && segment.y === position.y);
    }
}

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Snake;
}
