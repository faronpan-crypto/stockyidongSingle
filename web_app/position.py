"""仓位百分比：与 desktop `update_position` 中情绪/大V/昨日 三列求和逻辑一致。"""
from __future__ import annotations

from dataclasses import dataclass

POSITION_OPTIONS_SCORES = {
    "太阳": 10,
    "晴天": 7,
    "阴天": 4,
    "下雨": 1,
    "大雨": -2,
    "暴雨": -5,
    "飓风": -8,
}


@dataclass
class PositionResult:
    position_percent: float
    total_emotion_score: int
    three_dimension_total: int
    t_trading_hint: str
    new_position_allowed: bool
    rgb: tuple[int, int, int]


def compute_position(
    emotion: str,
    v_judge: str,
    yesterday: str,
    fundamental: int,
    technical: int,
    sentiment_dim: int,
    prev_three_dimension_total: int | None = None,
) -> PositionResult:
    e = POSITION_OPTIONS_SCORES.get(emotion, 0)
    v = POSITION_OPTIONS_SCORES.get(v_judge, 0)
    y = POSITION_OPTIONS_SCORES.get(yesterday, 0)
    total_emotion = e + v + y
    three_total = fundamental + technical + sentiment_dim
    position_percent = (total_emotion / 30.0) * 100
    position_percent = max(0.0, min(100.0, position_percent))

    if position_percent <= 50:
        ratio = position_percent / 50.0 if position_percent > 0 else 0.0
        red = int(255 * ratio)
        green = 255
        blue = 0
    else:
        ratio = (position_percent - 50) / 50.0
        red = 255
        green = int(255 * (1 - ratio))
        blue = 0

    if total_emotion < 0:
        t_hint = "下行趋势 不可以做T"
    elif position_percent <= 50:
        t_hint = "谨慎做T"
    else:
        t_hint = "上行趋势 可以做T"

    is_down = total_emotion < 0
    if prev_three_dimension_total is not None:
        is_down = is_down or (three_total < prev_three_dimension_total)
    new_ok = not (is_down or position_percent < 30)

    return PositionResult(
        position_percent=position_percent,
        total_emotion_score=total_emotion,
        three_dimension_total=three_total,
        t_trading_hint=t_hint,
        new_position_allowed=new_ok,
        rgb=(red, green, blue),
    )


def kelly_fraction(odds_b: float, win_prob_p: float) -> tuple[float, float]:
    """凯利比例 f 与百分比。f = (b*p - (1-p)) / b"""
    if odds_b <= 0 or not (0 < win_prob_p < 1):
        return 0.0, 0.0
    f = (odds_b * win_prob_p - (1 - win_prob_p)) / odds_b
    return f, f * 100.0
