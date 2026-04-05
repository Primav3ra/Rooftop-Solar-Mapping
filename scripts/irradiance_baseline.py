"""
ERA5-Land hourly GHI baselines for the PV mapping pipeline.

Collection : ECMWF/ERA5_LAND/HOURLY
Band       : surface_solar_radiation_downwards_hourly (J/m^2 per hour)
Resolution : ~9 km (vs MERRA-2 ~50 km)

Unit conversion: J/m^2 per hour / 3,600,000 = kWh/m^2 per hour.
Sum all hourly steps over the accounting window -> kWh/m^2 for that window.
Divide by number of years -> mean annual kWh/m^2/year (yearly mode).
"""
from __future__ import annotations

import ee
from datetime import date
from typing import Any, Dict, Optional


ERA5_COLLECTION = "ECMWF/ERA5_LAND/HOURLY"
ERA5_BAND = "surface_solar_radiation_downwards_hourly"  # J/m^2 per hour
ERA5_SCALE_M = 11_132.0   # 0.1 deg at equator (~9 km native)
_J_TO_KWH = 3_600_000.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mean_over_aoi(image: ee.Image, band: str, aoi: ee.Geometry, scale: float) -> Dict[str, Any]:
    """
    Robust mean over aoi: reduceRegion -> bestEffort -> centroid sample.
    Never clip the image before calling -- clipping a small AOI on a coarse
    image removes pixel centres and causes reduceRegion to return null.
    """
    def _reduce(best_effort: bool):
        return image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=scale,
            maxPixels=1e9,
            tileScale=2,
            bestEffort=best_effort,
        ).getInfo()

    for be in (False, True):
        raw = _reduce(be)
        val = raw.get(band) if raw else None
        if val is not None:
            return {"value": float(val), "source": "reduceRegion_bestEffort" if be else "reduceRegion", "raw": raw}

    centroid = aoi.centroid(1)
    fc = image.sample(region=centroid, scale=scale, numPixels=1, geometries=False)
    s = fc.first().getInfo() if fc.size().getInfo() > 0 else None
    if s and "properties" in s and band in s["properties"]:
        return {"value": float(s["properties"][band]), "source": "centroid_sample", "raw": s}

    return {"value": 0.0, "source": "fallback_zero", "raw": None}


def _era5_total(start_date: str, end_date_exclusive: str) -> ee.Image:
    return (
        ee.ImageCollection(ERA5_COLLECTION)
        .filterDate(start_date, end_date_exclusive)
        .select(ERA5_BAND)
        .sum()
        .divide(_J_TO_KWH)
        .rename("total_GHI_kWh_m2")
    )


# ---------------------------------------------------------------------------
# Public: yearly baseline
# ---------------------------------------------------------------------------

def era5_mean_annual_ghi_kwh_m2(
    aoi: ee.Geometry,
    start_year: int = 2020,
    end_year: int = 2024,
) -> ee.Image:
    """Mean annual GHI (kWh/m^2/year) from ERA5-Land over [start_year, end_year]. Band: annual_GHI_kWh_m2."""
    if end_year < start_year:
        raise ValueError("end_year must be >= start_year")
    n = end_year - start_year + 1
    total = _era5_total(f"{start_year}-01-01", f"{end_year + 1}-01-01")
    return total.divide(n).rename("annual_GHI_kWh_m2")


def get_era5_baseline_info(
    aoi: ee.Geometry,
    start_year: int = 2020,
    end_year: int = 2024,
    scale_m: float = ERA5_SCALE_M,
) -> Dict[str, Any]:
    """Mean annual GHI stats dict for API / utility."""
    r = _mean_over_aoi(era5_mean_annual_ghi_kwh_m2(aoi, start_year, end_year), "annual_GHI_kWh_m2", aoi, scale_m)
    return {
        "mean_annual_ghi_kwh_m2_year": r["value"],
        "start_year": start_year, "end_year": end_year,
        "collection": ERA5_COLLECTION, "band": ERA5_BAND,
        "reduce_scale_m": scale_m,
        "value_source": r["source"], "reduce_region_raw": r["raw"],
    }


# ---------------------------------------------------------------------------
# Public: arbitrary date-range baseline
# ---------------------------------------------------------------------------

def era5_total_ghi_kwh_m2_for_range(
    aoi: ee.Geometry,
    start_date: str,
    end_date_exclusive: str,
) -> ee.Image:
    """Total GHI (kWh/m^2) over [start_date, end_date_exclusive). Band: total_GHI_kWh_m2."""
    return _era5_total(start_date, end_date_exclusive)


def get_era5_range_info(
    aoi: ee.Geometry,
    start_date: str,
    end_date_exclusive: str,
    scale_m: float = ERA5_SCALE_M,
) -> Dict[str, Any]:
    """Period-total and annualised ERA5 GHI stats for an arbitrary date window."""
    r = _mean_over_aoi(_era5_total(start_date, end_date_exclusive), "total_GHI_kWh_m2", aoi, scale_m)
    total = float(r["value"])
    days = max((date.fromisoformat(end_date_exclusive) - date.fromisoformat(start_date)).days, 1)
    return {
        "range_total_ghi_kwh_m2": total,
        "range_annualized_ghi_kwh_m2_year": total * (365.25 / days),
        "range_start_date": start_date, "range_end_date_exclusive": end_date_exclusive,
        "range_days": days,
        "collection": ERA5_COLLECTION, "band": ERA5_BAND,
        "reduce_scale_m": scale_m,
        "value_source": r["source"], "reduce_region_raw": r["raw"],
    }


