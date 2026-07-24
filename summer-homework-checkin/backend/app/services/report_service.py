from datetime import date, datetime, timedelta
from html import escape as _esc

from ..models import CheckIn, LotteryRecord


def build_report(db, student, start: date, end: date) -> dict:
    checkins = (
        db.query(CheckIn)
        .filter(CheckIn.user_id == student.id, CheckIn.check_date >= start, CheckIn.check_date <= end)
        .all()
    )
    effective = [c for c in checkins if c.is_effective]
    checked_days = len({c.check_date for c in effective})
    makeup_count = len([c for c in effective if c.check_type == "makeup"])
    total_days = (end - start).days + 1
    completion_rate = round(checked_days / total_days, 4) if total_days else 0

    # 按 7 天为一块统计打卡分布
    weekly_buckets = []
    cur = start
    idx = 1
    while cur <= end:
        nxt = min(cur + timedelta(days=6), end)
        cnt = len({c.check_date for c in effective if cur <= c.check_date <= nxt})
        weekly_buckets.append({"week": idx, "start": cur.isoformat(), "end": nxt.isoformat(), "count": cnt})
        cur = nxt + timedelta(days=1)
        idx += 1

    records = db.query(LotteryRecord).filter_by(user_id=student.id).all()
    prize_wins = [
        {"name": r.prize_name, "drawn_at": r.drawn_at.strftime("%Y-%m-%d %H:%M")}
        for r in records if r.is_win
    ]

    return {
        "student_id": student.id,
        "nickname": student.nickname,
        "start": start,
        "end": end,
        "total_days": total_days,
        "checked_days": checked_days,
        "effective_checkins": len(effective),
        "makeup_count": makeup_count,
        "current_streak": student.current_streak,
        "longest_streak": student.longest_streak,
        "completion_rate": completion_rate,
        "weekly_buckets": weekly_buckets,
        "prize_wins": prize_wins,
        "lottery_draws": len(records),
    }


def build_html(report: dict) -> str:
    """生成卡通风格、可打印下载的可视化学习报告 HTML。

    安全加固：所有动态插入 HTML 的用户可控内容（昵称、奖品名）均经
    html.escape() 转义，防止存储型 XSS。
    """
    max_cnt = max([b["count"] for b in report["weekly_buckets"]] + [1])
    bars = ""
    for b in report["weekly_buckets"]:
        h = int(b["count"] / max_cnt * 120) if max_cnt else 0
        bars += (
            f'<div class="bar-col"><div class="bar" style="height:{h}px"></div>'
            f'<div class="bar-label">第{int(b["week"])}周</div>'
            f'<div class="bar-num">{int(b["count"])}</div></div>'
        )
    wins = "".join(f"<li>🎁 {_esc(str(w['name']))}（{_esc(str(w['drawn_at']))}）</li>" for w in report["prize_wins"]) or "<li>暂无中奖记录</li>"
    rate = f"{report['completion_rate'] * 100:.1f}%"
    nickname = _esc(str(report['nickname']))

    css = """
  body{font-family:"PingFang SC","Microsoft YaHei",sans-serif;background:#f3faff;color:#2b3a4a;margin:0;padding:24px}
  .card{background:#fff;border-radius:20px;padding:24px;max-width:720px;margin:0 auto;box-shadow:0 8px 24px rgba(80,150,220,.15)}
  h1{color:#2f80ed;text-align:center;margin:0 0 4px}
  .sub{text-align:center;color:#7a8aa0;margin-bottom:20px}
  .grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:16px 0}
  .stat{background:#eef6ff;border-radius:14px;padding:16px;text-align:center}
  .stat .v{font-size:28px;font-weight:700;color:#2f80ed}
  .stat .k{font-size:13px;color:#6b7c93;margin-top:4px}
  .chart{display:flex;align-items:flex-end;gap:10px;height:160px;padding:10px 4px;border-bottom:2px solid #e3edf7;margin-top:8px}
  .bar-col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end}
  .bar{width:60%;background:linear-gradient(180deg,#7eb6ff,#2f80ed);border-radius:8px 8px 0 0;min-height:2px}
  .bar-label{font-size:11px;color:#6b7c93;margin-top:6px}
  .bar-num{font-size:12px;color:#2f80ed;font-weight:700}
  .sec{margin-top:20px}
  .sec h2{font-size:16px;color:#2f80ed;border-left:4px solid #2f80ed;padding-left:8px}
  ul{color:#46566c}
  .btn{display:block;width:100%;margin-top:24px;padding:14px;background:#2f80ed;color:#fff;border:none;border-radius:14px;font-size:16px;cursor:pointer}
  @media print{body{background:#fff}.card{box-shadow:none}}
"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{nickname} 的暑假学习报告</title>
<style>{css}</style></head>
<body><div class="card">
  <h1>🌟 {nickname} 的暑假学习报告</h1>
  <div class="sub">统计区间：{_esc(str(report['start']))} ~ {_esc(str(report['end']))}（共 {int(report['total_days'])} 天）</div>
  <div class="grid">
    <div class="stat"><div class="v">{report['checked_days']}</div><div class="k">有效打卡天数</div></div>
    <div class="stat"><div class="v">{rate}</div><div class="k">作业完成率</div></div>
    <div class="stat"><div class="v">{report['longest_streak']}</div><div class="k">最长连续打卡</div></div>
    <div class="stat"><div class="v">{report['current_streak']}</div><div class="k">当前连续打卡</div></div>
  </div>
  <div class="sec"><h2>📅 每周打卡分布</h2><div class="chart">{bars}</div></div>
  <div class="sec"><h2>🎁 抽中奖品</h2><ul>{wins}</ul></div>
  <div class="sec"><h2>📝 整体情况</h2>
    <p>共完成有效打卡 <b>{report['effective_checkins']}</b> 次（其中补卡 {report['makeup_count']} 次），
    参与抽奖 <b>{report['lottery_draws']}</b> 次。坚持每日打卡，养成良好学习习惯！</p>
  </div>
  <button class="btn" onclick="window.print()">🖨️ 下载 / 打印报告</button>
</div></body></html>"""
