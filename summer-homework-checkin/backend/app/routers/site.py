"""站点公开配置接口（无需登录）。

学生端页面加载时调用，仅暴露展示类字段（如页面标题），
不泄露任何敏感配置。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SiteConfig
from ..config import CHECKIN_POINTS, MAKEUP_POINTS

router = APIRouter(prefix="/api/site-config", tags=["site"])

# 学生端默认标题（后台未配置自定义标题时使用）
DEFAULT_STUDENT_TITLE = "暑假作业打卡平台"
# 学生端登录页默认欢迎标语
DEFAULT_STUDENT_SLOGAN = "每天进步一点点，打卡赢好礼！"


def get_or_create_site_config(db: Session) -> SiteConfig:
    """获取站点配置单行记录，不存在则创建。"""
    cfg = db.query(SiteConfig).first()
    if not cfg:
        cfg = SiteConfig()
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def resolve_points(db: Session) -> tuple[int, int]:
    """解析生效的打卡积分（正常, 补卡）。

    后台配置非空则优先，否则回退到 config 默认常量。
    供审核发分与学生端文案展示共用，改配置后无需重启即生效。
    """
    cfg = db.query(SiteConfig).first()
    normal = cfg.checkin_points if cfg and cfg.checkin_points is not None else CHECKIN_POINTS
    makeup = cfg.makeup_points if cfg and cfg.makeup_points is not None else MAKEUP_POINTS
    return normal, makeup


@router.get("")
def get_public_site_config(db: Session = Depends(get_db)):
    """公开配置：学生端标题与欢迎标语（未配置时返回默认值），以及生效的打卡积分。"""
    cfg = db.query(SiteConfig).first()
    title = (cfg.student_title or "").strip() if cfg else ""
    slogan = (cfg.student_slogan or "").strip() if cfg else ""
    normal, makeup = resolve_points(db)
    return {
        "student_title": title or DEFAULT_STUDENT_TITLE,
        "student_slogan": slogan or DEFAULT_STUDENT_SLOGAN,
        "checkin_points": normal,
        "makeup_points": makeup,
    }
