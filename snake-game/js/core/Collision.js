// ===== Collision Detection Module =====

const Collision = {
    /**
     * 检测撞墙
     * @param {Object} head - 蛇头坐标 {x, y}
     * @param {number} gridWidth - 网格宽度
     * @param {number} gridHeight - 网格高度
     * @param {boolean} throughWall - 是否穿墙
     * @returns {boolean} 是否撞墙
     */
    checkWallCollision(head, gridWidth, gridHeight, throughWall) {
        if (throughWall) {
            return false; // 穿墙模式下不检测
        }
        return head.x < 0 || head.x >= gridWidth || head.y < 0 || head.y >= gridHeight;
    },

    /**
     * 检测撞自身
     * @param {Object} head - 蛇头坐标 {x, y}
     * @param {Array} body - 蛇身坐标数组（不包含头）
     * @returns {boolean} 是否撞到自身
     */
    checkSelfCollision(head, body) {
        return body.some(segment => segment.x === head.x && segment.y === head.y);
    },

    /**
     * 检测吃到食物
     * @param {Object} head - 蛇头坐标 {x, y}
     * @param {Object} foodPos - 食物坐标 {x, y}
     * @returns {boolean} 是否吃到食物
     */
    checkFoodCollision(head, foodPos) {
        return head.x === foodPos.x && head.y === foodPos.y;
    },

    /**
     * 检测撞到障碍物
     * @param {Object} head - 蛇头坐标 {x, y}
     * @param {Array} obstacles - 障碍物坐标数组
     * @returns {boolean} 是否撞到障碍物
     */
    checkObstacleCollision(head, obstacles) {
        if (!obstacles || obstacles.length === 0) return false;
        return obstacles.some(obs => obs.x === head.x && obs.y === head.y);
    },

    /**
     * 综合碰撞检测
     * @param {Object} head - 蛇头坐标
     * @param {Array} body - 蛇身
     * @param {number} gridWidth - 网格宽度
     * @param {number} gridHeight - 网格高度
     * @param {boolean} throughWall - 是否穿墙
     * @param {Array} obstacles - 障碍物数组
     * @returns {Object} 碰撞结果 {wall, self, obstacle}
     */
    checkAll(head, body, gridWidth, gridHeight, throughWall, obstacles) {
        return {
            wall: this.checkWallCollision(head, gridWidth, gridHeight, throughWall),
            self: this.checkSelfCollision(head, body),
            obstacle: this.checkObstacleCollision(head, obstacles || [])
        };
    }
};

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Collision;
}
