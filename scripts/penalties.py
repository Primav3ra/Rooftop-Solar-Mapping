"""
Penalty layers applied to the MERRA-2 baseline irradiance at 4m resolution.

Pipeline:
  baseline_irradiance (MERRA, uniform over AOI)
  x shadow_retention_fraction  (1 - shadow_fraction, from 2.5D building heights)
  = net_irradiance_kwh_m2_year  (spatially varying, per pixel)

Shadow model (simplified 2.5D):
  For a given solar geometry (altitude, azimuth), a building of height H casts a shadow
  of length L = H / tan(solar_altitude) in the direction opposite to the azimuth.
  We approximate the annual shadow frequency by sampling several representative solar
  positions (morning, noon, afternoon) across seasons and averaging the shadow mask.

This is a first-order approximation. A full hourly integration would be more accurate
but is too expensive for interactive GEE queries.
"""

from __future__ import annotations

import math
import ee
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Representative solar positions for Delhi (~28.6 N) across seasons
# Each entry: (solar_altitude_deg, solar_azimuth_deg_from_north)
# Chosen to represent morning/noon/afternoon in summer, winter, monsoon.
# ---------------------------------------------------------------------------
DELHI_SOLAR_POSITIONS: List[Tuple[float, float]] = [
    # Summer (May): high sun
    (30.0, 90.0),   # morning
    (82.0, 180.0),  # solar noon (near-overhead)
    (30.0, 270.0),  # afternoon
    # Winter (December): low sun
    (15.0, 120.0),  # morning
    (38.0, 180.0),  # solar noon
    (15.0, 240.0),  # afternoon
    # Equinox (March/September): mid sun
    (22.0, 90.0),
    (62.0, 180.0),
    (22.0, 270.0),
]


def _shadow_mask_for_solar_position(
    building_height: ee.Image,
    solar_altitude_deg: float,
    solar_azimuth_deg: float,
    pixel_size_m: float = 4.0,
) -> ee.Image:
    """
    Binary shadow mask (1 = in shadow, 0 = sunlit) for one solar position.

    Correct model:
      A pixel at location P is in shadow if a neighbouring building at location Q
      casts a shadow that reaches P. The shadow from Q reaches P when:
        distance(Q->P) <= building_height(Q) / tan(solar_altitude)
        and the direction Q->P matches the shadow direction.

    Implementation via translate:
      Shift the height image in the SHADOW direction (opposite to sun) by the
      shadow length for a 1m building. The shifted image at pixel P now contains
      the height of the building that would cast a shadow of exactly that length
      onto P. A pixel is shadowed if that shifted height EXCEEDS the pixel's own
      height (a taller neighbour's shadow reaches this pixel from above).

    This correctly handles:
      - Rooftop pixels: only shadowed if a TALLER adjacent building overshadows them.
      - Ground pixels: shadowed if any building's shadow reaches them.
      - Self-shadowing: a building cannot shadow its own rooftop.
    """
    alt_rad = math.radians(max(solar_altitude_deg, 1.0))
    shadow_length_per_m = 1.0 / math.tan(alt_rad)  # shadow length (m) per 1m of height

    # Shadow falls in the direction OPPOSITE to the sun azimuth
    shadow_az_rad = math.radians(solar_azimuth_deg + 180.0)
    dx_per_m_height = math.sin(shadow_az_rad) * shadow_length_per_m / pixel_size_m
    dy_per_m_height = math.cos(shadow_az_rad) * shadow_length_per_m / pixel_size_m

    # Translate the height image: pixel P receives the height of the building
    # that would cast its shadow tip exactly at P for this solar position.
    # We use the shadow length for a representative building height (mean ~10m for Delhi).
    # For a proper model we'd integrate over all heights, but this is a good approximation.
    REPRESENTATIVE_HEIGHT_M = 10.0
    dx_pixels = dx_per_m_height * REPRESENTATIVE_HEIGHT_M
    dy_pixels = dy_per_m_height * REPRESENTATIVE_HEIGHT_M

    neighbour_height_at_p = building_height.translate(dx_pixels, dy_pixels)

    # A pixel is in shadow if the neighbour casting the shadow is TALLER than this pixel.
    # This prevents a building from shadowing its own rooftop.
    in_shadow = neighbour_height_at_p.gt(building_height).rename("in_shadow")
    return in_shadow.toUint8()


def shadow_frequency_image(
    building_height: ee.Image,
    solar_positions: Optional[List[Tuple[float, float]]] = None,
    pixel_size_m: float = 4.0,
) -> ee.Image:
    """
    Mean shadow frequency across representative solar positions (0 to 1).

    0 = never shadowed across sampled positions (fully sunlit).
    1 = always shadowed across sampled positions.

    Parameters
    ----------
    building_height : ee.Image
        Band 'building_height' in metres.
    solar_positions : list of (altitude_deg, azimuth_deg), optional
        Defaults to DELHI_SOLAR_POSITIONS.
    pixel_size_m : float
        Native pixel size (~4m for Open Buildings).

    Returns
    -------
    ee.Image
        Single band 'shadow_frequency', float [0, 1].
    """
    if solar_positions is None:
        solar_positions = DELHI_SOLAR_POSITIONS

    shadow_images = [
        _shadow_mask_for_solar_position(building_height, alt, az, pixel_size_m).toFloat()
        for alt, az in solar_positions
    ]
    shadow_stack = ee.ImageCollection(shadow_images)
    return shadow_stack.mean().rename("shadow_frequency")


