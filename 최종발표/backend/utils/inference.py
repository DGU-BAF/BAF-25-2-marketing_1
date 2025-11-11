
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

def _monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())  

def compute_week_bounds(offset_weeks: int = 1) -> Tuple[date, date]:
    """
    offset_weeks:
      0 -> 이번주 (월~오늘 or 일요일까지)
      1 -> 지난주 (기본값)
    반환: (week_start(Mon), week_end(Sun))
    """
    today = date.today()
    this_monday = _monday_of_week(today)
    week_start = this_monday - timedelta(weeks=offset_weeks)
    week_end = week_start + timedelta(days=6)
    return (week_start, week_end)

def _daily_targets_by_user(user_row: Any) -> Dict[str, float]:
    """
    성별/프로필 기반 일일 권장량(간단 preset).
    필요 시 BMI/나이/활동량 반영하도록 확장 가능.
    """
    gender = (user_row.gender or "").lower()
    # kcal, protein(g), fat(g), carb(g), sodium(g)
    if gender == "male" or gender == "m":
        return {"kcal": 2600.0, "protein": 65.0, "fat": 65.0, "carb": 130.0, "sodium": 2.3}
    else:
        return {"kcal": 2000.0, "protein": 55.0, "fat": 50.0, "carb": 130.0, "sodium": 2.3}

def fetch_weekly_intake_per_day(db: Session, user_id: int, start_d: date, end_d: date) -> List[Dict[str, Any]]:
    """
    결과: [{"date":"YYYY-MM-DD", "kcal":..., "protein":..., "fat":..., "carb":..., "sodium":...}, ...]
    sodium: g 단위(foods.sodium_mg × servings / 1000)
    """
    rows = db.execute(text("""
        SELECT
          DATE(fl.consumed_at) AS d,
          COALESCE(SUM(f.kcal      * fl.servings), 0)            AS kcal,
          COALESCE(SUM(f.protein_g * fl.servings), 0)            AS protein,
          COALESCE(SUM(f.fat_g     * fl.servings), 0)            AS fat,
          COALESCE(SUM(f.carb_g    * fl.servings), 0)            AS carb,
          COALESCE(SUM(f.sodium_mg * fl.servings)/1000.0, 0)     AS sodium
        FROM food_logs fl
        JOIN foods f ON f.id = fl.food_id
        WHERE fl.user_id = :uid
          AND DATE(fl.consumed_at) BETWEEN :start AND :end
        GROUP BY DATE(fl.consumed_at)
        ORDER BY d ASC
    """), {"uid": user_id, "start": start_d, "end": end_d}).mappings().all()

    # 빈 요일도 0으로 채우기 
    day_map = {r["d"].isoformat(): dict(r) for r in rows}
    out: List[Dict[str, Any]] = []
    cur = start_d
    while cur <= end_d:
        key = cur.isoformat()
        if key in day_map:
            r = day_map[key]
            out.append({
                "date": key,
                "kcal": float(r["kcal"]),
                "protein": float(r["protein"]),
                "fat": float(r["fat"]),
                "carb": float(r["carb"]),
                "sodium": float(r["sodium"]),
            })
        else:
            out.append({"date": key, "kcal":0.0, "protein":0.0, "fat":0.0, "carb":0.0, "sodium":0.0})
        cur += timedelta(days=1)
    return out

def _safe_div(a: float, b: float) -> float:
    return (a / b) if b else 0.0

def compute_weekly_summary(chart_data: List[Dict[str, float]], daily_goal: Dict[str, float]) -> Dict[str, Any]:
    # 총합/평균
    total = {"kcal":0.0, "protein":0.0, "fat":0.0, "carb":0.0, "sodium":0.0}
    for r in chart_data:
        total["kcal"]    += r["kcal"]
        total["protein"] += r["protein"]
        total["fat"]     += r["fat"]
        total["carb"]    += r["carb"]
        total["sodium"]  += r["sodium"]

    days = max(len(chart_data), 1)
    avg = {k: total[k]/days for k in total.keys()}

    # 주간 목표 달성률(칼로리 기준) = (주간 총섭취 kcal) / (일일목표 kcal × 7)
    weekly_goal_kcal = daily_goal["kcal"] * 7.0
    goal_achv_rate = round(_safe_div(total["kcal"], weekly_goal_kcal) * 100.0, 1)

    # 베스트/워스트 데이: "목표칼로리 대비 근접/편차 최대"
    def gap_rate(v: float) -> float:
        return abs((v / daily_goal["kcal"] * 100.0) - 100.0) if daily_goal["kcal"] else 999.0

    if chart_data:
        best = min(chart_data, key=lambda r: gap_rate(r["kcal"]))
        worst = max(chart_data, key=lambda r: gap_rate(r["kcal"]))
        best_day = best["date"]
        worst_day = worst["date"]
    else:
        best_day = None
        worst_day = None

    # 주간 평균 macro 비율 (탄/단/지)
    macro_sum = avg["carb"] + avg["protein"] + avg["fat"]
    macro_ratio_avg = {
        "carb":   round(_safe_div(avg["carb"], macro_sum), 4),
        "protein":round(_safe_div(avg["protein"], macro_sum), 4),
        "fat":    round(_safe_div(avg["fat"], macro_sum), 4),
    }

    return {
        "total_kcal": round(total["kcal"], 1),
        "avg_kcal": round(avg["kcal"], 1),
        "goal_achv_rate": goal_achv_rate,
        "best_day": best_day,
        "worst_day": worst_day,
        "macro_ratio_avg": macro_ratio_avg,
    }

def build_daily_breakdown(chart_data: List[Dict[str, float]], daily_goal: Dict[str, float]) -> List[Dict[str, Any]]:
    out = []
    for r in chart_data:
        achv = round(_safe_div(r["kcal"], daily_goal["kcal"]) * 100.0, 1) if daily_goal["kcal"] else 0.0
        out.append({
            "date": r["date"],
            "kcal": round(r["kcal"], 1),
            "protein": round(r["protein"], 1),
            "fat": round(r["fat"], 1),
            "carb": round(r["carb"], 1),
            "sodium": round(r["sodium"], 3),  # g
            "goal_achv_rate": achv
        })
    return out

def build_weekly_report(db: Session, username: str, offset_weeks: int = 1) -> Dict[str, Any]:
    # 사용자 조회
    user = db.execute(text("""
        SELECT id, username, gender, meals_per_day
        FROM users
        WHERE username = :u
        LIMIT 1
    """), {"u": username}).mappings().first()
    if not user:
        return {"username": username, "error": "User not found."}

    # 기간 계산 (지난주 월~일)
    start_d, end_d = compute_week_bounds(offset_weeks=offset_weeks)

    # 일일 목표(성별 preset)
    daily_goal = _daily_targets_by_user(user)

    # 데이터 집계
    chart_data = fetch_weekly_intake_per_day(db, user_id=user["id"], start_d=start_d, end_d=end_d)

    # 요약 계산
    summary = compute_weekly_summary(chart_data, daily_goal=daily_goal)

    # 일자별 breakdown
    daily_breakdown = build_daily_breakdown(chart_data, daily_goal=daily_goal)

    return {
        "username": user["username"],
        "week": f"{start_d.isoformat()} ~ {end_d.isoformat()}",
        "summary": summary,
        "chart_data": chart_data,
        "daily_breakdown": daily_breakdown
    }
