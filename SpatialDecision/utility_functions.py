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

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *

from pyspatialite import dbapi2 as sqlite
import psycopg2 as pgsql
import numpy as np

import os.path
import math
import sys
from itertools import izip_longest

#
# Layer functions
#
def getVectorLayers(geom='all', provider='all'):
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


def getLayersListNames(layerslist):
    layer_names = [layer.name() for layer in layerslist]
    return layer_names


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
        types = (QVariant.Int, QVariant.LongLong, QVariant.Double, QVariant.UInt, QVariant.ULongLong)
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
def getFeaturesListValues(layer, name, values=list):
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


def getFeaturesRangeValues(layer, name, min, max):
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


#
# Canvas functions
#
# Display a message in the QGIS canvas
def showMessage(iface, msg, type='Info', lev=1, dur=2):
    iface.messageBar().pushMessage(type,msg,level=lev,duration=dur)


def getCanvasColour(iface):
    colour = iface.mapCanvas().canvasColor()
    return colour


#
# General functions
#
# Display an error message via Qt message box

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


# round number based on simple rules of thumb
# for suggestion on the best number to round
# some principles found here: http://www.tc3.edu/instruct/sbrown/stat/rounding.htm
def roundNumber(num):
    if isNumeric(num):
        if isinstance(num, basestring):
            convertNumeric(num)
        rounded = num
        if num > 100 or num < -100:
            rounded = round(num,1)
        elif (1 < num <= 100) or (-1 > num >= -100):
            rounded = round(num,2)
        elif (0.01 < num <= 1) or (-0.01 > num >= -1):
            rounded = round(num,4)
        else:
            rounded = round(num,6)
        return rounded


def truncateNumber(num,digits=9):
    if isNumeric(num):
        truncated = str(num)
        if '.' in truncated:
            truncated = truncated[:digits]
            truncated = truncated.rstrip('0').rstrip('.')
        return convertNumeric(truncated)


def calcGini(values):
    """
    Calculate gini coefficient, using transformed formula, like R code in 'ineq'
    :param values: list of numeric values
    :return: gini coefficient
    """
    S = sorted(values)
    N = len(values)
    T = sum(values)
    P = sum(xi * (i+1) for i,xi in enumerate(S))
    G = 2.0 * P/(N * T)
    gini = G - 1 - (1./N)
    return gini


def calcBins(values, minbins=3, maxbins=128):
    """Calculates the best number of bins for the given values
    Uses the Freedman-Diaconis modification of Scott's rule.
    """
    nbins = 1
    # prepare data
    if not isinstance(values, np.ndarray):
        values = np.array(values)
    # calculate stats
    range = np.nanmax(values)-np.nanmin(values)
    IQR = np.percentile(values,75)-np.percentile(values,25)
    # calculate bin size
    bin_size = 2 * IQR * np.size(values)**(-1.0/3)
    # calculate number of bins
    if bin_size > 0:
        nbins = range / bin_size

    nbins = max(minbins, min(maxbins, int(nbins)))

    return nbins


