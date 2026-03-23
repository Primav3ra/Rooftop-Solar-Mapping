"""
Baseline surface incoming shortwave from MERRA-2 reanalysis (hourly SWGDN).

Collection: NASA/GSFC/MERRA/rad/2, band SWGDN (W/m^2), hourly means.
Annual energy density (kWh/m^2/year): sum over all hours in interval of SWGDN/1000
per year-mean over inclusive [start_year, end_year].

Spatial resolution is coarse (~50-70 km); values are regional climatology, not rooftop-scale.
"""

from __future__ import annotations

import ee
from typing import Any, Dict, Optional
from datetime import date


MERRA_RAD_COLLECTION = "NASA/GSFC/MERRA/rad/2"
SWGDN_BAND = "SWGDN"


def _mean_over_aoi_with_fallback(
    image: ee.Image,
    band_name: str,
    aoi: ee.Geometry,
    scale_m: float,
) -> Dict[str, Any]:
    """
    Robust mean extractor for coarse datasets over small AOIs.
    Falls back from reduceRegion(mean) -> bestEffort -> centroid sample.
    """
    raw_primary = image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=scale_m,
        maxPixels=1e9,
        tileScale=2,
    ).getInfo()
    val = None if raw_primary is None else raw_primary.get(band_name)
    if val is not None:
        return {"value": float(val), "source": "reduceRegion", "raw": raw_primary}

    raw_best = image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=scale_m,
        bestEffort=True,
        maxPixels=1e9,
        tileScale=2,
    ).getInfo()
    val_best = None if raw_best is None else raw_best.get(band_name)
    if val_best is not None:
        return {"value": float(val_best), "source": "reduceRegion_bestEffort", "raw": raw_best}

    centroid = aoi.centroid(1)
    sample_fc = image.sample(
        region=centroid,
        scale=scale_m,
        numPixels=1,
        geometries=False,
    )
    sample = sample_fc.first().getInfo() if sample_fc.size().getInfo() > 0 else None
    if sample and "properties" in sample and band_name in sample["properties"]:
        return {
            "value": float(sample["properties"][band_name]),
            "source": "centroid_sample",
            "raw": {"sample": sample},
        }

    return {"value": 0.0, "source": "fallback_zero", "raw": {"primary": raw_primary, "best": raw_best}}


def merra2_mean_annual_sw_kwh_m2(
    aoi: ee.Geometry,
    start_year: int = 2015,
    end_year: int = 2019,
) -> ee.Image:
    """
    Mean annual surface incoming shortwave (all-sky) in kWh/m^2/year.

    For each hour: incremental energy ~ (SWGDN W/m^2) * 1 h = SWGDN/1000 kWh/m^2.
    Sums all hours from start_year-01-01 through end_year-12-31, divides by year count.
    """
    if end_year < start_year:
        raise ValueError("end_year must be >= start_year")

    start = ee.Date.fromYMD(start_year, 1, 1)
    end = ee.Date.fromYMD(end_year + 1, 1, 1)
    n_years = end_year - start_year + 1

    col = (
        ee.ImageCollection(MERRA_RAD_COLLECTION)
        .filterDate(start, end)
        .select(SWGDN_BAND)
    )

    total_kwh_m2 = col.sum().divide(1000.0)
    mean_annual = total_kwh_m2.divide(n_years).rename("annual_SWGDN_kWh_m2")
    # Do NOT clip to aoi here. MERRA pixels are ~50-70 km; clipping a small AOI
    # removes all pixel centers from the image, causing reduceRegion to return null.
    # The geometry= argument in reduceRegion already restricts the computation.
    return mean_annual


def reduce_mean_annual_sw_at_aoi(
    aoi: ee.Geometry,
    start_year: int = 2015,
    end_year: int = 2019,
    scale_m: float = 50_000.0,
    tile_scale: int = 2,
) -> ee.Dictionary:
    """Spatial mean of mean-annual kWh/m^2 image over AOI (MERRA-native scale is coarse)."""
    img = merra2_mean_annual_sw_kwh_m2(aoi, start_year, end_year)
    return img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=scale_m,
        maxPixels=1e9,
        tileScale=tile_scale,
    )


def get_merra_baseline_info(
    aoi: ee.Geometry,
    start_year: int = 2015,
    end_year: int = 2019,
    scale_m: float = 50_000.0,
) -> Dict[str, Any]:
    """Plain dict for API / run_analysis (calls getInfo once)."""
    img = merra2_mean_annual_sw_kwh_m2(aoi, start_year, end_year)
    mean_info = _mean_over_aoi_with_fallback(
        image=img,
        band_name="annual_SWGDN_kWh_m2",
        aoi=aoi,
        scale_m=scale_m,
    )
    return {
        "merra_mean_annual_sw_kwh_m2": mean_info["value"],
        "merra_start_year": start_year,
        "merra_end_year": end_year,
        "merra_collection": MERRA_RAD_COLLECTION,
        "merra_band": SWGDN_BAND,
        "reduce_scale_m": scale_m,
        "value_source": mean_info["source"],
        "reduce_region_raw": mean_info["raw"],
    }


def latest_complete_5y_range(today: Optional[date] = None) -> tuple[int, int]:
    """
    Return the latest complete 5-year range.
    Example: if today is in 2026, returns (2021, 2025).
    """
    if today is None:
        today = date.today()
    end_year = today.year - 1
    start_year = end_year - 4
    return start_year, end_year


