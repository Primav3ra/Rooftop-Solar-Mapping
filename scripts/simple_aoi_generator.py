#!/usr/bin/env python3
"""
Simple AOI GeoJSON Generator (without Earth Engine dependency)
Generates master AOI file with all cities
"""

import json
import os
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional

class CityTier(Enum):
    TIER_1 = "Tier 1"
    TIER_2 = "Tier 2" 
    TIER_3 = "Tier 3"

@dataclass
class CityAOI:
    name: str
    tier: CityTier
    coordinates: List[List[float]]
    description: str
    population: Optional[int] = None
    state: Optional[str] = None
    area_km2: Optional[float] = None

def get_cities_data() -> Dict[str, CityAOI]:
    """Get all city definitions"""
    return {
        # TIER 1 CITIES (Metro cities)
        "delhi": CityAOI(
            name="Delhi",
            tier=CityTier.TIER_1,
            coordinates=[
                [77.0, 28.4], [77.4, 28.4], [77.4, 28.8], [77.0, 28.8], [77.0, 28.4]
            ],
            description="National Capital Region - Central Delhi",
            population=32000000,
            state="Delhi",
            area_km2=1484
        ),
        "mumbai": CityAOI(
            name="Mumbai",
            tier=CityTier.TIER_1,
            coordinates=[
                [72.7, 18.8], [73.0, 18.8], [73.0, 19.3], [72.7, 19.3], [72.7, 18.8]
            ],
            description="Financial capital of India",
            population=20000000,
            state="Maharashtra",
            area_km2=603
        ),
        "bangalore": CityAOI(
            name="Bangalore",
            tier=CityTier.TIER_1,
            coordinates=[
                [77.4, 12.8], [77.8, 12.8], [77.8, 13.2], [77.4, 13.2], [77.4, 12.8]
            ],
            description="Silicon Valley of India",
            population=12000000,
            state="Karnataka",
            area_km2=741
        ),
        "chennai": CityAOI(
            name="Chennai",
            tier=CityTier.TIER_1,
            coordinates=[
                [80.0, 12.8], [80.4, 12.8], [80.4, 13.2], [80.0, 13.2], [80.0, 12.8]
            ],
            description="Gateway to South India",
            population=11000000,
            state="Tamil Nadu",
            area_km2=426
        ),
        "kolkata": CityAOI(
            name="Kolkata",
            tier=CityTier.TIER_1,
            coordinates=[
                [88.2, 22.4], [88.6, 22.4], [88.6, 22.8], [88.2, 22.8], [88.2, 22.4]
            ],
            description="Cultural capital of India",
            population=15000000,
            state="West Bengal",
            area_km2=205
        ),
        "hyderabad": CityAOI(
            name="Hyderabad",
            tier=CityTier.TIER_1,
            coordinates=[
                [78.2, 17.2], [78.6, 17.2], [78.6, 17.6], [78.2, 17.6], [78.2, 17.2]
            ],
            description="City of Pearls",
            population=10000000,
            state="Telangana",
            area_km2=650
        ),
        
        # TIER 2 CITIES (State capitals and major cities)
        "jaipur": CityAOI(
            name="Jaipur",
            tier=CityTier.TIER_2,
            coordinates=[
                [75.6, 26.6], [76.0, 26.6], [76.0, 27.0], [75.6, 27.0], [75.6, 26.6]
            ],
            description="Pink City - Capital of Rajasthan",
            population=4000000,
            state="Rajasthan",
            area_km2=467
        ),
        "ahmedabad": CityAOI(
            name="Ahmedabad",
            tier=CityTier.TIER_2,
            coordinates=[
                [72.4, 23.0], [72.8, 23.0], [72.8, 23.4], [72.4, 23.4], [72.4, 23.0]
            ],
            description="Manchester of India",
            population=8000000,
            state="Gujarat",
            area_km2=464
        ),
        "pune": CityAOI(
            name="Pune",
            tier=CityTier.TIER_2,
            coordinates=[
                [73.6, 18.4], [74.0, 18.4], [74.0, 18.8], [73.6, 18.8], [73.6, 18.4]
            ],
            description="Oxford of the East",
            population=7000000,
            state="Maharashtra",
            area_km2=331
        ),
        "kochi": CityAOI(
            name="Kochi",
            tier=CityTier.TIER_2,
            coordinates=[
                [76.0, 9.8], [76.4, 9.8], [76.4, 10.2], [76.0, 10.2], [76.0, 9.8]
            ],
            description="Queen of Arabian Sea",
            population=2000000,
            state="Kerala",
            area_km2=95
        ),
        "chandigarh": CityAOI(
            name="Chandigarh",
            tier=CityTier.TIER_2,
            coordinates=[
                [76.6, 30.6], [77.0, 30.6], [77.0, 31.0], [76.6, 31.0], [76.6, 30.6]
            ],
            description="City Beautiful - Planned city",
            population=1200000,
            state="Chandigarh",
            area_km2=114
        ),
        
        # TIER 3 CITIES (Emerging cities)
        "indore": CityAOI(
            name="Indore",
            tier=CityTier.TIER_3,
            coordinates=[
                [75.6, 22.6], [76.0, 22.6], [76.0, 23.0], [75.6, 23.0], [75.6, 22.6]
            ],
            description="Commercial capital of Madhya Pradesh",
            population=3000000,
            state="Madhya Pradesh",
            area_km2=530
        ),
        "bhopal": CityAOI(
            name="Bhopal",
            tier=CityTier.TIER_3,
            coordinates=[
                [77.2, 23.0], [77.6, 23.0], [77.6, 23.4], [77.2, 23.4], [77.2, 23.0]
            ],
            description="City of Lakes",
            population=2000000,
            state="Madhya Pradesh",
            area_km2=285
        ),
        "coimbatore": CityAOI(
            name="Coimbatore",
            tier=CityTier.TIER_3,
            coordinates=[
                [76.8, 10.8], [77.2, 10.8], [77.2, 11.2], [76.8, 11.2], [76.8, 10.8]
            ],
            description="Manchester of South India",
            population=2000000,
            state="Tamil Nadu",
            area_km2=246
        ),
        "vadodara": CityAOI(
            name="Vadodara",
            tier=CityTier.TIER_3,
            coordinates=[
                [73.0, 22.2], [73.4, 22.2], [73.4, 22.6], [73.0, 22.6], [73.0, 22.2]
            ],
            description="Cultural capital of Gujarat",
            population=2000000,
            state="Gujarat",
            area_km2=235
        )
    }

