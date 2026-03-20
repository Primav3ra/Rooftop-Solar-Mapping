#!/usr/bin/env python3
"""
Verify that dataset loaders in datasets.py and utility.py work against GEE.
Run from project root: python scripts/test_datasets.py
Or from scripts/: python test_datasets.py
"""
import sys
import os

# Ensure project root or scripts/ is on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import ee

# Small AOI: central Delhi (small box to keep GEE requests fast)
DELHI_SMALL = [[77.20, 28.58], [77.25, 28.58], [77.25, 28.62], [77.20, 28.62], [77.20, 28.58]]


def run_test(name: str, fn, *args, **kwargs):
    """Run a test and print pass/fail."""
    try:
        result = fn(*args, **kwargs)
        print(f"  [PASS] {name}")
        return result
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        return None


def main():
    print("GEE Dataset verification")
    print("=" * 50)

    # 1. Initialize Earth Engine
    project_id = os.environ.get("GEE_PROJECT_ID", "pv-mapping-india")
    try:
        ee.Initialize(project=project_id)
        print("[OK] Earth Engine initialized\n")
    except Exception as e:
        print(f"[ERROR] Earth Engine init failed: {e}")
        print("   Run: earthengine authenticate")
        return 1

    aoi = ee.Geometry.Polygon(DELHI_SMALL)

    # 2. Test datasets module directly
    print("Testing scripts.datasets functions (direct)")
    try:
        from scripts.datasets import (
            get_dem,
            get_open_buildings_temporal,
            get_sentinel2_composite,
            get_modis_lst_composite,
            get_available_datasets,
        )
    except ImportError:
        from datasets import (
            get_dem,
            get_open_buildings_temporal,
            get_sentinel2_composite,
            get_modis_lst_composite,
            get_available_datasets,
        )

    # get_dem (SRTM) - force evaluation with reduceRegion
    dem = run_test("get_dem(aoi, 'srtm')", get_dem, aoi, "srtm")
    if dem is not None:
        try:
            stats = dem.reduceRegion(ee.Reducer.min(), aoi, 500).getInfo()
            print(f"      -> elevation min: {stats}")
        except Exception as e:
            print(f"      -> reduceRegion failed: {e}")

    # get_dem (FABDEM) - may fail if sat-io not accessible
    run_test("get_dem(aoi, 'fabdem')", get_dem, aoi, "fabdem")

    # Open Buildings - force evaluation
    buildings = run_test("get_open_buildings_temporal(aoi, 2022)", get_open_buildings_temporal, aoi, 2022)
    if buildings is not None:
        try:
            names = buildings.bandNames().getInfo()
            print(f"      -> bands: {names}")
        except Exception as e:
            print(f"      -> bandNames failed: {e}")

    # Sentinel-2 composite - force evaluation (small scale)
    s2 = run_test(
        "get_sentinel2_composite(aoi, '2023-06-01', '2023-08-31')",
        get_sentinel2_composite,
        aoi,
        "2023-06-01",
        "2023-08-31",
    )
    if s2 is not None:
        try:
            names = s2.bandNames().getInfo()
            print(f"      -> bands (first 6): {names[:6] if len(names) >= 6 else names}")
        except Exception as e:
            print(f"      -> bandNames failed: {e}")

    # MODIS LST - force evaluation
    lst = run_test(
        "get_modis_lst_composite(aoi, '2023-06-01', '2023-08-31')",
        get_modis_lst_composite,
        aoi,
        "2023-06-01",
        "2023-08-31",
    )
    if lst is not None:
        try:
            stats = lst.reduceRegion(ee.Reducer.mean(), aoi, 1000).getInfo()
            print(f"      -> LST mean (raw): {stats}")
        except Exception as e:
            print(f"      -> reduceRegion failed: {e}")

    # Catalog listing (no GEE call)
    info = run_test("get_available_datasets()", get_available_datasets)
    if info:
        print(f"      -> {len(info)} datasets listed")

    # 3. Test utility.py integration (get_elevation_data, get_available_datasets)
    print("\nTesting utility.py integration (SolarMappingUtils)")
    try:
        from scripts.utility import SolarMappingUtils
    except ImportError:
        from utility import SolarMappingUtils

    utils = run_test("SolarMappingUtils(project_id)", SolarMappingUtils, project_id)
    if utils is not None:
        dem_util = run_test("utils.get_elevation_data(aoi)", utils.get_elevation_data, aoi)
        if dem_util is not None:
            try:
                stats = dem_util.reduceRegion(ee.Reducer.min(), aoi, 500).getInfo()
                print(f"      -> elevation min: {stats}")
            except Exception as e:
                print(f"      -> reduceRegion failed: {e}")
        run_test("utils.get_available_datasets()", utils.get_available_datasets)

    print("\n" + "=" * 50)
    print("Dataset verification finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
