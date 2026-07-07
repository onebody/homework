# 全年龄段贪吃蛇游戏 - 系统架构设计文档

> **文档版本**: v1.0  
> **创建日期**: 2026-06-04  
> **架构师**: 杉架（shan-jia）  
> **项目状态**: 架构设计阶段

---

## 一、架构概述

### 1.1 技术选型结论

经过综合评估，本项目采用 **HTML5 + Canvas + 原生JavaScript** 方案。

**选型理由**：
1. **零安装**：浏览器直接打开，降低用户使用门槛
2. **跨平台**：Windows/Mac/Linux/iOS/Android 全平台覆盖
3. **开发高效**：无需编译，热更新，调试便捷
4. **部署简单**：静态文件托管，CDN加速
5. **可扩展**：可打包为PWA，支持离线玩耍

### 1.2 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         用户界面层（UI Layer）               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ 游戏画布  │  │ 控制面板  │  │ 设置面板  │  │ 排行榜 │ │
│  │（Canvas） │  │（HTML）  │  │（HTML）  │  │（HTML）│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                       游戏逻辑层（Game Logic Layer）          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ 游戏引擎  │  │ 碰撞检测  │  │ 状态管理  │  │ 分数系统 │ │
│  │（Engine） │  │（Collision│  │（State）  │  │（Score）│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ 蛇控制器  │  │ 食物生成  │  │ 道具系统  │             │
│  │（Snake） │  │（Food）  │  │（PowerUp）│             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                      渲染层（Rendering Layer）               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Canvas    │  │ 动画系统  │  │ 粒子效果  │  │ 音效系统 │ │
│  │ 渲染器    │  │（Animate）│  │（Particle）│  │（Audio）│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│                      数据持久化层（Data Layer）              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Local     │  │ IndexedDB│  │ 云端同步  │             │
│  │ Storage   │  │（可选）  │  │（可选）  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、目录结构设计

```
snake-game/
├── index.html              # 入口页面
├── css/
│   ├── main.css           # 主样式文件
│   ├── themes/            # 主题样式
│   │   ├── classic.css    # 经典主题
│   │   ├── cartoon.css    # 卡通主题
│   │   ├── neon.css       # 霓虹主题
│   │   ├── nature.css     # 自然主题
│   │   └── minimal.css    # 简约主题
│   └── accessibility.css   # 无障碍样式（大字体、高对比度）
├── js/
│   ├── core/              # 核心模块
│   │   ├── GameEngine.js  # 游戏引擎（主循环、状态管理）
│   │   ├── Snake.js       # 蛇类（移动、增长、碰撞）
│   │   ├── Food.js        # 食物类（生成、消失）
│   │   ├── PowerUp.js     # 道具类（生成、效果）
│   │   └── Collision.js   # 碰撞检测模块
│   ├── ui/                # UI模块
│   │   ├── Menu.js        # 菜单界面
│   │   ├── HUD.js         # 游戏内HUD（分数、状态）
│   │   ├── Settings.js    # 设置面板
│   │   └── Leaderboard.js # 排行榜
│   ├── render/            # 渲染模块
│   │   ├── CanvasRenderer.js  # Canvas渲染器
│   │   ├── Animation.js       # 动画系统
│   │   └── ParticleSystem.js # 粒子效果系统
│   ├── audio/             # 音频模块
│   │   └── AudioManager.js   # 音效管理器
│   ├── data/              # 数据模块
│   │   ├── StorageManager.js # 本地存储管理
│   │   └── CloudSync.js      # 云端同步（可选）
│   ├── utils/             # 工具模块
│   │   ├── Constants.js   # 常量定义
│   │   ├── Helpers.js     # 工具函数
│   │   └── EventBus.js    # 事件总线
│   └── main.js            # 入口文件（初始化）
├── assets/               # 静态资源
│   ├── audio/            # 音效文件
│   │   ├── bgm.mp3       # 背景音乐
│   │   ├── eat.mp3       # 吃食物音效
│   │   ├── die.mp3       # 游戏结束音效
│   │   └── powerup.mp3   # 道具音效
│   ├── images/           # 图片资源
│   │   ├── snake-head.png
│   │   ├── snake-body.png
│   │   └── food.png
│   └── fonts/            # 字体文件
│       └── game-font.ttf
├── docs/                 # 文档
│   ├── PRD.md            # 产品需求文档
│   ├── ARCHITECTURE.md   # 本文件
│   └── API.md            # 接口文档
└── README.md             # 项目说明
```

