"""积分与打卡规则配置。生产环境可用环境变量覆盖。"""

# 每次打卡获得的基础积分
POINTS_PER_CHECKIN = 10

# 连续打卡达到阈值时的额外奖励
POINTS_STREAK_BONUS = 20

# 每连续打卡多少天发放一次额外奖励
STREAK_BONUS_EVERY = 7

# 积分兑换抽奖券的比例：每多少积分换 1 张抽奖券
POINTS_PER_TICKET = 50

# 每次抽奖消耗的抽奖券数量（固定为 1）
TICKETS_PER_DRAW = 1
