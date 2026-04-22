"""Sample trapped failures for the three demo chaos scenarios."""

SCENARIO_A_KEY_MUTATION = {
    "target_url": "https://mock.example.com/users",
    "method": "POST",
    "failed_payload": {
        "first_name": "John",
        "last_name": "Doe",
    },
    "failed_headers": {
        "Authorization": "Bearer demo-token",
    },
    "error_code": 400,
    "error_message": "Invalid request body",
}

SCENARIO_B_ROUTE_DRIFT = {
    "target_url": "https://mock.example.com/api/v1/transactions",
    "method": "GET",
    "failed_headers": {
        "Authorization": "Bearer demo-token",
    },
    "error_code": 404,
    "error_message": "Route not found",
}

SCENARIO_C_AUTH_DRIFT = {
    "target_url": "https://mock.example.com/api/v2/finance/ledger",
    "method": "GET",
    "failed_headers": {
        "Authorization": "Bearer demo-token",
    },
    "error_code": 401,
    "error_message": "Unauthorized",
    "auth_context": {
        "scheme": "bearer",
        "header_name": "Authorization",
    },
}
