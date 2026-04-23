# Production FastAPI Target Server Plan

## 1. Goal Description
You are 100% correct. Implementing a mock toy JSON is easy, but to show the ReMorph project to judges, we need to prove that the Fuzzer can ingest a massive, highly complex, automatically generated `openapi.json` from a production backend and STILL dynamically generate accurate Chaos Scenarios automatically. 

We will build a Financial Payment Gateway server. Financial APIs are the best to demonstrate production-readiness because they mandate complex, deeply nested schemas (billing addresses, multiple currencies) and strict, diverse security layers (X-API-Keys, Multi-Tenant Vendor IDs, and JWTs).

## 2. Directory Structure
```text
server/
├── app/
│   ├── __init__.py
│   ├── endpoints.py     # FastAPI Routers and path operations
│   ├── services.py      # Business logic and mock responses
│   └── schema.py        # Complex Pydantic v2 models
├── main.py              # FastAPI Application Factory
```

## 3. The API Design (5 Production Endpoints)

### A. Process Payment (`POST /api/v1/payments/process`)
- **Headers Required:** `x-api-key`, `x-vendor-id` (Multi-tenant requirement).
- **Body Schema (Pydantic):** 
  - `amount` (float, >0)
  - `currency` (Enum: USD, EUR, GBP)
  - `card_details` (Nested Object: `card_number`, `cvv`, `expiry`)
  - `billing_address` (Nested Object: `street`, `zip_code`, `iso_country`)
- **Significance:** Incredibly deep schema. Will prove the Fuzzer's recursive AST Tree Walker works flawlessly by dynamically mutating deeply nested properties like `iso_country`.

### B. Fetch Ledger Transactions (`GET /api/v1/ledger/transactions`)
- **Headers Required:** `Authorization: Bearer <JWT>`
- **Query Params:** `start_date` (datetime), `end_date` (datetime), `limit` (int, default 100)
- **Significance:** Explores pagination parameters and strict Bearer auth. Will prove Auth Drift logic.

### C. Onboard Corporate Client (`POST /api/v1/clients/onboard`)
- **Headers Required:** `Authorization: Bearer <JWT>`
- **Body Schema:**
  - `contact_email` (EmailStr)
  - `company_name` (String)
  - `registration_code` (String, Regex validated)
- **Significance:** Demonstrates Pydantic Regex validation boundaries and string format constraints.

### D. Update Subscription Status (`PUT /api/v1/subscriptions/{sub_id}/status`)
- **Headers Required:** `x-api-key`
- **Path Param:** `sub_id` (UUID format)
- **Body Schema:**
  - `status` (Enum: ACTIVE, SUSPENDED, CANCELED)
  - `reason_code` (String, optional)
- **Significance:** Tests `sub_id` route parsing constraints and Enums.

### E. Refund Transaction (`DELETE /api/v1/payments/{trx_id}`)
- **Headers Required:** `x-vendor-id`, `x-api-key`
- **Path Param:** `trx_id` (UUID)
- **Significance:** Path variable manipulation and multi-header requirements.

## 4. Why This Approach Rocks For Judges
At a hackathon, judges will see this server running, dynamically pull the `/openapi.json` from the Swagger UI layer, feed it into your Python Fuzzer, and instantly receive 1,000 perfectly generated Scenario A, B, C payloads that mathematically match Pydantic's strict rule engine. **It proves the Fuzzer acts autonomously.**
