# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SpatialDecision
                                 A QGIS plugin
 This is a SDSS template for the GEO1005 course
                              -------------------
        begin                : 2015-11-02
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Jorge Gil, TU Delft
        email                : j.a.lopesgil@tudelft.nl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4 import QtGui, QtCore
#from PyQt4.QtCore import *
#from PyQt4.QtGui import *
from qgis.core import *
from qgis.networkanalysis import *


from pyspatialite import dbapi2 as sqlite
import psycopg2 as pgsql
import numpy as np
import math
import os.path

try:
    import networkx as nx
    has_networkx = True
except ImportError, e:
    has_networkx = False


#
# Layer functions
#
def getLegendLayers(iface, geom='all', provider='all'):
    """Return list of valid QgsVectorLayer in QgsLegendInterface, with specific geometry type and/or data provider"""
    layers_list = []
    for layer in iface.legendInterface().layers():
        add_layer = False
        if layer.isValid() and layer.type() == QgsMapLayer.VectorLayer:
            if layer.hasGeometryType() and (geom is 'all' or layer.geometryType() in geom):
                if provider is 'all' or layer.dataProvider().name() in provider:
                    add_layer = True
        if add_layer:
            layers_list.append(layer)
    return layers_list


def getCanvasLayers(iface, geom='all', provider='all'):
    """Return list of valid QgsVectorLayer in QgsMapCanvas, with specific geometry type and/or data provider"""
    layers_list = []
    for layer in iface.mapCanvas().layers():
        add_layer = False
        if layer.isValid() and layer.type() == QgsMapLayer.VectorLayer:
            if layer.hasGeometryType() and (geom is 'all' or layer.geometryType() in geom):
                if provider is 'all' or layer.dataProvider().name() in provider:
                    add_layer = True
        if add_layer:
            layers_list.append(layer)
    return layers_list


def getRegistryLayers(geom='all', provider='all'):
    """Return list of valid QgsVectorLayer in QgsMapLayerRegistry, with specific geometry type and/or data provider"""
    layers_list = []
    for layer in QgsMapLayerRegistry.instance().mapLayers().values():
        add_layer = False
        if layer.isValid() and layer.type() == QgsMapLayer.VectorLayer:
            if layer.hasGeometryType() and (geom is 'all' or layer.geometryType() in geom):
                if provider is 'all' or layer.dataProvider().name() in provider:
                    add_layer = True
        if add_layer:
            layers_list.append(layer)
    return layers_list


def isLayerProjected(layer):
    projected = False
    if layer:
        projected = not layer.crs().geographicFlag()
    return projected


def getLegendLayerByName(iface, name):
    layer = None
    for i in iface.legendInterface().layers():
        if i.name() == name:
            layer = i
    return layer


def getCanvasLayerByName(iface, name):
    layer = None
    for i in iface.mapCanvas().layers():
        if i.name() == name:
            layer = i
    return layer


def getLayersListNames(layerslist):
    layer_names = [layer.name() for layer in layerslist]
    return layer_names


def getLayerPath(layer):
    path = ''
    provider = layer.dataProvider()
    provider_type = provider.name()
    if provider_type == 'spatialite':
        uri = QgsDataSourceURI(provider.dataSourceUri())
        path = uri.database()
    elif provider_type == 'ogr':
        uri = provider.dataSourceUri()
        path = os.path.dirname(uri)
    return path


def reloadLayer(layer):
    layer_name = layer.name()
    layer_provider = layer.dataProvider().name()
    new_layer = None
    if layer_provider in ('spatialite','postgres'):
        uri = QgsDataSourceURI(layer.dataProvider().dataSourceUri())
        new_layer = QgsVectorLayer(uri.uri(), layer_name, layer_provider)
    elif layer_provider == 'ogr':
        uri = layer.dataProvider().dataSourceUri()
        new_layer = QgsVectorLayer(uri.split("|")[0], layer_name, layer_provider)
    QgsMapLayerRegistry.instance().removeMapLayer(layer.id())
    if new_layer:
        QgsMapLayerRegistry.instance().addMapLayer(new_layer)
    return new_layer


#
# Field functions
#
def fieldExists(layer, name):
    fields = getFieldNames(layer)
    if name in fields:
        return True
    else:
        return False