---

## 三、核心类设计

### 3.1 游戏引擎（GameEngine）

```javascript
class GameEngine {
  // 属性
  state: GameState              // 当前游戏状态
  canvas: HTMLCanvasElement     // Canvas元素
  ctx: CanvasRenderingContext2D // 绘图上下文
  snake: Snake                 // 蛇对象
  food: Food                   // 食物对象
  powerUps: PowerUp[]         // 道具列表
  score: number                // 当前分数
  highScore: number            // 最高分
  difficulty: Difficulty       // 难度等级
  gameMode: GameMode          // 游戏模式
  
  // 方法
  init()                      // 初始化游戏
  start()                     // 开始游戏
  pause()                     // 暂停游戏
  resume()                    // 恢复游戏
  reset()                     // 重置游戏
  update(deltaTime)           // 更新游戏状态（每帧调用）
  render()                    // 渲染游戏画面（每帧调用）
  handleInput(direction)      // 处理用户输入
  checkCollision()            // 碰撞检测
  spawnFood()                 // 生成食物
  spawnPowerUp()              // 生成道具（P2功能）
  gameOver()                  // 游戏结束处理
}
```

### 3.2 蛇类（Snake）

```javascript
class Snake {
  // 属性
  body: Point[]                // 蛇身坐标数组（包含头）
  direction: Direction         // 当前移动方向
  nextDirection: Direction     // 下一帧方向（防止快速按键导致180度转向）
  speed: number               // 移动速度（格/秒）
  isAlive: boolean            // 是否存活
  skin: string                // 当前皮肤
  
  // 方法
  move()                      // 移动蛇（头部前进，尾部跟随）
  grow()                      // 吃到食物后增长
  setDirection(dir)           // 设置移动方向（防止180度转向）
  checkSelfCollision()        // 检测是否撞到自己
  checkWallCollision(width, height) // 检测是否撞墙
  draw(ctx)                   // 绘制蛇
}
```

### 3.3 食物类（Food）

```javascript
class Food {
  // 属性
  position: Point             // 食物位置
  type: FoodType             // 食物类型（普通/金色/彩虹/变质）
  value: number              // 分数价值
  spawnTime: number          // 生成时间（用于限时消失）
  duration: number           // 存在时长（毫秒，-1表示不消失）
  
  // 方法
  spawn(gridWidth, gridHeight, snakeBody) // 在随机位置生成食物（避开蛇身）
  isExpired()                // 检查是否过期
  draw(ctx)                  // 绘制食物
}
```

### 3.4 道具类（PowerUp）—— P2功能

```javascript
class PowerUp {
  // 属性
  position: Point             // 道具位置
  type: PowerUpType          // 道具类型（加速/减速/穿墙/磁铁）
  duration: number           // 效果持续时间（毫秒）
  spawnTime: number          // 生成时间
  
  // 方法
  spawn(gridWidth, gridHeight, snakeBody, foodPosition) // 生成道具
  applyEffect(snake)          // 应用道具效果
  draw(ctx)                  // 绘制道具
}
```

### 3.5 碰撞检测模块（Collision）

```javascript
class Collision {
  // 静态方法
  static checkWallCollision(snakeHead, gridWidth, gridHeight, throughWall) 
    // 检测撞墙（throughWall=true时穿墙）
  static checkSelfCollision(snakeHead, snakeBody) 
    // 检测撞自身
  static checkFoodCollision(snakeHead, foodPosition) 
    // 检测吃到食物
  static checkPowerUpCollision(snakeHead, powerUpPosition) 
    // 检测吃到道具
  static checkObstacleCollision(snakeHead, obstacles) 
    // 检测撞障碍物（障碍模式）
}
```

---

## 四、游戏状态机设计

### 4.1 状态定义

```javascript
const GameState = {
  IDLE: 'idle',             // 空闲状态（显示主菜单）
  READY: 'ready',           // 准备状态（倒计时3-2-1-Go）
  PLAYING: 'playing',       // 游戏中
  PAUSED: 'paused',         // 暂停
  GAME_OVER: 'game_over',   // 游戏结束
  SETTINGS: 'settings',      // 设置界面
  LEADERBOARD: 'leaderboard' // 排行榜界面
}
```

