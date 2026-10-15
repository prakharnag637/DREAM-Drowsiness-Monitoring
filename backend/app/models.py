from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base

class ResearchSession(Base):
    __tablename__ = "research_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_code = Column(String(40), unique=True, index=True, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="running", nullable=False)
    notes = Column(Text, nullable=True)
    measurements = relationship("Measurement", back_populates="session", cascade="all, delete-orphan")

class Measurement(Base):
    __tablename__ = "measurements"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    face_detected = Column(Integer, default=0)
    ear = Column(Float, nullable=True)
    mar = Column(Float, nullable=True)
    blink_rate = Column(Float, nullable=True)
    perclos = Column(Float, nullable=True)
    possible_yawns = Column(Integer, default=0)
    experimental_score = Column(Float, nullable=True)
    status = Column(String(40), nullable=True)
    session = relationship("ResearchSession", back_populates="measurements")
