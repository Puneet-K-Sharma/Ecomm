from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from database import Base

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False) # Maps to auth_users.id
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(String(500), nullable=True)

class StreamingProfile(Base):
    __tablename__ = "streaming_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False) # Maps to auth_users.id
    name = Column(String(100), nullable=False)
    img = Column(String(500), nullable=True)
    isKids = Column(Boolean, default=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(50))
    method = Column(String(10))
    user_email = Column(String(100), nullable=True)
    service_name = Column(String(50))
    path = Column(String(255))
    status_code = Column(Integer)

