# Testing

Because this utility requires ArcPy, meaningful runtime testing must occur in an ArcGIS Pro Python environment.

## Minimum smoke test

Start with a small or manageable country and File Geodatabase output:

```bat
python download_openbuildingmap_country.py <ISO3> ^
  --boundary-source "<ADM0 FeatureServer URL or local polygon dataset>" ^
  --iso-field <ISO3_FIELD> ^
  --output-type gdb ^
  --output-dir "<TEST_OUTPUT_FOLDER>" ^
  --verbose
```

Confirm that:

- the requested ADM0 selects at least one feature;
- intersecting OBM packages are found;
- packages download and decompress;
- the `building` layers append successfully;
- centroid mode returns a plausible feature count;
- `source_name` contains `OSM`, `Google`, and/or `MS` as appropriate;
- `Check Geometry` completes;
- when the geometry report is empty, `Repair Geometry` is not called;
- the final feature class opens correctly in ArcGIS Pro; and
- `_obm_work_<ISO3>` is removed after success unless `--keep-work` is used.

## Format tests

After the GDB smoke test, test `gpkg` and `geojson` on a small country. GeoJSON should be WGS84.

## Failure-path tests

Also test at least once:

- invalid ISO3;
- nonexistent `--iso-field`;
- output already exists without `--overwrite`;
- output replacement with `--overwrite`;
- secured FeatureServer access while signed into the correct portal; and
- `--keep-work` for diagnostic inspection.
