from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from typing import Optional

class CurrencyEnum(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

class SubscriptionStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELED = "CANCELED"

class CardDetails(BaseModel):
    card_number: str = Field(..., min_length=16, max_length=19, description="Raw PAN")
    cvv: str = Field(..., min_length=3, max_length=4)
    expiry: str = Field(..., pattern=r"^(0[1-9]|1[0-2])\/?([0-9]{4}|[0-9]{2})$")

class BillingAddress(BaseModel):
    street: str
    zip_code: str
    iso_country: str = Field(..., min_length=2, max_length=2)

class PaymentProcessRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: CurrencyEnum
    card_details: CardDetails
    billing_address: BillingAddress

class CorporateClientOnboardRequest(BaseModel):
    contact_email: EmailStr
    company_name: str
    registration_code: str = Field(..., pattern=r"^[A-Z0-9]{8,12}$")

class SubscriptionStatusUpdate(BaseModel):
    status: SubscriptionStatusEnum
    reason_code: Optional[str] = None
