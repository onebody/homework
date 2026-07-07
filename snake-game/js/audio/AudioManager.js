// ===== Audio Manager Module =====

const AudioManager = {
    /**
     * 初始化音频管理器
     */
    init() {
        this.sounds = {};
        this.enabled = true;
        this.loadSounds();
    },

    /**
     * 加载音效（使用Web Audio API生成简单音效）
     */
    loadSounds() {
        // 使用Web Audio API生成音效，无需外部音频文件
        this.audioContext = null;
        
        // 尝试创建AudioContext（需要用户交互后才能创建）
        this.initAudioContext = () => {
            if (!this.audioContext) {
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (AudioContext) {
                    this.audioContext = new AudioContext();
                }
            }
        };

        // 监听用户首次交互，初始化AudioContext
        document.addEventListener('click', () => {
            this.initAudioContext();
        }, { once: true });

        document.addEventListener('keydown', () => {
            this.initAudioContext();
        }, { once: true });
    },

    /**
     * 播放音效
     * @param {string} soundName - 音效名称 ('eat', 'gameover', 'move')
     */
    play(soundName) {
        if (!this.enabled) return;
        if (!this.audioContext) return;

        try {
            switch (soundName) {
                case 'eat':
                    this.playEatSound();
                    break;
                case 'gameover':
                    this.playGameOverSound();
                    break;
                case 'move':
                    // 移动音效可选（可能产生噪音）
                    // this.playMoveSound();
                    break;
                default:
                    console.warn(`Unknown sound: ${soundName}`);
            }
        } catch (error) {
            console.error('Audio playback error:', error);
        }
    },

    /**
     * 播放吃食物音效
     */
    playEatSound() {
        if (!this.audioContext) return;

        const oscillator = this.audioContext.createOscillator();
        const gainNode = this.audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(this.audioContext.destination);

        // 清脆的"叮"声
        oscillator.frequency.setValueAtTime(800, this.audioContext.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(1200, this.audioContext.currentTime + 0.1);

        gainNode.gain.setValueAtTime(0.3, this.audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.2);

        oscillator.start(this.audioContext.currentTime);
        oscillator.stop(this.audioContext.currentTime + 0.2);
    },

    /**
     * 播放游戏结束音效
     */
    playGameOverSound() {
        if (!this.audioContext) return;

        const oscillator = this.audioContext.createOscillator();
        const gainNode = this.audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(this.audioContext.destination);

        // 下降音调表示失败
        oscillator.frequency.setValueAtTime(400, this.audioContext.currentTime);
        oscillator.frequency.exponentialRampToValueAtTime(100, this.audioContext.currentTime + 0.5);

        gainNode.gain.setValueAtTime(0.3, this.audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.5);

        oscillator.start(this.audioContext.currentTime);
        oscillator.stop(this.audioContext.currentTime + 0.5);
    },

    /**
     * 播放移动音效（可选）
     */
    playMoveSound() {
        if (!this.audioContext) return;

        const oscillator = this.audioContext.createOscillator();
        const gainNode = this.audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(this.audioContext.destination);

        oscillator.frequency.setValueAtTime(200, this.audioContext.currentTime);
        
        gainNode.gain.setValueAtTime(0.05, this.audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.05);

        oscillator.start(this.audioContext.currentTime);
        oscillator.stop(this.audioContext.currentTime + 0.05);
    },

    /**
     * 播放背景音乐（循环）
     */
    playBackgroundMusic() {
        // 简单实现：不播放背景音乐（避免打扰用户）
        // 如需实现，可以创建简单的旋律循环
    },

    /**
     * 停止背景音乐
     */
    stopBackgroundMusic() {
        // 停止背景音乐
    },

    /**
     * 启用/禁用音效
     * @param {boolean} enabled - 是否启用
     */
    setEnabled(enabled) {
        this.enabled = enabled;
    },

    /**
     * 切换音效状态
     * @returns {boolean} 新的状态
     */
    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
};

// 导出（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AudioManager;
}