def getFieldNames(layer):
    fields_list = []
    if layer and layer.dataProvider():
        fields_list = [field.name() for field in layer.dataProvider().fields()]
    return fields_list


def getNumericFields(layer, type='all'):
    fields = []
    if type == 'all':
        types = (QtCore.QVariant.Int, QtCore.QVariant.LongLong, QtCore.QVariant.Double,
                 QtCore.QVariant.UInt, QtCore.QVariant.ULongLong)
    else:
        types = (type)
    if layer and layer.dataProvider():
        for field in layer.dataProvider().fields():
            if field.type() in types:
                fields.append(field)
    return fields


def getFieldIndex(layer, name):
    idx = layer.dataProvider().fields().indexFromName(name)
    return idx


def fieldHasValues(layer, name):
    if layer and fieldExists(layer, name):
    # find fields that only have NULL values
        idx = getFieldIndex(layer, name)
        maxval = layer.maximumValue(idx)
        minval = layer.minimumValue(idx)
        if maxval == NULL and minval == NULL:
            return False
        else:
            return True


def fieldHasNullValues(layer, name):
    if layer and fieldExists(layer, name):
        idx = getFieldIndex(layer, name)
        vals = layer.uniqueValues(idx,1)
        # depending on the provider list is empty or has NULL value in first position
        if len(vals) == 0 or (len(vals) == 1 and vals[0] == NULL):
            return True
        else:
            return False


def getFieldValues(layer, fieldname, null=True, selection=False):
    attributes = []
    ids = []
    if fieldExists(layer, fieldname):
        if selection:
            features = layer.selectedFeatures()
        else:
            request = QgsFeatureRequest().setSubsetOfAttributes([getFieldIndex(layer, fieldname)])
            features = layer.getFeatures(request)
        if null:
            for feature in features:
                attributes.append(feature.attribute(fieldname))
                ids.append(feature.id())
        else:
            for feature in features:
                val = feature.attribute(fieldname)
                if val != NULL:
                    attributes.append(val)
                    ids.append(feature.id())
    return attributes, ids


def addFields(layer, names, types):
    res = False
    if layer:
        provider = layer.dataProvider()
        caps = provider.capabilities()
        if caps & QgsVectorDataProvider.AddAttributes:
            fields = provider.fields()
            for i, name in enumerate(names):
                #add new field if it doesn't exist
                if fields.indexFromName(name) == -1:
                    res = provider.addAttributes([QgsField(name, types[i])])
        #apply changes if any made
        if res:
            layer.updateFields()
    return res


#
# Feature functions
#
def getFeaturesByListValues(layer, name, values=list):
    features = {}
    if layer:
        if fieldExists(layer, name):
            request = QgsFeatureRequest().setSubsetOfAttributes([getFieldIndex(layer, name)])
            iterator = layer.getFeatures(request)
            for feature in iterator:
                att = feature.attribute(name)
                if att in values:
                    features[feature.id()] = att
    return features


def selectFeaturesByListValues(layer, name, values=list):
    features = []
    if layer:
        if fieldExists(layer, name):
            request = QgsFeatureRequest().setSubsetOfAttributes([getFieldIndex(layer, name)])
            iterator = layer.getFeatures(request)
            for feature in iterator:
                att = feature.attribute(name)
                if att in values:
                    features.append(feature.id())
            layer.select(features)


def getFeaturesByRangeValues(layer, name, min, max):
    features = {}
    if layer:
        if fieldExists(layer, name):
            request = QgsFeatureRequest().setSubsetOfAttributes([getFieldIndex(layer, name)])
            iterator = layer.getFeatures(request)
            for feature in iterator:
                att = feature.attribute(name)
                if min <= att <= max:
                    features[feature.id()] = att
    return features


def selectFeaturesByRangeValues(layer, name, min, max):
    features = []
    if layer:
        if fieldExists(layer, name):
            request = QgsFeatureRequest().setSubsetOfAttributes([getFieldIndex(layer, name)])
            iterator = layer.getFeatures(request)
            for feature in iterator:
                att = feature.attribute(name)
                if min <= att <= max:
                    features.append(feature.id())
            layer.select(features)


