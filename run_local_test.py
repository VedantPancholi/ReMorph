"""Local harness for schema validation and full healing runs."""

import argparse

from app.config import get_settings
from app.main import process_trapped_error
from app.models.request_models import TrappedError
from app.services.doc_fetcher import load_local_spec
from app.services.schema_extractor import extract_schema_for_route
from app.services.url_utils import extract_path
from app.testsupport.sample_errors import (
    SCENARIO_A_KEY_MUTATION,
    SCENARIO_B_ROUTE_DRIFT,
    SCENARIO_C_AUTH_DRIFT,
)
from app.utils.json_utils import pretty_print_json

SCENARIOS = {
    "a": SCENARIO_A_KEY_MUTATION,
    "b": SCENARIO_B_ROUTE_DRIFT,
    "c": SCENARIO_C_AUTH_DRIFT,
}


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the local harness."""

    parser = argparse.ArgumentParser(description="Run ReMorph local validations.")
    parser.add_argument(
        "--mode",
        choices=("smoke", "heal"),
        default="smoke",
        help="Use 'smoke' for schema extraction only or 'heal' for the full flow.",
    )
    parser.add_argument(
        "--scenario",
        choices=tuple(SCENARIOS.keys()),
        default="a",
        help="Choose the sample failure scenario to run.",
    )
    return parser.parse_args()


def run_smoke_test(trapped_error_data: dict) -> None:
    """Run the local schema extraction smoke test."""

    settings = get_settings()
    trapped_error = TrappedError.model_validate(trapped_error_data)
    spec = load_local_spec(settings.LOCAL_SPEC_PATH)
    schema = extract_schema_for_route(
        spec,
        extract_path(trapped_error.target_url),
        trapped_error.method,
    )

    print("Mode: smoke")
    print("App:", settings.APP_NAME)
    print("Target route:", trapped_error.target_url)
    print("Resolved schema path:", schema.path)
    print("Required fields:", schema.required_fields)
    print("Security requirements:", [item.model_dump() for item in schema.security_requirements])


def run_full_heal(trapped_error_data: dict) -> None:
    """Run the full healing flow against the local sample spec."""

    settings = get_settings()
    healed = process_trapped_error(
        trapped_error_data,
        local_spec_path=settings.LOCAL_SPEC_PATH,
    )

    print("Mode: heal")
    print(pretty_print_json(healed))


def main() -> None:
    """Dispatch the selected local validation mode."""

    args = parse_args()
    scenario = SCENARIOS[args.scenario]

    if args.mode == "smoke":
        run_smoke_test(scenario)
        return

    run_full_heal(scenario)


if __name__ == "__main__":
    main()