def generate_master_aoi():
    """Generate master AOI GeoJSON with all cities"""
    print("🗺️  Generating master AOI GeoJSON...")
    
    cities = get_cities_data()
    
    # Create master GeoJSON structure
    master_geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    
    # Add all cities to the master file
    for city_name, city in cities.items():
        feature = {
            "type": "Feature",
            "properties": {
                "name": city.name,
                "tier": city.tier.value,
                "description": city.description,
                "population": city.population,
                "state": city.state,
                "area_km2": city.area_km2,
                "city_key": city_name
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [city.coordinates]
            }
        }
        master_geojson["features"].append(feature)
    
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    # Save to master AOI file
    with open('data/aoi.geojson', 'w') as f:
        json.dump(master_geojson, f, indent=2)
    
    print(f"✅ Master AOI GeoJSON created with {len(master_geojson['features'])} cities")
    print("📁 Saved to: data/aoi.geojson")
    
    return master_geojson

def generate_individual_city_files():
    """Generate individual AOI files for each city in organized folders"""
    print("\n🏙️  Generating individual city AOI files...")
    
    cities = get_cities_data()
    
    # Ensure cities directory exists
    os.makedirs('data/aoi/cities', exist_ok=True)
    
    for city_name, city in cities.items():
        city_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "name": city.name,
                        "tier": city.tier.value,
                        "description": city.description,
                        "population": city.population,
                        "state": city.state,
                        "area_km2": city.area_km2,
                        "city_key": city_name
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [city.coordinates]
                    }
                }
            ]
        }
        
        filename = f'data/aoi/cities/{city_name}.geojson'
        with open(filename, 'w') as f:
            json.dump(city_geojson, f, indent=2)
        
        print(f"✅ Created: {filename}")
    
    print(f"✅ Individual city files created for {len(cities)} cities")