#------------------------------
# Creation functions
#------------------------------
def createTempLayer(name, srid, attributes, types, values, coords):
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
                feat.setGeometry(QgsGeometry.fromPolyline([QgsPoint(float(val[coords[0]]),float(val[coords[1]])), \
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


# Function to build a topology from line layer
def buildTopology(self, axial, unlinks, links):
    index = createIndex(axial)
    axial_links = []
    unlinks_list = []
    links_list = []
    # get unlinks pairs
    if unlinks:
        features = unlinks.getFeatures(QgsFeatureRequest().setSubsetOfAttributes(['line1','line2'],unlinks.pendingFields()))
        for feature in features:
            unlinks_list.append((feature.attribute('line1'),feature.attribute('line2')))
    # get links pairs
    if links:
        features = links.getFeatures(QgsFeatureRequest().setSubsetOfAttributes(['line1','line2'],links.pendingFields()))
        for feature in features:
            links_list.append((feature.attribute('line1'),feature.attribute('line2')))
    # get axial intersections
    features = axial.getFeatures(QgsFeatureRequest().setSubsetOfAttributes([]))
    for feature in features:
        geom = feature.geometry()
        id = feature.id()
        box = geom.boundingBox()
        request = QgsFeatureRequest()
        if index:
            # should be faster to retrieve from index (if available)
            ints = index.intersects(box)
            request.setFilterFids(ints)
        else:
            # can retrieve objects using bounding box
            request.setFilterRect(box)
        request.setSubsetOfAttributes([])
        targets = axial.getFeatures(request)
        for target in targets:
            geom_b = target.geometry()
            id_b = target.id()
            if not id_b == id and geom.intersects(geom_b):
                # check if in the unlinks
                if (id,id_b) not in unlinks_list and (id,id_b) not in unlinks_list:
                    axial_links.append((id,id_b))
    return axial_links


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


def testSameDatabase(layers):
    #check if the layers are in the same database
    if len(layers) > 1:
        database = []
        for layer in layers:
            database.append(QgsDataSourceURI(layer.dataProvider().dataSourceUri()).database())
        if len(list(set(database))) > 1:
            return False
        else:
            return True
    return True


def getDBLayerTableName(layer):
    uri = QgsDataSourceURI(layer.dataProvider().dataSourceUri())
    return uri.table()


def getDBLayerGeometryColumn(layer):
    uri = QgsDataSourceURI(layer.dataProvider().dataSourceUri())
    return uri.geometryColumn()


def getDBLayerPrimaryKey(layer):
    uri = QgsDataSourceURI(layer.dataProvider().dataSourceUri())
    return uri.key()



#---------------------------------------------
# Shape file specific functions
#---------------------------------------------
def listShapeFolders():
    # get folder name and path of open layers
    res = dict()
    res['idx'] = 0
    res['name'] = []
    res['path'] = []
    layers = getVectorLayers('all', 'ogr')
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


def createShapeFileFullLayer(path, name, srid, attributes, types, values, coords):
    # create new layer with given attributes
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
                feat.setGeometry(QgsGeometry.fromPolyline([QgsPoint(float(val[coords[0]]),float(val[coords[1]])), \
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


def createShapeFileLayer(path, name, srid, attributes, types, geometrytype):
    # create new layer with given attributes
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


def insertShapeFileValues(layer, attributes, values, coords):
    # get the geometry type
    # todo: not working yet. attribute ids must match those from table.
    # use createShapeFileFullLayer instead
    res = False
    if layer:
        geom_type = layer.geometryType()
        provider = layer.dataProvider()
        caps = provider.capabilities()
        if caps & QgsVectorDataProvider.AddFeatures:
            # add features by iterating the values
            features = []
            for val in values:
                feat = QgsFeature()
                # add geometry
                try:
                    if geom_type in (0,3):
                        feat.setGeometry(QgsGeometry.fromPoint([QgsPoint(float(val[coords[0]]),float(val[coords[1]]))]))
                    elif geom_type in (1,4):
                        feat.setGeometry(QgsGeometry.fromPolyline([QgsPoint(float(val[coords[0]]),float(val[coords[1]])), \
                                                                   QgsPoint(float(val[coords[2]]),float(val[coords[3]]))]))
                except:
                    pass
                # add attributes
                for i, x in enumerate(val):
                    feat.addAttribute(i, x)
                features.append(feat)
            res, outFeats = provider.addFeatures(features)
            layer.updateFields()
        else:
            res = False
    else:
        res = False
    return res


def insertShapeFileGeometry(path, name, srid, geometry, attributes=None, values=None):
    # newfeature: function to insert new geometry features (and attributes) in shapefile
    pass


def addShapeFileAttributes(layer, attributes, types, values):
    # add attributes to the layer
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


#---------------------------------------------
# PostGIS database specific functions
#---------------------------------------------
# postgis geometry types
# 1 point; 2 line; 3 polygon; 4 multipoint; 5 multiline; 6 multipolygon

def listPostgisConnections():
    """ Retrieve a list of PostgreSQL connection names
    :return: connections - list of strings
    """
    settings = QSettings()
    settings.beginGroup('/PostgreSQL/connections')
    connections = [unicode(item) for item in settings.childGroups()]
    return connections


def getPostgisSelectedConnection():
    """

    :return:
    """
    #try to select directly the last opened dataBase
    try:
        settings = QSettings()
        last_db = settings.value(u'/PostgreSQL/connections/selected')
    except:
        last_db = ''
    return last_db


def getPostgisConnectionSettings():
    """Return all PostGIS connection settings stored in QGIS
    :return: connection dict() with name and other settings
    """
    con_settings = []
    settings = QSettings()
    settings.beginGroup('/PostgreSQL/connections')
    for item in settings.childGroups():
        con = dict()
        con['name'] = unicode(item)
        con['host'] = unicode(settings.value(u'%s/host' % unicode(item)))
        con['port'] = unicode(settings.value(u'%s/port' % unicode(item)))
        con['database'] = unicode(settings.value(u'%s/database' % unicode(item)))
        con['username'] = unicode(settings.value(u'%s/username' % unicode(item)))
        con['password'] = unicode(settings.value(u'%s/password' % unicode(item)))
        con_settings.append(con)
    settings.endGroup()
    if len(con_settings) < 1:
        con_settings = None
    return con_settings


def createPostgisConnectionSetting(name, connection=None):
    """

    :param name:
    :param connection:
    :return:
    """
    settings=QSettings()
    settings.beginGroup('/PostgreSQL/connections')
    if connection and isinstance(connection, dict):
        if 'host' in connection:
            settings.setValue(u'%s/host' % name,u'%s' % connection['host'])
        if 'port' in connection:
            settings.setValue(u'%s/port' % name,u'%s' % connection['port'])
        if 'dbname' in connection:
            settings.setValue(u'%s/database' % name,u'%s' % connection['dbname'])
        if 'user' in connection:
            settings.setValue(u'%s/saveUsername' % name,u'%s' % "true")
            settings.setValue(u'%s/username' % name,u'%s' % connection['user'])
        if 'password' in connection:
            settings.setValue(u'%s/savePassword' % name,u'%s' % "true")
            settings.setValue(u'%s/password' % name,u'%s' % connection['password'])
    settings.endGroup()


def getPostgisConnection(name):
    """

    :param name:
    :return:
    """
    con_str = getPostgisConnectionString(name)
    try:
        connection=pgsql.connect(con_str)
    except pgsql.Error, e:
        print e.pgerror
        connection = None
    return connection


def getPostgisConnectionString(name):
    """

    :param name:
    :return:
    """
    connection = ''
    settings = QSettings()
    settings.beginGroup('/PostgreSQL/connections/%s'%name)
    for item in settings.allKeys():
        if item in ('host','port','password'):
            connection += "%s='%s' " % (item, settings.value(item))
        elif item == 'database':
            connection += "dbname='%s' " % settings.value(item)
        elif item == 'username':
            connection += "user='%s' " % settings.value(item)
    return connection


def executePostgisQuery(connection, query, params='',commit=False):
    """Execute query (string) with given parameters (tuple)
    (optionally perform commit to save Db)
    :return: result set [header,data] or [error] error
    """
    query = unicode(query)
    header = []
    data = []
    error = ''
    cursor = connection.cursor()
    try:
        cursor.execute(query, params)
        if cursor.description is not None:
            header = [item[0] for item in cursor.description]
            data = cursor.fetchall()
        if commit:
            connection.commit()
    except pgsql.Error, e:
        error = e.pgerror
        connection.rollback()
    cursor.close()
    #return the result even if empty
    return header, data, error


def listPostgisSchemas(connection):
    schemas = []
    query = """SELECT schema_name from information_schema.schemata;"""
    header, data, error = executePostgisQuery(connection, query)
    if data:
        # only extract user schemas
        for schema in data:
            if schema[0] not in ('topology', 'information_schema') and schema[0][:3] != 'pg_':
                schemas.append(schema[0])
    return schemas


def getPostgisConnectionInfo(layer):
    info = dict()
    if layer:
        provider = layer.dataProvider()
        if provider.name() == 'postgres':
            uri = QgsDataSourceURI(provider.dataSourceUri())
            info['host'] = uri.host()
            info['port'] = uri.port()
            info['dbname'] = uri.database()
            info['user'] = uri.username()
            info['password'] = uri.password()
            connection_settings = getPostgisConnectionSettings()
            for connection in connection_settings:
                if connection['database'] == info['dbname']:
                    info['name'] = connection['name']
                    break
    return info


def getPostgisLayerInfo(layer):
    info = dict()
    if layer:
        provider = layer.dataProvider()
        if provider.name() == 'postgres':
            uri = QgsDataSourceURI(provider.dataSourceUri())
            info['database'] = uri.database()
            info['schema'] = uri.schema()
            info['table'] = uri.table()
            info['key'] = uri.keyColumn()
            info['geom'] = uri.geometryColumn()
            info['geomtype'] = uri.wkbType()
            info['srid'] = uri.srid()
            info['filter'] = uri.sql()
            connection_settings = getPostgisConnectionSettings()
            for connection in connection_settings:
                if connection['database'] == info['database']:
                    info['connection'] = connection['name']
                    break
    return info


def listPostgisGeomTables(connection):
    """query to read information about tables from the database
    each value returned is an element in the data list"""
    tables = []
    query = """SELECT * FROM geometry_columns ORDER BY lower(f_table_name)"""
    header, data, error = executePostgisQuery(connection, query)
    #extract information from query
    #info per table (array): name (0),geometry_column (1), geometry_column_type (2),
    # geometry_dimension (3), srid (4), spatial_index_enabled (5)
    if header != [] and data != []:
        tables = data
    #return the result even if empty
    return tables


def listPostgisColumns(connection, schema, name):
    '''query to extract the names and data types of the columns in a table of the database
    '''
    columns = {}
    query = """SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = '%s' AND table_name = '%s';""" % (schema, name)
    header, data, error = executePostgisQuery(connection, query)
    if data:
        for col in data:
            columns[col[0]] = col[1]
    #return the result even if empty
    return columns


def loadPostgisTable(connection, name, schema, table):
    """Load table (spatial or non-spatial) in QGIS
    """
    uri = QgsDataSourceURI()
    dsn = None
    for con in getPostgisConnectionSettings():
        if con['name'] == name:
            dsn = con
    if dsn:
        uri.setConnection(dsn['host'], dsn['port'], dsn['database'], dsn['username'], dsn['password'])
        geometry = getPostgisGeometryColumn(connection, schema, table)
        if geometry:
            uri.setDataSource("%s" % schema, "%s" % table, "%s" % geometry)
            layer=QgsVectorLayer(uri, "%s" % table, 'postgres')
            #add layer to canvas
            if layer.isValid():
                QgsMapLayerRegistry.instance().addMapLayer(layer)
            else:
                # newfeature: write error message?
                return False
        else:
            return False
    else:
        return False
    return True


def getPostgisLayer(connection, name, schema, table):
    """Load table in QGIS"""
    uri = QgsDataSourceURI()
    dsn = None
    for con in getPostgisConnectionSettings():
        if con['name'] == name:
            dsn = con
            break
    if dsn:
        uri.setConnection(dsn['host'], dsn['port'], dsn['database'], dsn['username'], dsn['password'])
        query = """SELECT f_geometry_column FROM geometry_columns WHERE f_table_schema = '%s' AND f_table_name = '%s'""" % (schema, table)
        header, data, error = executePostgisQuery(connection, query)
        if data != []:
            geometry = data[0][0]
            uri.setDataSource("%s" % schema, "%s" % table, "%s" % geometry)
            layer = QgsVectorLayer(uri.uri(), "%s" % table, 'postgres')
        else:
            layer = None
    else:
        layer = None
    return layer


def getPostgisGeometryColumn(connection, schema, table):
    geomname = ''
    query = """SELECT f_geometry_column FROM geometry_columns WHERE f_table_schema = '%s' AND f_table_name = '%s'""" % (schema, table)
    header, data, error = executePostgisQuery(connection, query)
    if data:
        geomname = data[0][0]
    return geomname


def createPostgisSpatialIndex(connection, schema, table, geomname):
    # create a spatial index if not present, it makes subsequent queries much faster
    index = table.lower().replace(" ","_")
    query = """CREATE INDEX %s_gidx ON "%s"."%s" USING GIST ("%s")""" % (index, schema, table, geomname)
    try:
        header, data, error = executePostgisQuery(connection, query)
    except:
        pass
    return


def testPostgisTableExists(connection, schema, name):
    '''
    :param connection:
    :param schema:
    :param name:
    :return:
    '''
    query = """SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = '%s' AND table_name = '%s' """ % (schema, name)
    header, data, error = executePostgisQuery(connection, query)
    if data:
        return True
    return False


def createPostgisTable(connection, schema, name, srid, attributes, types, geometrytype):
    res = True
    #Drop table
    header, data, error = executePostgisQuery(connection,"""DROP TABLE IF EXISTS "%s"."%s" CASCADE """ % (schema, name))
    # Get the fields
    fields = []
    for i, type in enumerate(types):
        field_type = ''
        if type in (QVariant.Char,QVariant.String): # field type is TEXT
            field_type = 'character varying'
        elif type in (QVariant.Bool,QVariant.Int,QVariant.LongLong,QVariant.UInt,QVariant.ULongLong): # field type is INTEGER
            field_type = 'integer'
        elif type == QVariant.Double: # field type is DOUBLE
            field_type = 'double precision'
        fields.append('"%s" %s'% (attributes[i],field_type))
    # Get the geometry
    geometry = False
    if geometrytype != '':
        if 'point' in geometrytype.lower():
            geometry = 'MULTIPOINT'
        elif 'line' in geometrytype.lower():
            geometry = 'MULTILINESTRING'
        elif 'polygon' in geometrytype.lower():
            geometry = 'MULTIPOLYGON'
    #Create new table
    fields = ','.join(fields)
    if len(fields) > 0:
        fields=', %s' % fields
    header, data, error = executePostgisQuery(connection,"""CREATE TABLE "%s"."%s" ( sid SERIAL NOT NULL PRIMARY KEY %s ) """ % (schema, name, fields))
    if error:
        res = False
    else:
        #Add the geometry column:
        if geometry:
            header, data, error = executePostgisQuery(connection,"""ALTER TABLE "%s"."%s" ADD COLUMN geom geometry('%s', %s) """ % (schema, name, geometry, srid))
            idx_name = name.lower().replace(" ","_")
            header,data, error = executePostgisQuery(connection,"""CREATE INDEX %s_gix ON "%s"."%s" USING GIST (geom) """ % (idx_name, schema, name))
        if error:
            res = False
    if res:
        #Commit changes to connection:
        connection.commit()
    return res


def insertPostgisValues(connection, schema, name, attributes, values, coords=None):
    res = False
    # get table srid and geometry column info
    query = """SELECT f_geometry_column,  type, srid FROM geometry_columns WHERE f_table_schema = '%s' AND f_table_name = '%s'""" % (schema, name)
    header, data, error = executePostgisQuery(connection, query)
    if data:
        geometry_attr = data[0][0]
        geometry_type = data[0][1]
        srid = data[0][2]
    else:
        res = False

    # iterate through values to populate geometry and attributes
    if values:
        res = True
        if geometry_type in ('POINT','MULTIPOINT') and len(coords) == 2:
            for val in values:
                WKT = "POINT(%s %s)" % (val[coords[0]],val[coords[1]])
                geometry_values = "ST_Multi(ST_GeomFromText('%s',%s))" % (WKT, srid)
                #Create line in DB table
                attr_values = ','.join(tuple([unicode(value) for value in val]))
                query = """INSERT INTO "%s"."%s" ("%s","%s") VALUES (%s,%s)""" % (schema, name, geometry_attr, '","'.join(attributes), geometry_values, attr_values)
                header, data, error = executePostgisQuery(connection, query, commit=False)
                if error:
                    res = False
                    break
        elif geometry_type in ('LINESTRING','MULTILINESTRING') and len(coords) == 4:
            for val in values:
                WKT = "LINESTRING(%s %s, %s %s)" % (val[coords[0]],val[coords[1]],val[coords[2]],val[coords[3]])
                geometry_values = "ST_Multi(ST_GeomFromText('%s',%s))" % (WKT, srid)
                attr_values = ','.join(tuple([unicode(value) for value in val]))
                query = """INSERT INTO "%s"."%s" ("%s","%s") VALUES (%s,%s)""" % (schema, name, geometry_attr, '","'.join(attributes), geometry_values, attr_values)
                header, data, error = executePostgisQuery(connection, query, commit=False)
                if error:
                    res = False
                    break
        else:
            for val in values:
                attr_values = ','.join(tuple([unicode(value) for value in val]))
                query = """INSERT INTO "%s"."%s" ("%s") VALUES (%s)""" % (schema, name, '","'.join(attributes), attr_values)
                header, data, error = executePostgisQuery(connection, query, commit=False)
                if error:
                    res = False
                    break
    else:
        res = False
    if res:
        #Commit changes to connection:
        connection.commit()
    return res


def addPostgisColumns(connection, schema, name, columns, types):
    # add new columns to the layer
    res = False
    fields = listPostgisColumns(connection, schema, name)
    for i, attr in enumerate(columns):
        #add new field if it doesn't exist
        if attr not in fields.keys():
            res = True
            field_type = ''
            if types[i] in (QVariant.Char,QVariant.String): # field type is TEXT
                field_type = 'character varying'
            elif types[i] in (QVariant.Bool,QVariant.Int,QVariant.LongLong,QVariant.UInt,QVariant.ULongLong): # field type is INTEGER
                field_type = 'integer'
            elif types[i] == QVariant.Double: # field type is DOUBLE
                field_type = 'double precision'
            if field_type != '':
                query = """ALTER TABLE "%s"."%s" ADD COLUMN "%s" %s""" % (schema, name, attr, field_type)
                header, data, error = executePostgisQuery(connection, query)
                if error:
                    res = False
                    break
    #Commit changes to connection:
    connection.commit()
    return res


def addPostgisAttributes(connection, schema, name, id, attributes, types, values):
    # add attributes with values to the layer
    res = addPostgisColumns(connection, schema, name, attributes, types)
    # update attribute values iterating over values
    if res:
        # identify attributes to update
        fields = listPostgisColumns(connection, schema, name)
        attr_index = {}
        attr_id = 0
        for j, attr in enumerate(attributes):
            if attr in fields.keys() and attr != id:
                attr_index[attr] = j
            elif attr == id:
                attr_id = j
        # get values for attributes
        for val in values:
            new_values = []
            for attr in attr_index.iterkeys():
                # add quotes if inserting a text value
                if types[attr_index[attr]] in (QVariant.Char,QVariant.String):
                    new_values.append(""" "%s" = '%s'""" % (attr,val[attr_index[attr]]))
                else:
                    new_values.append(""" "%s" = %s""" % (attr,val[attr_index[attr]]))
            if len(new_values) > 0:
                query = """UPDATE "%s"."%s" SET %s WHERE "%s" = %s""" % (schema, name, ', '.join(new_values), id, val[attr_id])
                header, data, error = executePostgisQuery(connection,query)
                if error:
                    res = False
                    break
        if res:
            connection.commit()
        else:
            connection.rollback()
    return res