def selectFeaturesByExpression(layer, expression):
    features = []
    if layer:
        request = QgsFeatureRequest().setFilterExpression(expression)
        iterator = layer.getFeatures(request)
        for feature in iterator:
            features.append(feature.id())
        layer.select(features)


def filterFeaturesByExpression(layer, expression):
    success = False
    if layer:
        try:
           success = layer.setSubsetString(expression)
        except:
            success = False
    return success


def getAllFeatures(layer):
    allfeatures = {}
    if layer:
        features = layer.getFeatures()
        allfeatures = {feature.id(): feature for feature in features}
    return allfeatures


def getAllFeatureIds(layer):
    ids = []
    if layer:
        features = layer.getFeatures()
        ids = [feature.id() for feature in features]
    return ids


def getAllFeatureSymbols(layer):
    symbols = {}
    if layer:
        renderer = layer.rendererV2()
        features = layer.getFeatures()
        for feature in features:
            symb = renderer.symbolsForFeature(feature)
            if len(symb) > 0:
                symbols = {feature.id(): symb[0].color()}
            else:
                symbols = {feature.id(): QColor(200,200,200,255)}
    return symbols


def getAllFeatureData(layer):
    data = {}
    symbols = {}
    if layer:
        renderer = layer.rendererV2()
        features = layer.getFeatures()
        for feature in features:
            data = {feature.id(): feature}
            symb = renderer.symbolsForFeature(feature)
            if len(symb) > 0:
                symbols = {feature.id(): symb[0].color()}
            else:
                symbols = {feature.id(): QColor(200,200,200,255)}
    return data, symbols


def getFeaturesByIntersection(base_layer, intersect_layer, crosses):
    features = []
    # retrieve objects to be intersected (list comprehension, more pythonic)
    intersect_geom = [QgsGeometry(feat.geometry()) for feat in intersect_layer.getFeatures()]
    # retrieve base layer objects
    base = base_layer.getFeatures()
    # should improve with spatial index for large data sets
    #index = createIndex(base_layer)
    # loop through base features and intersecting elements
    # appends if intersecting, when crosses = True
    # does the opposite if crosses = False
    for feat in base:
        append = not crosses
        base_geom = QgsGeometry(feat.geometry())
        for intersect in intersect_geom:
            if base_geom.intersects(intersect):
                append = crosses
                break
        if append:
            features.append(feat)
    return features


def getFeaturesIntersections(base_layer, intersect_layer):
    intersections = []
    # retrieve objects to be intersected (list comprehension, more pythonic)
    obstacles_geom = [QgsGeometry(feat.geometry()) for feat in intersect_layer.getFeatures()]
    # retrieve base layer objects
    base = base_layer.getFeatures()
    # loop through base features and intersecting elements
    for feat in base:
        base_geom = QgsGeometry(feat.geometry())
        for obst in obstacles_geom:
            if base_geom.intersects(obst):
                intersections.append(base_geom.intersection(obst))
    return intersections


def selectFeaturesByIntersection(base_layer, intersect_layer, crosses):
    features = []
    # retrieve objects to be intersected (list comprehension, more pythonic)
    obstacles_geom = [QgsGeometry(feat.geometry()) for feat in intersect_layer.getFeatures()]
    # retrieve base layer objects
    base = base_layer.getFeatures()
    # loop through base features and intersecting elements
    for feat in base:
        append = not crosses
        base_geom = QgsGeometry(feat.geometry())
        for obst in obstacles_geom:
            if base_geom.intersects(obst):
                append = crosses
                break
        if append:
            features.append(feat.id())
    base_layer.select(features)


#
# Canvas functions
#
# Display a message in the QGIS canvas
def showMessage(iface, msg, type='Info', lev=1, dur=2):
    iface.messageBar().pushMessage(type,msg,level=lev,duration=dur)


def getCanvasColour(iface):
    colour = iface.mapCanvas().canvasColor()
    return colour


