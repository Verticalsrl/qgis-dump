# -*- coding: utf-8 -*-
"""
GeoPackage Dump - QGIS plugin
Main dialog: lets you pick a PostgreSQL/PostGIS connection configured in QGIS,
choose whether to export the whole database or a single schema, pick the
destination .gpkg file and run the dump with ogr2ogr.
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

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
    QWidget,
)

from . import pg_utils

# In PyQt6 (QGIS 4.x) enums are namespaced (Qt.CursorShape.WaitCursor),
# in PyQt5 (QGIS 3.x) they are still accessible in the "flat" form Qt.WaitCursor.
try:
    _WAIT_CURSOR = Qt.CursorShape.WaitCursor
except AttributeError:
    _WAIT_CURSOR = Qt.WaitCursor


class DumpWorker(QThread):
    """Runs ogr2ogr in a separate thread so the QGIS UI doesn't freeze."""

    line_output = pyqtSignal(str)
    finished_ok = pyqtSignal(int)
    finished_error = pyqtSignal(str)

    def __init__(self, cmd, parent=None):
        super().__init__(parent)
        self._cmd = cmd

    def run(self):
        try:
            returncode = pg_utils.run_command_streaming(self._cmd, self.line_output.emit)
            self.finished_ok.emit(returncode)
        except FileNotFoundError:
            self.finished_error.emit(
                "Command 'ogr2ogr' not found. Check that GDAL is available "
                "in the PATH of your QGIS installation."
            )
        except Exception as exc:  # noqa: BLE001
            self.finished_error.emit(str(exc))


class GeoPackageDumpDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dump to GeoPackage")
        self.resize(560, 480)

        self._worker = None
        self._current_params = None

        self._build_ui()
        self._populate_connections()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.combo_connections = QComboBox()
        self.combo_connections.currentTextChanged.connect(self._on_connection_changed)
        form.addRow("QGIS connection:", self.combo_connections)

        scope_widget = QWidget()
        scope_layout = QHBoxLayout(scope_widget)
        scope_layout.setContentsMargins(0, 0, 0, 0)

        self.radio_whole_db = QRadioButton("Whole database")
        self.radio_schema = QRadioButton("Specific schema")
        self.radio_whole_db.setChecked(True)
        self.scope_group = QButtonGroup(self)
        self.scope_group.addButton(self.radio_whole_db)
        self.scope_group.addButton(self.radio_schema)
        self.radio_whole_db.toggled.connect(self._on_scope_toggled)

        scope_layout.addWidget(self.radio_whole_db)
        scope_layout.addWidget(self.radio_schema)
        form.addRow("What to export:", scope_widget)

        self.combo_schema = QComboBox()
        self.combo_schema.setEnabled(False)
        form.addRow("Schema:", self.combo_schema)

        output_widget = QWidget()
        output_layout = QHBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.edit_output = QLineEdit()
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._on_browse)
        output_layout.addWidget(self.edit_output)
        output_layout.addWidget(self.btn_browse)
        form.addRow("GeoPackage file:", output_widget)

        self.check_overwrite = QCheckBox("Overwrite the file if it already exists")
        self.check_overwrite.setChecked(True)
        form.addRow("", self.check_overwrite)

        layout.addLayout(form)

        layout.addWidget(QLabel("Log:"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        button_row = QHBoxLayout()
        self.btn_refresh_schemas = QPushButton("Refresh schemas")
        self.btn_refresh_schemas.clicked.connect(self._load_schemas)
        button_row.addWidget(self.btn_refresh_schemas)
        button_row.addStretch()

        self.btn_export = QPushButton("Export")
        self.btn_export.clicked.connect(self._on_export)
        button_row.addWidget(self.btn_export)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        button_row.addWidget(self.btn_close)

        layout.addLayout(button_row)

    # ------------------------------------------------------------- actions
    def _populate_connections(self):
        self.combo_connections.clear()
        names = pg_utils.list_pg_connections()
        if not names:
            self._append_log(
                "No PostgreSQL connection found. Create one from "
                "Layer > Add Layer > Add PostGIS Layer."
            )
        self.combo_connections.addItems(names)

    def _on_connection_changed(self, _name):
        self.combo_schema.clear()
        self._current_params = None

    def _on_scope_toggled(self, whole_db_checked):
        self.combo_schema.setEnabled(not whole_db_checked)
        if not whole_db_checked and self.combo_schema.count() == 0:
            self._load_schemas()

    def _get_current_params(self):
        name = self.combo_connections.currentText()
        if not name:
            return None
        if self._current_params is None:
            self._current_params = pg_utils.get_pg_connection_params(name)
        return self._current_params

    def _load_schemas(self):
        params = self._get_current_params()
        if not params:
            QMessageBox.warning(self, "Warning", "Select a connection first.")
            return
        try:
            self.setCursor(_WAIT_CURSOR)
            schemas = pg_utils.list_schemas(params)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Connection error",
                "Could not read schemas from the database:\n{}".format(exc),
            )
            return
        finally:
            self.unsetCursor()

        self.combo_schema.clear()
        self.combo_schema.addItems(schemas)
        self._append_log("Found {} schema(s).".format(len(schemas)))

    def _on_browse(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save GeoPackage as", "", "GeoPackage (*.gpkg)"
        )
        if path:
            if not path.lower().endswith(".gpkg"):
                path += ".gpkg"
            self.edit_output.setText(path)

    def _append_log(self, text):
        self.log_view.appendPlainText(text)

    def _set_ui_enabled(self, enabled):
        self.combo_connections.setEnabled(enabled)
        self.radio_whole_db.setEnabled(enabled)
        self.radio_schema.setEnabled(enabled)
        self.combo_schema.setEnabled(enabled and self.radio_schema.isChecked())
        self.edit_output.setEnabled(enabled)
        self.btn_browse.setEnabled(enabled)
        self.check_overwrite.setEnabled(enabled)
        self.btn_refresh_schemas.setEnabled(enabled)
        self.btn_export.setEnabled(enabled)

    def _on_export(self):
        params = self._get_current_params()
        if not params:
            QMessageBox.warning(self, "Warning", "Select a valid connection.")
            return

        output_path = self.edit_output.text().strip()
        if not output_path:
            QMessageBox.warning(self, "Warning", "Specify the destination GeoPackage file.")
            return

        schemas = None
        if self.radio_schema.isChecked():
            schema_name = self.combo_schema.currentText()
            if not schema_name:
                QMessageBox.warning(self, "Warning", "Select a schema to export.")
                return
            schemas = [schema_name]
        else:
            # Whole database: explicitly enumerate all non-system schemas, because
            # ogr2ogr by default only reads the 'public' schema.
            try:
                schemas = pg_utils.list_schemas(params)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(
                    self,
                    "Connection error",
                    "Could not read schemas from the database:\n{}".format(exc),
                )
                return
            if not schemas:
                QMessageBox.warning(self, "Warning", "No schema found to export.")
                return

        cmd = pg_utils.build_ogr2ogr_command(
            params,
            output_path,
            schemas=schemas,
            overwrite=self.check_overwrite.isChecked(),
        )

        # Show the command (without a plaintext password) in the log
        self._append_log("Starting dump to: {}".format(output_path))
        self._append_log("Schemas: {}".format(", ".join(schemas)))

        self._set_ui_enabled(False)
        self._worker = DumpWorker(cmd, self)
        self._worker.line_output.connect(self._append_log)
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.finished_error.connect(self._on_finished_error)
        self._worker.start()

    def _on_finished_ok(self, returncode):
        self._set_ui_enabled(True)
        if returncode == 0:
            self._append_log("Dump completed successfully.")
            QMessageBox.information(self, "Completed", "Dump to GeoPackage completed.")
        else:
            self._append_log("ogr2ogr exited with error code {}.".format(returncode))
            QMessageBox.critical(
                self,
                "Error",
                "ogr2ogr returned an error (code {}). Check the log for details.".format(
                    returncode
                ),
            )

    def _on_finished_error(self, message):
        self._set_ui_enabled(True)
        self._append_log("Error: {}".format(message))
        QMessageBox.critical(self, "Error", message)
