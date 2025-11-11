
from typing import List, Literal, Optional
from pydantic import BaseModel

class MacroRatio(BaseModel):
    carb: float
    protein: float
    fat: float

class MealPoint(BaseModel):
    meal_index: int
    kcal: float
    protein: float
    fat: float
    carb: float
    sodium: float   # g

class DashboardResponse(BaseModel):
    date: str
    total_kcal: float
    macro_ratio: MacroRatio
    meals: List[MealPoint]

class RecommendationItem(BaseModel):
    name: str
    score: float
    servings: float 
    kcal: float
    protein: float
    fat: float
    carb: float
    sodium: float
    rem_kcal: float
    rem_protein: float
    rem_fat: float
    rem_carb: float
    rem_sodium: float

class RecommendationResponse(BaseModel):
    mode: Literal["next", "summary"]
    label: str
    recommendations: Optional[List[RecommendationItem]] = None
    summary: Optional[DashboardResponse] = None
