"""P117 premium closed-beta scope contract test."""

from pathlib import Path


SCOPE = (Path(__file__).parents[2] / "docs/product/PREMIUM_BETA_SCOPE.md").read_text(encoding="utf-8")


def test_beta_scope_includes_exact_product_foundation():
    for item in (
        "MEDAR", "Daily Intelligence", "Trading Workspace", "Trading Coach",
        "Portfolio Guardian", "memory consent", "notification center", "NQ and MNQ",
        "Research seam",
    ):
        assert item in SCOPE


def test_beta_scope_explicitly_defers_non_mvp_and_real_authority():
    for item in (
        "Robotics", "smart-home", "Genealogy", "Kitchen", "Health and wearable",
        "Full video AI", "LIVE trading", "Real payments", "Production authentication",
    ):
        assert item in SCOPE
    assert "zero execution side effects" in SCOPE
    assert "Billing is synthetic and cannot charge" in SCOPE
    assert "PAPER and LIVE remain explicitly separate" in SCOPE