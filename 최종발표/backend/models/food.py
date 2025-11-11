from sqlalchemy import Column, Integer, String, Boolean, DECIMAL
from backend.database import Base

class Food(Base):
    __tablename__ = "foods"

    id           = Column(Integer, primary_key=True)
    name         = Column(String(255), nullable=False)
    category     = Column(String(100))
    serving_desc = Column(String(100))
    kcal         = Column(DECIMAL(10,2), nullable=False)
    protein_g    = Column(DECIMAL(10,2), nullable=False)
    fat_g        = Column(DECIMAL(10,2), nullable=False)
    carb_g       = Column(DECIMAL(10,2), nullable=False)
    sugar_g      = Column(DECIMAL(10,2))
    sodium_mg    = Column(DECIMAL(10,2))
    fiber_g      = Column(DECIMAL(10,2))
    is_active    = Column(Boolean, nullable=False, default=True)
