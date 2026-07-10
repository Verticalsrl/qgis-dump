# -*- coding: utf-8 -*-
"""
GeoPackage Dump - QGIS plugin
Adds a menu/toolbar entry that opens a dialog to export a PostgreSQL/PostGIS
connection (whole database or a single schema) to a GeoPackage file.
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

import os

from qgis.PyQt.QtGui import QIcon

# In PyQt6 (QGIS 4.x) QAction lives in QtGui, in PyQt5 (QGIS 3.x) in QtWidgets.
try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from .dump_dialog import GeoPackageDumpDialog


class GeoPackageDumpPlugin:

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        self.action = QAction(QIcon(icon_path), "Dump to GeoPackage...", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        # "Database" menu (falls back to a generic plugin menu on older QGIS versions)
        try:
            self.iface.addPluginToDatabaseMenu("&GeoPackage Dump", self.action)
        except AttributeError:
            self.iface.addPluginToMenu("&GeoPackage Dump", self.action)

        self.iface.addToolBarIcon(self.action)

    def unload(self):
        try:
            self.iface.removePluginDatabaseMenu("&GeoPackage Dump", self.action)
        except AttributeError:
            self.iface.removePluginMenu("&GeoPackage Dump", self.action)
        self.iface.removeToolBarIcon(self.action)

    def run(self):
        self.dialog = GeoPackageDumpDialog(self.iface.mainWindow())
        self.dialog.show()