def generate_tier_files():
    """Generate AOI files grouped by tier"""
    print("\n📊 Generating tier-based AOI files...")
    
    cities = get_cities_data()
    
    # Ensure tiers directory exists
    os.makedirs('data/aoi/tiers', exist_ok=True)
    
    for tier in CityTier:
        cities_in_tier = [city for city in cities.values() if city.tier == tier]
        
        tier_geojson = {
            "type": "FeatureCollection",
            "features": []
        }
        
        for city in cities_in_tier:
            feature = {
                "type": "Feature",
                "properties": {
                    "name": city.name,
                    "tier": city.tier.value,
                    "description": city.description,
                    "population": city.population,
                    "state": city.state,
                    "area_km2": city.area_km2,
                    "region": f"tier_{tier.value.lower().replace(' ', '_')}"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [city.coordinates]
                }
            }
            tier_geojson["features"].append(feature)
        
        filename = f'data/aoi/tiers/{tier.value.lower().replace(" ", "_")}.geojson'
        with open(filename, 'w') as f:
            json.dump(tier_geojson, f, indent=2)
        
        print(f"✅ Created: {filename} ({len(cities_in_tier)} cities)")

def generate_regional_files():
    """Generate AOI files grouped by region"""
    print("\n🌍 Generating regional AOI files...")
    
    cities = get_cities_data()
    
    # Define regions
    regions = {
        "north": ["delhi", "chandigarh", "jaipur"],
        "south": ["bangalore", "chennai", "kochi", "coimbatore"],
        "west": ["mumbai", "pune", "ahmedabad", "vadodara"],
        "east": ["kolkata"],
        "central": ["hyderabad", "indore", "bhopal"]
    }
    
    # Ensure regions directory exists
    os.makedirs('data/aoi/regions', exist_ok=True)
    
    for region_name, city_names in regions.items():
        cities_in_region = [cities[name] for name in city_names if name in cities]
        
        regional_geojson = {
            "type": "FeatureCollection",
            "features": []
        }
        
        for city in cities_in_region:
            feature = {
                "type": "Feature",
                "properties": {
                    "name": city.name,
                    "tier": city.tier.value,
                    "description": city.description,
                    "population": city.population,
                    "state": city.state,
                    "area_km2": city.area_km2,
                    "region": region_name
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [city.coordinates]
                }
            }
            regional_geojson["features"].append(feature)
        
        filename = f'data/aoi/regions/{region_name}.geojson'
        with open(filename, 'w') as f:
            json.dump(regional_geojson, f, indent=2)
        
        print(f"✅ Created: {filename} ({len(cities_in_region)} cities)")

def main():
    """Main function to generate organized AOI files"""
    print("🚀 Starting Organized AOI Generation")
    print("=" * 50)
    
    try:
        # Generate master AOI
        master_geojson = generate_master_aoi()
        
        # Generate individual city files
        generate_individual_city_files()
        
        # Generate tier-based files
        generate_tier_files()
        
        # Generate regional files
        generate_regional_files()
        
        print("\n🎉 All organized AOI files generated successfully!")
        print(f"📊 Total cities: {len(master_geojson['features'])}")
        
        # Show summary by tier
        tier_counts = {}
        for feature in master_geojson['features']:
            tier = feature['properties']['tier']
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        
        print("\n📈 Cities by tier:")
        for tier, count in tier_counts.items():
            print(f"  • {tier}: {count} cities")
        
        print("\n📁 Generated files:")
        print("  • data/aoi.geojson (Master file)")
        print("  • data/aoi/cities/ (Individual city files)")
        print("  • data/aoi/tiers/ (Tier-based files)")
        print("  • data/aoi/regions/ (Regional files)")
        
    except Exception as e:
        print(f"❌ Error generating AOI files: {str(e)}")
        raise

if __name__ == "__main__":
    main()
