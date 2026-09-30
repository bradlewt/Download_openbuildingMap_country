# Troubleshooting

## `No module named arcpy`

Run the script from the ArcGIS Pro Python environment rather than a generic Python installation.

## FeatureServer layer cannot be opened

Check that the URL points to a specific layer, normally ending in `/FeatureServer/<layer_id>`, and that ArcGIS Pro is signed into the correct portal if the service is secured.

## ISO field not found / no ADM0 feature selected

Confirm the `--iso-field` name and the country-code convention used by the layer. Not every administrative-boundary dataset uses the same ISO3 field name or treatment of territories.

## No OpenBuildingMap packages intersect

Inspect the dissolved ADM0 geometry and the upstream OBM package index before changing selection logic. An empty or incorrect ADM0 selection is the first thing to rule out.

## Append reports a schema mismatch

OBM packages are expected to use a consistent building schema. Inspect the affected GeoPackages before weakening schema validation because an upstream schema change may have occurred.

## Geometry problems remain after repair

Keep the work directory with `--keep-work`, inspect the geometry-check reports, and examine representative affected features. Avoid repeated blind repair passes.

## Processing is slow or disk use is high

Country-scale building datasets can contain millions of features. Temporary storage may include compressed packages, decompressed GeoPackages, scratch building feature classes, geometry reports, and final outputs.

Prefer File Geodatabase for large ArcGIS workflows and avoid GeoJSON unless it is actually needed.

## Output already exists

The script fails early rather than silently replacing final data. Use `--overwrite` only when replacement is intended.

## The upstream manifest changes

The default manifest URL is configurable:

```bat
--manifest-url "<NEW_MANIFEST_URL>"
```

Use this only after verifying the new manifest schema still exposes package polygons and a URL field.
