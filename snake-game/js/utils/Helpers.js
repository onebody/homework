// ===== Utility Functions =====

/**
 * 生成指定范围内的随机整数
 * @param {number} min - 最小值（包含）
 * @param {number} max - 最大值（包含）
 * @returns {number} 随机整数
 */
function randomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

/**
 * 检查两个坐标点是否相同
 * @param {Object} pos1 - 坐标点1 {x, y}
 * @param {Object} pos2 - 坐标点2 {x, y}
 * @returns {boolean} 是否相同
 */
function isSamePosition(pos1, pos2) {
    return pos1.x === pos2.x && pos1.y === pos2.y;
}

/**
 * 检查某个位置是否在数组中
 * @param {Object} position - 坐标 {x, y}
 * @param {Array} array - 坐标数组
 * @returns {boolean} 是否存在
 */
function isPositionInArray(position, array) {
    return array.some(pos => isSamePosition(pos, position));
}

/**
 * 生成随机食物类型
 * @returns {Object} 食物类型对象 {color, value}
 */
function getRandomFoodType() {
    const rand = Math.random();
    if (rand < 0.05) { // 5% 概率
        return FOOD_TYPE.RAINBOW;
    } else if (rand < 0.15) { // 10% 概率
        return FOOD_TYPE.GOLDEN;
    } else {
        return FOOD_TYPE.NORMAL;
    }
}

/**
 * 格式化时间（秒 -> MM:SS）
 * @param {number} seconds - 秒数
 * @returns {string} 格式化后的时间字符串
 */
function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * 防抖函数
 * @param {Function} func - 要防抖的函数
 * @param {number} wait - 等待时间（毫秒）
 * @returns {Function} 防抖后的函数
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 节流函数
 * @param {Function} func - 要节流的函数
 * @param {number} limit - 时间间隔（毫秒）
 * @returns {Function} 节流后的函数
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * 深拷贝对象
 * @param {*} obj - 要拷贝的对象
 * @returns {*} 拷贝后的对象
 */
function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * 获取URL参数
 * @param {string} name - 参数名
 * @returns {string|null} 参数值
 */
function getUrlParam(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

/**
 * 触发设备震动（移动端）
 * @param {number|number[]} pattern - 震动模式（毫秒）
 */
function vibrate(pattern) {
    if (navigator.vibrate) {
        navigator.vibrate(pattern);
    }
}

/**
 * 检查是否移动端
 * @returns {boolean} 是否移动设备
 */
function isMobileDevice() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        randomInt,
        isSamePosition,
        isPositionInArray,
        getRandomFoodType,
        formatTime,
        debounce,
        throttle,
        deepClone,
        getUrlParam,
        vibrate,
        isMobileDevice
    };
}
