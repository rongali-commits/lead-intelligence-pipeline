from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize, deduplicate, score, and export lead records from local HTML."
    )
    parser.add_argument("input", type=Path, help="Local HTML source")
    parser.add_argument("--output", type=Path, default=Path("output"))
    parser.add_argument("--minimum-score", type=int, default=75)
    args = parser.parse_args()

    result = run_pipeline(args.input, args.output, args.minimum_score)
    print(
        f"Collected {result.collected} rows, retained {result.unique} unique records, "
        f"and qualified {result.qualified} at score >= {result.minimum_score}."
    )
    print(f"Outputs: {result.output_directory.resolve()}")


if __name__ == "__main__":
    main()

