"""Deliberately regenerate the golden reference output. Run manually and review the diff --
never run this reflexively just to make test_golden_risk_calculations.py pass; a diff here means
either the fixed synthetic scenario changed (fine, expected) or a risk calculation's numeric
output changed (needs a reviewed reason -- see CLAUDE.md "Git conventions").

Usage: .venv\\Scripts\\python.exe -m tests.golden.generate_reference
"""

from __future__ import annotations

import json

from tests.golden.test_golden_risk_calculations import REFERENCE_PATH, _compute_golden_output


def main() -> None:
    output = _compute_golden_output()
    REFERENCE_PATH.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(f"wrote {REFERENCE_PATH}")
    for k, v in output.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
