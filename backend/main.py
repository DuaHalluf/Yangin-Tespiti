from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from typing import List
from ultralytics import YOLO
import numpy as np
import cv2
import hashlib
from datetime import datetime

from database import engine, SessionLocal
from models import Detection, User, Base

app = FastAPI()

Base.metadata.create_all(bind=engine)

# =====================================================
# MODEL
# =====================================================

import os
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "Trained-Models", "yolo8_best.pt")
model      = YOLO(MODEL_PATH)
CLASS_MAP  = {0: "smoke", 1: "fire"}

# =====================================================
# YARDIMCI
# =====================================================

def hash_password(p: str) -> str:
    return hashlib.sha256(p.encode()).hexdigest()

# =====================================================
# SCHEMAS
# =====================================================

class AuthRequest(BaseModel):
    username: str
    password: str

class DetectionItem(BaseModel):
    class_name: str
    confidence: float
    camera_id:  str = "Kamera-1"    # ← YENİ
    location:   str = "Bilinmiyor"  # ← YENİ

class SaveRequest(BaseModel):
    detections: List[DetectionItem]
    camera_id:  str = "Kamera-1"    # ← YENİ
    location:   str = "Bilinmiyor"  # ← YENİ

# =====================================================
# ROOT
# =====================================================

@app.get("/")
def root():
    return {"message": "Yangin Detection Backend Calisiyor"}

# =====================================================
# REGISTER
# =====================================================

@app.post("/register")
def register(req: AuthRequest):
    if len(req.username) < 3:
        raise HTTPException(400, "Kullanici adi en az 3 karakter olmali.")
    if len(req.password) < 4:
        raise HTTPException(400, "Sifre en az 4 karakter olmali.")

    db       = SessionLocal()
    existing = db.query(User).filter(User.username == req.username).first()

    if existing:
        db.close()
        raise HTTPException(400, "Bu kullanici adi zaten alinmis.")

    db.add(User(username=req.username, password_hash=hash_password(req.password)))
    db.commit()
    db.close()
    return {"message": f"'{req.username}' basariyla kayit oldu!"}

# =====================================================
# LOGIN
# =====================================================

@app.post("/login")
def login(req: AuthRequest):
    db   = SessionLocal()
    user = db.query(User).filter(User.username == req.username).first()
    db.close()

    if not user:
        raise HTTPException(401, "Kullanici bulunamadi.")
    if user.password_hash != hash_password(req.password):
        raise HTTPException(401, "Sifre yanlis.")

    return {"message": "Giris basarili!", "username": user.username}

# =====================================================
# DETECT  (fotoğraf)
# =====================================================

@app.post("/detect")
async def detect_image(
    file:      UploadFile = File(...),
    camera_id: str = Query(default="Kamera-1"),    # ← YENİ
    location:  str = Query(default="Bilinmiyor")   # ← YENİ
):
    contents = await file.read()
    nparr    = np.frombuffer(contents, np.uint8)
    img      = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    results    = model(img)[0]
    detections = []
    db         = SessionLocal()

    for box in results.boxes:
        cls          = int(box.cls[0])
        conf         = float(box.conf[0])
        x1,y1,x2,y2 = map(int, box.xyxy[0])
        class_name   = CLASS_MAP.get(cls, "unknown")

        db.add(Detection(
            class_name=class_name,
            confidence=conf,
            camera_id=camera_id,   # ← YENİ
            location=location      # ← YENİ
        ))
        detections.append({
            "class":      class_name,
            "confidence": round(conf, 2),
            "box":        [x1, y1, x2, y2],
            "timestamp":  str(datetime.now()),
            "camera_id":  camera_id,   # ← YENİ
            "location":   location     # ← YENİ
        })

    db.commit()
    db.close()

    return {"filename": file.filename, "total": len(detections), "detections": detections}

# =====================================================
# SAVE  (video / kamera frame sonuçları)
# =====================================================

@app.post("/save")
def save_detections(req: SaveRequest):
    if not req.detections:
        return {"saved": 0}

    db = SessionLocal()

    for det in req.detections:
        db.add(Detection(
            class_name=det.class_name,
            confidence=det.confidence,
            camera_id=req.camera_id,   # ← YENİ
            location=req.location      # ← YENİ
        ))

    db.commit()
    db.close()

    return {"saved": len(req.detections)}

# =====================================================
# HISTORY
# =====================================================

@app.get("/history")
def get_history(limit: int = 20):
    db   = SessionLocal()
    rows = db.query(Detection).order_by(Detection.id.desc()).limit(limit).all()
    result = [
        {
            "id":         r.id,
            "class":      r.class_name,
            "confidence": round(r.confidence, 2),
            "timestamp":  str(r.timestamp),
            "camera_id":  r.camera_id,   # ← YENİ
            "location":   r.location     # ← YENİ
        }
        for r in rows
    ]
    db.close()
    return result

# =====================================================
# STATS
# =====================================================

@app.get("/stats")
def get_stats():
    db          = SessionLocal()
    fire_count  = db.query(Detection).filter(Detection.class_name == "fire").count()
    smoke_count = db.query(Detection).filter(Detection.class_name == "smoke").count()
    total       = db.query(Detection).count()
    db.close()
    return {"total_fire": fire_count, "total_smoke": smoke_count, "total_detections": total}