"""Local JSON adapter only. No clock loop, network, process or database capability."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.collector_cycle import cycle
from scripts.collector_operation_plan import instant


def main():
    try:
        # Explicit injected evidence and evaluation time; no implicit wall clock.
        payload = json.load(sys.stdin)
        print(json.dumps(cycle(payload["operation_config"], payload["budget_config"],
                               payload["evidence"], instant(payload["now"])), sort_keys=True))
    except Exception:
        print(json.dumps(dict(decision="BLOCKED", reason="INVALID_INPUT", simulation_only=True,
                              execution_authorized=False, actual_provider_requests=0)))


if __name__ == "__main__":
    main()
