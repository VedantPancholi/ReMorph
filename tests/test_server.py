import uuid

from fastapi.testclient import TestClient

from target_api.server.main import app

client = TestClient(app)

VALID_BEARER = (
    "Bearer "
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJ1c2VyIjoiZnV6emVyX2FnZW50XzAwNyIsInJvbGUiOiJhZG1pbiJ9."
    "UuceJXhdiSBpwb47N1MffwuX3vd8KFwvtNYZP8wVTTo"
)

def test_process_payment_success():
    response = client.post(
        "/api/v1/payments/process",
        json={
            "amount": 100.50,
            "currency": "USD",
            "card_details": {
                "card_number": "1234567812345678",
                "cvv": "123",
                "expiry": "12/26"
            },
            "billing_address": {
                "street": "123 Main St",
                "zip_code": "12345",
                "iso_country": "US"
            }
        },
        headers={
            "x-api-key": "secret",
            "x-vendor-id": "ven-123",
            "Authorization": VALID_BEARER,
        }
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "payment_approved"
    assert body["vendor_tenant"] == "ven-123"
    assert body["transaction_id"] == "trx-5678"
    assert body["amount_processed"] == 100.5

def test_process_payment_bad_schema():
    response = client.post(
        "/api/v1/payments/process",
        json={
            "amount": -50, # Must be > 0
            "currency": "USD",
            "card_details": {"card_number": "short", "cvv": "1", "expiry": "12/26"},
            "billing_address": {"street": "123 Main St", "zip_code": "12345", "iso_country": "USA"} # ISO must be length 2
        },
        headers={
            "x-api-key": "secret",
            "x-vendor-id": "ven-123",
            "Authorization": VALID_BEARER,
        }
    )
    assert response.status_code == 422

def test_fetch_transactions_success():
    response = client.get(
        "/api/v1/ledger/transactions?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T00:00:00Z",
        headers={"authorization": VALID_BEARER}
    )
    assert response.status_code == 200

def test_fetch_transactions_auth_failure():
    response = client.get(
        "/api/v1/ledger/transactions?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T00:00:00Z",
        headers={"authorization": "Basic bad-token"} # invalid scheme
    )
    assert response.status_code == 403
    
def test_update_subscription():
    sub_id = str(uuid.uuid4())
    response = client.put(
        f"/api/v1/subscriptions/{sub_id}/status",
        json={"status": "CANCELED", "reason_code": "user_req"},
        headers={"x-api-key": "secret", "Authorization": VALID_BEARER}
    )
    assert response.status_code == 200

def test_refund_payment():
    trx_id = str(uuid.uuid4())
    response = client.delete(
        f"/api/v1/payments/{trx_id}",
        headers={
            "x-api-key": "secret",
            "x-vendor-id": "ven-123",
            "Authorization": VALID_BEARER,
        }
    )
    assert response.status_code == 200
