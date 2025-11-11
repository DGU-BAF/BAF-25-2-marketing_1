
from __future__ import annotations
from datetime import date
import numpy as np
from typing import List, Tuple
from backend.sql import fetch_one, fetch_all
from backend.schemas.responses import RecommendationResponse, RecommendationItem
from backend.models.recommend import PRESET_T, build_menu_df, recommend_scaled_with_servings
from backend.services.nutrients_sql import total_intake_today, meals_done_today
from backend.services.dashboard_service import get_dashboard

def _user_targets_and_meals(username: str) -> Tuple[np.ndarray, int]:
    u = fetch_one(
        "SELECT gender, IFNULL(meals_per_day,3) AS meals FROM users WHERE username=:uname",
        {"uname": username}
    )
    if not u:
        raise ValueError(f"User '{username}' not found.")
    gender = (u.get("gender") or "female").lower()
    key = "male" if gender.startswith("m") else "female"
    return PRESET_T[key].copy(), int(u["meals"])

def _menu_df_all():
    rows = fetch_all("""
        SELECT name, kcal, protein_g AS protein, fat_g AS fat, carb_g AS carb, (sodium_mg/1000.0) AS sodium
        FROM foods
        WHERE is_active = 1
    """)
    tuples = [(r["name"], r["kcal"], r["protein"], r["fat"], r["carb"], r["sodium"]) for r in rows]
    return build_menu_df(tuples)

def recommend_or_summary(username: str, target_date: date | None = None) -> RecommendationResponse:
    T, meals_per_day = _user_targets_and_meals(username)
    tot = total_intake_today(username, target_date)  # dict: kcal, protein, fat, carb, sodium
    C = np.array([tot["kcal"], tot["protein"], tot["fat"], tot["carb"], tot["sodium"]], dtype=float)
    done = meals_done_today(username, target_date)

    if done < meals_per_day:
        menu_df = _menu_df_all()

    
        table = recommend_scaled_with_servings(
            T, C, done, meals_per_day, menu_df,
            topk=5,
            servings_candidates=(0.5, 1.0, 1.5, 2.0),
        )

        items: List[RecommendationItem] = []
        for _, r in table.iterrows():
            items.append(RecommendationItem(
                name=str(r["name"]),
                score=float(r["score"]),
                servings=float(r["servings"]),
                kcal=float(r["kcal"]),
                protein=float(r["protein"]),
                fat=float(r["fat"]),
                carb=float(r["carb"]),
                sodium=float(r["sodium"]),
                rem_kcal=float(r["rem_kcal"]),
                rem_protein=float(r["rem_protein"]),
                rem_fat=float(r["rem_fat"]),
                rem_carb=float(r["rem_carb"]),
                rem_sodium=float(r["rem_sodium"]),
            ))
        return RecommendationResponse(
            mode="next",
            label=f"[추천] {done+1}/{meals_per_day} 끼니",
            recommendations=items
        )

    dash = get_dashboard(username, target_date)
    return RecommendationResponse(
        mode="summary",
        label="[요약] 오늘 리포트",
        summary=dash
    )
