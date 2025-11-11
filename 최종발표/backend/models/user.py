from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import relationship
from backend.database import Base

class User(Base):
    __tablename__ = "users" 

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(200), nullable=False)  
    height = Column(Float, nullable=True)
    weight = Column(Float, nullable=True)
    gender = Column(String(10), nullable=True)    
    meals_per_day = Column(Integer, nullable=True)


    food_logs = relationship(
        "FoodLog",                    
        back_populates="user",         
        cascade="all, delete-orphan" 
    )
