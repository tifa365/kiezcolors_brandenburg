#!/usr/bin/env python3
"""
Download Brandenburg ALKIS data and generate vector tiles.

Usage:
    uv run scripts/make-tiles-bb.py

Requirements (handled by uv):
    requests, shapely, geojson
"""
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "shapely",
#     "geojson",
# ]
# ///

import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

# Brandenburg WFS endpoint
WFS_URL = "https://isk.geobasis-bb.de/ows/alkis_vereinf_wfs"

# Brandenburg bounding box (EPSG:4326)
BB_BBOX = {
    "minx": 11.2,
    "miny": 51.35,
    "maxx": 14.77,
    "maxy": 53.56,
}

# Grid size for chunked downloads (degrees)
GRID_SIZE = 0.5

# Output paths
DATA_DIR = Path(__file__).parent.parent / "data"
TILES_DIR = Path(__file__).parent.parent / "static" / "tiles"
OUTPUT_GEOJSON = DATA_DIR / "alkis_bb.geojson"


def get_features_for_bbox(minx: float, miny: float, maxx: float, maxy: float) -> list:
    """Fetch features from WFS for a given bounding box."""
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": "ave:Nutzung",
        "OUTPUTFORMAT": "application/json",
        "SRSNAME": "EPSG:4326",
        "BBOX": f"{miny},{minx},{maxy},{maxx},EPSG:4326",
        "COUNT": "100000",
    }

    url = f"{WFS_URL}?{urlencode(params)}"
    print(f"  Fetching bbox ({minx:.2f}, {miny:.2f}, {maxx:.2f}, {maxy:.2f})...")

    try:
        response = requests.get(url, timeout=300)
        response.raise_for_status()
        data = response.json()
        features = data.get("features", [])
        print(f"    → {len(features)} features")
        return features
    except requests.RequestException as e:
        print(f"    ⚠ Error: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"    ⚠ JSON decode error: {e}")
        return []


def download_all_features() -> list:
    """Download all features using a grid-based approach."""
    all_features = []
    seen_ids = set()

    x = BB_BBOX["minx"]
    while x < BB_BBOX["maxx"]:
        y = BB_BBOX["miny"]
        while y < BB_BBOX["maxy"]:
            features = get_features_for_bbox(
                x, y, min(x + GRID_SIZE, BB_BBOX["maxx"]), min(y + GRID_SIZE, BB_BBOX["maxy"])
            )

            for f in features:
                fid = f.get("id") or f.get("properties", {}).get("gml_id")
                if fid and fid not in seen_ids:
                    seen_ids.add(fid)
                    all_features.append(f)

            y += GRID_SIZE
        x += GRID_SIZE

    print(f"\nTotal unique features: {len(all_features)}")
    return all_features


def transform_features(features: list) -> list:
    """Transform features to match Kiezcolors schema (nutzart → bezeich)."""
    transformed = []

    for f in features:
        props = f.get("properties", {})
        nutzart = props.get("nutzart", "")

        # Map Brandenburg nutzart to Berlin-style bezeich
        bezeich = map_nutzart_to_bezeich(nutzart)

        if bezeich:
            new_feature = {
                "type": "Feature",
                "properties": {"bezeich": bezeich},
                "geometry": f.get("geometry"),
            }
            transformed.append(new_feature)

    return transformed


def map_nutzart_to_bezeich(nutzart: str) -> str | None:
    """Map Brandenburg nutzart values to Berlin ALKIS bezeich values."""
    mapping = {
        # Wohnen
        "Wohnbaufläche": "AX_Wohnbauflaeche",
        # Industrie/Gewerbe
        "Industrie- und Gewerbefläche": "AX_IndustrieUndGewerbeflaeche",
        # Gemischte Nutzung
        "Fläche gemischter Nutzung": "AX_FlaecheGemischterNutzung",
        # Besondere funktionale Prägung
        "Fläche besonderer funktionaler Prägung": "AX_FlaecheBesondererFunktionalerPraegung",
        # Sport/Freizeit
        "Sport-, Freizeit- und Erholungsfläche": "AX_SportFreizeitUndErholungsflaeche",
        # Verkehr
        "Straßenverkehr": "AX_Strassenverkehr",
        "Weg": "AX_Weg",
        "Platz": "AX_Platz",
        "Bahnverkehr": "AX_Bahnverkehr",
        "Flugverkehr": "AX_Flugverkehr",
        "Schiffsverkehr": "AX_Schiffsverkehr",
        # Natur
        "Wald": "AX_Wald",
        "Gehölz": "AX_Gehoelz",
        "Heide": "AX_Heide",
        "Moor": "AX_Moor",
        "Sumpf": "AX_Sumpf",
        "Landwirtschaft": "AX_Landwirtschaft",
        "Unland/Vegetationslose Fläche": "AX_UnlandVegetationsloseFlaeche",
        "Friedhof": "AX_Friedhof",
        # Wasser
        "Fließgewässer": "AX_Fliessgewaesser",
        "Stehendes Gewässer": "AX_StehendesGewaesser",
        "Hafenbecken": "AX_Hafenbecken",
        # Sonstiges
        "Tagebau, Grube, Steinbruch": "AX_TagebauGrubeSteinbruch",
        "Halde": "AX_Halde",
    }

    return mapping.get(nutzart)


def save_geojson(features: list, output_path: Path):
    """Save features as GeoJSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    geojson = {"type": "FeatureCollection", "features": features}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f)

    print(f"Saved {len(features)} features to {output_path}")


def generate_tiles(geojson_path: Path, tiles_dir: Path):
    """Generate vector tiles using tippecanoe."""
    # Remove existing tiles
    if tiles_dir.exists():
        import shutil

        shutil.rmtree(tiles_dir)

    cmd = [
        "tippecanoe",
        "--output-to-directory",
        str(tiles_dir),
        "--use-attribute-for-id=id",
        "--no-tile-compression",
        "--force",
        "-B",
        "10",
        "--minimum-zoom=10",
        "--maximum-zoom=13",
        "--layer=alkis",
        str(geojson_path),
    ]

    print(f"\nGenerating tiles...")
    print(f"Command: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
        print(f"Tiles generated in {tiles_dir}")
    except FileNotFoundError:
        print("⚠ tippecanoe not found. Install it with: brew install tippecanoe")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"⚠ tippecanoe failed: {e}")
        sys.exit(1)


def main():
    print("=" * 60)
    print("Brandenburg ALKIS Data Download & Tile Generation")
    print("=" * 60)
    print(f"\nWFS: {WFS_URL}")
    print(f"Output: {OUTPUT_GEOJSON}")
    print(f"Tiles: {TILES_DIR}")
    print()

    # Step 1: Download
    print("Step 1: Downloading features from WFS...")
    features = download_all_features()

    if not features:
        print("No features downloaded. Exiting.")
        sys.exit(1)

    # Step 2: Transform
    print("\nStep 2: Transforming features to Kiezcolors schema...")
    transformed = transform_features(features)
    print(f"Transformed {len(transformed)} features")

    # Step 3: Save GeoJSON
    print("\nStep 3: Saving GeoJSON...")
    save_geojson(transformed, OUTPUT_GEOJSON)

    # Step 4: Generate tiles
    print("\nStep 4: Generating vector tiles...")
    generate_tiles(OUTPUT_GEOJSON, TILES_DIR)

    print("\n" + "=" * 60)
    print("Done! Next steps:")
    print("  1. Update src/lib/components/map/Map.svelte with Brandenburg bounds")
    print("  2. Update src/lib/assets/berlin.js with Brandenburg outline")
    print("  3. Update attribution in Footer.svelte")
    print("=" * 60)


if __name__ == "__main__":
    main()
