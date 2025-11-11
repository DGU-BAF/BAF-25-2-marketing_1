
from __future__ import annotations
from datetime import date
from backend.schemas.responses import DashboardResponse, MacroRatio, MealPoint
from backend.services.nutrients_sql import total_intake_today, meals_breakdown_today

def _macro_ratio(carb: float, protein: float, fat: float) -> MacroRatio:
    s = carb + protein + fat
    return MacroRatio(carb=carb/s if s else 0.0,
                      protein=protein/s if s else 0.0,
                      fat=fat/s if s else 0.0)

def get_dashboard(user_id: int, target_date: date | None = None) -> DashboardResponse:
    totals = total_intake_today(user_id, target_date)
    meals = meals_breakdown_today(user_id, target_date)
    points = [MealPoint(**m) for m in meals]
    return DashboardResponse(
        date=(target_date or date.today()).isoformat(),
        total_kcal=totals["kcal"],
        macro_ratio=_macro_ratio(totals["carb"], totals["protein"], totals["fat"]),
        meals=points
    )
