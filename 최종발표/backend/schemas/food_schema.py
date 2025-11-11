from pydantic import BaseModel
from typing import List, Optional

class FoodUploadResponseItem(BaseModel):
    detected_name: str
    matched_name: str
    category: Optional[str] = None
    serving_desc: Optional[str] = None

    serving_count: float
    portion_g: Optional[float] = None

    kcal: float
    protein_g: float
    fat_g: float
    carb_g: float
    sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    fiber_g: Optional[float] = None

class FoodUploadResponse(BaseModel):
    username: str
    image_path: str
    items: List[FoodUploadResponseItem]
