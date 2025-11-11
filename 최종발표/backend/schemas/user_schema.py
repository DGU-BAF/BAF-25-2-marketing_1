from pydantic import BaseModel
from typing import Optional
from pydantic import BaseModel, constr

class UserCreate(BaseModel):
    username: constr(min_length=3, max_length=50)
    password: constr(min_length=4, max_length=72)
    height: Optional[float] = None
    weight: Optional[float] = None
    gender: Optional[str] = None
    meals_per_day: Optional[int] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserOut(BaseModel):
    id: int
    username: str
    height: Optional[float]
    weight: Optional[float]
    gender: Optional[str]
    meals_per_day: Optional[int]

    class Config:
        orm_mode = True