def shadow_retention_fraction(
    building_height: ee.Image,
    solar_positions: Optional[List[Tuple[float, float]]] = None,
    pixel_size_m: float = 4.0,
) -> ee.Image:
    """
    Fraction of irradiance retained after shadow penalty (1 - shadow_frequency).

    1.0 = fully sunlit, 0.0 = always shadowed.
    Multiply baseline irradiance by this to get shadow-adjusted irradiance.
    """
    freq = shadow_frequency_image(building_height, solar_positions, pixel_size_m)
    return ee.Image(1.0).subtract(freq).rename("shadow_retention")


def net_irradiance_image(
    baseline_kwh_m2_year: float,
    shadow_retention: ee.Image,
) -> ee.Image:
    """
    Per-pixel net irradiance after shadow penalty.

    Parameters
    ----------
    baseline_kwh_m2_year : float
        Regional MERRA-2 mean annual irradiance (uniform scalar).
    shadow_retention : ee.Image
        Band 'shadow_retention' [0, 1] from shadow_retention_fraction().

    Returns
    -------
    ee.Image
        Band 'net_irradiance_kwh_m2_year', spatially varying.
    """
    return (
        shadow_retention
        .multiply(baseline_kwh_m2_year)
        .rename("net_irradiance_kwh_m2_year")
    )


def per_building_yield(
    net_irradiance: ee.Image,
    roof_mask: ee.Image,
    aoi: ee.Geometry,
    buildings_fc: ee.FeatureCollection,
    panel_efficiency: float = 0.18,
    performance_ratio: float = 0.80,
    scale_m: float = 4.0,
) -> ee.FeatureCollection:
    """
    Annual PV yield per building footprint (kWh/year).

    For each building polygon in buildings_fc:
      yield = sum(net_irradiance * roof_mask * pixelArea) * efficiency * PR

    Parameters
    ----------
    net_irradiance : ee.Image
        Band 'net_irradiance_kwh_m2_year' from net_irradiance_image().
    roof_mask : ee.Image
        Binary roof candidate mask (band 'roof_candidate').
    aoi : ee.Geometry
        AOI polygon (used to clip buildings_fc).
    buildings_fc : ee.FeatureCollection
        Building footprint polygons (e.g. from Open Buildings vector layer).
    panel_efficiency : float
        PV panel efficiency (default 18%).
    performance_ratio : float
        System performance ratio accounting for inverter, wiring, temp losses (default 80%).
    scale_m : float
        Reduce scale in metres (should match roof_mask resolution, ~4m).

    Returns
    -------
    ee.FeatureCollection
        Same features with added properties:
          roof_area_m2, net_irradiance_kwh_m2_year (mean), annual_yield_kwh
    """
    energy_img = (
        net_irradiance
        .multiply(roof_mask.toFloat())
        .multiply(ee.Image.pixelArea())
        .rename("energy_kwh_pixel")
    )

    def add_yield(feature: ee.Feature) -> ee.Feature:
        geom = feature.geometry()
        stats = energy_img.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geom,
            scale=scale_m,
            maxPixels=1e7,
        )
        total_energy_kwh = ee.Number(stats.get("energy_kwh_pixel")).multiply(
            panel_efficiency * performance_ratio
        )
        roof_area = (
            roof_mask.toFloat()
            .multiply(ee.Image.pixelArea())
            .reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=geom,
                scale=scale_m,
                maxPixels=1e7,
            )
            .get("roof_candidate")
        )
        irr_mean = (
            net_irradiance.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geom,
                scale=scale_m,
                maxPixels=1e7,
            )
            .get("net_irradiance_kwh_m2_year")
        )
        return feature.set({
            "roof_area_m2": roof_area,
            "net_irradiance_kwh_m2_year": irr_mean,
            "annual_yield_kwh": total_energy_kwh,
        })

    return buildings_fc.filterBounds(aoi).map(add_yield)


def get_shadow_stats(
    aoi: ee.Geometry,
    building_height: ee.Image,
    solar_positions: Optional[List[Tuple[float, float]]] = None,
    scale_m: float = 4.0,
) -> Dict[str, Any]:
    """
    Aggregate shadow statistics over the AOI: mean shadow frequency and retention.

    Returns a plain Python dict (calls getInfo).
    """
    retention = shadow_retention_fraction(building_height, solar_positions, scale_m)
    raw = retention.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=scale_m,
        maxPixels=1e9,
        tileScale=4,
    ).getInfo()
    mean_retention = raw.get("shadow_retention") if raw else None
    mean_shadow = (1.0 - mean_retention) if mean_retention is not None else None
    return {
        "mean_shadow_frequency": mean_shadow,
        "mean_shadow_retention": mean_retention,
        "n_solar_positions": len(solar_positions or DELHI_SOLAR_POSITIONS),
        "reduce_scale_m": scale_m,
        "reduce_region_raw": raw,
    }
