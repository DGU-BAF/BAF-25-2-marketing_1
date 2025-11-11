from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.database import Base

class FoodLog(Base):
    __tablename__ = "food_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    food_id = Column(Integer, ForeignKey("foods.id"), nullable=False)
    meal_index = Column(Integer, nullable=False)  # 1=아침, 2=점심, 3=저녁, 4=간식
    servings = Column(Float, nullable=False, default=1.0)
    source = Column(String(32))
    note = Column(String(255))
    image_url = Column(String(255))
    consumed_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    # 관계 설정
    user = relationship("User", back_populates="food_logs")
    food = relationship("Food")
