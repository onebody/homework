// ===== Event Bus (Pub/Sub Pattern) =====

class EventBus {
    constructor() {
        this.listeners = {};
    }

    /**
     * 订阅事件
     * @param {string} event - 事件名称
     * @param {Function} callback - 回调函数
     */
    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }

    /**
     * 取消订阅
     * @param {string} event - 事件名称
     * @param {Function} callback - 要移除的回调函数
     */
    off(event, callback) {
        if (!this.listeners[event]) return;
        
        if (callback) {
            this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
        } else {
            delete this.listeners[event];
        }
    }

    /**
     * 发布事件
     * @param {string} event - 事件名称
     * @param {*} data - 事件数据
     */
    emit(event, data) {
        if (!this.listeners[event]) return;
        
        this.listeners[event].forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error(`Error in event listener for ${event}:`, error);
            }
        });
    }

    /**
     * 一次性订阅（只触发一次）
     * @param {string} event - 事件名称
     * @param {Function} callback - 回调函数
     */
    once(event, callback) {
        const onceWrapper = (data) => {
            callback(data);
            this.off(event, onceWrapper);
        };
        this.on(event, onceWrapper);
    }

    /**
     * 清除所有监听器
     */
    clear() {
        this.listeners = {};
    }
}

// 创建全局事件总线实例
const globalEventBus = new EventBus();

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EventBus;
}