# ---------------------------------------------------------------------------
# Public: point sampling for /api/yield (centroid, period)
# ---------------------------------------------------------------------------

def sample_era5_period_ghi_kwh_m2_at_point(
    point: ee.Geometry,
    start_date: str,
    end_date_exclusive: str,
    scale_m: float = ERA5_SCALE_M,
) -> Dict[str, Any]:
    """Period-integrated GHI (kWh/m^2) at a point (AOI centroid). Used by /api/yield."""
    img = _era5_total(start_date, end_date_exclusive)
    fc = img.sample(region=point, scale=scale_m, numPixels=1, geometries=False)
    if fc.size().getInfo() == 0:
        return {"value": 0.0, "source": "no_sample", "raw": None}
    s = fc.first().getInfo()
    val = (s.get("properties") or {}).get("total_GHI_kWh_m2") if s else None
    if val is None:
        return {"value": 0.0, "source": "null_band", "raw": s}
    return {"value": float(val), "source": "centroid_sample", "raw": s}


# ---------------------------------------------------------------------------
# Public: roof-masked baselines
# ---------------------------------------------------------------------------

def _compute_roof_area_m2(roof_mask: ee.Image, aoi: ee.Geometry, scale: float = 4.0) -> float:
    raw = (
        roof_mask.toFloat()
        .multiply(ee.Image.pixelArea())
        .rename("roof_area_m2")
        .reduceRegion(reducer=ee.Reducer.sum(), geometry=aoi, scale=scale, maxPixels=1e9, tileScale=2)
        .getInfo()
    )
    return 0.0 if (raw is None or raw.get("roof_area_m2") is None) else float(raw["roof_area_m2"])


def get_roof_masked_era5_baseline_info(
    aoi: ee.Geometry,
    roof_mask: ee.Image,
    start_year: int = 2020,
    end_year: int = 2024,
    scale_m: float = ERA5_SCALE_M,
    roof_area_scale_m: float = 4.0,
) -> Dict[str, Any]:
    """Roof area x regional ERA5 annual GHI -> pre-penalty total (yearly mode)."""
    roof_area = _compute_roof_area_m2(roof_mask, aoi, roof_area_scale_m)
    r = _mean_over_aoi(era5_mean_annual_ghi_kwh_m2(aoi, start_year, end_year), "annual_GHI_kWh_m2", aoi, scale_m)
    irr = float(r["value"])
    return {
        "roof_area_m2": roof_area,
        "regional_irradiance_kwh_m2_year": irr,
        "pre_penalty_total_kwh_year": irr * roof_area if roof_area > 0 else 0.0,
        "start_year": start_year, "end_year": end_year,
        "collection": ERA5_COLLECTION, "band": ERA5_BAND,
        "reduce_scale_m": scale_m, "roof_area_scale_m": roof_area_scale_m,
        "method": "two_scale_roof_area_x_era5_annual",
        "irradiance_source": r["source"],
    }


def get_roof_masked_era5_baseline_for_date_range(
    aoi: ee.Geometry,
    roof_mask: ee.Image,
    start_date: str,
    end_date_exclusive: str,
    scale_m: float = ERA5_SCALE_M,
    roof_area_scale_m: float = 4.0,
) -> Dict[str, Any]:
    """Roof area x period ERA5 GHI -> pre-penalty totals (quarterly / daily mode)."""
    range_info = get_era5_range_info(aoi, start_date, end_date_exclusive, scale_m)
    roof_area = _compute_roof_area_m2(roof_mask, aoi, roof_area_scale_m)
    period_total = float(range_info["range_total_ghi_kwh_m2"])
    annualized = float(range_info["range_annualized_ghi_kwh_m2_year"])
    return {
        "roof_area_m2": roof_area,
        "regional_irradiance_kwh_m2_year": annualized,
        "period_ghi_kwh_m2": period_total,
        "pre_penalty_total_kwh_year": annualized * roof_area if roof_area > 0 else 0.0,
        "pre_penalty_total_kwh_period": period_total * roof_area if roof_area > 0 else 0.0,
        "range_start_date": start_date, "range_end_date_exclusive": end_date_exclusive,
        "range_days": range_info["range_days"],
        "collection": ERA5_COLLECTION, "band": ERA5_BAND,
        "reduce_scale_m": scale_m, "roof_area_scale_m": roof_area_scale_m,
        "method": "two_scale_roof_area_x_era5_range_annualized",
        "irradiance_source": range_info["value_source"],
    }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def latest_complete_5y_range(today: Optional[date] = None) -> tuple[int, int]:
    """Latest complete 5-year range, e.g. (2021, 2025) if today is 2026."""
    if today is None:
        today = date.today()
    end = today.year - 1
    return end - 4, end
