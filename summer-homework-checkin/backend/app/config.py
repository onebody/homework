import os
import warnings
from datetime import date

# 项目根目录（backend/）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 上传文件存储目录
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
# Docker 部署：允许重定向上传目录到持久化卷
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", UPLOAD_DIR)
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 前端静态资源目录
STUDENT_DIR = os.path.join(BASE_DIR, "..", "frontend", "student")
ADMIN_DIR = os.path.join(BASE_DIR, "..", "frontend", "admin")

# SQLite 数据库（轻量、零配置、可持久化）
DB_PATH = os.path.join(BASE_DIR, "app.db")
# Docker 部署：允许重定向数据库路径到持久化卷
DB_PATH = os.environ.get("DB_PATH", DB_PATH)
DATABASE_URL = f"sqlite:///{DB_PATH}"

# 签名密钥（生产环境务必通过环境变量注入）
# 未设置环境变量时，自动生成随机密钥（仅首次启动，后续需保持一致）
_SECRET_FILE = os.path.join(BASE_DIR, ".secret_key")
if os.environ.get("SUMMER_SECRET"):
    SECRET = os.environ["SUMMER_SECRET"]
elif os.path.exists(_SECRET_FILE):
    with open(_SECRET_FILE, "r") as f:
        SECRET = f.read().strip()
else:
    import secrets
    SECRET = secrets.token_hex(32)
    try:
        with open(_SECRET_FILE, "w") as f:
            f.write(SECRET)
    except Exception:
        pass
    warnings.warn(
        "⚠️  SECURITY: 未设置 SUMMER_SECRET 环境变量，已自动生成随机密钥并保存到 .secret_key 文件。"
        "生产环境请通过环境变量 SUMMER_SECRET 设置固定密钥。",
        RuntimeWarning,
        stacklevel=2,
    )
TOKEN_EXPIRE_DAYS = 30

# CORS 允许的来源（生产环境请设置为实际域名）
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:8001,http://127.0.0.1:8000"
).split(",")

# 暑假全周期（用于报表默认统计窗口）
SUMMER_START = date(2026, 7, 1)
SUMMER_END = date(2026, 8, 31)

# 打卡规则
GEO_THRESHOLD_METERS = int(os.environ.get("GEO_THRESHOLD_METERS", "1500"))  # 距常用位置超过该值则标记代打卡风险
MAX_MAKEUP_PER_MONTH = int(os.environ.get("MAX_MAKEUP_PER_MONTH", "3"))       # 单自然月最多补卡次数（支持环境变量覆盖）
MIN_PHOTO_BYTES = 5 * 1024       # 照片最小体积（防占位图）
MIN_PHOTO_DIM = 200              # 照片最小边长（防缩略图/占位图）
PHOTO_MAX_BYTES = 10 * 1024 * 1024

# 抽奖解锁阈值
LOTTERY_STREAK_THRESHOLD = 7     # 连续有效打卡天数达到该值解锁 1 次抽奖资格

# 积分规则（打卡自动获得，用于积分商城兑换奖品）
CHECKIN_POINTS = int(os.environ.get("CHECKIN_POINTS", "10"))   # 正常打卡所得积分
MAKEUP_POINTS = int(os.environ.get("MAKEUP_POINTS", "5"))      # 补卡所得积分（低于正常打卡，鼓励当日完成）

# 人脸识别（1:1 本人比对，预留多用户扩展）
FACE_MATCH_THRESHOLD = float(os.environ.get("FACE_MATCH_THRESHOLD", "0.4"))  # 余弦相似度阈值，越高越严格
FACE_DET_SIZE = (320, 320)       # 人脸检测输入尺寸（越小越快、越小越易漏检）
FACE_MODEL_NAME = "buffalo_l"    # insightface 预训练模型（检测+识别）

# 打卡时的人脸策略：
#   enforce  -> 已采集底图后，人脸不通过则拒绝打卡（最强防代打卡）
#   soft     -> 已采集底图后，人脸不通过仅标记高风险但仍记录（容错优先）
FACE_MODE_ON_ENROLLED = os.environ.get("FACE_MODE_ON_ENROLLED", "enforce")
