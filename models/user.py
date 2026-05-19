from sqlalchemy import Column, String
from database import Base

class User(Base):
    __tablename__ = "users"
    
    uid = Column(String(128), primary_key=True, index=True)  # Firebase UID
    username = Column(String(100), nullable=False)
    
    def __repr__(self):
        return f"<User(uid={self.uid}, username={self.username})>"
