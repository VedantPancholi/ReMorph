# ReMorph Phase 1: Chaos Gym & API Fuzzer

**ReMorph** is a synthetic API Fuzzer and target engine designed to train Reinforcement Learning (RL) agents. Phase 1 provides the live testing environment—a "Chaos Gym" consisting of a strictly validated live FastAPI server, and a fully generic Abstract Syntax Tree (AST) Fuzzing script that attacks it.

---

## 🛠️ 1. Project Requirements

You must install the ecosystem dependencies before running the project. 

```bash
pip install -r requirements.txt
```

*(If you are running in a virtual environment, ensure it is activated: `source .venv/bin/activate`)*

---

## 🚀 2. Step-by-Step Execution Guide

To utilize the Phase 1 ecosystem, run these components sequentially in your terminal:

### Step 1: Boot the Live Target Server
ReMorph utilizes a highly strict Financial Gateway mock built in FastAPI. It utilizes heavy Pydantic constraints, nested regex, and Cryptographic PyJWT validations. It is the target your RL agent will hit.

Open a terminal and start the server:
```bash
uvicorn server.main:app --reload
```
*The server will boot on `http://127.0.0.1:8000`.*

### Step 2: Generate (or review) the Universal Contract
The Fuzzer relies entirely on `openapi.json` to reverse-engineer schemas. It does not use hardcoded arrays. You can look at the spec we use inside `specs/openapi.json`. 

If you ever add new routes to `server/app/endpoints.py`, re-generate the contract via:
```bash
python server/export_openapi.py
or
python3 -m server.export_openapi
```
*This will sync the absolute latest FastAPI routing into the Swagger schema file.*

### Step 3: Unleash the Universal Fuzzer
The `dataset_generator.py` is the algorithmic weapon. It dynamically loops through the AST defined in `openapi.json`, bypasses generic bounds, and aggressively tests the target server using 11 Advanced Array mutations (Type Coercion, Null Injection, Route Regression, Signatures Forgery, etc).

Run the Generator to generate the Dataset mapping:
```bash
# This iterates 1 pass over the API surface (Generates ~47 deep dataset records)
python dataset_generator.py -m 1

# This iterates 10 passes for deep epoch weighting (Generates ~470 RL records)
python dataset_generator.py -m 10
```

---

## 🌐 3. Interactive Swagger UI & Authentication Guide

Because the server is fully operational, you can test the APIs manually through the UI! 

1. Ensure the server is running (`uvicorn server.main:app`).
2. Open your browser to the Interactive Dashboard: **`http://127.0.0.1:8000/docs`**

### 🔓 How to Authorize in Swagger
Because the server enforces genuine enterprise cryptography, you must authenticate yourself first before hitting ANY endpoints smoothly:
1. Locate the **Green "Authorize" Padlock Button** at the top right of the Swagger dashboard.
2. In the `HTTPBearer` pop-up box, simply paste the cryptographically signed JWT below *(do **not** type "Bearer ", Swagger handles it natively!)*:
   `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZnV6emVyX2FnZW50XzAwNyIsInJvbGUiOiJhZG1pbiJ9.UuceJXhdiSBpwb47N1MffwuX3vd8KFwvtNYZP8wVTTo`
3. Click "Authorize" and then "Close".

### 🧪 Executing a Manual API Payload
1. Click on the `POST /api/v1/payments/process` route.
2. Click **"Try it out"**.
3. Under the `x-api-key` header box, type the string: `secret`
4. Under the `x-vendor-id` header box, type the string: `ven-123`
5. In the Request Body box, use this perfect baseline:
```json
{
  "amount": 100.50,
  "currency": "USD",
  "card_details": {
    "card_number": "1234567812345678",
    "cvv": "123",
    "expiry": "12/26"
  },
  "billing_address": {
    "street": "123 Wall St",
    "zip_code": "10005",
    "iso_country": "US"
  }
}
```
6. Click **Execute**. You should witness a pure `201 Created` string return from the backend!

---

## 📊 4. Consuming the Final Output (`training_dataset.json`)

The final output is `training_dataset.json`. 

By design, it structurally logs Live Server logic. The Phase 2 Developer/RL Agent must ingest this file and parse the `"actual_server_response"` tracing data, calculating the exact algorithmic divergence to bridge the `"failed_payload"` matrix back into the `"success_payload"`.
