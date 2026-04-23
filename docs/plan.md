# ReMorph Universal Fuzzer Architecture Plan

## Goal Description
The Fuzzer is a pure Python engine (`target_api/dataset_generator.py`) designed to automatically ingest an enterprise API specification (`target_api/specs/openapi.json`), deterministically mutate it to generate common failures (Schema, Route, and Auth drifts), and output a robust training dataset (`target_api/training_dataset.json`).

Instead of hardcoding rules specifically for `/users` or `first_name`, this plan defines a **Universal** and **Generic** architecture so that the Fuzzer can adapt to any system's `openapi.json` automatically. This will allow ReMorph's AI to self-heal and resolve error states dynamically in a production environment.

## Optimization Strategy (Enterprise-Grade Scale)
To support tech giants like Amazon or Stripe (whose OpenAPI specs often exceed 50-100MB and contain thousands of complex schema nested references), the Fuzzer implements a hyper-optimized architecture:
1. **Compilation & Memory Pruning:** Standard `openapi.json` specs are bloated with `descriptions`, `examples`, and custom `x-` extensions. During initialization, the Fuzzer extracts the AST (Abstract Syntax Tree), strips all non-functional metadata, and flattens it into a lightweight, memory-efficient Python Dataclass structure.
2. **O(1) Route Resolution:** It caches valid routes, HTTP verbs, and Security Schemes in O(1) lookup tables (Hash Maps/Sets) ensuring generation logic runs in microseconds per record.
3. **Multi-processing & Chunking:** For massive datasets (e.g., millions of training records), generation is distributed via Python `concurrent.futures.ProcessPoolExecutor`. Workers stream generated JSON natively to the disk using buffered chunking (`yield`), preventing RAM overflows.
4. **Multi-Schema Normalization:** Built-in standardizers detect if the file is Swagger 2.0 (using `definitions`) or OpenAPI 3.x (using `components/schemas`) and unifies them into a single traversable graph.

## How the Universal Algorithms Work (Agnostic Design)

### 1. Universal Schema Drift Generator
*How it works without seeing the API before:*
- The engine acts as an intelligent AST Walker that maps any `requestBody` objects in the spec.
- **Enterprise Polymorphism:** It explicitly supports `allOf` (merging multiple schemas into one), `oneOf` (randomly selecting one sub-schema path to mutate), and `anyOf` to match maximum-complexity enterprise designs.
- It dynamically extracts the `required` keys list and their `type` properties.
- **The Universal Drift:** It takes the learned requirement and applies mathematical inverses:
  - Takes a required key (e.g. `customer_id`) and programmatically alters it by appending strings (`customer_id_invalid`), dropping characters, or stripping it completely.
  - Takes a required type (e.g. `number`) and substitutes it with a natively illegal Python object (e.g., injecting an empty array `[]` where a `boolean` is expected).
- **Result:** It generates an exact 400 Bad Request payload dynamically for any schema structure, regardless of deep nesting or polymorphism.

### 2. Universal Route Drift Generator
*How it works without seeing the API before:*
- The engine parses `paths` into a list of strings (`["/cart", "/api/v2/finance/x"]`).
- It tokenizes the paths using the `/` delimiter.
- **The Universal Drift:** The engine applies heuristic algorithms to the tokens:
  - **Version Regressions:** Uses regex to detect API versions (`v1`, `v2`, `v3`). If it sees `v2`, it subtracts 1 and queries `v1`.
  - **Lexical Swapping:** Replaces the final node of the path (e.g., `x`) with a semantically likely but incorrect noun (from a small internal dictionary or randomly generated hash), while ensuring the newly generated route does not accidentally match an existing valid route (checked against the O(1) Route Cache).
- **Result:** Guaranteed 404 Route Not Found, structurally similar to real-world typos.

### 3. Universal Auth Drift Generator
*How it works without seeing the API before:*
- The engine checks the `security` property of any given path.
- It dynamically loops back to `components/securitySchemes` to figure out what the path *wants* (e.g., it learns "this path requires an API key in the header called `x-api-key`").
- **The Universal Drift:** The Fuzzer flips the requirement. 
  - If the schema demands `ApiKeyAuth`, the fuzzer injects `Authorization: Bearer <token>`.
  - If the schema demands `OAuth2 / Bearer`, the fuzzer injects `x-api-key: base64...`.
  - Or it systematically drops the auth header entirely from a route known to require one.
- **Result:** Guaranteed 401 Unauthorized for any secure endpoint in the spec.

## Engine Output Loop
- Loop over valid paths randomly, call the 3 mutators systematically.
- Use `uuid` and `random` standard libraries uniformly to generate a minimum of 100+ random but deterministic records.
- Saves standard formatted JSON matching the ReMorph standard schema into `target_api/training_dataset.json`.

## Verification Plan
- Run `python target_api/dataset_generator.py` locally.
- Validate `target_api/training_dataset.json` contains valid JSON.
- Verify generated array matches the exact schema expected by the RL script.
