// ===== Canvas Renderer Module =====

const CanvasRenderer = {
    /**
     * 绘制网格背景
     * @param {CanvasRenderingContext2D} ctx - Canvas上下文
     * @param {number} gridSize - 格子大小
     * @param {number} canvasWidth - Canvas宽度
     * @param {number} canvasHeight - Canvas高度
     */
    drawGrid(ctx, gridSize, canvasWidth, canvasHeight) {
        ctx.strokeStyle = '#E0E0E0';
        ctx.lineWidth = 0.5;

        // 垂直线
        for (let x = 0; x <= canvasWidth; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvasHeight);
            ctx.stroke();
        }

        // 水平线
        for (let y = 0; y <= canvasHeight; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvasWidth, y);
            ctx.stroke();
        }
    },

    /**
     * 绘制障碍物
     * @param {CanvasRenderingContext2D} ctx - Canvas上下文
     * @param {Array} obstacles - 障碍物坐标数组
     * @param {number} gridSize - 格子大小
     */
    drawObstacles(ctx, obstacles, gridSize) {
        if (!obstacles || obstacles.length === 0) return;

        ctx.fillStyle = '#9E9E9E';

        obstacles.forEach(obs => {
            const x = obs.x * gridSize;
            const y = obs.y * gridSize;

            // 绘制障碍物（带阴影效果）
            ctx.fillRect(x + 1, y + 1, gridSize - 2, gridSize - 2);

            // 绘制交叉线表示危险
            ctx.strokeStyle = '#F44336';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(x + 4, y + 4);
            ctx.lineTo(x + gridSize - 4, y + gridSize - 4);
            ctx.moveTo(x + gridSize - 4, y + 4);
            ctx.lineTo(x + 4, y + gridSize - 4);
            ctx.stroke();
        });
    },

    /**
     * 绘制蛇
     * @param {CanvasRenderingContext2D} ctx - Canvas上下文
     * @param {Snake} snake - 蛇对象
     * @param {number} gridSize - 格子大小
     */
    drawSnake(ctx, snake, gridSize) {
        const colors = SKIN_COLORS[snake.skin] || SKIN_COLORS.classic;

        // 绘制蛇身（从尾部到头部，这样头部在最上层）
        for (let i = snake.body.length - 1; i >= 0; i--) {
            const segment = snake.body[i];
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
                if (snake.direction === DIRECTION.RIGHT) {
                    ctx.fillRect(x + gridSize - eyeOffset, y + eyeOffset, eyeSize, eyeSize);
                    ctx.fillRect(x + gridSize - eyeOffset, y + gridSize - eyeOffset - eyeSize, eyeSize, eyeSize);
                } else if (snake.direction === DIRECTION.LEFT) {
                    ctx.fillRect(x + eyeOffset - eyeSize, y + eyeOffset, eyeSize, eyeSize);
                    ctx.fillRect(x + eyeOffset - eyeSize, y + gridSize - eyeOffset - eyeSize, eyeSize, eyeSize);
                } else if (snake.direction === DIRECTION.UP) {
                    ctx.fillRect(x + eyeOffset, y + eyeOffset - eyeSize, eyeSize, eyeSize);
                    ctx.fillRect(x + gridSize - eyeOffset - eyeSize, y + eyeOffset - eyeSize, eyeSize, eyeSize);
                } else if (snake.direction === DIRECTION.DOWN) {
                    ctx.fillRect(x + eyeOffset, y + gridSize - eyeOffset, eyeSize, eyeSize);
                    ctx.fillRect(x + gridSize - eyeOffset - eyeSize, y + gridSize - eyeOffset, eyeSize, eyeSize);
                }
            } else {
                // 身体
                ctx.fillStyle = colors.body;
                ctx.fillRect(x + 2, y + 2, gridSize - 4, gridSize - 4);

                // 身体连接处的圆角效果
                ctx.beginPath();
                ctx.arc(x + gridSize / 2, y + gridSize / 2, gridSize / 2 - 2, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    },

    /**
     * 绘制食物
     * @param {CanvasRenderingContext2D} ctx - Canvas上下文
     * @param {Food} food - 食物对象
     * @param {number} gridSize - 格子大小
     */
    drawFood(ctx, food, gridSize) {
        if (!food.active) return;

        const x = food.position.x * gridSize;
        const y = food.position.y * gridSize;
        const centerX = x + gridSize / 2;
        const centerY = y + gridSize / 2;
        const radius = gridSize / 2 - 2;

        // 绘制食物（圆形）
        ctx.fillStyle = food.type.color;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.fill();

        // 添加高光效果
        ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.beginPath();
        ctx.arc(centerX - radius / 3, centerY - radius / 3, radius / 3, 0, Math.PI * 2);
        ctx.fill();

        // 特殊食物添加额外效果
        if (food.type === FOOD_TYPE.GOLDEN || food.type === FOOD_TYPE.RAINBOW) {
            // 金色或彩虹食物添加闪烁效果
            const pulse = Math.sin(Date.now() / 200) * 0.2 + 0.8;
            ctx.globalAlpha = pulse;
            ctx.fillStyle = food.type === FOOD_TYPE.RAINBOW ? '#FF69B4' : '#FFD700';
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius + 2, 0, Math.PI * 2);
            ctx.fill();
            ctx.globalAlpha = 1.0;
        }
    },

    /**
     * 绘制分数（Canvas上）
     * @param {CanvasRenderingContext2D} ctx - Canvas上下文
     * @param {number} score - 当前分数
     * @param {number} highScore - 最高分
     * @param {number} canvasWidth - Canvas宽度
     */
    drawScore(ctx, score, highScore, canvasWidth) {
        ctx.fillStyle = '#212121';
        ctx.font = '16px Arial';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText(`分数: ${score}`, 10, 10);

        ctx.textAlign = 'right';
        ctx.fillText(`最高分: ${highScore}`, canvasWidth - 10, 10);
    },

    /**
     * 清除画布
     * @param {CanvasRenderingContext2D} ctx - Canvas上下文
     * @param {number} width - 画布宽度
     * @param {number} height - 画布高度
     */
    clearCanvas(ctx, width, height) {
        ctx.fillStyle = '#FAFAFA';
        ctx.fillRect(0, 0, width, height);
    }
};

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CanvasRenderer;
}
