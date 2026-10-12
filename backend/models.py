from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime, timezone, timedelta
from database import Base

def turkey_time():
    return datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)

# =====================================================
# DETECTION TABLOSU
# =====================================================

class Detection(Base):

    __tablename__ = "detections"

    id         = Column(Integer, primary_key=True, index=True)
    class_name = Column(String)
    confidence = Column(Float)
    timestamp  = Column(DateTime, default=turkey_time)
    camera_id  = Column(String, default="Kamera-1")    # ← YENİ
    location   = Column(String, default="Bilinmiyor")  # ← YENİ

# =====================================================
# USER TABLOSU
# =====================================================

class User(Base):

    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String, unique=True, index=True)
    password_hash = Column(String)
    created_at    = Column(DateTime, default=turkey_time)