### 4.2 状态转换图

```
┌───────┐
│       │
│ IDLE  │◄──────────────────────────────────┐
│       │                                    │
└───┬───┘                                    │
    │ 用户点击"开始游戏"                       │
    ▼                                          │
┌───────┐   倒计时结束                      ┌───────┐
│ READY │──────────────►│ PLAYING │
└───────┘                              └───┬───┘
                                          │   │
                     用户按暂停键          │   │ 游戏结束条件触发
                          │   ▼
                          ┌───────┐       │
                          │ PAUSED │◄─────┤
                          └───┬───┘       │
                              │ 用户按继续   │
                              ▼              │
                            ┌───────┐       │
                            │ PLAYING │◄────┘
                            └───┬───┘
                                │
                                ▼
                            ┌───────┐
                            │GAME_OVER│──► 用户点击"重新开始" ──► IDLE
                            └───────┘
```

---

## 五、接口设计

### 5.1 游戏控制接口

```javascript
// 游戏控制API（供UI层调用）
const GameAPI = {
  // 游戏控制
  startGame: () => void,           // 开始游戏
  pauseGame: () => void,           // 暂停游戏
  resumeGame: () => void,          // 恢复游戏
  resetGame: () => void,           // 重置游戏
  changeDirection: (dir) => void,  // 改变方向
  
  // 设置
  setDifficulty: (level) => void,  // 设置难度
  setGameMode: (mode) => void,     // 设置游戏模式
  setSkin: (skinName) => void,     // 设置皮肤
  toggleSound: () => void,          // 切换音效
  toggleVibration: () => void,     // 切换震动（移动端）
  
  // 查询
  getScore: () => number,           // 获取当前分数
  getHighScore: () => number,       // 获取最高分
  getState: () => GameState,        // 获取当前状态
  getSnakeLength: () => number,     // 获取蛇长度
}
```

### 5.2 事件系统

```javascript
// 事件类型
const GameEvents = {
  GAME_START: 'game_start',           // 游戏开始
  GAME_PAUSE: 'game_pause',          // 游戏暂停
  GAME_RESUME: 'game_resume',        // 游戏恢复
  GAME_OVER: 'game_over',            // 游戏结束
  SCORE_CHANGE: 'score_change',      // 分数变化
  EAT_FOOD: 'eat_food',             // 吃到食物
  EAT_POWERUP: 'eat_powerup',        // 吃到道具
  DIRECTION_CHANGE: 'direction_change', // 方向改变
  HIGH_SCORE: 'high_score',          // 刷新最高分
}

// 事件总线（发布-订阅模式）
class EventBus {
  constructor() {
    this.listeners = {}
  }
  
  on(event, callback) {
    // 订阅事件
  }
  
  off(event, callback) {
    // 取消订阅
  }
  
  emit(event, data) {
    // 发布事件
  }
}
```

---

## 六、数据模型设计

### 6.1 本地存储数据结构（LocalStorage）

```javascript
// LocalStorage Key: `snake-game-data`
{
  // 游戏设置
  settings: {
    soundEnabled: boolean,        // 音效是否开启
    vibrationEnabled: boolean,    // 震动是否开启
    selectedSkin: string,         // 当前皮肤
    selectedDifficulty: string,   // 当前难度
    selectedMode: string,         // 当前模式
    language: string,             // 语言（zh/en/ja/es）
    fontSize: 'normal' | 'large', // 字体大小
    eyeCareMode: boolean,         // 护眼模式
  },
  
  // 最高分记录
  highScores: {
    classic: {
      easy: number,
      medium: number,
      hard: number,
    },
    timed: {
      60: number,
      120: number,
      180: number,
    },
    obstacle: number,
    // ... 其他模式
  },
  
  // 成就列表
  achievements: string[],  // 已解锁成就ID数组
  
  // 游戏统计
  statistics: {
    totalGames: number,     // 总游戏局数
    totalPlayTime: number,  // 总游戏时长（秒）
    maxScore: number,       // 历史最高分
    averageScore: number,   // 平均分数
  },
  
  // 排行榜（本地前10）
  leaderboard: [
    { score: number, date: string, mode: string, difficulty: string },
    // ...
  ],
}
```

