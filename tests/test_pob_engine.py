"""Tests for the PoB calculation engine."""

import pytest
from pathlib import Path


POB_PATH = Path(__file__).parent.parent / "vendor" / "PathOfBuilding-PoE2"


@pytest.mark.skipif(
    not (POB_PATH / "src" / "HeadlessWrapper.lua").exists(),
    reason="PoB-PoE2 submodule not initialized",
)
class TestPoBEngine:
    """Tests that require the PoB-PoE2 submodule to be present."""

    def test_pob_path_exists(self):
        """PoB-PoE2 submodule is cloned and has expected structure."""
        assert (POB_PATH / "src" / "HeadlessWrapper.lua").exists()
        assert (POB_PATH / "src" / "Launch.lua").exists()
        assert (POB_PATH / "src" / "Data").is_dir()

    # TODO: Day 3-4 — test lupa boots HeadlessWrapper
    # TODO: Day 7-8 — test loading a real build
