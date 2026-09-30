# Methodology

## 1. Resolve ADM0

The requested country is identified by ISO3. The ADM0 source may be an ArcGIS FeatureServer layer or a local ArcPy-readable polygon dataset. When `--iso-field` is supplied, the script selects the requested ISO3 and dissolves selected polygons into one country geometry.

Natural Earth is a fallback when no boundary source is provided.

## 2. Identify required OpenBuildingMap packages

The country polygon is spatially intersected with the OpenBuildingMap download index.

**This intersection is only a download-selection step.** It is deliberately broader than final country membership so every package that could contain a qualifying building is available locally.

## 3. Download and decompress

Required `.gpkg.bz2` packages are downloaded using temporary `.part` files. A file is renamed to its final path only after the transfer completes. Existing completed downloads are reused.

## 4. Assemble buildings

The first source building layer initializes the scratch target; subsequent source layers are appended. This avoids constructing one very large merge input list.

## 5. Assign country membership

The default mode is `centroid`, implemented with ArcGIS `HAVE_THEIR_CENTER_IN` for polygon inputs.

The complete building footprint is retained when the building polygon's center lies inside ADM0. Thus:

- an edge that merely touches ADM0 does not qualify the building;
- a boundary-crossing footprint is assigned according to its center; and
- the source footprint is preserved rather than cut.

Alternatives are `clip` and `intersect`.

This is a processing convention and should not be interpreted as resolving legal or political boundary questions.

## 6. Preserve and clarify provenance

OpenBuildingMap's `source_id` remains unchanged. The script adds `source_name`:

| source_id | source_name |
| ---: | --- |
| 0 | OSM |
| 1 | Google |
| 2 | MS |

Unexpected values become `Unknown` rather than being silently recoded.

## 7. Geometry QA

Geometry modification is conditional:

1. run `Check Geometry`;
2. if zero problems are reported, do not modify geometry;
3. if problems are reported, run `Repair Geometry`; and
4. run `Check Geometry` once more to verify the repair.

## 8. Export and cleanup

The validated country dataset is exported to requested formats. On successful completion, the large temporary work directory is removed unless `--keep-work` was requested.

## Reproducibility record

For production use, record ISO3, extraction date, OpenBuildingMap version/date, ADM0 source/version, ISO field, boundary mode, geometry validation method, output format, and Git commit/release tag.
