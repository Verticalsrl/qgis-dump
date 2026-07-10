# GeoPackage Dump

[![License: GPL v2+](https://img.shields.io/badge/License-GPLv2%2B-blue.svg)](LICENSE)
![QGIS](https://img.shields.io/badge/QGIS-3.16%20%E2%80%93%204.x-green.svg)

QGIS plugin that exports a PostgreSQL/PostGIS connection already configured in
QGIS to a GeoPackage (`.gpkg`) file, letting you choose between exporting the
**whole database** or **a single schema** (useful when the database is too
large for a full dump).

The dump runs via `ogr2ogr` (GDAL), in a separate thread, with a real-time log
in the plugin window.

## Requirements

- QGIS 3.16 or later.
- `ogr2ogr` available in the PATH of your QGIS installation (included by
  default in standard OSGeo4W/QGIS installations on Windows, macOS and
  Linux).
- The Python library `psycopg2` available in the QGIS Python environment
  (usually already present; if missing: `pip install psycopg2` in the
  Python environment used by QGIS, or on Linux `sudo apt install
  python3-psycopg2`).
- At least one PostgreSQL/PostGIS connection already saved in QGIS
  (Layer → Add Layer → Add PostGIS Layer → New).

## Installation

1. Open QGIS → **Plugins** → **Manage and Install Plugins...**
2. Go to the **Install from ZIP** tab.
3. Select the `geopackage_dump.zip` file.
4. Click **Install Plugin**.

## Usage

1. Menu **Database → GeoPackage Dump → Dump to GeoPackage...** (or the
   toolbar icon).
2. Select the PostgreSQL **connection** to use.
3. Choose whether to export the **whole database** or a **specific schema**
   (in that case click "Refresh schemas" if the list is empty).
4. Choose the destination **.gpkg** file with "Browse...".
5. Click **Export**: the log shows `ogr2ogr` progress in real time.

## Notes on credentials

- If the QGIS connection uses an **Authentication configuration** (authcfg),
  the plugin tries to resolve username/password via the QGIS authentication
  manager. If the manager hasn't been unlocked yet in the session, QGIS may
  prompt for the master password.
- If the connection uses a **service file** (`pg_service.conf`), that is
  used instead: nothing else is needed.

## Known limitations

- Only supports **PostgreSQL/PostGIS** connections (not SpatiaLite, Oracle,
  MSSQL, etc.).
- The "whole database" export explicitly enumerates all non-system schemas
  and passes them to `ogr2ogr` (by default OGR only reads the `public`
  schema).
- The dump exports the tables/views readable by the connection's user;
  insufficient permissions on some tables can produce partial errors visible
  in the log.

## License

Distributed under the **GNU General Public License v2 or later
(GPL-2.0-or-later)**. See the [LICENSE](LICENSE) file.

## Author

**Vertical Srl** — <https://vertical-srl.it> · <info@vertical-srl.it>
