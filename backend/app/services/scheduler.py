"""
SM-2 间隔重复算法
从 V1 移植，逻辑无变化

评分标准：
  1 = 忘记 (Again)
  3 = 困难 (Hard)
  4 = 良好 (Good)
  5 = 简单 (Easy)
"""

import math
from datetime import date, datetime, timedelta, timezone


def calculate_sm2(
    quality: int,
    previous_interval: int,
    previous_ease_factor: float,
    previous_reps: int,
) -> dict:
    """
    SM-2 算法核心

    :param quality: 用户评分 (1-5)，< 3 视为忘记
    :param previous_interval: 上次间隔天数
    :param previous_ease_factor: 上次难度系数
    :param previous_reps: 连续成功次数
    :return: {"interval", "ease_factor", "reps"}
    """
    new_ease_factor = previous_ease_factor
    new_reps = previous_reps

    # 忘记：重置
    if quality < 3:
        return {
            "interval": 1,
            "ease_factor": new_ease_factor,
            "reps": 0,
        }

    # 记住：递增
    new_reps += 1

    if new_reps == 1:
        new_interval = 1
    elif new_reps == 2:
        new_interval = 6  # Anki 标准
    else:
        new_interval = math.ceil(previous_interval * previous_ease_factor)

    # 更新难度系数（经典 SM-2 公式，EF 最低 1.3）
    ef_modifier = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    new_ease_factor = max(1.3, previous_ease_factor + ef_modifier)

    return {
        "interval": new_interval,
        "ease_factor": round(new_ease_factor, 2),
        "reps": new_reps,
    }


def get_next_review_date(interval: int) -> date:
    """根据间隔天数计算下次复习的具体日期（基于 UTC）"""
    return datetime.now(timezone.utc).date() + timedelta(days=interval)
