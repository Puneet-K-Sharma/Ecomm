from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserProfileBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None

class UserProfileCreate(UserProfileBase):
    pass

class UserProfileResponse(UserProfileBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True

class StreamingProfileBase(BaseModel):
    name: str
    img: Optional[str] = None
    isKids: bool = False

class StreamingProfileCreate(StreamingProfileBase):
    pass

class StreamingProfileResponse(StreamingProfileBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True

class AuditLogBase(BaseModel):
    ip_address: str
    method: str
    service_name: str
    path: str
    status_code: int
    user_email: Optional[str] = None

class AuditLogCreate(AuditLogBase):
    pass

class AuditLogResponse(AuditLogBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

