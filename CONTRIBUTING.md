# Contributing

Contributions that improve reliability, interoperability, documentation, or performance are welcome.

## Development principles

Please preserve these design choices unless a change explicitly documents why it should differ:

- ISO3 is the primary country selector.
- Both online FeatureServer and local ADM0 sources are supported.
- `centroid` is the default country-membership method.
- Original building polygons are not clipped unless `clip` is explicitly requested.
- The original `source_id` is preserved.
- `source_name` is additive convenience metadata.
- Geometry is checked before any repair.
- `Repair Geometry` does not run when the initial geometry check is clean.
- Existing final outputs are not silently replaced.
- Large datasets are processed incrementally where practical.

## Before a pull request

1. Run the script in a supported ArcGIS Pro Python environment.
2. Run at least one manageable end-to-end country test when processing logic changes.
3. Confirm `python download_openbuildingmap_country.py --help` is accurate.
4. Update documentation for behavioral or CLI changes.
5. Do not commit generated GIS data, credentials, tokens, or signed URLs.

## Bug reports

A useful report includes ArcGIS Pro version, ISO3, ADM0 source type, boundary mode, output type, full error text, and the command used with credentials and sensitive paths removed.
