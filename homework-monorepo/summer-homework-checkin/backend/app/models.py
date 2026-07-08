from datetime import datetime, date

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """统一用户表：role 区分 student / parent / admin。"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(16), nullable=False, default="student")  # student|parent|admin
    nickname = Column(String(64), nullable=False)

    # 学生专属
    grade = Column(Integer, default=3)
    home_lat = Column(Float, nullable=True)
    home_lng = Column(Float, nullable=True)
    bind_code = Column(String(16), nullable=True)  # 供家长绑定的展示码

    # 人脸识别（1:1 本人比对；face_embedding 为 512 维向量的 JSON，预留多用户 1:N 扩展）
    face_enrolled = Column(Boolean, default=False)
    face_embedding = Column(Text, nullable=True)     # JSON 化的 512 维向量
    face_id_path = Column(String(256), nullable=True)  # 人脸底图相对 UPLOAD_DIR 路径

    # 家长专属
    phone = Column(String(32), nullable=True)

    # 统计冗余字段（由打卡服务维护）
    current_streak = Column(Integer, default=0)        # 当前连续有效打卡天数
    longest_streak = Column(Integer, default=0)         # 历史最长连续天数
    effective_checkins = Column(Integer, default=0)     # 累计有效打卡次数
    lottery_tickets = Column(Integer, default=0)        # 当前可用抽奖资格
    points = Column(Integer, default=0)                 # 积分余额（打卡获得，用于兑换奖品）
    last_7_milestone = Column(Integer, default=0)       # 已解锁的 7 的倍数里程碑

    created_at = Column(DateTime, default=datetime.utcnow)

    checkins = relationship("CheckIn", back_populates="user", cascade="all, delete-orphan")
    lottery_records = relationship("LotteryRecord", back_populates="user")
    bindings_as_student = relationship(
        "StudentParent", foreign_keys="StudentParent.student_id",
        back_populates="student", cascade="all, delete-orphan"
    )
    bindings_as_parent = relationship(
        "StudentParent", foreign_keys="StudentParent.parent_id",
        back_populates="parent", cascade="all, delete-orphan"
    )


class StudentParent(Base):
    """家长-孩子绑定关系（多对多）。"""
    __tablename__ = "student_parent"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("User", foreign_keys=[student_id], back_populates="bindings_as_student")
    parent = relationship("User", foreign_keys=[parent_id], back_populates="bindings_as_parent")


class CheckIn(Base):
    """打卡记录。check_type: normal（当天）| makeup（补卡）。"""
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    check_date = Column(Date, nullable=False, index=True)     # 所打卡对应的自然日
    check_time = Column(DateTime, default=datetime.utcnow)    # 精确提交时间
    photo_path = Column(String(256), nullable=False)          # 相对 UPLOAD_DIR 的路径
    location_lat = Column(Float, nullable=True)
    location_lng = Column(Float, nullable=True)
    check_type = Column(String(16), default="normal")         # normal|makeup
    makeup_reason = Column(String(256), nullable=True)
    makeup_proof_path = Column(String(256), nullable=True)    # 补卡额外凭证
    geo_distance = Column(Float, nullable=True)               # 距常用位置距离(米)
    geo_flag = Column(Boolean, default=False)                 # 是否超出阈值（代打卡风险）
    scene_check = Column(String(16), default="pending")       # pass|warn|pending
    face_status = Column(String(16), nullable=True)           # match|mismatch|no_face|multiple_faces|not_enrolled|model_unavailable
    face_score = Column(Float, nullable=True)                 # 人脸相似度
    face_flag = Column(Boolean, default=False)                # 人脸不通过（代打卡风险）
    review_status = Column(String(16), default="pending")    # pending|approved|rejected
    review_note = Column(String(256), nullable=True)         # 审核备注
    is_effective = Column(Boolean, default=True)              # 是否计入有效打卡
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="checkins")

    @property
    def photo_url(self):
        from .utils.storage import public_url
        return public_url(self.photo_path)


class Prize(Base):
    """奖品。category: stationery(文具)|outdoor(户外)|interest(兴趣)。
    is_lottery_ticket=True 表示该奖品是"抽奖机会"，兑换后给用户增加 lottery_tickets，
    不创建 Redemption 记录，不扣库存，可无限次兑换。
    """
    __tablename__ = "prizes"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(16), default="stationery")
    probability = Column(Float, default=0.1)   # 中奖概率权重 0~1
    stock = Column(Integer, default=-1)        # -1 表示不限量
    status = Column(String(8), default="on")   # on|off
    cost_points = Column(Integer, default=0)   # 积分兑换所需积分（0 表示不参与积分兑换）
    is_lottery_ticket = Column(Boolean, default=False)  # 是否为抽奖机会奖品
    ticket_qty = Column(Integer, default=1)    # 每次兑换获得的抽奖券数量（仅 is_lottery_ticket=True 时有效）
    image_url = Column(String(256), nullable=True)
    is_preset = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LotteryRecord(Base):
    """抽奖行为记录。"""
    __tablename__ = "lottery_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    prize_id = Column(Integer, ForeignKey("prizes.id"), nullable=True)
    prize_name = Column(String(128), nullable=True)
    is_win = Column(Boolean, default=False)
    drawn_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="lottery_records")
    prize = relationship("Prize")


class Redemption(Base):
    """积分兑换记录。支持「直接选择替换」：replaced_by 指向新的兑换记录。"""
    __tablename__ = "redemptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    prize_id = Column(Integer, ForeignKey("prizes.id"), nullable=False)
    prize_name = Column(String(128), nullable=False)
    cost_points = Column(Integer, default=0)            # 兑换时扣减的积分
    redeemed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(16), default="pending")      # pending|fulfilled|replaced|cancelled
    replaced_by = Column(Integer, ForeignKey("redemptions.id"), nullable=True)  # 被替换后指向新记录
    note = Column(String(256), nullable=True)
    review_note = Column(String(256), nullable=True)          # 审核备注
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 操作管理员
    reviewed_at = Column(DateTime, nullable=True)              # 操作时间

    user = relationship("User", foreign_keys=[user_id], backref="redemptions")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    prize = relationship("Prize")


class Notification(Base):
    """站内通知（学生与家长共用）。"""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_role = Column(String(16), nullable=False)  # student|parent
    type = Column(String(16), default="system")          # checkin|lottery|system|redeem
    title = Column(String(128), nullable=False)
    content = Column(Text, nullable=True)
    read = Column(Boolean, default=False)
    related_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChallengeTask(Base):
    """闯关任务定义。管理员可创建多个任务，按 sort_order 排序。"""
    __tablename__ = "challenge_tasks"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0)
    reward_points = Column(Integer, default=10)
    status = Column(String(16), default="locked")
    unlock_at = Column(DateTime, nullable=True)
    unlock_condition = Column(String(256), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChallengeCheckIn(Base):
    """闯关任务打卡记录。"""
    __tablename__ = "challenge_checkins"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("challenge_tasks.id"), nullable=False, index=True)
    content = Column(Text, nullable=True)
    attachments = Column(Text, nullable=True)
    review_status = Column(String(16), default="pending")
    review_note = Column(String(256), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    task = relationship("ChallengeTask")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