def printCanvas(filename=''):
    if not filename:
        filename = 'print_map.pdf'

    # image size parameters
    imageWidth_mm = 10000
    imageHeight_mm = 10000
    dpi = 300

    map_settings = self.iface.mapCanvas().mapSettings()
    c = QgsComposition(map_settings)
    c.setPaperSize(imageWidth_mm, imageHeight_mm)
    c.setPrintResolution(dpi)

    x, y = 0, 0
    w, h = c.paperWidth(), c.paperHeight()
    composerMap = QgsComposerMap(c, x ,y, w, h)
    composerMap.setBackgroundEnabled(True)
    c.addItem(composerMap)

    dpmm = dpi / 25.4
    width = int(dpmm * c.paperWidth())
    height = int(dpmm * c.paperHeight())

    # create output image and initialize it
    image = QtGui.QImage(QtCore.QSize(width, height), QtGui.QImage.Format_ARGB32)
    image.setDotsPerMeterX(dpmm * 1000)
    image.setDotsPerMeterY(dpmm * 1000)
    imagePainter = QtGui.QPainter(image)

    c.setPlotStyle(QgsComposition.Print)
    c.renderPage( imagePainter, 0 )
    imagePainter.end()

    image.save(filename, "PDF")

#
# Network functions
#
def makeUndirectedGraph(network_layer, points=list):
    graph = None
    tied_points = []
    if network_layer:
        director = QgsLineVectorLayerDirector(network_layer, -1, '', '', '', 3)
        properter = QgsDistanceArcProperter()
        director.addProperter(properter)
        builder = QgsGraphBuilder(network_layer.crs())
        tied_points = director.makeGraph(builder, points)
        graph = builder.graph()
    return graph, tied_points


def makeDirectedGraph(network_layer, points=list, direction_field=-1, one_way='', reverse_way='', two_way='', default_direction=3):
    graph = None
    tied_points = []
    if network_layer:
        director = QgsLineVectorLayerDirector(network_layer, direction_field, one_way, reverse_way, two_way, default_direction)
        properter = QgsDistanceArcProperter()
        director.addProperter(properter)
        builder = QgsGraphBuilder(network_layer.crs())
        tied_points = director.makeGraph(builder, points)
        graph = builder.graph()
    return graph, tied_points


def calculateRouteTree(graph, tied_points, origin, destination, impedance=0):
    points = []
    if tied_points:
        try:
            from_point = tied_points[origin]
            to_point = tied_points[destination]
        except:
            return points

        # analyse graph
        if graph:
            form_id = graph.findVertex(from_point)
            tree = QgsGraphAnalyzer.shortestTree(graph, form_id, impedance)
            form_id = tree.findVertex(from_point)
            to_id = tree.findVertex(to_point)

            # iterate to get all points in route
            if to_id == -1:
                pass
            else:
                while form_id != to_id:
                    l = tree.vertex(to_id).inArc()
                    if len(l) == 0:
                        break
                    e = tree.arc(l[0])
                    points.insert(0, tree.vertex(e.inVertex()).point())
                    to_id = e.outVertex()

                points.insert(0, from_point)

    return points


def calculateRouteDijkstra(graph, tied_points, origin, destination, impedance=0):
    points = []
    if tied_points:
        try:
            from_point = tied_points[origin]
            to_point = tied_points[destination]
        except:
            return points

        # analyse graph
        if graph:
            from_id = graph.findVertex(from_point)
            to_id = graph.findVertex(to_point)

            (tree, cost) = QgsGraphAnalyzer.dijkstra(graph, from_id, impedance)

            if tree[to_id] == -1:
                pass
            else:
                curPos = to_id
                while curPos != from_id:
                    points.append(graph.vertex(graph.arc(tree[curPos]).inVertex()).point())
                    curPos = graph.arc(tree[curPos]).outVertex()

                points.append(from_point)
                points.reverse()

    return points


def calculateServiceArea(graph, tied_points, origin, cutoff, impedance=0):
    points = {}
    if tied_points:
        try:
            from_point = tied_points[origin]
        except:
            return points

        # analyse graph
        if graph:
            from_id = graph.findVertex(from_point)

            (tree, cost) = QgsGraphAnalyzer.dijkstra(graph, from_id, impedance)

            i = 0
            while i < len(cost):
                if cost[i] > cutoff and tree[i] != -1:
                    outVertexId = graph.arc(tree[i]).outVertex()
                    if cost[outVertexId] < cutoff:
                        points[str(i)]=((graph.vertex(i).point()),cost)
                i += 1

    return points

