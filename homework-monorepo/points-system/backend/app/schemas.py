from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date


class UserCreate(BaseModel):
    username: str
    display_name: str = ""


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    created_at: datetime


class AccountOut(BaseModel):
    user_id: int
    balance: int
    total_earned: int
    total_spent: int
    updated_at: datetime


class LedgerOut(BaseModel):
    id: int
    user_id: int
    tx_type: str
    amount: int
    balance_after: int
    ref_type: Optional[str]
    ref_id: Optional[int]
    note: Optional[str]
    created_at: datetime


class CheckInOut(BaseModel):
    id: int
    user_id: int
    check_date: date
    points_earned: int
    streak: int
    bonus: int


class PrizeOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    cost_points: int
    stock: int
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    can_redeem: Optional[bool] = None   # 前端展示用：当前用户是否可兑换


class RedemptionOut(BaseModel):
    id: int
    user_id: int
    prize_id: int
    prize_name: str
    cost_points: int
    status: str
    created_at: datetime


class CheckInRequest(BaseModel):
    user_id: int


class RedeemRequest(BaseModel):
    user_id: int
    prize_id: int


class CheckInResult(BaseModel):
    checkin: CheckInOut
    points_earned: int
    bonus: int
    streak: int
    balance: int


class RedeemResult(BaseModel):
    redemption: RedemptionOut
    balance: int


class ConvertRequest(BaseModel):
    user_id: int
    qty: int  # 兑换的抽奖券数量（≥1），支持单笔或多笔（多次兑换累加）


class ConversionOut(BaseModel):
    id: int
    user_id: int
    qty: int
    cost_points: int
    status: str
    created_at: datetime


class ConvertResult(BaseModel):
    conversion: ConversionOut
    balance: int          # 兑换后积分余额
    lottery_tickets: int  # 兑换后抽奖券数量


class LotteryTicketLedgerOut(BaseModel):
    id: int
    user_id: int
    tx_type: str
    amount: int
    balance_after: int
    ref_type: Optional[str]
    ref_id: Optional[int]
    note: Optional[str]
    created_at: datetime


class LotteryPrizeOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    weight: int
    stock: Optional[int]
    is_win: int


class LotteryDrawOut(BaseModel):
    id: int
    user_id: int
    prize_name: str
    is_win: int
    created_at: datetime


class DrawRequest(BaseModel):
    user_id: int


class DrawResult(BaseModel):
    draw: LotteryDrawOut
    lottery_tickets: int  # 抽奖后剩余抽奖券数量
    can_lottery: bool     # 是否仍满足抽奖条件（券≥1）
