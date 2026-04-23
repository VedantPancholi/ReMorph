from fastapi import APIRouter, Depends, Header, HTTPException, Query, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from uuid import UUID
from datetime import datetime
import jwt

from .schema import (
    PaymentProcessRequest, 
    CorporateClientOnboardRequest,
    SubscriptionStatusUpdate
)

router = APIRouter()

security = HTTPBearer()

def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        # Cryptographically parse the JWT
        payload = jwt.decode(token, "ReMorphSecretKey2026", algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401, 
            detail="Authentication failed: Invalid Cryptographic JWT signature. Token rejected."
        )

@router.post("/payments/process", status_code=201)
async def process_payment(
    payload: PaymentProcessRequest,
    x_api_key: str = Header(..., description="Provider API Key"),
    x_vendor_id: str = Header(..., description="Multi-tenant Vendor Routing ID"),
    auth: dict = Depends(verify_jwt)
):
    if x_api_key != "secret":
        raise HTTPException(
            status_code=401, 
            detail="Authentication failed: The provided x-api-key is invalid for the requested vendor environment."
        )
    return {
        "status": "payment_approved", 
        "transaction_id": f"trx-{payload.card_details.card_number[-4:]}", 
        "amount_processed": payload.amount,
        "vendor_tenant": x_vendor_id
    }

@router.get("/ledger/transactions")
async def fetch_transactions(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    limit: int = Query(100),
    auth: str = Depends(verify_jwt)
):
    return {"transactions": [], "limit": limit}

@router.post("/clients/onboard", status_code=201)
async def onboard_client(
    payload: CorporateClientOnboardRequest,
    auth: dict = Depends(verify_jwt)
):
    return {
        "status": "client_onboarded", 
        "assigned_email": payload.contact_email,
        "registration_reference": payload.registration_code,
        "jwt_user_extracted": auth.get("user")
    }

@router.put("/subscriptions/{sub_id}/status")
async def update_subscription(
    payload: SubscriptionStatusUpdate,
    sub_id: UUID = Path(...),
    x_api_key: str = Header(...),
    auth: dict = Depends(verify_jwt)
):
    return {"status": "updated", "id": str(sub_id)}

@router.delete("/payments/{trx_id}")
async def refund_payment(
    trx_id: UUID = Path(...),
    x_api_key: str = Header(...),
    x_vendor_id: str = Header(...),
    auth: dict = Depends(verify_jwt)
):
    if x_api_key != "secret":
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return {"status": "refunded", "trx_id": str(trx_id)}
