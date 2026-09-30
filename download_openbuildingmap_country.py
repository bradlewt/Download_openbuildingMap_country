#!/usr/bin/env python
# SPDX-License-Identifier: MIT
# Additional patent grant: see PATENT_GRANT.md
"""Download and assemble OpenBuildingMap buildings for one ISO3 country.

Designed for the ArcGIS Pro Python environment (ArcPy).

Typical workflow:
    ISO3 -> ADM0 -> intersecting OBM packages -> download/decompress -> append
    -> country membership (centroid by default) -> source_name -> geometry QA
    -> requested outputs.
"""

from __future__ import annotations

import argparse
import bz2
import concurrent.futures
from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Iterable, Sequence
import urllib.request

import arcpy

__version__ = "0.1.0"

LOGGER = logging.getLogger("obm_country_extractor")

OBM_MANIFEST_URL = (
    "https://umap.openstreetmap.de/de/datalayer/"
    "81684/ac9788a9-c215-417d-a580-cb545acd78b9/"
)

NATURAL_EARTH_COUNTRIES_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_10m_admin_0_countries.geojson"
)

NATURAL_EARTH_ISO3_FIELDS = (
    "ADM0_A3",
    "ISO_A3",
    "ISO_A3_EH",
    "SOV_A3",
    "GU_A3",
    "SU_A3",
    "BRK_A3",
)

SOURCE_NAME_MAP = {
    0: "OSM",
    1: "Google",
    2: "MS",
}


@dataclass(frozen=True)
class OutputPaths:
    """Resolved paths used by one run."""

    output_dir: Path
    work_dir: Path
    scratch_gdb: Path
    tile_dir: Path
    gdb: Path
    gpkg: Path
    geojson: Path
    feature_class_name: str


def configure_logging(verbose: bool = False) -> None:
    """Configure console logging once."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )


def is_url(value: str | os.PathLike[str]) -> bool:
    text = str(value).lower()
    return text.startswith("http://") or text.startswith("https://")


def safe_delete(dataset: str | os.PathLike[str] | None) -> None:
    """Delete an ArcGIS dataset/layer when it exists."""
    if dataset and arcpy.Exists(str(dataset)):
        arcpy.management.Delete(str(dataset))


def feature_count(dataset: str | os.PathLike[str]) -> int:
    """Return feature/table row count as an integer."""
    return int(arcpy.management.GetCount(str(dataset))[0])


def validate_iso3(value: str) -> str:
    """Normalize and validate a three-letter ISO code."""
    iso3 = value.strip().upper()
    if len(iso3) != 3 or not iso3.isalpha():
        raise ValueError("ISO3 must be exactly three letters, for example THA.")
    return iso3


def normalize_source_id(value: object) -> int | None:
    """Normalize OBM source_id values that may arrive as numeric-like types."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def sql_text_equals(dataset_or_layer: str, field_name: str, value: str) -> str:
    """Build a text equality expression for local data or a feature service."""
    try:
        field = arcpy.AddFieldDelimiters(dataset_or_layer, field_name)
    except Exception:
        field = field_name
    escaped = value.replace("'", "''")
    return f"{field} = '{escaped}'"


