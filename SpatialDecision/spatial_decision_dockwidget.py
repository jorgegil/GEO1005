# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SpatialDecisionDockWidget
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

from PyQt4 import QtGui, QtCore, uic
from qgis.core import *
from qgis.networkanalysis import *

import os
import os.path
import random

from . import utility_functions as uf


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'spatial_decision_dockwidget_base.ui'))


class SpatialDecisionDockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = QtCore.pyqtSignal()
    #custom signals
    updateAttribute = QtCore.pyqtSignal(str)

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(SpatialDecisionDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # define globals
        self.iface = iface
        self.canvas = self.iface.mapCanvas()

        # set up GUI operation signals
        # data
        self.iface.projectRead.connect(self.updateLayers)
        self.iface.newProjectCreated.connect(self.updateLayers)
        self.openScenarioButton.clicked.connect(self.openScenario)
        self.saveScenarioButton.clicked.connect(self.saveScenario)
        self.selectLayerCombo.activated.connect(self.setSelectedLayer)
        self.selectAttributeCombo.activated.connect(self.setSelectedAttribute)

        # analysis
        self.graph = QgsGraph()
        self.tied_points = []
        self.setNetworkButton.clicked.connect(self.buildNetwork)
        self.shortestRouteButton.clicked.connect(self.calculateRoute)

        # visualisation

        # reporting
        self.featureCounterUpdateButton.clicked.connect(self.updateNumberFeatures)
        self.saveMapButton.clicked.connect(self.saveMap)
        self.saveMapPathButton.clicked.connect(self.selectFile)

        # set current UI restrictions


        # initialisation
        self.updateLayers()

        #run simple tests


    def closeEvent(self, event):
        # disconnect interface signals
        self.iface.projectRead.disconnect(self.updateLayers)
        self.iface.newProjectCreated.disconnect(self.updateLayers)

        self.closingPlugin.emit()
        event.accept()

#######
#    Data functions
#######
    def openScenario(self,filename=""):
        scenario_open = False
        scenario_file = os.path.join('/Users/jorge/github/GEO1005','sample_data','time_test.qgs')
        # check if file exists
        if os.path.isfile(scenario_file):
            self.iface.addProject(scenario_file)
            scenario_open = True
        else:
            last_dir = uf.getLastDir("SDSS")
            new_file = QtGui.QFileDialog.getOpenFileName(self, "", last_dir, "(*.qgs)")
            if new_file:
                self.iface.addProject(new_file)
                scenario_open = True
        if scenario_open:
            self.updateLayers()

    def saveScenario(self):
        self.iface.actionSaveProject()

    def updateLayers(self):
        layers = uf.getLegendLayers(self.iface, 'all', 'all')
        self.selectLayerCombo.clear()
        self.base_layer = None
        if layers:
            layer_names = uf.getLayersListNames(layers)
            self.selectLayerCombo.addItems(layer_names)
            self.base_layer = uf.getLegendLayerByName(self.iface,layer_names[0])
        self.updateAttributes(self.base_layer)

    def setSelectedLayer(self):
        layer_name = self.selectLayerCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        self.updateAttributes(layer)

    def getSelectedLayer(self):
        layer_name = self.selectLayerCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        return layer

    def updateAttributes(self, layer):
        self.selectAttributeCombo.clear()
        if layer:
            fields = uf.getFieldNames(layer)
            self.selectAttributeCombo.addItems(fields)

    def setSelectedAttribute(self):
        field_name = self.selectAttributeCombo.currentText()
        self.updateAttribute.emit(field_name)

    def getSelectedAttribute(self):
        field_name = self.selectAttributeCombo.currentText()
        return field_name

#######
#    Analysis functions
#######
    def getNetwork(self):
        roads_layer = self.getSelectedLayer()
        # see if there is an obstacles layer to subtract roads from the network
        obstacles_layer = uf.getLegendLayerByName(self.iface, "Obstacles")
        if obstacles_layer:
            # retrieve roads outside obstacles (inside = False)
            features = uf.getFeaturesByIntersection(roads_layer, obstacles_layer, False)
            # add these roads to a new temporary layer
            road_network = uf.createTempLayer('Temp_Network','LINESTRING',roads_layer.crs().postgisSrid(),[],[])
            road_network.dataProvider().addFeatures(features)
        else:
            road_network = roads_layer
        return road_network

    def buildNetwork(self):
        self.network_layer = self.getNetwork()
        # get the points to be used as origin and destination
        # in this case gets the centroid of the selected features
        selected_sources = self.getSelectedLayer().selectedFeatures()
        source_points = [feature.geometry().centroid().asPoint() for feature in selected_sources]
        # build the graph including these points
        if len(source_points) > 1:
            self.graph, self.tied_points = uf.makeUndirectedGraph(self.network_layer, source_points)
            # the tied points are the new source_points on the graph
            if self.graph and self.tied_points:
                print "network is built for %s points" % len(self.tied_points)

    def calculateRoute(self):
        # origin and destination must be in the set of tied_points
        options = len(self.tied_points)
        if options > 1:
            # origin and destination are given as an index in the tied_points list
            origin = 0
            destination = random.randint(1,options-1)
            # calculate the shortest path for the given origin and destination
            path = uf.calculateRouteDijkstra(self.graph, self.tied_points, origin, destination)
            #create a layer to store the route results
            routes_layer = uf.getLegendLayerByName(self.iface, "Routes")
            if not routes_layer:
                attribs = ['id','distance']
                types = [QtCore.QVariant.String,QtCore.QVariant.Double]
                routes_layer = uf.createTempLayer('Routes','LINESTRING',self.network_layer.crs().postgisSrid(), attribs, types)
                uf.loadTempLayer(routes_layer)
            uf.insertTempFeatures(routes_layer, [path], [['testing',100.00]])
            self.refreshCanvas(routes_layer)

    def refreshCanvas(self, layer):
        if self.canvas.isCachingEnabled():
            layer.setCacheImage(None)
        else:
            self.canvas.refresh()

#######
#    Visualisation functions
#######



#######
#    Reporting functions
#######
    def updateNumberFeatures(self):
        if self.base_layer:
            count = self.base_layer.featureCount()
            self.featureCounterLCD.display(count)

    def selectFile(self):
        last_dir = uf.getLastDir("SDSS")
        path = QtGui.QFileDialog.getSaveFileName(self, "Save map file", last_dir, "PNG (*.png)")
        if path.strip()!="":
            path = unicode(path)
            uf.setLastDir(path,"SDSS")
            #name = os.path.basename(path)
            self.saveMapPathEdit.setText(path)

    def saveMap(self):
        filename = self.saveMapPathEdit.text()
        if filename != '':
            self.canvas.saveAsImage(filename,None,"PNG")

    def updateReport(self,report):
        pass