def merra2_total_sw_kwh_m2_for_range(
    aoi: ee.Geometry,
    start_date: str,
    end_date_exclusive: str,
) -> ee.Image:
    """
    Total incoming shortwave energy over [start_date, end_date_exclusive) in kWh/m^2.
    """
    col = (
        ee.ImageCollection(MERRA_RAD_COLLECTION)
        .filterDate(start_date, end_date_exclusive)
        .select(SWGDN_BAND)
    )
    # Do NOT clip to aoi — same reason as merra2_mean_annual_sw_kwh_m2.
    return col.sum().divide(1000.0).rename("total_SWGDN_kWh_m2")


def get_merra_range_info(
    aoi: ee.Geometry,
    start_date: str,
    end_date_exclusive: str,
    scale_m: float = 50_000.0,
) -> Dict[str, Any]:
    """
    Baseline stats for an arbitrary date range (daily/monthly/custom possible).
    Returns period total and annualized values (kWh/m^2/year).
    """
    total_img = merra2_total_sw_kwh_m2_for_range(aoi, start_date, end_date_exclusive)
    mean_info = _mean_over_aoi_with_fallback(
        image=total_img,
        band_name="total_SWGDN_kWh_m2",
        aoi=aoi,
        scale_m=scale_m,
    )
    total_kwh_m2 = float(mean_info["value"])

    d0 = date.fromisoformat(start_date)
    d1 = date.fromisoformat(end_date_exclusive)
    days = max((d1 - d0).days, 1)
    annualized = total_kwh_m2 * (365.25 / days)

    return {
        "range_total_sw_kwh_m2": total_kwh_m2,
        "range_annualized_sw_kwh_m2_year": annualized,
        "range_start_date": start_date,
        "range_end_date_exclusive": end_date_exclusive,
        "range_days": days,
        "merra_collection": MERRA_RAD_COLLECTION,
        "merra_band": SWGDN_BAND,
        "reduce_scale_m": scale_m,
        "value_source": mean_info["source"],
        "reduce_region_raw": mean_info["raw"],
    }



def get_roof_masked_merra_baseline_info(
    aoi: ee.Geometry,
    roof_mask: ee.Image,
    start_year: int = 2020,
    end_year: int = 2024,
    scale_m: float = 50_000.0,
    roof_area_scale_m: float = 4.0,
) -> Dict[str, Any]:
    """
    Roof-masked MERRA-2 baseline: regional irradiance applied to candidate rooftop area.

    Two-scale method:
    - roof_area_m2: summed at 4m (Open Buildings resolution) -- spatially precise.
    - regional_irradiance_kwh_m2_year: MERRA-2 mean at ~50km -- one value for the whole AOI.
      MERRA is too coarse to vary within a neighbourhood; spatial variation comes from
      shadow/UHI penalties applied later.
    - pre_penalty_total_kwh_year: roof_area_m2 * regional_irradiance -- theoretical maximum
      before any shadow, soiling, or efficiency losses.

    Note: Option A (mean per m2) and Option B (total / area) are mathematically identical
    by construction at this stage. The meaningful comparison comes after penalties are applied.
    """
    baseline = merra2_mean_annual_sw_kwh_m2(aoi, start_year=start_year, end_year=end_year)

    # Step 1: total candidate rooftop area at fine scale (4m)
    roof_area_raw = (
        roof_mask.toFloat()
        .multiply(ee.Image.pixelArea())
        .rename("roof_area_m2")
        .reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=aoi,
            scale=roof_area_scale_m,
            maxPixels=1e9,
            tileScale=2,
        )
        .getInfo()
    )
    roof_area_m2 = (
        0.0
        if roof_area_raw is None or roof_area_raw.get("roof_area_m2") is None
        else float(roof_area_raw["roof_area_m2"])
    )

    # Step 2: regional irradiance at MERRA scale (one value covers the whole AOI)
    irr_info = _mean_over_aoi_with_fallback(
        image=baseline,
        band_name="annual_SWGDN_kWh_m2",
        aoi=aoi,
        scale_m=scale_m,
    )
    regional_irradiance = float(irr_info["value"])  # kWh/m2/year; 0.0 if fallback

    # Step 3: pre-penalty total energy on all candidate rooftops
    pre_penalty_total = regional_irradiance * roof_area_m2 if roof_area_m2 > 0 else 0.0

    return {
        # --- core outputs ---
        "roof_area_m2": roof_area_m2,
        "regional_irradiance_kwh_m2_year": regional_irradiance,
        "pre_penalty_total_kwh_year": pre_penalty_total,
        # --- provenance ---
        "merra_start_year": start_year,
        "merra_end_year": end_year,
        "merra_collection": MERRA_RAD_COLLECTION,
        "merra_band": SWGDN_BAND,
        "reduce_scale_m": scale_m,
        "roof_area_scale_m": roof_area_scale_m,
        "method": "two_scale_roof_area_x_merra_mean",
        "irradiance_source": irr_info["source"],
        # --- raw GEE outputs for debugging ---
        "roof_area_reduce_region_raw": roof_area_raw,
        "irradiance_reduce_region_raw": irr_info["raw"],
    }
