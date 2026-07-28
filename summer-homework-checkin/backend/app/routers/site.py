"""站点公开配置接口（无需登录）。

学生端页面加载时调用，仅暴露展示类字段（如页面标题），
不泄露任何敏感配置。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SiteConfig

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


@router.get("")
def get_public_site_config(db: Session = Depends(get_db)):
    """公开配置：学生端标题与欢迎标语（未配置时返回默认值）。"""
    cfg = db.query(SiteConfig).first()
    title = (cfg.student_title or "").strip() if cfg else ""
    slogan = (cfg.student_slogan or "").strip() if cfg else ""
    return {
        "student_title": title or DEFAULT_STUDENT_TITLE,
        "student_slogan": slogan or DEFAULT_STUDENT_SLOGAN,
    }
