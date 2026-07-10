# GeoPackage Dump — plugin QGIS

Esporta una connessione PostgreSQL/PostGIS già configurata in QGIS verso un file
GeoPackage (.gpkg), scegliendo se esportare l'**intero database** o **un singolo schema**
(utile quando il database è troppo pesante per un dump completo).

Il dump viene eseguito tramite `ogr2ogr` (GDAL), in un thread separato, con log in tempo
reale nella finestra del plugin.

## Requisiti

- QGIS 3.16 o superiore.
- `ogr2ogr` disponibile nel PATH dell'installazione di QGIS (incluso di default nelle
  installazioni standard OSGeo4W/QGIS su Windows, macOS e Linux).
- Libreria Python `psycopg2` disponibile nell'ambiente Python di QGIS (di norma già
  presente; se manca: `pip install psycopg2` nell'ambiente Python usato da QGIS, oppure
  su Linux `sudo apt install python3-psycopg2`).
- Almeno una connessione PostgreSQL/PostGIS già salvata in QGIS
  (Livello → Aggiungi Layer → Aggiungi Layer PostGIS → Nuovo).

## Installazione

1. Aprire QGIS → **Plugin** → **Gestisci e installa plugin...**
2. Scheda **Installa da ZIP**.
3. Selezionare il file `geopackage_dump.zip`.
4. Cliccare **Installa plugin**.

## Utilizzo

1. Menu **Database → GeoPackage Dump → Dump verso GeoPackage...** (oppure icona in toolbar).
2. Selezionare la **connessione** PostgreSQL da usare.
3. Scegliere se esportare l'**intero database** o **uno schema specifico** (in questo
   caso cliccare "Aggiorna schemi" se l'elenco è vuoto).
4. Scegliere il file **.gpkg** di destinazione con "Sfoglia...".
5. Cliccare **Esporta**: il log mostra l'avanzamento di `ogr2ogr` in tempo reale.

## Note sulle credenziali

- Se la connessione QGIS usa una **Configurazione autenticazione** (authcfg), il plugin
  prova a risolvere username/password tramite il gestore autenticazioni di QGIS. Se il
  gestore non è ancora stato sbloccato nella sessione, QGIS potrebbe chiedere la
  password master.
- Se la connessione usa un **service file** (`pg_service.conf`), viene usato quello: non
  serve altro.

## Limitazioni note

- Supporta solo connessioni **PostgreSQL/PostGIS** (non SpatiaLite, Oracle, MSSQL, ecc.).
- L'esportazione "intero database" enumera esplicitamente tutti gli schemi non di
  sistema e li passa a `ogr2ogr` (per default OGR legge solo lo schema `public`).
- Il dump esporta le tabelle/viste leggibili dall'utente della connessione; permessi
  insufficienti su alcune tabelle possono generare errori parziali visibili nel log.
