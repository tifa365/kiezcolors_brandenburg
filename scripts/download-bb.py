#!/usr/bin/env python3
"""
Download Brandenburg ALKIS Nutzung data from WFS as GML.
Conversion to GeoJSON requires ogr2ogr (GDAL).

Usage:
    uv run scripts/download-bb.py

Then convert with:
    ogr2ogr -f GeoJSON -t_srs EPSG:4326 data/alkis_bb.geojson data/alkis_bb.gml
"""
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
# ]
# ///

import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests

# Brandenburg WFS endpoint
WFS_URL = "https://isk.geobasis-bb.de/ows/alkis_vereinf_wfs"

# Output paths
DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_GML = DATA_DIR / "alkis_bb.gml"
OUTPUT_GEOJSON = DATA_DIR / "alkis_bb.geojson"

# Brandenburg bbox - we'll download in chunks due to 100k feature limit
# Format: (minx, miny, maxx, maxy) in EPSG:25833 (native CRS)
CHUNKS = [
    # West Brandenburg
    (280000, 5700000, 350000, 5800000),
    (280000, 5800000, 350000, 5900000),
    (280000, 5900000, 350000, 6000000),
    # Central-West
    (350000, 5700000, 420000, 5800000),
    (350000, 5800000, 420000, 5900000),
    (350000, 5900000, 420000, 6000000),
    # Central
    (420000, 5700000, 490000, 5800000),
    (420000, 5800000, 490000, 5900000),
    (420000, 5900000, 490000, 6000000),
    # Central-East
    (490000, 5700000, 560000, 5800000),
    (490000, 5800000, 560000, 5900000),
    (490000, 5900000, 560000, 6000000),
    # East Brandenburg
    (560000, 5700000, 630000, 5800000),
    (560000, 5800000, 630000, 5900000),
    (560000, 5900000, 630000, 6000000),
]


def download_chunk(minx: float, miny: float, maxx: float, maxy: float, output_path: Path) -> bool:
    """Download a single chunk from WFS as GML."""
    params = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": "ave:Nutzung",
        "SRSNAME": "EPSG:25833",
        "BBOX": f"{minx},{miny},{maxx},{maxy},EPSG:25833",
        "COUNT": "100000",
    }

    url = f"{WFS_URL}?{urlencode(params)}"
    print(f"  Downloading chunk ({minx}, {miny}) - ({maxx}, {maxy})...")

    try:
        response = requests.get(url, timeout=600, stream=True)
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"    → {size_mb:.1f} MB")
        return True

    except requests.RequestException as e:
        print(f"    ⚠ Error: {e}")
        return False


def merge_and_convert(chunk_files: list[Path], output_geojson: Path):
    """Merge GML chunks and convert to GeoJSON using ogr2ogr."""
    print("\nMerging and converting to GeoJSON...")

    # First file - create new output
    first = True
    for gml_file in chunk_files:
        if not gml_file.exists():
            continue

        cmd = [
            "ogr2ogr",
            "-f", "GeoJSON",
            "-t_srs", "EPSG:4326",
        ]

        if first:
            cmd.extend([str(output_geojson), str(gml_file)])
            first = False
        else:
            cmd.extend(["-update", "-append", str(output_geojson), str(gml_file)])

        print(f"  Processing {gml_file.name}...")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"    ⚠ ogr2ogr error: {e.stderr.decode()}")
        except FileNotFoundError:
            print("    ⚠ ogr2ogr not found. Install GDAL first:")
            print("      brew install gdal")
            return False

    if output_geojson.exists():
        size_mb = output_geojson.stat().st_size / (1024 * 1024)
        print(f"\n✓ Created {output_geojson} ({size_mb:.1f} MB)")
        return True
    return False


def main():
    print("=" * 60)
    print("Brandenburg ALKIS Nutzung - WFS Download")
    print("=" * 60)
    print(f"\nWFS: {WFS_URL}")
    print(f"Output: {OUTPUT_GEOJSON}")
    print(f"Chunks: {len(CHUNKS)}")
    print()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Download chunks
    chunk_files = []
    for i, (minx, miny, maxx, maxy) in enumerate(CHUNKS):
        chunk_file = DATA_DIR / f"alkis_bb_chunk_{i:02d}.gml"
        chunk_files.append(chunk_file)

        if chunk_file.exists():
            print(f"  Chunk {i} already exists, skipping...")
            continue

        download_chunk(minx, miny, maxx, maxy, chunk_file)

    # Merge and convert
    if merge_and_convert(chunk_files, OUTPUT_GEOJSON):
        print("\n" + "=" * 60)
        print("Next step: Generate tiles with tippecanoe")
        print("=" * 60)
        print(f"""
tippecanoe \\
  --output-to-directory static/tiles \\
  --layer=alkis \\
  --no-tile-compression \\
  --force \\
  -B 10 \\
  --minimum-zoom=10 \\
  --maximum-zoom=13 \\
  {OUTPUT_GEOJSON}
""")


if __name__ == "__main__":
    main()
