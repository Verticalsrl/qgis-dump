# -*- coding: utf-8 -*-
"""
GeoPackage Dump - QGIS plugin
Helper functions to read PostgreSQL/PostGIS connections saved in QGIS, resolve
credentials (including via authcfg) and run the dump to GeoPackage via ogr2ogr.
Vertical Srl - https://vertical-srl.it

Copyright (C) 2026 Vertical Srl

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, see <https://www.gnu.org/licenses/>.
"""

import re
import subprocess

from qgis.core import QgsSettings, QgsApplication, QgsAuthMethodConfig

# PostgreSQL system schemas to always exclude from the list shown to the user
SYSTEM_SCHEMA_PREFIXES = ("pg_temp_", "pg_toast_temp_")
SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "pg_toast"}


def _normalize_sslmode(raw):
    """
    QGIS stores sslmode as the name of its internal enum (e.g. 'SslPrefer',
    'SslVerifyCa') instead of the value expected by libpq/psycopg2 ('prefer',
    'verify-ca', ...). This function normalizes both formats to the correct
    libpq value.
    """
    if not raw:
        return ""
    value = str(raw).strip()
    # strip the optional "Ssl" prefix (case-insensitive)
    value = re.sub(r"^[Ss]sl", "", value)
    if not value:
        return ""
    # CamelCase -> kebab-case (e.g. "VerifyCa" -> "verify-ca", "Prefer" -> "prefer")
    value = re.sub(r"(?<!^)(?=[A-Z])", "-", value).lower()
    # normalize any underscore variants to hyphens
    value = value.replace("_", "-")

    valid = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
    if value not in valid:
        # Unrecognized value: better to ignore it (no sslmode) than fail the
        # connection with a value libpq doesn't understand.
        return ""
    return value


def list_pg_connections():
    """Return the sorted list of PostgreSQL connection names configured in QGIS."""
    settings = QgsSettings()
    settings.beginGroup("PostgreSQL/connections")
    names = settings.childGroups()
    settings.endGroup()
    return sorted(names)


def get_pg_connection_params(name):
    """
    Read the parameters of a PostgreSQL connection saved in QGIS (Settings > Connections).
    If the connection uses an "Authentication configuration" (authcfg), try to
    resolve username/password via the QGIS authentication manager.
    """
    settings = QgsSettings()
    base = "PostgreSQL/connections/{}".format(name)

    params = {
        "service": settings.value("{}/service".format(base), "", type=str),
        "host": settings.value("{}/host".format(base), "", type=str),
        "port": settings.value("{}/port".format(base), "5432", type=str),
        "database": settings.value("{}/database".format(base), "", type=str),
        "username": settings.value("{}/username".format(base), "", type=str),
        "password": settings.value("{}/password".format(base), "", type=str),
        "authcfg": settings.value("{}/authcfg".format(base), "", type=str),
        "sslmode": _normalize_sslmode(settings.value("{}/sslmode".format(base), "", type=str)),
    }

    if params["authcfg"]:
        cfg = QgsAuthMethodConfig()
        ok = QgsApplication.authManager().loadAuthenticationConfig(params["authcfg"], cfg, True)
        if ok:
            cfg_map = cfg.configMap()
            params["username"] = cfg_map.get("username", params["username"])
            params["password"] = cfg_map.get("password", params["password"])

    return params


def _connect(params):
    """Open a psycopg2 connection using the resolved parameters."""
    import psycopg2  # deferred import: not needed if only ogr2ogr is used

    kwargs = {}
    if params.get("service"):
        kwargs["service"] = params["service"]
    else:
        kwargs["host"] = params.get("host") or "localhost"
        kwargs["port"] = params.get("port") or "5432"
        if params.get("database"):
            kwargs["dbname"] = params["database"]
        if params.get("username"):
            kwargs["user"] = params["username"]
        if params.get("password"):
            kwargs["password"] = params["password"]
        if params.get("sslmode"):
            kwargs["sslmode"] = params["sslmode"]
    return psycopg2.connect(**kwargs)


def list_schemas(params):
    """Query the database and return the available schemas (system schemas excluded)."""
    conn = _connect(params)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT schema_name FROM information_schema.schemata ORDER BY schema_name;"
        )
        rows = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()

    schemas = [
        s for s in rows
        if s not in SYSTEM_SCHEMAS and not s.startswith(SYSTEM_SCHEMA_PREFIXES)
    ]
    return schemas


def build_pg_connection_string(params, schemas=None):
    """Build the OGR 'PG:...' connection string to pass to ogr2ogr."""
    parts = []
    if params.get("service"):
        parts.append("service={}".format(params["service"]))
    else:
        if params.get("host"):
            parts.append("host={}".format(params["host"]))
        if params.get("port"):
            parts.append("port={}".format(params["port"]))
        if params.get("database"):
            parts.append("dbname={}".format(params["database"]))
        if params.get("username"):
            parts.append("user={}".format(params["username"]))
        if params.get("password"):
            parts.append("password={}".format(params["password"]))
        if params.get("sslmode"):
            parts.append("sslmode={}".format(params["sslmode"]))

    if schemas:
        parts.append("schemas={}".format(",".join(schemas)))

    return "PG:" + " ".join(parts)


def build_ogr2ogr_command(params, output_path, schemas=None, overwrite=True):
    """Build the list of arguments for the ogr2ogr command."""
    pg_conn = build_pg_connection_string(params, schemas=schemas)

    cmd = ["ogr2ogr", "-f", "GPKG"]
    if overwrite:
        cmd.append("-overwrite")
    cmd += [output_path, pg_conn, "-progress"]
    return cmd


def run_command_streaming(cmd, line_callback=None):
    """
    Run a command in a subprocess, sending each output line (stdout+stderr)
    to line_callback as it arrives. Returns the exit code.
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )
    try:
        for line in iter(process.stdout.readline, ""):
            if line_callback:
                line_callback(line.rstrip("\n"))
        process.stdout.close()
    finally:
        returncode = process.wait()
    return returncode
