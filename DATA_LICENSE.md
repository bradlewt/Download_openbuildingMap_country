# Data License and Attribution

This repository contains software for downloading and transforming **OpenBuildingMap (OBM)** data. The repository's software license does not relicense OpenBuildingMap or user-supplied administrative boundary data.

## OpenBuildingMap

OpenBuildingMap describes itself as a global building-footprint dataset combining OpenStreetMap, Google Open Buildings, and Microsoft Global ML Building Footprints. The publisher states that the database is licensed under the **Open Data Commons Open Database License (ODbL) v1.0**.

The OBM building table documents `source_id` as:

| source_id | Source |
| ---: | --- |
| 0 | OpenStreetMap |
| 1 | Google |
| 2 | Microsoft |

This utility preserves `source_id` and adds `source_name` as a convenience field (`OSM`, `Google`, `MS`).

### Requested dataset citation

Oostwegel, L. J. N.; Schorlemmer, D.; Lingner, L.; Evaz Zadeh, T. (2025). *OpenBuildingMap*. GFZ Data Services. https://doi.org/10.5880/GFZ.LKUT.2025.002

Associated publication:

Oostwegel, L. J. N.; Schorlemmer, D.; Guéguen, P. (2025). *From Footprints to Functions: A Comprehensive Global and Semantic Building Footprint Dataset*. Scientific Data. https://doi.org/10.1038/s41597-025-06132-z

Current dataset information and licensing: https://www.openbuildingmap.org/

## Administrative boundaries

Administrative boundaries supplied through ArcGIS Online, ArcGIS Enterprise, a local dataset, or another provider may have their own licensing and attribution requirements. Users are responsible for ensuring that their chosen ADM0 source may be used for the intended purpose.

When the Natural Earth fallback is used, consult Natural Earth's current terms for any applicable requirements.

## Important distinction

The **MIT License and additional patent grant apply to this repository's software only**. They do not replace or modify the ODbL or other licenses that apply to downloaded data.

This summary is not legal advice.