#
# General functions
#
def getLastDir(tool_name=''):
    path = ''
    settings = QtCore.QSettings(tool_name,"")
    settings.value("lastUsedDir",str(""))
    return path


def setLastDir(filename, tool_name=''):
    path = QtCore.QFileInfo(filename).absolutePath()
    settings = QtCore.QSettings(tool_name,"")
    settings.setValue("lastUsedDir", str(unicode(path)))


# check if a text string is of numeric type
def isNumeric(txt):
    try:
        int(txt)
        return True
    except ValueError:
        try:
            long(txt)
            return True
        except ValueError:
            try:
                float(txt)
                return True
            except ValueError:
                return False


# convert a text string to a numeric value, if possible
def convertNumeric(txt):
    try:
        value = int(txt)
    except ValueError:
        try:
            value = long(txt)
        except ValueError:
            try:
                value = float(txt)
            except ValueError:
                value = ''
    return value


def truncateNumber(num,digits=9):
    if isNumeric(num):
        truncated = str(num)
        if '.' in truncated:
            truncated = truncated[:digits]
            truncated = truncated.rstrip('0').rstrip('.')
        return convertNumeric(truncated)


# Function to create a spatial index for QgsVectorDataProvider
def createIndex(layer):
    provider = layer.dataProvider()
    caps = provider.capabilities()
    if caps & QgsVectorDataProvider.CreateSpatialIndex:
        feat = QgsFeature()
        index = QgsSpatialIndex()
        fit = provider.getFeatures()
        while fit.nextFeature(feat):
            index.insertFeature(feat)
        return index
    else:
        return None


def drawRouteBand(canvas, points, colour='red', width=3):
    # check QColor.colorNames() for valid colour names
    rb = QgsRubberBand(canvas, False)
    try:
        rb.setColor(QtGui.QColor(colour))
    except:
        rb.setColor(QtCore.Qt.red)
    rb.setWidth(width)
    for pnt in points:
        rb.addPoint(pnt)
    rb.show()


#------------------------------
# General database functions
#------------------------------
def getDBLayerConnection(layer):
    provider = layer.providerType()
    uri = QgsDataSourceURI(layer.dataProvider().dataSourceUri())
    if provider == 'spatialite':
        path = uri.database()
        connection_object = getSpatialiteConnection(path)
    elif provider == 'postgres':
        connection_object = pgsql.connect(uri.connectionInfo().encode('utf-8'))
    else:
        connection_object = None
    return connection_object

def getSpatialiteConnection(path):
    try:
        connection=sqlite.connect(path)
    except sqlite.OperationalError, error:
        #pop_up_error("Unable to connect to selected database: \n %s" % error)
        connection = None
    return connection

def getDBLayerTableName(layer):
    uri = QgsDataSourceURI(layer.dataProvider().dataSourceUri())
    return uri.table()


def getDBLayerGeometryColumn(layer):
    uri = QgsDataSourceURI(layer.dataProvider().dataSourceUri())
    return uri.geometryColumn()


def getDBLayerPrimaryKey(layer):
    uri = QgsDataSourceURI(layer.dataProvider().dataSourceUri())
    return uri.key()


#------------------------------
# Layer creation functions
#------------------------------
def createTempLayer(name, geometry, srid, attributes, types):
    #geometry can be 'POINT', 'LINESTRING' or 'POLYGON' or the 'MULTI' version of the previous
    vlayer = QgsVectorLayer('%s?crs=EPSG:%s'% (geometry, srid), name, "memory")
    provider = vlayer.dataProvider()
    #create the required fields
    if attributes:
        vlayer.startEditing()
        fields = []
        for i, att in enumerate(attributes):
            fields.append(QgsField(att, types[i]))
        # add the fields to the layer
        try:
            provider.addAttributes(fields)
        except:
            return None
        vlayer.commitChanges()
    return vlayer


def loadTempLayer(layer):
    QgsMapLayerRegistry.instance().addMapLayer(layer)


