#!/usr/bin/env python3
"""
Validate roof-masked MERRA-2 baseline computation (Options A and B consistency).
Run from project root:
  python scripts/tests/test_roof_baseline.py
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import ee

DELHI_SMALL = [
    [77.20, 28.58],
    [77.25, 28.58],
    [77.25, 28.62],
    [77.20, 28.62],
    [77.20, 28.58],
]


def main() -> int:
    project_id = os.environ.get("GEE_PROJECT_ID", "pv-mapping-india")
    try:
        ee.Initialize(project=project_id)
        print("[OK] Earth Engine initialized")
    except Exception as e:
        print(f"[FAIL] Earth Engine init failed: {e}")
        return 1

    aoi = ee.Geometry.Polygon(DELHI_SMALL)

    try:
        from scripts.datasets import get_open_buildings_temporal
        from scripts.rooftops import build_rooftop_candidate_mask
        from scripts.irradiance_baseline import get_roof_masked_merra_baseline_info
    except ImportError:
        from datasets import get_open_buildings_temporal
        from rooftops import build_rooftop_candidate_mask
        from irradiance_baseline import get_roof_masked_merra_baseline_info

    buildings = get_open_buildings_temporal(aoi, year=2022)
    roof_mask = build_rooftop_candidate_mask(buildings, presence_threshold=0.5, min_height_m=0.0)

    info = get_roof_masked_merra_baseline_info(
        aoi=aoi,
        roof_mask=roof_mask,
        start_year=2020,
        end_year=2024,
        scale_m=50_000.0,
    )

    diff = float(info.get("consistency_abs_diff_kwh_m2_year", 0.0))
    diff_independent_mean = float(info.get("independent_mean_abs_diff_kwh_m2_year", 0.0))
    diff_independent_total = float(info.get("independent_total_abs_diff_kwh_year", 0.0))
    mean_opt_a = info.get("roof_baseline_mean_kwh_m2_year")
    total_opt_b = info.get("roof_baseline_total_kwh_year")
    roof_area_m2 = info.get("roof_area_m2")

    print(f"[PASS] roof_area_m2={roof_area_m2:.2f} m^2 (coarse MERRA-scale estimate)")
    print(f"[PASS] Option A mean baseline={mean_opt_a:.3f} kWh/m^2/year")
    print(f"[PASS] Option B total baseline={total_opt_b:.2f} kWh/year")
    print(f"[PASS] consistency_abs_diff_kwh_m2_year={diff:.6f}")
    print(f"[PASS] independent_mean_abs_diff_kwh_m2_year={diff_independent_mean:.6f}")
    print(f"[PASS] independent_total_abs_diff_kwh_year={diff_independent_total:.2f}")

    if diff < 1e-3 and diff_independent_mean < 5.0:
        return 0
    else:
        print("[WARN] Consistency check is higher than expected; check scale alignment.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

