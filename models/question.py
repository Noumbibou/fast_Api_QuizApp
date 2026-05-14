from sqlalchemy import Column, Integer, String, Enum, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime

class QuestionLevel(enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class QuestionSet(Base):
    __tablename__ = "question_sets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    level = Column(Enum(QuestionLevel), nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relation avec les questions
    questions = relationship("Question", back_populates="question_set", cascade="all, delete-orphan")

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    set_id = Column(Integer, ForeignKey("question_sets.id"), nullable=False)
    level = Column(Enum(QuestionLevel), nullable=False)
    question = Column(String(500), nullable=False)
    option_a = Column(String(200), nullable=False)
    option_b = Column(String(200), nullable=False)
    option_c = Column(String(200), nullable=False)
    option_d = Column(String(200), nullable=False)
    correct_answer = Column(String(1), nullable=False)  # A, B, C, or D
    is_active = Column(Boolean, default=True, nullable=False)  # Soft delete
    
    # Relation avec le question set
    question_set = relationship("QuestionSet", back_populates="questions")
