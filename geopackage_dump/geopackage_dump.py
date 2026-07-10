# -*- coding: utf-8 -*-
"""
Plugin QGIS "GeoPackage Dump".
Aggiunge una voce di menu/toolbar che apre un dialog per esportare una connessione
PostgreSQL/PostGIS (intero database o singolo schema) verso un file GeoPackage.
"""

import os

from qgis.PyQt.QtGui import QIcon

# In PyQt6 (QGIS 4.x) QAction vive in QtGui, in PyQt5 (QGIS 3.x) in QtWidgets.
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
        self.action = QAction(QIcon(icon_path), "Dump verso GeoPackage...", self.iface.mainWindow())
        self.action.triggered.connect(self.run)

        # Menu "Database" (se assente su vecchie versioni di QGIS, ripiega su un menu plugin generico)
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
