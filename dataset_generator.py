import json
import os
import random
import re
import uuid
import argparse
import httpx
import jwt

class ReMorphFuzzer:
    def __init__(self, spec_path: str = "specs/openapi.json", base_url: str = "http://127.0.0.1:8000"):
        self.spec_path = spec_path
        self.base_url = base_url
        self.api_spec = self._load_specification()
        self.resolved_schemas = {}
        self._initialize_caches()
        self.client = httpx.Client(base_url=self.base_url, timeout=10.0)

    def _load_specification(self) -> dict:
        if not os.path.exists(self.spec_path):
            raise FileNotFoundError(f"🚨 Missing API Contract! Could not find {self.spec_path}")
        with open(self.spec_path, 'r') as file:
            return json.load(file)

    def _initialize_caches(self):
        schemas_root = self.api_spec.get("components", {}).get("schemas", {})
        for key, val in schemas_root.items():
            self.resolved_schemas[f"#/components/schemas/{key}"] = val

    def _resolve_ref(self, schema: dict) -> dict:
        if "$ref" in schema:
            return self.resolved_schemas.get(schema["$ref"], {})
        return schema

    def _deep_extract_required(self, schema: dict) -> dict:
        schema = self._resolve_ref(schema)
        props = {}
        if "properties" in schema:
            for k, v in schema["properties"].items():
                v_res = self._resolve_ref(v)
                if "enum" in v_res:
                    props[k] = {"type": "enum", "values": v_res["enum"]}
                elif v_res.get("type") == "object" or "$ref" in v:
                    props[k] = self._deep_extract_required(v_res)
                else:
                    props[k] = v_res.get("type", "string")
        
        required_keys = schema.get("required", list(props.keys()))
        return {k: props.get(k, "string") for k in required_keys if k in props}

    def _get_valid_headers(self):
        valid_token = jwt.encode({"user": "fuzzer_agent_007", "role": "admin"}, "ReMorphSecretKey2026", algorithm="HS256")
        return {"x-api-key": "secret", "x-vendor-id": "ven-123", "Authorization": f"Bearer {valid_token}"}

    def _get_valid_payload_for_schema(self, req_fields):
        payload = {}
        for k, t in req_fields.items():
            if isinstance(t, dict):
                if t.get("type") == "enum":
                    payload[k] = t["values"][0]
                else:
                    payload[k] = self._get_valid_payload_for_schema(t)
                continue
            k_lower = str(k).lower()
            if "email" in k_lower: payload[k] = "test@example.com"
            elif "card" in k_lower or "pan" in k_lower: payload[k] = "1234567812345678"
            elif "cvv" in k_lower: payload[k] = "123"
            elif "expiry" in k_lower: payload[k] = "12/26"
            elif "zip" in k_lower: payload[k] = "12345"
            elif "country" in k_lower or "iso" in k_lower: payload[k] = "US"
            elif "currency" in k_lower: payload[k] = "USD"
            elif "status" in k_lower: payload[k] = "ACTIVE"
            elif "registration" in k_lower or "code" in k_lower: payload[k] = "ABCD12345XYZ"
            elif t == "string": payload[k] = "test_string"
            elif t == "number" or t == "integer": payload[k] = 100
            elif t == "boolean": payload[k] = True
            else: payload[k] = {}
        return payload

    def execute_live_request(self, method: str, url: str, headers: dict, json_payload: dict = None, tag: str = "scenario"):
        try:
            req_kwargs = {"headers": headers}
            if json_payload is not None:
                req_kwargs["json"] = json_payload
            
            response = self.client.request(method, url, **req_kwargs)
            is_success = response.status_code < 400
            
            record = {
                "target_url": f"{self.base_url}{url}",
                "method": method.upper(),
                "actual_server_response": response.text,
                "request_id": f"req-{str(uuid.uuid4())[:8]}",
                "source_component": "api_proxy",
                "scenario_type": tag
            }
            if is_success:
                record["success_payload"] = json_payload
                record["success_headers"] = headers
                record["status_code"] = response.status_code
            else:
                record["failed_payload"] = json_payload
                record["failed_headers"] = headers
                record["error_code"] = response.status_code
            return record
        except Exception as e:
            return {"target_url": f"{self.base_url}{url}", "method": method.upper(), "error_code": 503, "actual_server_response": str(e), "scenario_type": "server_down"}

    def perform_generic_request(self, raw_path, method, req_fields, strategy="success"):
        # Universal Path Generation: Replaces any {...} token perfectly
        url_path = re.sub(r'\{[^\}]+\}', "123e4567-e89b-12d3-a456-426614174000", raw_path)
        
        # Universal Query Param handling (Mock basic queries if required)
        if "ledger" in raw_path and method.lower() == "get":
            url_path += "?start_date=2024-01-01T00:00:00Z&end_date=2024-01-31T00:00:00Z&limit=100"
            
        active_method = method
        if strategy == "route_method_spoof":
            active_method = "GET" if method.upper() != "GET" else "POST"

        if strategy == "route_regression" and re.search(r'v(\d+)', url_path):
            url_path = re.sub(r'v(\d+)', lambda m: f"v{int(m.group(1))-1}", url_path)
        elif strategy == "route_invalid_path":
            url_path += "/invalid_path_404"

        headers = self._get_valid_headers()
        
        if strategy == "auth_missing_token":
            if "Authorization" in headers: del headers["Authorization"]
        elif strategy == "auth_malformed_jwt":
            headers["Authorization"] = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI.invalid.token.123"
        elif strategy == "auth_missing_tenant":
            if "x-vendor-id" in headers: del headers["x-vendor-id"]

        payload = None

        # Build Universal Body perfectly aligned with AST parsing
        if active_method.lower() in ['post', 'put', 'patch'] and req_fields:
            payload = self._get_valid_payload_for_schema(req_fields)
            if payload:
                key = random.choice(list(payload.keys()))
                if strategy == "schema_missing_key":
                    del payload[key]
                elif strategy == "schema_type_coercion":
                    payload[key] = [1, 2, 3]
                elif strategy == "schema_extra_key":
                    payload["unexpected_injected_vector"] = "chaos"
                elif strategy == "schema_null_injection":
                    payload[key] = None
            elif strategy.startswith("schema_"):
                 payload = {"unexpected_drift": "chaos"}
            
        return self.execute_live_request(active_method, url_path, headers, payload, tag=strategy)

    def run_fuzzer(self, multiplier=1):
        print("🚀 Initializing ReMorph UNIVERSAL Generator...")
        results = []
        paths = self.api_spec.get("paths", {})
        
        # Universal AST Sweeper! 
        for _ in range(multiplier):
            for path, methods in paths.items():
                for method, details in methods.items():
                    method = method.upper()
                    
                    schema = {}
                    if "requestBody" in details:
                        try:
                            schema = details["requestBody"].get("content", {}).get("application/json", {}).get("schema", {})
                        except: pass
                    req_fields = self._deep_extract_required(schema)
                    
                    # Stage 1: The PERFECT BASE TRUTH
                    results.append(self.perform_generic_request(path, method, req_fields, "success_attempt"))
                    
                    # Stage 2: Universal SCHEMA DRIFT Matrix (Only if Schema exists)
                    if req_fields:
                        for s_drift in ["schema_missing_key", "schema_type_coercion", "schema_extra_key", "schema_null_injection"]:
                            results.append(self.perform_generic_request(path, method, req_fields, s_drift))
                    
                    # Stage 3: Universal ROUTE DRIFT Matrix
                    for r_drift in ["route_regression", "route_method_spoof", "route_invalid_path"]:
                        results.append(self.perform_generic_request(path, method, req_fields, r_drift))
                    
                    # Stage 4: Universal AUTH DRIFT Matrix
                    for a_drift in ["auth_missing_token", "auth_malformed_jwt", "auth_missing_tenant"]:
                        results.append(self.perform_generic_request(path, method, req_fields, a_drift))
                    
        with open("training_dataset.json", "w") as f:
            json.dump(results, f, indent=2)
            
        print(f"✅ Swept {len(results)} UNIVERSAL Network Requests!")
        print(f"📁 Semantic Truth & Delta mapping complete -> training_dataset.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ReMorph Network Fuzzer")
    parser.add_argument("-m", "--multiplier", type=int, default=1, help="Iterate over the entire universal API space X times.")
    args = parser.parse_args()
    
    fuzzer = ReMorphFuzzer()
    fuzzer.run_fuzzer(multiplier=args.multiplier)
