import os
from azure.monitor.opentelemetry import configure_azure_monitor

connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    configure_azure_monitor(connection_string=connection_string)

from prometheus_fastapi_instrumentator import Instrumentator
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import models, schemas
from database import engine, get_db
from security import verify_token
import uuid

app = FastAPI(title="Payment Service")

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

@app.on_event("startup")
def startup():
    try:
        models.Base.metadata.create_all(bind=engine)
    except Exception as exc:
        print(f"DB init skipped during startup: {exc}")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"service": "Payment Service", "status": "online"}

@app.post("/payments", response_model=schemas.PaymentResponse)
def process_payment(payment_in: schemas.PaymentCreate, request: Request, db: Session = Depends(get_db)):
    user_payload = verify_token(request)
    user_id = user_payload.get("id")
    existing_payment = db.query(models.Payment).filter(
        models.Payment.order_id == payment_in.order_id,
        models.Payment.status == "Completed"
    ).first()
    if existing_payment:
        raise HTTPException(status_code=400, detail="Payment already completed for this order")
    transaction_id = f"txn_{uuid.uuid4()}"
    payment_status = "Completed"
    wallet = db.query(models.Wallet).filter(models.Wallet.user_id == user_id).first()
    if not wallet or wallet.balance < payment_in.amount:
        raise HTTPException(status_code=400, detail="Insufficient Wallet Balance")
    wallet.balance -= payment_in.amount
    new_payment = models.Payment(
        order_id=payment_in.order_id,
        user_id=user_id,
        amount=payment_in.amount,
        status=payment_status,
        transaction_id=transaction_id
    )
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    return new_payment

@app.get("/payments/order/{order_id}", response_model=schemas.PaymentResponse)
def get_payment_status(order_id: int, request: Request, db: Session = Depends(get_db)):
    user_payload = verify_token(request)
    user_id = user_payload.get("id")
    payment = db.query(models.Payment).filter(
        models.Payment.order_id == order_id,
        models.Payment.user_id == user_id
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment

@app.get("/wallet/balance", response_model=schemas.WalletResponse)
def get_balance(request: Request, db: Session = Depends(get_db)):
    user_payload = verify_token(request)
    user_id = user_payload.get("id")
    wallet = db.query(models.Wallet).filter(models.Wallet.user_id == user_id).first()
    if not wallet:
        wallet = models.Wallet(user_id=user_id, balance=0.0)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet

@app.post("/wallet/deposit", response_model=schemas.WalletResponse)
def deposit_funds(deposit: schemas.WalletDeposit, request: Request, db: Session = Depends(get_db)):
    user_payload = verify_token(request)
    user_id = user_payload.get("id")
    wallet = db.query(models.Wallet).filter(models.Wallet.user_id == user_id).first()
    if not wallet:
        wallet = models.Wallet(user_id=user_id, balance=0.0)
        db.add(wallet)
    wallet.balance += deposit.amount
    db.commit()
    db.refresh(wallet)
    return wallet

Instrumentator().instrument(app).expose(app)
