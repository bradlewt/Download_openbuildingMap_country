# OpenBuildingMap Country Extractor

A reusable **ArcGIS Pro / ArcPy** command-line utility for producing country-level OpenBuildingMap building-footprint datasets from an ISO3 code.

## What it does

Given a country such as `THA`, `MLI`, or `UKR`, the script:

1. obtains an ADM0 polygon from ArcGIS Online/Enterprise, a local polygon dataset, or a Natural Earth fallback;
2. selects the requested ISO3 and dissolves multipart ADM0 features;
3. identifies OpenBuildingMap packages intersecting the country;
4. downloads and decompresses the required `.gpkg.bz2` packages;
5. assembles the building features incrementally;
6. assigns buildings to the country using the **building center inside ADM0** by default;
7. preserves `source_id` and adds `source_name` (`OSM`, `Google`, `MS`);
8. runs `Check Geometry`;
9. runs `Repair Geometry` **only when the check reports problems**, then checks again; and
10. exports File Geodatabase, GeoJSON, GeoPackage, or multiple formats.

OpenBuildingMap states that its dataset is distributed per country as GeoPackages organized on a level-6 Quadkey grid (1,271 files total). See https://www.openbuildingmap.org/.

## Requirements

- **ArcGIS Pro** with ArcPy.
- The ArcGIS Pro Python environment.
- Internet access to OpenBuildingMap and, when applicable, the online ADM0 service.
- Sufficient local disk space for compressed packages, decompressed GeoPackages, scratch data, and output.

No additional `pip install` step is required for the Python standard-library dependencies used by the script.

> This script is not intended for a generic Python installation because it imports `arcpy`.

## Quick start

Open an **ArcGIS Pro Python Command Prompt** in the repository folder and run:

```bat
python download_openbuildingmap_country.py --help
```

### ArcGIS Online / Enterprise ADM0

```bat
python download_openbuildingmap_country.py MLI ^
  --boundary-source "https://services.arcgis.com/XXXXX/arcgis/rest/services/ADM0/FeatureServer/0" ^
  --iso-field ISO3 ^
  --output-type gdb ^
  --gdb "D:\GIS\OpenBuildingMap\Buildings.gdb"
```

The service URL should point to the specific feature layer, normally ending in `/FeatureServer/<layer_id>`. For a secured service, sign in to the correct portal in ArcGIS Pro before running the script.

### Local global ADM0

```bat
python download_openbuildingmap_country.py UKR ^
  --boundary-source "D:\GIS\Admin\Global_Admin.gdb\ADM0" ^
  --iso-field ISO3 ^
  --output-type gdb ^
  --gdb "D:\GIS\OpenBuildingMap\Buildings.gdb"
```

If the File Geodatabase does not exist, the script creates it.

### Multiple output formats

```bat
python download_openbuildingmap_country.py KHM ^
  --boundary-source "D:\GIS\Admin\Global_Admin.gdb\ADM0" ^
  --iso-field ISO3 ^
  --output-type all ^
  --output-dir "D:\GIS\OpenBuildingMap"
```

`all` produces File Geodatabase + GeoPackage + GeoJSON.

## Country assignment

The default is:

```text
--boundary-mode centroid
```

For polygon inputs, the script uses ArcGIS `HAVE_THEIR_CENTER_IN`. The complete original building polygon is retained when its polygon center falls inside ADM0.

This avoids both of the following:

- including a building merely because its edge touches the country; and
- manufacturing a cut building footprint at an administrative boundary.

Available modes:

| Mode | Behavior |
| --- | --- |
| `centroid` | Keep the whole building when its center is inside ADM0. **Default.** |
| `clip` | Geometrically cut building polygons at ADM0. |
| `intersect` | Keep the whole building when any part intersects ADM0. |

Package discovery still uses intersection because every package that could contain a qualifying building must first be downloaded. Package intersection does **not** determine final building membership.

## Geometry quality assurance

The script uses a check-first policy:

