from datetime import datetime, date
from pydantic import BaseModel, ConfigDict


class UserRegister(BaseModel):
    username: str
    password: str
    nickname: str
    role: str = "student"          # student | parent
    grade: int = 3
    phone: str | None = None
    home_lat: float | None = None
    home_lng: float | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: str
    nickname: str
    grade: int | None = None
    phone: str | None = None
    home_lat: float | None = None
    home_lng: float | None = None
    bind_code: str | None = None
    face_enrolled: bool = False
    current_streak: int = 0
    longest_streak: int = 0
    effective_checkins: int = 0
    lottery_tickets: int = 0
    points: int = 0


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CheckInCreate(BaseModel):
    location_lat: float | None = None
    location_lng: float | None = None
    check_type: str = "normal"      # normal | makeup
    makeup_reason: str | None = None
    makeup_for_date: str | None = None  # 补卡目标日期 ISO，如 2026-07-05


class CheckInOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    check_date: date
    check_time: datetime
    photo_path: str
    photo_url: str = ""
    location_lat: float | None = None
    location_lng: float | None = None
    check_type: str
    makeup_reason: str | None = None
    makeup_proof_path: str | None = None
    geo_distance: float | None = None
    geo_flag: bool = False
    scene_check: str
    face_status: str | None = None
    face_score: float | None = None
    face_flag: bool = False
    review_status: str = "pending"
    review_note: str | None = None
    is_effective: bool = True


class ReviewRequest(BaseModel):
    status: str  # approved | rejected
    note: str | None = None


class RedemptionReviewRequest(BaseModel):
    action: str  # approve | reject
    note: str | None = None


class StreakOut(BaseModel):
    current_streak: int
    longest_streak: int
    effective_checkins: int
    lottery_tickets: int
    today_checked: bool
    today_pending: bool = False
    can_makeup_this_month: int      # 本月剩余可补卡次数


class PrizeCreate(BaseModel):
    name: str
    description: str | None = None
    category: str = "stationery"
    probability: float = 0.1
    stock: int = -1
    status: str = "on"
    cost_points: int = 0
    is_lottery_ticket: bool = False
    ticket_qty: int = 1
    image_url: str | None = None


class PrizeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    probability: float | None = None
    stock: int | None = None
    status: str | None = None
    cost_points: int | None = None
    is_lottery_ticket: bool | None = None
    ticket_qty: int | None = None
    image_url: str | None = None


class PrizeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    category: str
    probability: float
    stock: int
    status: str
    image_url: str | None = None
    is_preset: bool
    cost_points: int = 0
    is_lottery_ticket: bool = False
    ticket_qty: int = 1


class LotteryResult(BaseModel):
    is_win: bool
    prize_name: str | None = None
    prize_id: int | None = None
    tickets_left: int
    message: str


class LotteryRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    prize_name: str | None = None
    is_win: bool
    drawn_at: datetime


class BindRequest(BaseModel):
    child_username: str
    bind_code: str


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    title: str
    content: str | None = None
    read: bool
    related_id: int | None = None
    created_at: datetime


class ChildSummary(BaseModel):
    student_id: int
    nickname: str
    current_streak: int
    longest_streak: int
    effective_checkins: int
    lottery_tickets: int
    points: int = 0
    today_checked: bool
    today_pending: bool = False


class RedeemRequest(BaseModel):
    prize_id: int


class RedeemReplaceRequest(BaseModel):
    new_prize_id: int


class RedemptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    prize_id: int
    prize_name: str
    cost_points: int
    redeemed_at: datetime
    status: str
    replaced_by: int | None = None
    note: str | None = None
    review_note: str | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None


class MallOut(BaseModel):
    points: int
    lottery_tickets: int
    prizes: list                       # 可兑换奖品列表（含 cost_points）
    redemptions: list                  # 我的兑换记录
    lottery_records: list


class ReportOut(BaseModel):
    student_id: int
    nickname: str
    start: date
    end: date
    total_days: int
    checked_days: int
    effective_checkins: int
    makeup_count: int
    current_streak: int
    longest_streak: int
    completion_rate: float
    weekly_buckets: list            # [{week, count}]
    prize_wins: list                # [{name, drawn_at}]
    lottery_draws: int


class FaceEnrollOut(BaseModel):
    ok: bool
    has_face: bool
    face_count: int
    face_id_url: str | None = None
    message: str


class FaceStatusOut(BaseModel):
    face_enrolled: bool
    face_id_url: str | None = None
    message: str


# ── 闯关任务 ────────────────────────────────────────────────────────────────

class ChallengeTaskCreate(BaseModel):
    name: str
    description: str | None = None
    sort_order: int = 0
    reward_points: int = 10
    status: str = "locked"
    unlock_at: str | None = None
    unlock_condition: str | None = None


class ChallengeTaskUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    reward_points: int | None = None
    status: str | None = None
    unlock_at: str | None = None
    unlock_condition: str | None = None


class ChallengeTaskOut(BaseModel):
    """管理端任务输出（含完整字段）。"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    sort_order: int
    reward_points: int
    status: str
    unlock_at: datetime | None = None
    unlock_condition: str | None = None
    created_at: datetime
    # 统计字段（路由层填充）
    total_checkins: int = 0
    pending_reviews: int = 0


class ChallengeTaskStudentOut(BaseModel):
    """学生端任务输出（含当前用户打卡状态）。"""
    id: int
    name: str
    description: str | None = None
    sort_order: int
    reward_points: int
    status: str
    unlock_at: datetime | None = None
    user_status: str = ""
    latest_checkin: dict | None = None


class ChallengeCheckInCreate(BaseModel):
    content: str | None = None
    attachments: str | None = None


class ChallengeCheckInOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    task_id: int
    content: str | None = None
    attachments: str | None = None
    review_status: str
    review_note: str | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    # 路由层填充
    user_nickname: str = ""


class ChallengeCheckInReviewRequest(BaseModel):
    status: str
    note: str | None = None
