from sqlalchemy import Column, Integer, String, Enum, Boolean
from database import Base
import enum

class QuestionLevel(enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(Enum(QuestionLevel), nullable=False)
    question = Column(String(500), nullable=False)
    option_a = Column(String(200), nullable=False)
    option_b = Column(String(200), nullable=False)
    option_c = Column(String(200), nullable=False)
    option_d = Column(String(200), nullable=False)
    correct_answer = Column(String(1), nullable=False)  # A, B, C, or D
    is_active = Column(Boolean, default=True, nullable=False)  # Soft delete
