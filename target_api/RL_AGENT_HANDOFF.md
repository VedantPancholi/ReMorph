# ReMorph Project Handoff: Context for Reinforcement Learning (Phase 2)

**To the Next Developer & Agent System:**
We have successfully completed Phase 1 of the ReMorph project. We designed and built the "Target API," consisting of a highly secure Enterprise FastAPI Target Server, and a heavily advanced, algorithmic Universal API Fuzzer.

Your objective for Phase 2 is to consume the outputs of Phase 1 and build a Reinforcement Learning (RL) model that trains an autonomous agent to "self-heal" broken integrations in real-time.

Below is the exact context of what we built, your system boundaries, and the data structures you will ingest.

---

## 1. What We Built (The Target API)

### The Target Environment (`/server`)
We built a restrictive, production-ready Financial Gateway API in FastAPI. It strictly enforces:
1. **Multi-Tenant JWT Authentication**: Requires `x-api-key`, `x-vendor-id`, and an HS256 cryptographically signed `Bearer` token using FastAPI's native `HTTPBearer` dependency.
2. **Deep Pydantic Validation**: Nested schemas rejecting invalid emails, bad enum values (`USD`, `EUR`), missing keys, and poor nested objects.
3. **Strict Restful Routing**: Catches bad `HTTP Methods` and invalid `HTTP Paths`.

### The Universal Matrix Fuzzer (`target_api/dataset_generator.py`)
We built a pure Python Fuzzing engine that operates on **100% Mathematical Universality**. 
It ingests an organic OpenAPI 3.0.3 spec (`target_api/specs/openapi.json`), uses an Abstract Syntax Tree (AST) to infer the schemas/Enums, and dynamically generates network traffic.

It intentionally attacks the API using an **11-Factor Advanced Matrix:**
- **Schema Drifts:** Deletes required fields, forces type coercion (sending arrays instead of strings), injects null values, and adds unexpected keys.
- **Route Drifts:** Regresses versions (`/v1/` to `/v0/`), spoofs HTTP methods (sends `GET` instead of `POST`), and fragments URL paths.
- **Auth Drifts:** Drops the JWT entirely, forges invalid cryptographic signatures, and drops tenant boundaries.

---

## 2. Your Primary Input: The Training Dataset

Your RL Model will exclusively train on the output of the Fuzzer: `target_api/training_dataset.json`. 
This file contains thousands of organic network transaction records based on live `httpx` network calls. **Crucially**, the dataset dynamically separates logs based on genuine API responses.

### A. The "True Success" Base Truth Structure
When a request perfectly passes all cryptographic and Pydantic rules (`HTTP 200/201`), the JSON log is mathematically mapped like this:
```json
{
  "target_url": "http://127.0.0.1:8000/api/v1/clients/onboard",
  "method": "POST",
  "actual_server_response": "{\"status\":\"client_onboarded\",\"assigned_email\":\"test@example.com\"}",
  "scenario_type": "success_attempt",
  "success_payload": {
    "contact_email": "test@example.com",
    "company_name": "ReMorph Corp",
    "registration_code": "ABCD12345XYZ"
  },
  "success_headers": {
    "Authorization": "Bearer <SIGNED_JWT>"
  },
  "status_code": 201
}
```
*Notice how valid parameters map to the keys `success_payload` and `success_headers`.*

### B. The "Chaotic Failure" Structure (The RL Learning Material)
When the fuzzer applies one of the 11 Matrix Drifts, the server violently rejects it. The JSON dynamically logs the *explicit detailed tracebacks* from the server. Your model must interpret these strings to understand *why* it failed.
```json
{
  "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
  "method": "POST",
  "actual_server_response": "{\"detail\":[{\"type\":\"missing\",\"loc\":[\"body\",\"currency\"],\"msg\":\"Field required\"}]}",
  "scenario_type": "schema_missing_key",
  "failed_payload": {
    "amount": 100,
    "card_details": { ... }
  },
  "error_code": 422
}
```
*Notice how trapped parameters map to `failed_payload` and `error_code`.*

---

## 3. Your RL Agent's Task (Phase 2)

As the new developer, your objective is to build an RL model/Transformer that:
1. Parses `target_api/training_dataset.json`.
2. **Evaluates the Delta:** Compares the broken state (`failed_payload` + `error_code`, e.g. 422) against the literal traceback embedded in `actual_server_response` (e.g. `"msg":"Field required"`).
3. **Action / Target:** The model must learn an actionable mapping algorithm to generate the delta required to structurally modify `failed_payload` into the `success_payload` layout.

By mastering the mathematical gaps between the 11 Advanced Matrix edge-cases and the Base Truths, your agent will become fully capable of autonomous, universal API self-healing. Start building the model execution flow!
