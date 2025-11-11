
from datetime import date, datetime
from typing import Dict, Tuple, List, Optional
from backend.sql import fetch_one, fetch_all

def _day_range_kst(d: Optional[date] = None) -> Tuple[datetime, datetime]:
    d = d or date.today()
    return (datetime(d.year, d.month, d.day, 0, 0, 0),
            datetime(d.year, d.month, d.day, 23, 59, 59))

def total_intake_today(username: str, target_date: Optional[date] = None) -> Dict[str, float]:
    d0, d1 = _day_range_kst(target_date)
    row = fetch_one(
        """
        SELECT
          COALESCE(SUM(f.kcal*fl.servings),0)               AS kcal,
          COALESCE(SUM(f.protein_g*fl.servings),0)          AS protein,
          COALESCE(SUM(f.fat_g*fl.servings),0)              AS fat,
          COALESCE(SUM(f.carb_g*fl.servings),0)             AS carb,
          COALESCE(SUM(f.sodium_mg*fl.servings)/1000.0,0)   AS sodium
        FROM food_logs fl
        JOIN foods f ON f.id=fl.food_id
        JOIN users u ON u.id=fl.user_id
        WHERE u.username=:uname
          AND fl.consumed_at BETWEEN :s AND :e
        """, {"uname": username, "s": d0, "e": d1}
    ) or {}
    return {
        "kcal": float(row.get("kcal", 0)),
        "protein": float(row.get("protein", 0)),
        "fat": float(row.get("fat", 0)),
        "carb": float(row.get("carb", 0)),
        "sodium": float(row.get("sodium", 0))
    }

def meals_done_today(username: str, target_date: Optional[date] = None) -> int:
    d0, d1 = _day_range_kst(target_date)
    row = fetch_one(
        """
        SELECT COUNT(DISTINCT fl.meal_index) AS meals_done
        FROM food_logs fl
        JOIN users u ON u.id=fl.user_id
        WHERE u.username=:uname
          AND fl.consumed_at BETWEEN :s AND :e
        """, {"uname": username, "s": d0, "e": d1}
    ) or {"meals_done": 0}
    return int(row["meals_done"] or 0)

def meals_breakdown_today(username: str, target_date: Optional[date] = None) -> List[Dict]:
    d0, d1 = _day_range_kst(target_date)
    rows = fetch_all(
        """
        SELECT
          fl.meal_index,
          SUM(f.kcal*fl.servings)               AS kcal,
          SUM(f.protein_g*fl.servings)          AS protein,
          SUM(f.fat_g*fl.servings)              AS fat,
          SUM(f.carb_g*fl.servings)             AS carb,
          SUM(f.sodium_mg*fl.servings)/1000.0   AS sodium
        FROM food_logs fl
        JOIN foods f ON f.id=fl.food_id
        JOIN users u ON u.id=fl.user_id
        WHERE u.username=:uname
          AND fl.consumed_at BETWEEN :s AND :e
        GROUP BY fl.meal_index
        ORDER BY fl.meal_index
        """, {"uname": username, "s": d0, "e": d1}
    )
    return [
        {"meal_index": int(r["meal_index"]),
         "kcal": float(r["kcal"] or 0),
         "protein": float(r["protein"] or 0),
         "fat": float(r["fat"] or 0),
         "carb": float(r["carb"] or 0),
         "sodium": float(r["sodium"] or 0)}
        for r in rows
    ]