### 6.2 云端同步数据结构（可选，P2功能）

```javascript
// 云端数据库（如Firebase/Supabase）
{
  userId: string,           // 用户ID（匿名或登录）
  displayName: string,      // 显示名称
  avatar: string,           // 头像URL
  highScore: number,        // 最高分
  totalGames: number,       // 总游戏局数
  achievements: string[],   // 成就列表
  lastPlayed: string,       // 最后游戏时间
}
```

---

## 七、性能优化方案

### 7.1 渲染优化

1. **使用 `requestAnimationFrame`**：保证60FPS流畅渲染
2. **离屏Canvas缓存**：静态元素（网格背景、皮肤）预先渲染到离屏Canvas
3. **局部重绘**：只重绘发生变化区域，而非整个Canvas
4. **减少状态变化**：合并多次DOM操作为一次

```javascript
// 离屏Canvas缓存示例
const offscreenCanvas = document.createElement('canvas')
const offscreenCtx = offscreenCanvas.getContext('2d')
// 预先绘制网格背景
drawGrid(offscreenCtx)
// 主渲染循环中直接绘制缓存图像
ctx.drawImage(offscreenCanvas, 0, 0)
```

### 7.2 内存优化

1. **对象池技术**：复用GameObject（蛇身段、食物、粒子），减少GC压力
2. **及时销毁**：游戏结束后清除定时器和事件监听
3. **图片压缩**：使用WebP格式，减少内存占用

```javascript
// 对象池示例
class ObjectPool {
  constructor(type, initialSize) {
    this.pool = []
    // 初始化对象池
    for (let i = 0; i < initialSize; i++) {
      this.pool.push(new type())
    }
  }
  
  acquire() {
    // 从池中获取对象
    return this.pool.length > 0 ? this.pool.pop() : new type()
  }
  
  release(obj) {
    // 归还对象到池
    obj.reset()
    this.pool.push(obj)
  }
}
```

### 7.3 电池优化（移动端）

1. **降低帧率**：当游戏暂停或后台运行时，停止渲染循环
2. **减少CPU占用**：使用`requestAnimationFrame`而非`setInterval`
3. **优化触摸事件**：使用`passive: true`提升滚动性能

```javascript
// 页面可见性API - 自动暂停
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    gameEngine.pause()
  }
})
```

---

## 八、跨平台适配方案

### 8.1 响应式布局

```css
/* 移动端优先设计 */
.game-container {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 平板适配 */
@media (min-width: 768px) {
  .game-container {
    width: 700px;
    margin: 0 auto;
  }
}

/* 桌面端适配 */
@media (min-width: 1024px) {
  .game-container {
    width: 900px;
    margin: 0 auto;
  }
}
```

### 8.2 触控 vs 键盘控制

```javascript
// 统一输入抽象层
class InputManager {
  constructor() {
    this.initKeyboard()
    this.initTouch()
  }
  
  initKeyboard() {
    document.addEventListener('keydown', (e) => {
      switch(e.key) {
        case 'ArrowUp': case 'w': case 'W':
          this.handleDirection('up')
          break
        // ... 其他方向
      }
    })
  }
  
  initTouch() {
    let touchStartX, touchStartY
    document.addEventListener('touchstart', (e) => {
      touchStartX = e.touches[0].clientX
      touchStartY = e.touches[0].clientY
    })
    
    document.addEventListener('touchend', (e) => {
      const deltaX = e.changedTouches[0].clientX - touchStartX
      const deltaY = e.changedTouches[0].clientY - touchStartY
      // 判断滑动方向
      if (Math.abs(deltaX) > Math.abs(deltaY)) {
        this.handleDirection(deltaX > 0 ? 'right' : 'left')
      } else {
        this.handleDirection(deltaY > 0 ? 'down' : 'up')
      }
    })
  }
}
```

---

## 九、PWA（渐进式网页应用）方案

### 9.1 为什么需要PWA

1. **离线玩耍**：无需网络也能玩
2. **桌面快捷方式**：像原生APP一样打开
3. **推送通知**：提醒用户回来玩（可选）

### 9.2 PWA配置

