import os
from azure.monitor.opentelemetry import configure_azure_monitor

# Configure Azure Monitor for Application Insights
connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    configure_azure_monitor(connection_string=connection_string)

from fastapi import FastAPI, Request, Response, BackgroundTasks, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import jwt
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator

from database import engine, Base, SessionLocal, get_db
from models import AuditLog

Base.metadata.create_all(bind=engine)

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://jpshop.puneetdevops.online")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8002")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8003")
CART_SERVICE_URL = os.getenv("CART_SERVICE_URL", "http://cart-service:8004")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://order-service:8005")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8006")
REVIEW_SERVICE_URL = os.getenv("REVIEW_SERVICE_URL", "http://review-service:8007")
WISHLIST_SERVICE_URL = os.getenv("WISHLIST_SERVICE_URL", "http://wishlist-service:8008")
VAULT_SERVICE_URL = os.getenv("VAULT_SERVICE_URL", "http://vault-service:8009")

SERVICES = {
    "auth": AUTH_SERVICE_URL,
    "user": USER_SERVICE_URL,
    "product": PRODUCT_SERVICE_URL,
    "cart": CART_SERVICE_URL,
    "order": ORDER_SERVICE_URL,
    "payment": PAYMENT_SERVICE_URL,
    "review": REVIEW_SERVICE_URL,
    "wishlist": WISHLIST_SERVICE_URL,
    "vault": VAULT_SERVICE_URL,
}

app = FastAPI(title="API Gateway")

allowed_origins = [
    FRONTEND_URL,
    FRONTEND_URL.replace("https://", "http://"),
    "https://api.puneetdevops.online",
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin")
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response

@app.middleware("http")
async def forward_proto_middleware(request: Request, call_next):
    if request.headers.get("x-forwarded-proto") == "https":
        request.scope["scheme"] = "https"
    return await call_next(request)

def save_audit_log(ip_address: str, method: str, service_name: str, path: str, status_code: int, user_email: str = None):
    db = SessionLocal()
    try:
        log_entry = AuditLog(
            ip_address=ip_address,
            method=method,
            user_email=user_email,
            service_name=service_name,
            path=path,
            status_code=status_code,
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"Failed to save audit log: {e}")
    finally:
        db.close()

@app.get("/health")
def health_check():
    return {"status": "gateway is live"}

@app.get("/admin/audit-logs")
def get_audit_logs(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        token = auth_header.split(" ")[1]
        payload = jwt.decode(token, options={"verify_signature": False})
        if payload.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin required")
        return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def route_request(service_name: str, path: str, request: Request, background_tasks: BackgroundTasks):
    if service_name not in SERVICES:
        return Response(status_code=404, content="Service not found")

    if request.method == "OPTIONS":
        return Response(status_code=204)

    url = f"{SERVICES[service_name]}/{path}"
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    body = await request.body()
    client_ip = request.client.host if request.client else "unknown"
    user_email = "Anonymous"

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, options={"verify_signature": False})
            user_email = payload.get("sub", "Unknown")
        except:
            pass

    headers["X-User-Email"] = user_email

    async with httpx.AsyncClient() as client:
        try:
            proxy_response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=request.query_params,
                timeout=30.0,
            )
            background_tasks.add_task(save_audit_log, client_ip, request.method, service_name, path, proxy_response.status_code, user_email)
            excluded_cors_headers = ["access-control-allow-origin", "access-control-allow-credentials", "access-control-allow-methods", "access-control-allow-headers"]
            proxy_headers = {k: v for k, v in proxy_response.headers.items() if k.lower() not in excluded_cors_headers}
            origin = request.headers.get("origin")
            if origin in allowed_origins:
                proxy_headers["Access-Control-Allow-Origin"] = origin
                proxy_headers["Access-Control-Allow-Credentials"] = "true"
                proxy_headers["Vary"] = "Origin"
            return Response(content=proxy_response.content, status_code=proxy_response.status_code, headers=proxy_headers)
        except Exception as e:
            return Response(status_code=503, content=f"Gateway Error: {str(e)}")

Instrumentator().instrument(app).expose(app)
