import os
from azure.monitor.opentelemetry import configure_azure_monitor

# Configure Azure Monitor for Application Insights
connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    configure_azure_monitor(connection_string=connection_string)

from prometheus_fastapi_instrumentator import Instrumentator

from typing import List
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models, schemas
from database import engine, get_db
from security import verify_token

from sqlalchemy import text
models.Base.metadata.create_all(bind=engine)

# Auto-migration for missing columns
try:
    with engine.begin() as conn:
        columns_to_add = {
            "first_name": "NVARCHAR(100) NULL",
            "last_name": "NVARCHAR(100) NULL",
            "phone": "NVARCHAR(20) NULL",
            "address": "NVARCHAR(500) NULL"
        }
        for col, type_info in columns_to_add.items():
            result = conn.execute(text(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'user_profiles' AND COLUMN_NAME = '{col}'"))
            if not result.fetchone():
                print(f"Adding missing column '{col}' to 'user_profiles' table")
                conn.execute(text(f"ALTER TABLE user_profiles ADD {col} {type_info}"))
except Exception as e:
    print(f"Migration failed for user-service: {e}")

app = FastAPI(title="User Service")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://jpshop.puneetdevops.online",
        "http://jpshop.puneetdevops.online",
        "https://api.puneetdevops.online",
        "http://localhost:5173",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"service": "User Service", "status": "online"}

@app.get("/profile", response_model=schemas.UserProfileResponse)
def get_profile(request: Request, db: Session = Depends(get_db)):
    user_payload = verify_token(request)
    user_id = user_payload.get("id")
    
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile

@app.post("/profile", response_model=schemas.UserProfileResponse)
def update_profile(profile_in: schemas.UserProfileCreate, request: Request, db: Session = Depends(get_db)):
    user_payload = verify_token(request)
    user_id = user_payload.get("id")
    
    profile = db.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()
    if not profile:
        profile = models.UserProfile(user_id=user_id, **profile_in.model_dump(exclude_unset=True))
        db.add(profile)
    else:
        for key, value in profile_in.model_dump(exclude_unset=True).items():
            setattr(profile, key, value)
            
    db.commit()
    db.refresh(profile)
    return profile

@app.get("/streaming-profiles", response_model=List[schemas.StreamingProfileResponse])
def get_streaming_profiles(request: Request, db: Session = Depends(get_db)):
    user_payload = verify_token(request)
    user_id = user_payload.get("id")
    profiles = db.query(models.StreamingProfile).filter(models.StreamingProfile.user_id == user_id).all()
    return profiles

@app.post("/streaming-profiles", response_model=schemas.StreamingProfileResponse)
def create_streaming_profile(profile_in: schemas.StreamingProfileCreate, request: Request, db: Session = Depends(get_db)):
    user_payload = verify_token(request)
    user_id = user_payload.get("id")
    new_profile = models.StreamingProfile(user_id=user_id, **profile_in.model_dump())
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile

@app.post("/internal/audit-logs", status_code=201)
def create_audit_log(log_in: schemas.AuditLogCreate, db: Session = Depends(get_db)):
    db_log = models.AuditLog(**log_in.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return {"status": "success", "id": db_log.id}

@app.get("/admin/audit-logs", response_model=List[schemas.AuditLogResponse])
def get_audit_logs(request: Request, db: Session = Depends(get_db)):
    payload = verify_token(request)
    if payload.get("role") != "admin":
         raise HTTPException(status_code=403, detail="Admin required")
    return db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(100).all()

# Expose metrics for Prometheus
Instrumentator().instrument(app).expose(app)