def download_url(
    url: str,
    destination: Path,
    *,
    retries: int = 3,
    timeout: int = 180,
) -> Path:
    """Download a URL atomically, reusing a completed local file when present."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and destination.stat().st_size > 0:
        LOGGER.debug("Reusing existing download: %s", destination)
        return destination

    partial = destination.with_suffix(destination.suffix + ".part")

    for attempt in range(1, retries + 1):
        try:
            partial.unlink(missing_ok=True)
            request = urllib.request.Request(
                url,
                headers={"User-Agent": f"OBM-country-extractor/{__version__}"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                with partial.open("wb") as stream:
                    shutil.copyfileobj(response, stream, length=1024 * 1024)
            partial.replace(destination)
            return destination
        except Exception:
            partial.unlink(missing_ok=True)
            if attempt == retries:
                raise
            delay = 2**attempt
            LOGGER.warning(
                "Download attempt %d/%d failed; retrying in %d seconds: %s",
                attempt,
                retries,
                delay,
                url,
            )
            time.sleep(delay)

    raise RuntimeError(f"Download failed unexpectedly: {url}")


def decompress_bz2(source: Path, destination: Path) -> Path:
    """Decompress a .bz2 file atomically, reusing completed output when present."""
    if destination.exists() and destination.stat().st_size > 0:
        LOGGER.debug("Reusing decompressed package: %s", destination)
        return destination

    partial = destination.with_suffix(destination.suffix + ".part")
    partial.unlink(missing_ok=True)

    with bz2.open(source, "rb") as src, partial.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)

    partial.replace(destination)
    return destination


def resolve_paths(args: argparse.Namespace, iso3: str) -> OutputPaths:
    """Resolve all output and scratch paths for one run."""
    output_dir = Path(args.output_dir).expanduser().resolve()
    feature_class_name = args.feature_class or f"OBM_{iso3}"

    return OutputPaths(
        output_dir=output_dir,
        work_dir=output_dir / f"_obm_work_{iso3}",
        scratch_gdb=output_dir / f"_obm_work_{iso3}" / "scratch.gdb",
        tile_dir=output_dir / f"_obm_work_{iso3}" / "tiles",
        gdb=Path(args.gdb).expanduser().resolve()
        if args.gdb
        else output_dir / f"OpenBuildingMap_{iso3}.gdb",
        gpkg=Path(args.gpkg).expanduser().resolve()
        if args.gpkg
        else output_dir / f"OpenBuildingMap_{iso3}.gpkg",
        geojson=Path(args.geojson).expanduser().resolve()
        if args.geojson
        else output_dir / f"OBM_{iso3}.geojson",
        feature_class_name=feature_class_name,
    )


def requested_formats(output_type: str) -> set[str]:
    """Expand combined output choices into individual formats."""
    mapping = {
        "gdb": {"gdb"},
        "geojson": {"geojson"},
        "gpkg": {"gpkg"},
        "both": {"gdb", "geojson"},
        "all": {"gdb", "geojson", "gpkg"},
    }
    return mapping[output_type]


def preflight_outputs(paths: OutputPaths, formats: set[str], overwrite: bool) -> None:
    """Fail before downloading when a requested final output already exists."""
    existing: list[str] = []

    if "gdb" in formats:
        target = os.path.join(str(paths.gdb), paths.feature_class_name)
        if arcpy.Exists(target):
            existing.append(target)

    if "gpkg" in formats:
        target = os.path.join(str(paths.gpkg), paths.feature_class_name)
        if arcpy.Exists(target):
            existing.append(target)

    if "geojson" in formats and paths.geojson.exists():
        existing.append(str(paths.geojson))

    if existing and not overwrite:
        joined = "\n  - ".join(existing)
        raise FileExistsError(
            "One or more final outputs already exist. Use --overwrite to replace them:\n"
            f"  - {joined}"
        )


def ensure_workspaces(paths: OutputPaths) -> None:
    """Create the output directory, work directory, tile directory, and scratch GDB."""
    paths.output_dir.mkdir(parents=True, exist_ok=True)
    paths.work_dir.mkdir(parents=True, exist_ok=True)
    paths.tile_dir.mkdir(parents=True, exist_ok=True)

    if not arcpy.Exists(str(paths.scratch_gdb)):
        arcpy.management.CreateFileGDB(str(paths.work_dir), paths.scratch_gdb.name)


def extract_country_feature_natural_earth(
    iso3: str,
    source_geojson: Path,
    output_geojson: Path,
) -> Path:
    """Extract all Natural Earth features matching ISO3 into one GeoJSON file."""
    with source_geojson.open("r", encoding="utf-8") as stream:
        data = json.load(stream)

    matches = []
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        values = {
            str(properties.get(field, "")).upper()
            for field in NATURAL_EARTH_ISO3_FIELDS
            if properties.get(field) is not None
        }
        if iso3 in values:
            matches.append(feature)

    if not matches:
        raise ValueError(
            f"ISO3 '{iso3}' was not found in the Natural Earth fallback. "
            "Provide --boundary-source and --iso-field instead."
        )

    payload = {
        "type": "FeatureCollection",
        "name": f"country_{iso3}",
        "features": matches,
    }
    with output_geojson.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream)
    return output_geojson


def validate_polygon_source(source: str, iso_field: str | None) -> None:
    """Validate that an ADM0 source is polygon geometry and optional ISO field exists."""
    description = arcpy.Describe(source)
    shape_type = getattr(description, "shapeType", None)
    if shape_type and str(shape_type).lower() != "polygon":
        raise ValueError(f"ADM0 boundary source must be polygon geometry, not {shape_type}.")

    if iso_field:
        fields = {field.name.lower(): field for field in arcpy.ListFields(source)}
        field = fields.get(iso_field.lower())
        if field is None:
            available = ", ".join(sorted(f.name for f in fields.values()))
            raise ValueError(
                f"ISO field '{iso_field}' was not found in the ADM0 source. "
                f"Available fields include: {available}"
            )


def make_country_boundary(
    *,
    iso3: str,
    work_dir: Path,
    scratch_gdb: Path,
    boundary_source: str | None,
    iso_field: str | None,
    natural_earth_url: str,
) -> str:
    """Create one dissolved ADM0 polygon for the requested ISO3."""
    country_fc = os.path.join(str(scratch_gdb), f"country_{iso3}")
    safe_delete(country_fc)

    if boundary_source:
        LOGGER.info("Using ADM0 boundary source: %s", boundary_source)
        try:
            validate_polygon_source(boundary_source, iso_field)
        except Exception as exc:
            if is_url(boundary_source):
                raise RuntimeError(
                    "Could not read the ArcGIS feature-service layer. Confirm the URL points "
                    "to a FeatureServer layer (for example .../FeatureServer/0). For secured "
                    "services, sign in to the correct portal in ArcGIS Pro."
                ) from exc
            raise

        where_clause = None
        if iso_field:
            where_clause = sql_text_equals(boundary_source, iso_field, iso3)
            LOGGER.info("Selecting ADM0 where %s = '%s'", iso_field, iso3)

        layer_name = f"adm0_source_{iso3}"
        safe_delete(layer_name)
        try:
            arcpy.management.MakeFeatureLayer(boundary_source, layer_name, where_clause)
            count = feature_count(layer_name)
            if count == 0:
                raise ValueError(
                    f"No ADM0 features were found for {iso3}. Check --iso-field and the "
                    "country-code convention used by the boundary source."
                )
            LOGGER.info("ADM0 selection contains %s polygon feature(s).", f"{count:,}")
            arcpy.management.Dissolve(layer_name, country_fc)
        finally:
            safe_delete(layer_name)
        return country_fc

    LOGGER.info("No ADM0 source supplied; using Natural Earth 1:10m fallback.")
    world_geojson = work_dir / "natural_earth_countries.geojson"
    country_geojson = work_dir / f"country_{iso3}.geojson"
    download_url(natural_earth_url, world_geojson)
    extract_country_feature_natural_earth(iso3, world_geojson, country_geojson)

    temp_fc = os.path.join(str(scratch_gdb), f"country_parts_{iso3}")
    safe_delete(temp_fc)
    arcpy.conversion.JSONToFeatures(str(country_geojson), temp_fc, "POLYGON")
    arcpy.management.Dissolve(temp_fc, country_fc)
    return country_fc


def get_intersecting_packages(
    country_fc: str,
    manifest_geojson: Path,
    scratch_gdb: Path,
) -> list[dict[str, str | None]]:
    """Return unique OBM packages whose index polygons intersect the country."""
    manifest_fc = os.path.join(str(scratch_gdb), "obm_manifest")
    safe_delete(manifest_fc)
    arcpy.conversion.JSONToFeatures(str(manifest_geojson), manifest_fc, "POLYGON")

    layer_name = "obm_manifest_lyr"
    safe_delete(layer_name)
    try:
        arcpy.management.MakeFeatureLayer(manifest_fc, layer_name)
        arcpy.management.SelectLayerByLocation(
            layer_name,
            "INTERSECT",
            country_fc,
            selection_type="NEW_SELECTION",
        )

        fields = {field.name.lower(): field.name for field in arcpy.ListFields(manifest_fc)}
        url_field = fields.get("url")
        quadkey_field = fields.get("quadkey")
        filename_field = fields.get("filename")

        if not url_field:
            raise RuntimeError(
                "The OpenBuildingMap download manifest does not contain the expected URL "
                "field. The upstream manifest schema may have changed."
            )

        cursor_fields = [url_field]
        if quadkey_field:
            cursor_fields.append(quadkey_field)
        if filename_field:
            cursor_fields.append(filename_field)

        packages: list[dict[str, str | None]] = []
        with arcpy.da.SearchCursor(layer_name, cursor_fields) as rows:
            for row in rows:
                url = str(row[0])
                index = 1
                quadkey = None
                filename = None

                if quadkey_field:
                    quadkey = str(row[index]) if row[index] is not None else None
                    index += 1
                if filename_field:
                    filename = str(row[index]) if row[index] is not None else None

                if not filename:
                    filename = os.path.basename(url)
                    if filename.endswith(".bz2"):
                        filename = filename[:-4]

                packages.append(
                    {"url": url, "quadkey": quadkey, "filename": filename}
                )
    finally:
        safe_delete(layer_name)

    if not packages:
        raise RuntimeError("No OpenBuildingMap packages intersect the requested country.")

    unique = {str(package["url"]): package for package in packages}
    return sorted(
        unique.values(),
        key=lambda item: (str(item.get("quadkey") or ""), str(item["url"])),
    )


def download_packages(
    packages: Sequence[dict[str, str | None]],
    tile_dir: Path,
    workers: int,
) -> list[Path]:
    """Download compressed OBM packages concurrently."""

    def download_one(package: dict[str, str | None]) -> Path:
        url = str(package["url"])
        filename = os.path.basename(url)
        if not filename.endswith(".bz2"):
            filename = f"{package['filename']}.bz2"
        return download_url(url, tile_dir / filename)

    LOGGER.info("Downloading with %d worker(s)...", workers)
    downloaded: list[Path] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(download_one, package) for package in packages]
        for completed, future in enumerate(
            concurrent.futures.as_completed(futures), start=1
        ):
            path = future.result()
            downloaded.append(path)
            LOGGER.info("  Downloaded %d/%d: %s", completed, len(futures), path.name)

    return sorted(downloaded)


def decompress_packages(compressed_files: Iterable[Path]) -> list[Path]:
    """Decompress all downloaded .bz2 packages."""
    compressed = list(compressed_files)
    geopackages: list[Path] = []
    LOGGER.info("Decompressing GeoPackages...")

    for index, source in enumerate(compressed, start=1):
        destination = (
            source.with_suffix("")
            if source.name.endswith(".bz2")
            else Path(f"{source}.gpkg")
        )
        decompress_bz2(source, destination)
        geopackages.append(destination)
        LOGGER.info("  Decompressed %d/%d: %s", index, len(compressed), destination.name)

    return geopackages


def find_building_feature_class(gpkg_path: Path) -> str:
    """Locate the OBM building feature class inside a GeoPackage."""
    found: list[str] = []
    for dirpath, _, filenames in arcpy.da.Walk(str(gpkg_path), datatype="FeatureClass"):
        for name in filenames:
            path = os.path.join(dirpath, name)
            if name.lower() == "building":
                return path
            found.append(path)

    if len(found) == 1:
        return found[0]

    raise RuntimeError(
        f"Could not uniquely locate the building feature class in {gpkg_path}."
    )


def assemble_packages(geopackages: Sequence[Path], raw_fc: str) -> str:
    """Create one feature class, then append subsequent OBM packages."""
    if not geopackages:
        raise ValueError("No GeoPackages were supplied for assembly.")

    safe_delete(raw_fc)
    total = len(geopackages)

    for index, gpkg in enumerate(geopackages, start=1):
        building_fc = find_building_feature_class(gpkg)
        LOGGER.info("[%d/%d] Adding %s", index, total, gpkg.name)
        if index == 1:
            arcpy.management.CopyFeatures(building_fc, raw_fc)
        else:
            arcpy.management.Append(building_fc, raw_fc, "TEST")

    return raw_fc


def retain_by_boundary(
    raw_fc: str,
    country_fc: str,
    output_fc: str,
    boundary_mode: str,
) -> str:
    """Apply the selected country-membership rule to building polygons."""
    safe_delete(output_fc)

    if boundary_mode == "clip":
        LOGGER.info("Boundary mode: CLIP")
        LOGGER.info("Geometrically clipping buildings to the ADM0 boundary.")
        arcpy.analysis.PairwiseClip(raw_fc, country_fc, output_fc)
        return output_fc

    relationship = {
        "centroid": "HAVE_THEIR_CENTER_IN",
        "intersect": "INTERSECT",
    }[boundary_mode]

    if boundary_mode == "centroid":
        LOGGER.info("Boundary mode: CENTROID")
        LOGGER.info(
            "Keeping complete building polygons when their center falls inside ADM0."
        )
    else:
        LOGGER.info("Boundary mode: INTERSECT")
        LOGGER.info("Keeping complete building polygons when any part intersects ADM0.")

    layer_name = "obm_buildings_boundary_lyr"
    safe_delete(layer_name)
    try:
        arcpy.management.MakeFeatureLayer(raw_fc, layer_name)
        arcpy.management.SelectLayerByLocation(
            layer_name,
            relationship,
            country_fc,
            selection_type="NEW_SELECTION",
        )
        count = feature_count(layer_name)
        LOGGER.info("Boundary selection retained %s building(s).", f"{count:,}")
        arcpy.management.CopyFeatures(layer_name, output_fc)
    finally:
        safe_delete(layer_name)

    return output_fc


def add_source_name(feature_class: str) -> None:
    """Add/update a human-readable source_name field from OBM source_id."""
    fields = {field.name.lower(): field.name for field in arcpy.ListFields(feature_class)}
    source_id_field = fields.get("source_id")
    if not source_id_field:
        raise RuntimeError("Expected OpenBuildingMap field 'source_id' was not found.")

    source_name_field = fields.get("source_name")
    if not source_name_field:
        LOGGER.info("Adding source_name text field.")
        arcpy.management.AddField(
            feature_class,
            "source_name",
            "TEXT",
            field_length=12,
            field_alias="Source Name",
        )
        source_name_field = "source_name"

    LOGGER.info("Populating source_name: 0=OSM, 1=Google, 2=MS.")
    unknown = 0
    with arcpy.da.UpdateCursor(
        feature_class, [source_id_field, source_name_field]
    ) as cursor:
        for row in cursor:
            mapped = SOURCE_NAME_MAP.get(normalize_source_id(row[0]))
            if mapped is None:
                mapped = "Unknown"
                unknown += 1
            row[1] = mapped
            cursor.updateRow(row)

    if unknown:
        LOGGER.warning(
            "%s feature(s) had an unrecognized source_id and were labeled 'Unknown'.",
            f"{unknown:,}",
        )


def check_and_conditionally_repair(
    feature_class: str,
    report_workspace: Path,
    prefix: str,
    validation_method: str,
) -> dict[str, int | bool]:
    """Check geometry and repair only when the initial check reports problems."""
    first_report = os.path.join(str(report_workspace), f"{prefix}_geometry_check")
    safe_delete(first_report)

    LOGGER.info("Checking geometry (%s)...", validation_method)
    arcpy.management.CheckGeometry(feature_class, first_report, validation_method)
    problems_before = feature_count(first_report)

    if problems_before == 0:
        LOGGER.info("No geometry problems found. Repair Geometry will not be run.")
        return {
            "problems_before": 0,
            "repair_run": False,
            "problems_after": 0,
        }

    LOGGER.warning(
        "Found %s geometry problem record(s). Running Repair Geometry.",
        f"{problems_before:,}",
    )
    arcpy.management.RepairGeometry(
        feature_class,
        "DELETE_NULL",
        validation_method,
    )

    second_report = os.path.join(str(report_workspace), f"{prefix}_geometry_recheck")
    safe_delete(second_report)
    LOGGER.info("Rechecking geometry after repair...")
    arcpy.management.CheckGeometry(feature_class, second_report, validation_method)
    problems_after = feature_count(second_report)

    if problems_after:
        LOGGER.warning(
            "%s geometry problem record(s) remain after repair.",
            f"{problems_after:,}",
        )
    else:
        LOGGER.info("Geometry is clean after repair.")

    return {
        "problems_before": problems_before,
        "repair_run": True,
        "problems_after": problems_after,
    }


def ensure_file_gdb(gdb_path: Path) -> str:
    """Create a File Geodatabase when it does not exist."""
    if gdb_path.suffix.lower() != ".gdb":
        raise ValueError("--gdb must end in .gdb")
    gdb_path.parent.mkdir(parents=True, exist_ok=True)
    if not arcpy.Exists(str(gdb_path)):
        arcpy.management.CreateFileGDB(str(gdb_path.parent), gdb_path.name)
    return str(gdb_path)


def ensure_geopackage(gpkg_path: Path) -> str:
    """Create a GeoPackage using the latest version supported by ArcGIS Pro."""
    if gpkg_path.suffix.lower() != ".gpkg":
        raise ValueError("--gpkg must end in .gpkg")
    gpkg_path.parent.mkdir(parents=True, exist_ok=True)
    if not arcpy.Exists(str(gpkg_path)):
        arcpy.management.CreateSQLiteDatabase(str(gpkg_path), "GEOPACKAGE")
    return str(gpkg_path)


def export_gdb(source_fc: str, paths: OutputPaths) -> str:
    """Export the processed buildings to a File Geodatabase."""
    gdb = ensure_file_gdb(paths.gdb)
    target = os.path.join(gdb, paths.feature_class_name)
    safe_delete(target)
    LOGGER.info("Writing File Geodatabase feature class: %s", target)
    arcpy.management.CopyFeatures(source_fc, target)
    return target


def export_geopackage(source_fc: str, paths: OutputPaths) -> str:
    """Export the processed buildings to a GeoPackage."""
    gpkg = ensure_geopackage(paths.gpkg)
    target = os.path.join(gpkg, paths.feature_class_name)
    safe_delete(target)
    LOGGER.info("Writing GeoPackage feature class: %s", target)
    arcpy.conversion.ExportFeatures(source_fc, target)
    return target


def export_geojson(source_fc: str, paths: OutputPaths) -> str:
    """Export the processed buildings to GeoJSON in WGS84."""
    paths.geojson.parent.mkdir(parents=True, exist_ok=True)
    paths.geojson.unlink(missing_ok=True)
    LOGGER.info("Writing GeoJSON: %s", paths.geojson)
    arcpy.conversion.FeaturesToJSON(
        source_fc,
        str(paths.geojson),
        "NOT_FORMATTED",
        "NO_Z_VALUES",
        "NO_M_VALUES",
        "GEOJSON",
        "WGS84",
        "USE_FIELD_NAME",
    )
    return str(paths.geojson)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Download and assemble OpenBuildingMap building footprints for one ISO3 country."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("iso3", help="Three-letter ISO country code, e.g. THA, MLI, UKR")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    boundary = parser.add_argument_group("ADM0 boundary")
    boundary.add_argument(
        "--boundary-source",
        help=(
            "Local polygon dataset or ArcGIS Online/Enterprise FeatureServer layer URL. "
            "If omitted, Natural Earth 1:10m is used."
        ),
    )
    boundary.add_argument(
        "--iso-field",
        help=(
            "Field in --boundary-source containing ISO3 values. If omitted, the entire "
            "boundary source is treated as the requested country."
        ),
    )
    boundary.add_argument(
        "--boundary-mode",
        choices=("centroid", "clip", "intersect"),
        default="centroid",
        help=(
            "centroid keeps the whole building when its center is in the country; clip "
            "cuts at ADM0; intersect keeps any building that intersects ADM0."
        ),
    )

    output = parser.add_argument_group("Outputs")
    output.add_argument(
        "--output-type",
        choices=("gdb", "geojson", "gpkg", "both", "all"),
        default="gdb",
        help="both means GDB + GeoJSON; all means GDB + GeoJSON + GeoPackage.",
    )
    output.add_argument(
        "--output-dir",
        default=os.getcwd(),
        help="Base directory for outputs and temporary work files.",
    )
    output.add_argument("--gdb", help="Target File Geodatabase path.")
    output.add_argument("--gpkg", help="Target GeoPackage path.")
    output.add_argument("--geojson", help="Target GeoJSON path.")
    output.add_argument(
        "--feature-class",
        help="Output feature-class name; defaults to OBM_<ISO3>.",
    )
    output.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace requested final outputs when they already exist.",
    )

    quality = parser.add_argument_group("Geometry quality assurance")
    quality.add_argument(
        "--repair-method",
        choices=("OGC", "ESRI"),
        default="OGC",
        help="Validation method for Check Geometry and, only when needed, Repair Geometry.",
    )
    quality.add_argument(
        "--skip-geometry-check",
        action="store_true",
        help="Skip Check Geometry and conditional repair entirely.",
    )

    download = parser.add_argument_group("Download and diagnostics")
    download.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent OBM package downloads.",
    )
    download.add_argument(
        "--keep-work",
        action="store_true",
        help="Retain the country work directory, downloads, scratch GDB, and intermediates.",
    )
    download.add_argument(
        "--manifest-url",
        default=OBM_MANIFEST_URL,
        help="Advanced override for the OpenBuildingMap download manifest URL.",
    )
    download.add_argument(
        "--natural-earth-url",
        default=NATURAL_EARTH_COUNTRIES_URL,
        help="Advanced override for the Natural Earth fallback GeoJSON URL.",
    )
    download.add_argument(
        "--verbose",
        action="store_true",
        help="Show additional diagnostic logging.",
    )

    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be 1 or greater")
    return args


def run(args: argparse.Namespace) -> list[str]:
    """Execute one complete country extraction and return final output paths."""
    iso3 = validate_iso3(args.iso3)
    paths = resolve_paths(args, iso3)
    formats = requested_formats(args.output_type)

    preflight_outputs(paths, formats, args.overwrite)
    ensure_workspaces(paths)

    arcpy.env.overwriteOutput = True
    arcpy.env.parallelProcessingFactor = "100%"

    LOGGER.info("=" * 72)
    LOGGER.info("OpenBuildingMap Country Extractor %s", __version__)
    LOGGER.info("Country: %s", iso3)
    LOGGER.info("Boundary mode: %s", args.boundary_mode)
    LOGGER.info("=" * 72)

    country_fc = make_country_boundary(
        iso3=iso3,
        work_dir=paths.work_dir,
        scratch_gdb=paths.scratch_gdb,
        boundary_source=args.boundary_source,
        iso_field=args.iso_field,
        natural_earth_url=args.natural_earth_url,
    )

    manifest_path = paths.work_dir / "obm_manifest.geojson"
    LOGGER.info("Downloading OpenBuildingMap package manifest...")
    download_url(args.manifest_url, manifest_path)

    packages = get_intersecting_packages(country_fc, manifest_path, paths.scratch_gdb)
    LOGGER.info("Found %s intersecting OBM package(s).", f"{len(packages):,}")

    compressed = download_packages(packages, paths.tile_dir, args.workers)
    geopackages = decompress_packages(compressed)

    raw_fc = os.path.join(str(paths.scratch_gdb), f"obm_{iso3}_raw")
    assemble_packages(geopackages, raw_fc)
    LOGGER.info(
        "Assembled %s building feature(s) from source packages.",
        f"{feature_count(raw_fc):,}",
    )

    country_buildings = os.path.join(str(paths.scratch_gdb), f"obm_{iso3}_country")
    retain_by_boundary(raw_fc, country_fc, country_buildings, args.boundary_mode)
    add_source_name(country_buildings)

    if args.skip_geometry_check:
        LOGGER.info("Geometry check skipped by user.")
    else:
        check_and_conditionally_repair(
            country_buildings,
            paths.scratch_gdb,
            f"obm_{iso3}",
            args.repair_method,
        )

    LOGGER.info(
        "Final country dataset contains %s building(s).",
        f"{feature_count(country_buildings):,}",
    )

    outputs: list[str] = []
    if "gdb" in formats:
        outputs.append(export_gdb(country_buildings, paths))
    if "gpkg" in formats:
        outputs.append(export_geopackage(country_buildings, paths))
    if "geojson" in formats:
        outputs.append(export_geojson(country_buildings, paths))

    LOGGER.info("=" * 72)
    LOGGER.info("Completed successfully.")
    for output in outputs:
        LOGGER.info("Output: %s", output)
    LOGGER.info("=" * 72)

    if not args.keep_work:
        LOGGER.info("Removing temporary work directory: %s", paths.work_dir)
        shutil.rmtree(paths.work_dir, ignore_errors=True)

    return outputs


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        run(args)
        return 0
    except KeyboardInterrupt:
        LOGGER.error("Cancelled by user.")
        return 130
    except Exception as exc:
        LOGGER.error("ERROR: %s", exc)
        try:
            messages = arcpy.GetMessages()
            if messages:
                LOGGER.error(messages)
        except Exception:
            pass
        if args.verbose:
            LOGGER.exception("Detailed traceback")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