def insertTempFeatures(layer, coordinates, attributes):
    provider = layer.dataProvider()
    geometry_type = provider.geometryType()
    for i, geom in enumerate(coordinates):
        fet = QgsFeature()
        if geometry_type == 1:
            fet.setGeometry(QgsGeometry.fromPoint(geom))
        elif geometry_type == 2:
            fet.setGeometry(QgsGeometry.fromPolyline(geom))
        # in the case of polygons, instead of coordinates we insert the geometry
        elif geometry_type == 3:
            fet.setGeometry(geom)
        if attributes:
            fet.setAttributes(attributes[i])
        provider.addFeatures([fet])
    provider.updateExtents()


def createTempLayerFull(name, srid, attributes, types, values, coords):
    # create an instance of a memory vector layer
    type = ''
    if len(coords) == 2: type = 'Point'
    elif len(coords) == 4: type = 'LineString'
    vlayer = QgsVectorLayer('%s?crs=EPSG:%s'% (type, srid), name, "memory")
    provider = vlayer.dataProvider()
    #create the required fields
    fields = []
    for i, name in enumerate(attributes):
        fields.append(QgsField(name, types[i]))
    # add the fields to the layer
    vlayer.startEditing()
    try:
        provider.addAttributes(fields)
    except:
        return None
    # add features by iterating the values
    features = []
    for i, val in enumerate(values):
        feat = QgsFeature()
        # add geometry
        try:
            if type == 'Point':
                feat.setGeometry(QgsGeometry.fromPoint([QgsPoint(float(val[coords[0]]),float(val[coords[1]]))]))
            elif type == 'LineString':
                feat.setGeometry(QgsGeometry.fromPolyline([QgsPoint(float(val[coords[0]]),float(val[coords[1]])),
                                                           QgsPoint(float(val[coords[2]]),float(val[coords[3]]))]))
        except:
            pass
        # add attribute values
        feat.setAttributes(list(val))
        features.append(feat)
    # add the features to the layer
    try:
        provider.addFeatures(features)
    except:
        return None

    vlayer.commitChanges()
    vlayer.updateExtents()
    if not vlayer.isValid():
        print "Layer failed to load!"
        return None
    return vlayer


#---------------------------------------------
# Shape file specific functions
#---------------------------------------------
def listShapeFolders():
    # get folder name and path of open layers
    res = dict()
    res['idx'] = 0
    res['name'] = []
    res['path'] = []
    layers = getRegistryLayers('all', 'ogr')
    for layer in layers:
        provider = layer.dataProvider()
        if layer.storageType() == 'ESRI Shapefile':
            path = os.path.dirname(layer.dataProvider().dataSourceUri())
            try:
                idx = res['path'].index(path)
            except:
                res['name'].append(os.path.basename(os.path.normpath(path))) #layer.name()
                res['path'].append(path)
            #for the file name: os.path.basename(uri).split('|')[0]
    #case: no folders available
    if len(res['name']) < 1:
        res = None
    #return the result even if empty
    return res


def testShapeFileExists(path, name):
    filename = path+"/"+name+".shp"
    exists = os.path.isfile(filename)
    return exists


def copyLayerToShapeFile(layer, path, name):
    #Get layer provider
    provider = layer.dataProvider()
    filename = path+"/"+name+".shp"
    fields = provider.fields()
    if layer.hasGeometryType():
        geometry = layer.wkbType()
    else:
        geometry = None
    srid = layer.crs()
    # create an instance of vector file writer, which will create the vector file.
    writer = QgsVectorFileWriter(filename, "CP1250", fields, geometry, srid, "ESRI Shapefile")
    if writer.hasError() != QgsVectorFileWriter.NoError:
        print "Error when creating shapefile: ", writer.hasError()
        return None
    # add features by iterating the values
    for feat in layer.getFeatures():
        writer.addFeature(feat)
    # delete the writer to flush features to disk
    del writer
    # open the newly created file
    vlayer = QgsVectorLayer(filename, name, "ogr")
    if not vlayer.isValid():
        print "Layer failed to load!"
        return None
    return vlayer


