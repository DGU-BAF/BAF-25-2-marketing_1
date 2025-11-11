from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Iterable, Tuple, Sequence

NUTRI_COLS = ["kcal", "protein", "fat", "carb", "sodium"]

# 성별 프리셋
PRESET_T = {
    "male":   np.array([2600, 65, 65, 130, 2.3], dtype=float),
    "female": np.array([2000, 55, 50, 130, 2.3], dtype=float),
}

# 추천 인분 후보
DEFAULT_SERVINGS_CANDIDATES: Sequence[float] = (0.5, 1.0, 1.5, 2.0)

def build_menu_df(rows: Iterable[Tuple]) -> pd.DataFrame:
    """
    rows: [(name, kcal, protein, fat, carb, sodium), ...]
    """
    df = pd.DataFrame(rows, columns=["name"] + NUTRI_COLS)
    for c in NUTRI_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df


def next_meal_targets(T: np.ndarray, C: np.ndarray, done: int, meals: int):
    """
    T: 일일 목표량 벡터 [kcal, protein, fat, carb, sodium]
    C: 현재까지 누적 섭취량 벡터
    done: 오늘까지 섭취한 끼니 수
    meals: 하루 끼니 수
    반환:
      R = T - C           (남은 일일 목표)
      P = clip(R/remain)  (다음 끼니 권장량)
      remain = 남은 끼니 수
    """
    remain = max(meals - done, 1)
    R = T - C
    P = np.clip(R / remain, 0, None)
    return R, P, remain

def recommend_scaled_with_servings(
    T: np.ndarray,
    C: np.ndarray,
    done: int,
    meals: int,
    menu_df: pd.DataFrame,
    topk: int = 5,
    servings_candidates: Sequence[float] = DEFAULT_SERVINGS_CANDIDATES,  
    w_under: Dict[str, float] | None = None,
    w_over:  Dict[str, float] | None = None,
    use_after_for: Tuple[str, ...] = ("sodium",),  # 나트륨은 일일 초과 기준으로 페널티
) -> pd.DataFrame:
    """
    반환 df 컬럼:
      ['name','servings','score'] + NUTRI_COLS + [f'rem_{c}' for c in NUTRI_COLS]
    NUTRI_COLS 값은 '권장 인분 s*'가 곱해진 스케일 영양치.
    """
    if menu_df.empty:
        return pd.DataFrame(columns=["name","servings","score"] + NUTRI_COLS + [f"rem_{c}" for c in NUTRI_COLS])

    if w_under is None:
        w_under = {"kcal":1.0, "protein":1.2, "fat":1.0, "carb":1.0, "sodium":2.0}
    if w_over  is None:
        w_over  = {"kcal":1.0, "protein":0.8, "fat":1.0, "carb":1.0, "sodium":3.0}

    idx = {c:i for i,c in enumerate(NUTRI_COLS)}
    _, P, _ = next_meal_targets(T, C, done, meals)  # 다음 끼니 권장량

    out_rows = []
    for _, r in menu_df.iterrows():
        x1 = r[NUTRI_COLS].to_numpy(float)  # 1인분 영양
        best_s = 1.0
        best_score = float("inf")
        best_after = None

        for s in servings_candidates:
            x = s * x1             # s 인분 섭취
            after = C + x          # 섭취 후 누적
            err_P = x - P          # 끼니 권장량 대비 오차
            err_after = after - T  # 일일 목표 대비 오차

            score = 0.0
            for c in NUTRI_COLS:
                i = idx[c]
                under = max(-err_P[i], 0.0)  # 부족 페널티
                # 초과 페널티: 나트륨 등은 일일 기준, 나머지는 끼니 기준
                over  = max((err_after if c in use_after_for else err_P)[i], 0.0)
                score += w_under[c]*under + w_over[c]*over

            if score < best_score:
                best_score = score
                best_s = s
                best_after = after

        s_star = float(best_s)
        x_star = s_star * x1
        after  = best_after if best_after is not None else (C + x_star)

        out_rows.append({
            "name": str(r["name"]),
            "servings": s_star,
            "score": float(best_score),
            **{c: float(x_star[idx[c]]) for c in NUTRI_COLS},                      # 스케일된 영양
            **{f"rem_{c}": float(max(T[idx[c]] - after[idx[c]], 0.0)) for c in NUTRI_COLS},  # 섭취 후 잔여
        })

    df = pd.DataFrame(out_rows).sort_values(["score", "name"], ascending=[True, True]).head(topk)
    return df

def recommend_scaled(
    T: np.ndarray, C: np.ndarray, done: int, meals: int, menu_df: pd.DataFrame,
    topk: int = 5,
    w_under: Dict[str, float] | None = None,
    w_over:  Dict[str, float] | None = None,
    use_after_for: Tuple[str, ...] = ("sodium",),
) -> pd.DataFrame:
    if menu_df.empty:
        return pd.DataFrame(columns=["name","score"]+NUTRI_COLS+[f"rem_{c}" for c in NUTRI_COLS])

    if w_under is None:
        w_under = {"kcal":1.0, "protein":1.2, "fat":1.0, "carb":1.0, "sodium":2.0}
    if w_over  is None:
        w_over  = {"kcal":1.0, "protein":0.8, "fat":1.0, "carb":1.0, "sodium":3.0}

    idx = {c:i for i,c in enumerate(NUTRI_COLS)}
    _, P, _ = next_meal_targets(T, C, done, meals)

    out_rows = []
    for _, r in menu_df.iterrows():
        x = r[NUTRI_COLS].to_numpy(float)  # 1식 영양
        after = C + x
        err_P = x - P
        err_after = after - T

        score = 0.0
        for c in NUTRI_COLS:
            i = idx[c]
            under = max(-err_P[i], 0.0)
            over  = max((err_after if c in use_after_for else err_P)[i], 0.0)
            score += w_under[c]*under + w_over[c]*over

        out_rows.append({
            "name": r["name"], "score": float(score),
            **{c: float(r[c]) for c in NUTRI_COLS},
            **{f"rem_{c}": float(max(T[idx[c]] - after[idx[c]], 0.0)) for c in NUTRI_COLS},
        })

    return pd.DataFrame(out_rows).sort_values("score").head(topk)
