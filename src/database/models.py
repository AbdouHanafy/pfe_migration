"""
Database models
"""

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from src.database.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    matricule = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
