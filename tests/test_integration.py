"""Integration tests comparing Python outputs against stored reference data.

Dynamically discovers model fixtures under ``tests/fixtures/models/``, runs
each model's analysis on the fly via ``run_analysis()``, and asserts that the
results match the reference data within tolerance.

In Phase 1, only high-level assertions are active.  AUC and pointwise assertions
are gated behind ``ASSERT_AUC`` and ``ASSERT_POINTWISE`` flags for activation in
Phase 2 when reference data will be Python-generated.
"""

import pytest
from pathlib import Path

from compare_runs import evaluate_tolerances
from atc138.driver import run_analysis

# Phase 1: Only high-level assertions are active.
# Enable these in Phase 2 when reference data is Python-generated
# and tighter tolerances are appropriate. Note that tolerances will also need
# to be adjusted in compare_runs.py for Phase 2.
ASSERT_AUC = False
ASSERT_POINTWISE = False

def get_model_fixtures():
    """Discover model fixture directories for pytest parametrization.

    Each subdirectory of ``tests/fixtures/models/`` that contains a
    ``reference/`` folder is treated as a test fixture.  Returns a sorted
    list of ``(name, path)`` tuples.
    """
    fixtures_dir = Path(__file__).parent / "fixtures" / "models"
    models = []

    if not fixtures_dir.exists():
        return models

    for model_dir in fixtures_dir.iterdir():
        if model_dir.is_dir() and model_dir.name != "__pycache__":
            models.append((model_dir.name, model_dir))
    return sorted(models, key=lambda x: x[0])

@pytest.mark.integration
@pytest.mark.parametrize("model_name, model_dir", get_model_fixtures())
def test_reference_comparison(model_name, model_dir, tmp_path):
    """Run a model and assert its outputs match the stored reference data."""
    repo_root = Path(__file__).parent.parent
    example_dir = repo_root / "examples" / model_name

    if not example_dir.is_dir():
        raise FileNotFoundError(f"Example directory for {model_name} not found at {example_dir}")

    reference_dir = model_dir / "reference"

    run_analysis(str(example_dir), str(tmp_path))
    results = evaluate_tolerances(str(reference_dir), str(tmp_path))

    hl = results["high_level"]

    # High-level assertions
    for metric_key, label in [("reoc", "Reoccupancy"), ("func", "Functional"), ("full", "Full repair")]:
        if metric_key in hl:
            m = hl[metric_key]
            assert m["pass"], (
                f"High-level metric '{label}' failed tolerance check for {model_name}. "
                f"Py Mean: {m['mean']:.1f}, Ref Mean: {m['ref_mean']:.1f}, Diff: {m['pct_diff']:.3f}%"
            )

    # AUC assertions (gated for Phase 2)
    if ASSERT_AUC:
        for tag_key, label in [("reoc", "Reoccupancy"), ("func", "Functional")]:
            for item in results["auc"][tag_key]:
                assert item["pass"], (
                    f"AUC metric failed for {label}, System: {item['system']} "
                    f"in {model_name}. "
                    f"Py AUC: {item['auc_py']:.3f}, Ref AUC: {item['auc_ref']:.3f}, "
                    f"Diff: {item['pct_diff']:.4f}%"
                )

    # Pointwise assertions (gated for Phase 2)
    if ASSERT_POINTWISE:
        for tag_key, label in [("reoc", "Reoccupancy"), ("func", "Functional")]:
            for item in results["pointwise"][tag_key]:
                assert item["pass"], (
                    f"Pointwise metric failed for {label}, System: {item['system']} "
                    f"in {model_name}. "
                    f"MAE: {item['MAE']:.4f}, P95: {item['P95_abs']:.4f}"
                )
