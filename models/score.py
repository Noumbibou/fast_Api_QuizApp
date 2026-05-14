from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.sql import func
from database import Base

class Score(Base):
    __tablename__ = "scores"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(128), nullable=False, index=True)  # Firebase UID
    level = Column(String(20), nullable=False, index=True)
    score = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Champs anti-triche
    cheated = Column(Boolean, default=False, nullable=False)  # Triche détectée
    cheat_score = Column(Integer, default=0, nullable=False)  # Score de suspicion (0-5+)
    time_spent = Column(Integer, default=0, nullable=False)  # Temps total en secondes
    latitude = Column(Float, nullable=True)  # Position GPS
    longitude = Column(Float, nullable=True)  # Position GPS
    camera_active = Column(Boolean, default=True, nullable=False)  # Caméra active
    
    def __repr__(self):
        return f"<Score(user_id={self.user_id}, level={self.level}, score={self.score}/{self.total}, cheated={self.cheated})>"