def createShapeFileLayer(path, name, srid, attributes, types, geometrytype):
    # create new empty layer with given attributes
    # todo: created table has no attributes. not used
    # use createShapeFileFullLayer instead
    filename = path+"/"+name+".shp"
    #create the required fields
    fields = QgsFields()
    for i, attr in enumerate(attributes):
        fields.append(QgsField(attr, types[i]))
    # create an instance of vector file writer, which will create the vector file.
    writer = None
    if 'point' in geometrytype.lower():
        writer = QgsVectorFileWriter(filename, "CP1250", fields, QGis.WKBPoint, srid, "ESRI Shapefile")
    elif 'line' in geometrytype.lower():
        writer = QgsVectorFileWriter(filename, "CP1250", fields, QGis.WKBLineString, srid, "ESRI Shapefile")
    elif 'polygon' in geometrytype.lower():
        writer = QgsVectorFileWriter(filename, "CP1250", fields, QGis.WKBPolygon, srid, "ESRI Shapefile")
    if writer.hasError() != QgsVectorFileWriter.NoError:
        print "Error when creating shapefile: ", writer.hasError()
        return None
    # delete the writer to flush features to disk (optional)
    del writer
    # open the newly created file
    vlayer = QgsVectorLayer(filename, name, "ogr")
    if not vlayer.isValid():
        print "Layer failed to open!"
        return None
    return vlayer


def createShapeFileFullLayer(path, name, srid, attributes, types, values, coords):
    # create new layer with given attributes and data, including geometry (point and lines only)
    filename = path+"/"+name+".shp"
    #create the required fields
    fields = QgsFields()
    for i, attr in enumerate(attributes):
        fields.append(QgsField(attr, types[i]))
    # create an instance of vector file writer, which will create the vector file.
    writer = None
    if len(coords) == 2:
        type = 'point'
        writer = QgsVectorFileWriter(filename, "CP1250", fields, QGis.WKBPoint, srid, "ESRI Shapefile")
    elif len(coords) == 4:
        type = 'line'
        writer = QgsVectorFileWriter(filename, "CP1250", fields, QGis.WKBLineString, srid, "ESRI Shapefile")
    if writer.hasError() != QgsVectorFileWriter.NoError:
        print "Error when creating shapefile: ", writer.hasError()
        return None
    # add features by iterating the values
    feat = QgsFeature()
    for i, val in enumerate(values):
        # add geometry
        try:
            if type == 'point':
                feat.setGeometry(QgsGeometry.fromPoint([QgsPoint(float(val[coords[0]]),float(val[coords[1]]))]))
            elif type == 'line':
                feat.setGeometry(QgsGeometry.fromPolyline([QgsPoint(float(val[coords[0]]),float(val[coords[1]])),
                                                           QgsPoint(float(val[coords[2]]),float(val[coords[3]]))]))
        except: pass
        # add attributes
        attrs = []
        for j, attr in enumerate(attributes):
            attrs.append(val[j])
        feat.setAttributes(attrs)
        writer.addFeature(feat)
    # delete the writer to flush features to disk (optional)
    del writer
    # open the newly created file
    vlayer = QgsVectorLayer(filename, name, "ogr")
    if not vlayer.isValid():
        print "Layer failed to load!"
        return None
    return vlayer


def addShapeFileAttributes(layer, attributes, types, values):
    # add attributes to an existing layer
    attributes_pos = dict()
    res = False
    if layer:
        provider = layer.dataProvider()
        caps = provider.capabilities()
        res = False
        if caps & QgsVectorDataProvider.AddAttributes:
            fields = provider.fields()
            count = fields.count()
            for i, name in enumerate(attributes):
                #add new field if it doesn't exist
                if fields.indexFromName(name) == -1:
                    res = provider.addAttributes([QgsField(name, types[i])])
                    # keep position of attributes that are added, since name can change
                    attributes_pos[i] = count
                    count += 1
            #apply changes if any made
            if res:
                layer.updateFields()
        # update attribute values by iterating the layer's features
        res = False
        if caps & QgsVectorDataProvider.ChangeAttributeValues:
            #fields = provider.fields() #the fields must be retrieved again after the updateFields() method
            iter = layer.getFeatures()
            for i, feature in enumerate(iter):
                fid = feature.id()
                #to update the features the attribute/value pairs must be converted to a dictionary for each feature
                attrs = {}
                for j in attributes_pos.iterkeys():
                    field_id = attributes_pos[j]
                    val = values[i][j]
                    attrs.update({field_id: val})
                #update the layer with the corresponding dictionary
                res = provider.changeAttributeValues({fid: attrs})
            #apply changes if any made
            if res:
                layer.updateFields()
    return res