**manifest.json**：
```json
{
  "name": "贪吃蛇大冒险",
  "short_name": "贪吃蛇",
  "description": "全年龄段都爱玩的贪吃蛇游戏",
  "start_url": "/index.html",
  "display": "standalone",
  "background_color": "#F5F5F5",
  "theme_color": "#4CAF50",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

**service-worker.js**：
```javascript
// 缓存策略：Cache First（静态资源）
const CACHE_NAME = 'snake-game-v1'
const urlsToCache = [
  '/',
  '/index.html',
  '/css/main.css',
  '/js/main.js',
  // ... 其他静态资源
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(urlsToCache))
  )
})
```

---

## 十、测试策略

### 10.1 单元测试

使用 **Jest** 测试核心逻辑：

```javascript
// Snake.test.js
describe('Snake', () => {
  test('should move correctly', () => {
    const snake = new Snake()
    snake.setDirection('right')
    snake.move()
    expect(snake.body[0]).toEqual({ x: 6, y: 5 })
  })
  
  test('should not allow 180-degree turn', () => {
    const snake = new Snake()
    snake.setDirection('right')
    snake.setDirection('left')  // 应该被忽略
    expect(snake.direction).toBe('right')
  })
})
```

### 10.2 集成测试

使用 **Puppeteer** 进行端到端测试：

```javascript
// e2e.test.js
describe('Game E2E', () => {
  test('should start game when clicking start button', async () => {
    await page.click('#start-button')
    const state = await page.evaluate(() => gameEngine.state)
    expect(state).toBe('playing')
  })
})
```

### 10.3 性能测试

使用 **Chrome DevTools Performance Tab** 分析帧率和内存占用。

**性能指标**：
- 启动时间：< 2秒
- 帧率：稳定60FPS（波动< 5FPS）
- 内存占用：< 50MB
- 电池消耗：< 2%/小时（移动端）

---

## 十一、部署方案

### 11.1 托管平台

推荐使用以下平台（免费且支持CDN加速）：

1. **GitHub Pages**：免费、简单、自动HTTPS
2. **Vercel**：自动部署、全球CDN、支持自定义域名
3. **Netlify**：类似Vercel，支持表单处理

### 11.2 CI/CD流程

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm run build  # 可选：压缩、打包
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./
```

---

## 十二、风险评估与应对

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| 浏览器兼容性（旧版IE） | 高 | 低 | 放弃支持IE，提示升级浏览器 |
| 移动端性能问题 | 中 | 中 | 降低画质、减少粒子效果 |
| 触控误操作 | 中 | 中 | 增加虚拟方向键、防误触处理 |
| 本地存储容量不足 | 低 | 低 | 只存储关键数据、定期清理 |
| PWA安装率低下 | 低 | 中 | 增加安装引导提示 |

---

## 十三、技术债务管理

1. **代码规范**：使用ESLint + Prettier强制代码风格
2. **模块化**：按功能拆分文件，避免单个文件过大
3. **文档**：每个类和函数都要有JSDoc注释
4. **重构计划**：每完成一个里程碑，进行代码审查并重构

---

## 十四、附录

### 14.1 技术栈版本

| 技术 | 版本 | 用途 |
|------|------|------|
| HTML5 | - | 页面结构 |
| CSS3 | - | 样式和动画 |
| JavaScript | ES6+ | 游戏逻辑 |
| Canvas API | - | 游戏渲染 |
| Web Audio API | - | 音效播放 |
| LocalStorage API | - | 本地数据存储 |
| Service Worker | - | PWA离线支持 |

### 14.2 开发工具

| 工具 | 用途 |
|------|------|
| VS Code | 代码编辑器 |
| Chrome DevTools | 调试和性能分析 |
| Git | 版本控制 |
| GitHub | 代码托管和CI/CD |
| Figma | UI设计（可选） |

### 14.3 参考资料

- [MDN Canvas API](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API)
- [HTML5 Game Development](https://developer.mozilla.org/en-US/docs/Games)
- [Game Loop](https://www.sitepoint.com/how-to-make-a-simple-html5-canvas-game/)

---

**文档结束**

> 本文档由架构师**杉架**（shan-jia）完成  
> 下一步：交由项目经理**节进**（jie-jin）进行项目规划
