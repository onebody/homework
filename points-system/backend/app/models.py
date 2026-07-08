from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime, date, timezone

from app.database import Base


class User(Base):
    """用户（积分账户的归属主体）。"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    display_name = Column(String(128), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PointAccount(Base):
    """积分账户：每个用户一行，记录余额与累计收支。"""
    __tablename__ = "point_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    balance = Column(Integer, default=0, nullable=False)        # 当前可用积分
    total_earned = Column(Integer, default=0, nullable=False)    # 累计获得
    total_spent = Column(Integer, default=0, nullable=False)     # 累计支出
    lottery_tickets = Column(Integer, default=0, nullable=False)  # 当前抽奖券数量（≥1 即解锁抽奖）
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="account")


class PointLedger(Base):
    """积分流水：每一笔收入/支出都落一条，保证账户可追溯、可对账。"""
    __tablename__ = "point_ledgers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    tx_type = Column(String(16), nullable=False)     # earn（收入）| spend（支出）
    amount = Column(Integer, nullable=False)         # 变动数量（正数）
    balance_after = Column(Integer, nullable=False)  # 变动后的余额（用于对账）
    ref_type = Column(String(32))                    # checkin | redemption
    ref_id = Column(Integer)                         # 关联业务主键
    note = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class CheckIn(Base):
    """打卡记录：每日一行，记录连续天数与本次获得积分。"""
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    check_date = Column(Date, nullable=False, index=True)   # 打卡对应的自然日
    points_earned = Column(Integer, default=0)
    streak = Column(Integer, default=1)                     # 截至当天的连续打卡天数
    bonus = Column(Integer, default=0)                      # 本次连续奖励积分
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 防重复打卡：同一用户同一天只能有一条
    __table_args__ = (
        UniqueConstraint("user_id", "check_date", name="uq_user_check_date"),
    )


class Prize(Base):
    """奖品表：兑换标的，含所需积分、库存与有效期。"""
    __tablename__ = "prizes"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text)
    cost_points = Column(Integer, nullable=False)   # 兑换所需积分
    stock = Column(Integer, default=0, nullable=False)  # 剩余库存
    valid_from = Column(DateTime)                    # 兑换开始时间（可空=不限制）
    valid_to = Column(DateTime)                      # 兑换结束时间（可空=不限制）
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Redemption(Base):
    """兑换记录：每次成功兑换生成一条，关联用户与奖品。"""
    __tablename__ = "redemptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    prize_id = Column(Integer, ForeignKey("prizes.id"), index=True, nullable=False)
    cost_points = Column(Integer, nullable=False)    # 兑换时消耗的积分（快照）
    status = Column(String(16), default="issued")    # issued（已发放）| cancelled
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    prize = relationship("Prize")


class Conversion(Base):
    """积分兑换抽奖券记录：每次成功兑换生成一条，关联用户与兑换数量。"""
    __tablename__ = "conversions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    qty = Column(Integer, nullable=False)            # 兑换得到的抽奖券数量
    cost_points = Column(Integer, nullable=False)    # 兑换消耗的积分（快照）
    status = Column(String(16), default="issued")    # issued（已发放）| cancelled
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")


class LotteryTicketLedger(Base):
    """抽奖券流水：每一笔发放/消耗都落一条，保证券账户可追溯、可对账。"""
    __tablename__ = "lottery_ticket_ledgers"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    tx_type = Column(String(16), nullable=False)     # issue（发放）| consume（消耗）
    amount = Column(Integer, nullable=False)         # 变动数量（正数，方向由 tx_type 决定）
    balance_after = Column(Integer, nullable=False)  # 变动后的抽奖券余额
    ref_type = Column(String(32))                    # convert | draw
    ref_id = Column(Integer)                         # 关联业务主键
    note = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class LotteryPrize(Base):
    """抽奖奖池：按 weight 加权随机，stock 为 None 表示不限量（如「谢谢参与」）。"""
    __tablename__ = "lottery_prizes"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text)
    weight = Column(Integer, nullable=False, default=1)   # 中奖权重（相对值）
    stock = Column(Integer, default=None)                # 剩余库存（NULL=不限量）
    is_win = Column(Integer, default=1)                  # 1=中奖 0=未中奖（谢谢参与）
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class LotteryDraw(Base):
    """抽奖记录：每次成功抽奖生成一条，标记是否中奖与所得奖品。"""
    __tablename__ = "lottery_draws"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    prize_id = Column(Integer, ForeignKey("lottery_prizes.id"), index=True, nullable=False)
    prize_name = Column(String(128), nullable=False)
    is_win = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    prize = relationship("LotteryPrize")
