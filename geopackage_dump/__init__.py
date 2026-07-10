# -*- coding: utf-8 -*-


def classFactory(iface):
    from .geopackage_dump import GeoPackageDumpPlugin
    return GeoPackageDumpPlugin(iface)
