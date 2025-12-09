#!/usr/bin/env python3
"""
Convert Brandenburg ALKIS GeoJSON: map nutzart to bezeich and generate tiles.

Usage:
    uv run scripts/convert-bb.py
"""
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

import json
import subprocess
import sys
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_GEOJSON = DATA_DIR / "alkis_bb.geojson"
OUTPUT_GEOJSON = DATA_DIR / "alkis_bb_converted.geojson"
TILES_DIR = Path(__file__).parent.parent / "static" / "tiles"

# Mapping Brandenburg nutzart to Berlin-style bezeich
NUTZART_TO_BEZEICH = {
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


def convert_features():
    """Convert nutzart to bezeich in GeoJSON."""
    print(f"Loading {INPUT_GEOJSON}...")

    with open(INPUT_GEOJSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Converting {len(data['features'])} features...")

    converted_features = []
    skipped = 0
    nutzart_counts = {}

    for feature in data["features"]:
        nutzart = feature.get("properties", {}).get("nutzart", "")
        nutzart_counts[nutzart] = nutzart_counts.get(nutzart, 0) + 1

        bezeich = NUTZART_TO_BEZEICH.get(nutzart)

        if bezeich:
            converted_features.append({
                "type": "Feature",
                "properties": {"bezeich": bezeich},
                "geometry": feature.get("geometry"),
            })
        else:
            skipped += 1

    print(f"\nNutzart counts:")
    for nutzart, count in sorted(nutzart_counts.items(), key=lambda x: -x[1]):
        bezeich = NUTZART_TO_BEZEICH.get(nutzart, "SKIPPED")
        print(f"  {nutzart}: {count} -> {bezeich}")

    print(f"\nConverted: {len(converted_features)}")
    print(f"Skipped: {skipped}")

    output = {"type": "FeatureCollection", "features": converted_features}

    print(f"\nSaving to {OUTPUT_GEOJSON}...")
    with open(OUTPUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(output, f)

    size_mb = OUTPUT_GEOJSON.stat().st_size / (1024 * 1024)
    print(f"Saved ({size_mb:.1f} MB)")

    return OUTPUT_GEOJSON


def generate_tiles(geojson_path: Path):
    """Generate vector tiles using tippecanoe."""
    import shutil

    # Remove existing tiles
    if TILES_DIR.exists():
        print(f"\nRemoving existing tiles directory...")
        shutil.rmtree(TILES_DIR)

    cmd = [
        "tippecanoe",
        "--output-to-directory", str(TILES_DIR),
        "--layer=alkis",
        "--no-tile-compression",
        "--force",
        "-B", "10",
        "--minimum-zoom=10",
        "--maximum-zoom=13",
        str(geojson_path),
    ]

    print(f"\nGenerating tiles...")
    print(f"Command: {' '.join(cmd)}")

    try:
        subprocess.run(cmd, check=True)
        print(f"\nTiles generated in {TILES_DIR}")
    except FileNotFoundError:
        print("tippecanoe not found. Install it with: brew install tippecanoe")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"tippecanoe failed: {e}")
        sys.exit(1)


def main():
    print("=" * 60)
    print("Brandenburg ALKIS Data Conversion & Tile Generation")
    print("=" * 60)

    # Step 1: Convert
    output_path = convert_features()

    # Step 2: Generate tiles
    generate_tiles(output_path)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
