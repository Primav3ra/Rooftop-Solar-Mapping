"""
Centralized GEE dataset loaders for the PV mapping pipeline.
All catalog IDs and band names are documented for reproducibility.
"""
from __future__ import annotations

import ee
from typing import Optional
from datetime import datetime


CATALOG = {
    "srtm_dem": "USGS/SRTMGL1_003",
    "fabdem": "projects/sat-io/open-datasets/FABDEM",
    "open_buildings_temporal": "GOOGLE/Research/open-buildings-temporal/v1",
    "open_buildings_vector": "GOOGLE/Research/open-buildings/v3/polygons",
    "sentinel2_sr": "COPERNICUS/S2_SR_HARMONIZED",
    "modis_lst": "MODIS/061/MOD11A2",
}


def get_dem(aoi: ee.Geometry, dem_type: str = "srtm") -> ee.Image:
    """Return elevation (metres) clipped to aoi. dem_type: 'srtm' or 'fabdem'."""
    if dem_type == "srtm":
        return ee.Image(CATALOG["srtm_dem"]).select("elevation").clip(aoi)
    if dem_type == "fabdem":
        return (
            ee.ImageCollection(CATALOG["fabdem"])
            .filterBounds(aoi)
            .mosaic()
            .select(0)
            .rename("elevation")
            .clip(aoi)
        )
    raise ValueError(f"dem_type must be 'srtm' or 'fabdem', got: {dem_type}")


def get_open_buildings_temporal(aoi: ee.Geometry, year: Optional[int] = None) -> ee.Image:
    """
    Open Buildings 2.5D Temporal mosaic clipped to aoi.
    Bands: building_presence, building_height, building_fractional_count.
    year: 2016-2023; defaults to latest available (2023).
    """
    col = ee.ImageCollection(CATALOG["open_buildings_temporal"]).filterBounds(aoi)
    if year is not None:
        start_ms = int(datetime(year, 1, 1).timestamp() * 1000)
        end_ms = int(datetime(year + 1, 1, 1).timestamp() * 1000)
        col = col.filter(
            ee.Filter.And(
                ee.Filter.gte("system:time_start", start_ms),
                ee.Filter.lt("system:time_start", end_ms),
            )
        )
    return (
        col.mosaic()
        .clip(aoi)
        .select(["building_presence", "building_height", "building_fractional_count"])
    )


def get_open_buildings_vector(
    aoi: ee.Geometry,
    confidence_threshold: float = 0.7,
) -> ee.FeatureCollection:
    """Open Buildings v3 polygons filtered to aoi and confidence >= threshold."""
    return (
        ee.FeatureCollection(CATALOG["open_buildings_vector"])
        .filterBounds(aoi)
        .filter(ee.Filter.gte("confidence", confidence_threshold))
    )


def get_sentinel2_composite(
    aoi: ee.Geometry,
    start_date: str,
    end_date: str,
) -> ee.Image:
    """
    Cloud-masked (QA60) median Sentinel-2 L2A composite clipped to aoi.
    Returns multiband surface reflectance for DBSI/NDVI computation.
    """
    def _mask(img: ee.Image) -> ee.Image:
        qa = img.select("QA60")
        return img.updateMask(
            qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
        )
    return (
        ee.ImageCollection(CATALOG["sentinel2_sr"])
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .map(_mask)
        .median()
        .clip(aoi)
    )


def get_modis_lst_composite(
    aoi: ee.Geometry,
    start_date: str,
    end_date: str,
    use_night: bool = True,
) -> ee.Image:
    """
    Median MODIS MOD11A2 Land Surface Temperature in Kelvin (scale 0.02).
    Convert to degC: (LST * 0.02) - 273.15.
    use_night=True (default) uses LST_Night_1km, else LST_Day_1km.
    """
    band = "LST_Night_1km" if use_night else "LST_Day_1km"
    return (
        ee.ImageCollection(CATALOG["modis_lst"])
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .select(band)
        .median()
        .clip(aoi)
        .rename("LST")
    )


def get_available_datasets() -> dict:
    """Dataset catalog metadata (IDs and purpose)."""
    return {
        "srtm_dem": {"id": CATALOG["srtm_dem"], "purpose": "30m global DEM"},
        "fabdem": {"id": CATALOG["fabdem"], "purpose": "30m bare-earth DEM, buildings/forest removed"},
        "open_buildings_temporal": {
            "id": CATALOG["open_buildings_temporal"],
            "purpose": "Building presence, height, fractional count; ~4m; 2016-2023",
        },
        "open_buildings_vector": {
            "id": CATALOG["open_buildings_vector"],
            "purpose": "Individual building footprint polygons with confidence scores",
        },
        "sentinel2_sr": {"id": CATALOG["sentinel2_sr"], "purpose": "Surface reflectance for DBSI, NDVI"},
        "modis_lst": {"id": CATALOG["modis_lst"], "purpose": "8-day LST for UHI (day/night)"},
    }
