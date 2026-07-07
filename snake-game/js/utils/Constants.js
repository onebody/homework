// ===== Game Constants =====
const GRID_SIZE = 20; // 每个格子的像素大小
const GRID_WIDTH = 30; // 横向格子数
const GRID_HEIGHT = 30; // 纵向格子数

const DIRECTION = {
    UP: { x: 0, y: -1 },
    DOWN: { x: 0, y: 1 },
    LEFT: { x: -1, y: 0 },
    RIGHT: { x: 1, y: 0 }
};

const GAME_STATE = {
    IDLE: 'idle',
    READY: 'ready',
    PLAYING: 'playing',
    PAUSED: 'paused',
    GAME_OVER: 'game_over'
};

const DIFFICULTY = {
    EASY: { name: 'easy', speed: 5, throughWall: true, obstacleCount: 0 },
    MEDIUM: { name: 'medium', speed: 8, throughWall: false, obstacleCount: 5 },
    HARD: { name: 'hard', speed: 12, throughWall: false, obstacleCount: 10 }
};

const GAME_MODE = {
    CLASSIC: 'classic',
    TIMED: 'timed',
    OBSTACLE: 'obstacle'
};

const FOOD_TYPE = {
    NORMAL: { color: '#F44336', value: 1 },
    GOLDEN: { color: '#FFD700', value: 3 },
    RAINBOW: { color: '#FF69B4', value: 5 }
};

const SKIN_COLORS = {
    classic: {
        head: '#4CAF50',
        body: '#8BC34A',
        eye: '#FFFFFF'
    },
    cartoon: {
        head: '#FF6B6B',
        body: '#FFE66D',
        eye: '#FFFFFF'
    },
    neon: {
        head: '#00FF41',
        body: '#0ABDE3',
        eye: '#FFFFFF'
    },
    nature: {
        head: '#2D3436',
        body: '#636E72',
        eye: '#FFFFFF'
    },
    minimal: {
        head: '#2C3E50',
        body: '#7F8C8D',
        eye: '#FFFFFF'
    }
};

// 游戏配置默认值
const DEFAULT_SETTINGS = {
    soundEnabled: true,
    vibrationEnabled: true,
    selectedSkin: 'classic',
    selectedDifficulty: 'easy',
    selectedMode: 'classic',
    language: 'zh',
    fontSize: 'normal',
    eyeCareMode: false
};

// LocalStorage Key
const STORAGE_KEY = 'snake-game-data';
