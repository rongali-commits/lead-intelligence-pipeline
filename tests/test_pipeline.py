from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from lead_intelligence import run_pipeline


def test_sample_pipeline_deduplicates_scores_and_exports(tmp_path: Path) -> None:
    sample = Path(__file__).parents[1] / "sample_data" / "directory.html"

    result = run_pipeline(sample, tmp_path, minimum_score=75)

    assert result.collected == 7
    assert result.unique == 6
    assert result.duplicates_removed == 1
    assert result.qualified == 5
    assert json.loads((tmp_path / "summary.json").read_text())["qualified"] == 5

    with (tmp_path / "qualified_leads.csv").open(newline="", encoding="utf-8") as handle:
        qualified = list(csv.DictReader(handle))
    assert {row["company"] for row in qualified} >= {"Nova Clinics", "Peak Realty", "CloudCart"}
    assert len([row for row in qualified if "Peak Realty" in row["company"]]) == 1


def test_score_threshold_is_validated(tmp_path: Path) -> None:
    sample = Path(__file__).parents[1] / "sample_data" / "directory.html"
    with pytest.raises(ValueError, match="between 0 and 100"):
        run_pipeline(sample, tmp_path, minimum_score=101)