```text
Check Geometry
    |
    +-- 0 problems ------> no geometry modification
    |
    +-- problems found --> Repair Geometry --> Check Geometry again
```

The default validation method is `OGC`.

```bat
--repair-method OGC
```

Use Esri validation with:

```bat
--repair-method ESRI
```

To deliberately skip geometry checking:

```bat
--skip-geometry-check
```

## Source field

The original OpenBuildingMap `source_id` is preserved. The script adds `source_name`:

| source_id | source_name |
| ---: | --- |
| 0 | OSM |
| 1 | Google |
| 2 | MS |
| other/unrecognized | Unknown |

## Output formats

`--output-type` accepts:

- `gdb` - File Geodatabase feature class;
- `gpkg` - GeoPackage feature class;
- `geojson` - GeoJSON projected to WGS84;
- `both` - File Geodatabase + GeoJSON; or
- `all` - File Geodatabase + GeoPackage + GeoJSON.

File Geodatabase is recommended for large ArcGIS-native workflows. ArcGIS documents a 4 GB maximum output file size for `Features To JSON`, so GeoJSON is not appropriate for very large national extracts.

## Common options

```text
ISO3                    Three-letter country code
--boundary-source       FeatureServer URL or local polygon dataset
--iso-field             ISO3 field in the ADM0 source
--boundary-mode         centroid | clip | intersect
--output-type           gdb | gpkg | geojson | both | all
--output-dir            Base output and work directory
--gdb                    Target File Geodatabase
--gpkg                   Target GeoPackage
--geojson                Target GeoJSON file
--feature-class          Output feature-class name
--repair-method          OGC | ESRI
--skip-geometry-check    Disable geometry QA
--workers                Concurrent package downloads
--overwrite              Replace existing requested outputs
--keep-work              Keep downloads, scratch GDB, and intermediates
--verbose                Show diagnostic logging
--version                Show script version
```

Use `--help` for the authoritative command list.

## Temporary data and disk use

By default the script creates:

```text
_obm_work_<ISO3>/
```

inside the output directory. On a successful run, the entire work directory is removed automatically because country-scale building intermediates can be very large.

Use:

```bat
--keep-work
```

when debugging or when you intentionally want to inspect downloaded GeoPackages and scratch outputs.

## Data licensing and citation

OpenBuildingMap states that the database is licensed under **ODbL v1.0** and requests citation of the GFZ dataset:

> Oostwegel, L. J. N.; Schorlemmer, D.; Lingner, L.; Evaz Zadeh, T. (2025). OpenBuildingMap. GFZ Data Services. https://doi.org/10.5880/GFZ.LKUT.2025.002

See [DATA_LICENSE.md](DATA_LICENSE.md) for details.

## Software license

The repository software is released under the **MIT License**, with an **additional patent grant rider modeled on the patent-license concept in Apache License 2.0 Section 3**.

- MIT text: [LICENSE](LICENSE)
- Additional patent grant: [PATENT_GRANT.md](PATENT_GRANT.md)

The rider is an additional grant, not the Apache-2.0 license itself; there is therefore no single standard SPDX identifier for the combined arrangement.

## Documentation

- [Methodology](docs/METHODOLOGY.md)
- [Testing](docs/TESTING.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Example commands](examples/commands.md)
- [First GitHub repository guide](FIRST_REPO_GUIDE.md)

## Reproducibility

For analytical or production use, record at minimum:

- ISO3;
- extraction date;
- OpenBuildingMap version/date;
- ADM0 source and version/date;
- ISO3 field used;
- boundary mode;
- geometry-validation method;
- output format; and
- repository Git commit or release tag.

## Limitations

- Requires ArcGIS Pro / ArcPy.
- Results depend on the quality and currency of OpenBuildingMap and the chosen ADM0 source.
- Feature services may change schema, URL, access, or authentication requirements.
- Country-scale building data can require substantial processing time and disk space.
- Centroid/center assignment is a processing convention and is not a determination of sovereignty or disputed boundaries.
- Changes to the upstream OpenBuildingMap download manifest may require script updates.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
