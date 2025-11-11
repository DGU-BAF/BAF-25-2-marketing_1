
import re
from typing import List, Tuple
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from backend.models.food import Food

ALIASES = {
    "ramen": ["라면","라멘","ramyeon"],
    "kimbap": ["김밥","gimbap","kimbob","kimbap"],
    "bibimbap": ["비빔밥","bibim-bap"],
    "tteokbokki": ["떡볶이","topokki","ddukbokki","tteok-bokki"],
    "jjajangmyeon": ["짜장면","자장면","jajangmyeon","jjajang"],
    "jjamppong": ["짬뽕","jjambbong","jjamppong"],
    "friedchicken": ["후라이드치킨","치킨","fried chicken","fried-chicken"],
    "pizza": ["피자"],
    "bossam": ["보쌈"],
}

def _normalize(s: str) -> str:
    t = (s or "").strip().lower()
    t = re.sub(r"[\s\-\_]+", "", t)
    t = re.sub(r"[^\w가-힣]+", "", t)
    return t

def _generate_candidates(raw_label: str) -> List[str]:
    t = _normalize(raw_label)
    for k, vals in ALIASES.items():
        if t == _normalize(k) or t in [_normalize(v) for v in vals]:
            norm_vals = {_normalize(v) for v in vals}
            norm_vals.add(_normalize(k))
            return list(norm_vals)
    return [t]

def _trigrams(s: str) -> set:
    return { s[i:i+3] for i in range(0, max(0, len(s)-2)) }

def _trigram_sim(a: str, b: str) -> float:
    if not a or not b: return 0.0
    A, B = _trigrams(a), _trigrams(b)
    if not A or not B: return 0.0
    return len(A & B) / len(A | B)

def _edit_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def find_food_by_name(db: Session, raw_label: str):
    """
    YOLO/EfficientNet에서 추출된 음식 이름(raw_label)을 DB의 Food 테이블과 매칭
    """
    cands = _generate_candidates(raw_label)
    rows = []

    for c in cands:
        q = f"%{c}%"
        row = db.query(Food).filter(Food.is_active == True, Food.name.like(q)).first()
        if row:
            rows.append(row)

    if rows:
        norm_target = _normalize(raw_label)
        rows = sorted(rows, key=lambda r: 1.0 - _edit_ratio(norm_target, _normalize(r.name)))
        return rows[0]

    all_names = db.query(Food.name, Food.id).filter(Food.is_active == True).all()
    if not all_names:
        return None

    norm_target = _normalize(raw_label)
    scored: List[Tuple[float, int, str]] = []
    for name, fid in all_names:
        ns = _normalize(name)
        tri = _trigram_sim(norm_target, ns)
        if tri >= 0.25:
            ed = _edit_ratio(norm_target, ns)
            score = 0.7*tri + 0.3*ed
            scored.append((score, fid, name))

    if not scored:
        return None

    scored.sort(key=lambda t: t[0], reverse=True)
    best_fid = scored[0][1]
    return db.query(Food).get(best_fid)

def food_per_serving_dict(food) -> dict:
    """DB에서 불러온 Food 객체를 1인분 영양정보 dict로 변환"""
    return {
        "kcal":       float(food.kcal or 0),
        "protein_g":  float(food.protein_g or 0),
        "fat_g":      float(food.fat_g or 0),
        "carb_g":     float(food.carb_g or 0),
        "sugar_g":    float(food.sugar_g or 0),
        "sodium_mg":  float(food.sodium_mg or 0),
        "fiber_g":    float(food.fiber_g or 0),
    }

def scale_nutrients(nutrients: dict, servings: float) -> dict:
    """1인분 영양정보 × servings 배수 계산"""
    return {k: round(v * servings, 3) for k, v in nutrients.items()}
