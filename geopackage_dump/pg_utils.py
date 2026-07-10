# -*- coding: utf-8 -*-
"""
Funzioni di supporto per leggere le connessioni PostgreSQL/PostGIS salvate in QGIS,
risolvere le credenziali (anche via authcfg) ed eseguire il dump verso GeoPackage
tramite ogr2ogr.
"""

import re
import subprocess

from qgis.core import QgsSettings, QgsApplication, QgsAuthMethodConfig

# Schemi di sistema PostgreSQL da escludere sempre dall'elenco proposto all'utente
SYSTEM_SCHEMA_PREFIXES = ("pg_temp_", "pg_toast_temp_")
SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "pg_toast"}


def _normalize_sslmode(raw):
    """
    QGIS salva sslmode come nome dell'enum interno (es. 'SslPrefer', 'SslVerifyCa')
    invece del valore atteso da libpq/psycopg2 ('prefer', 'verify-ca', ...).
    Questa funzione normalizza entrambi i formati nel valore libpq corretto.
    """
    if not raw:
        return ""
    value = str(raw).strip()
    # rimuove l'eventuale prefisso "Ssl" (case-insensitive)
    value = re.sub(r"^[Ss]sl", "", value)
    if not value:
        return ""
    # CamelCase -> kebab-case (es. "VerifyCa" -> "verify-ca", "Prefer" -> "prefer")
    value = re.sub(r"(?<!^)(?=[A-Z])", "-", value).lower()
    # normalizza eventuali varianti con underscore invece del trattino
    value = value.replace("_", "-")

    valid = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
    if value not in valid:
        # Valore non riconosciuto: meglio ignorarlo (nessun sslmode) che far fallire
        # la connessione con un valore che libpq non capisce.
        return ""
    return value


def list_pg_connections():
    """Ritorna la lista ordinata dei nomi delle connessioni PostgreSQL configurate in QGIS."""
    settings = QgsSettings()
    settings.beginGroup("PostgreSQL/connections")
    names = settings.childGroups()
    settings.endGroup()
    return sorted(names)


def get_pg_connection_params(name):
    """
    Legge i parametri di una connessione PostgreSQL salvata in QGIS (Impostazioni > Connessioni).
    Se la connessione usa una "Configurazione autenticazione" (authcfg) prova a risolvere
    username/password tramite il gestore autenticazioni di QGIS.
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
    """Apre una connessione psycopg2 usando i parametri risolti."""
    import psycopg2  # import ritardato: potrebbe non servire se si usa solo ogr2ogr

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
    """Interroga il database e ritorna gli schemi disponibili (esclusi quelli di sistema)."""
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
    """Costruisce la stringa di connessione OGR 'PG:...' da passare a ogr2ogr."""
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
    """Costruisce la lista di argomenti per il comando ogr2ogr."""
    pg_conn = build_pg_connection_string(params, schemas=schemas)

    cmd = ["ogr2ogr", "-f", "GPKG"]
    if overwrite:
        cmd.append("-overwrite")
    cmd += [output_path, pg_conn, "-progress"]
    return cmd


def run_command_streaming(cmd, line_callback=None):
    """
    Esegue un comando in un sottoprocesso, inviando ogni riga di output
    (stdout+stderr) a line_callback man mano che arriva. Ritorna il codice di uscita.
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
