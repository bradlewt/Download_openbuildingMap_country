# Command Examples

## Thailand using an ArcGIS Online / Enterprise ADM0 service

```bat
python download_openbuildingmap_country.py THA ^
  --boundary-source "https://services.arcgis.com/XXXXX/arcgis/rest/services/ADM0/FeatureServer/0" ^
  --iso-field ISO3 ^
  --output-type gdb ^
  --gdb "D:\GIS\OpenBuildingMap\Buildings.gdb"
```

## Mali using a local global ADM0

```bat
python download_openbuildingmap_country.py MLI ^
  --boundary-source "D:\GIS\Admin\Global_Admin.gdb\ADM0" ^
  --iso-field ISO3 ^
  --boundary-mode centroid ^
  --output-type gdb ^
  --gdb "D:\GIS\OpenBuildingMap\Buildings.gdb"
```

## Cambodia to all supported formats

```bat
python download_openbuildingmap_country.py KHM ^
  --boundary-source "D:\GIS\Admin\Global_Admin.gdb\ADM0" ^
  --iso-field ISO3 ^
  --output-type all ^
  --output-dir "D:\GIS\OpenBuildingMap"
```

## Retain buildings on any intersection

```bat
python download_openbuildingmap_country.py LAO ^
  --boundary-source "D:\GIS\Admin\Global_Admin.gdb\ADM0" ^
  --iso-field ISO3 ^
  --boundary-mode intersect ^
  --output-type gdb
```

## Physically clip footprints at ADM0

```bat
python download_openbuildingmap_country.py BEL ^
  --boundary-source "D:\GIS\Admin\Global_Admin.gdb\ADM0" ^
  --iso-field ISO3 ^
  --boundary-mode clip ^
  --output-type gpkg
```

## Natural Earth fallback

```bat
python download_openbuildingmap_country.py NPL ^
  --output-type gdb ^
  --output-dir "D:\GIS\OpenBuildingMap"
```

## Keep scratch data for inspection

```bat
python download_openbuildingmap_country.py THA ^
  --boundary-source "D:\GIS\Admin\Global_Admin.gdb\ADM0" ^
  --iso-field ISO3 ^
  --keep-work ^
  --verbose
```
