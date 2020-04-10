# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PRW_Data_Opvrager
                                 A QGIS plugin
 Deze plugin vraagt meetgegevens op van de Prowat database.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2020-04-09
        git sha              : $Format:%H$
        copyright            : (C) 2020 by KRS-dev
        email                : kevinschuurman98@gmail.com
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
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .PRW_dialog import PRW_Data_OpvragerDialog
from qgis.core import QgsDataSourceUri, QgsCredentials

import os
import xlwt
import pandas as pd
import cx_Oracle as cora



class PRW_Data_Opvrager:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'PRW_Data_Opvrager_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&PRW')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

        # Initialize database connector variables
        self.username = None
        self.password = None
        self.dsn = None
        self.selected_layer = None
        self.database = None
        self.dateMax = None
        self.dateMin = None
        self.fileName = None
        self.outputLocation = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('PRW_Data_Opvrager', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/PRW/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'PRW Data Opvrager'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&PRW'),
                action)
            self.iface.removeToolBarIcon(action)


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = PRW_Data_OpvragerDialog()
            self.dlg.OutputLocation.setStorageMode(1)
            self.dlg.OutputLocation.setFilePath(self.dlg.OutputLocation.defaultRoot())

        settings = QSettings()
        allkeys = settings.allKeys()
        databases = [k for k in allkeys if 'database' in k]
        databaseNames = [settings.value(k) for k in databases]
        self.dlg.DatabaseComboBox.clear()
        self.dlg.DatabaseComboBox.addItems(databaseNames) 

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            self.selected_layer = self.dlg.MapLayerComboBox.currentLayer()
            self.database = self.dlg.DatabaseComboBox.currentText()
            self.dateMax = self.dlg.DateMax.date().toString('yyyy-MM-dd')
            self.dateMin = self.dlg.DateMin.date().toString('yyyy-MM-dd')
            self.fileName = self.dlg.FileName.text()
            self.outputLocation = self.dlg.OutputLocation.filePath()
            
            settings = QSettings()
            allkeys = settings.allKeys()
            allvalues = [settings.value(k) for k in allkeys]
            allsettings = dict(zip(allkeys, allvalues))
            for key, val in allsettings.items():
                if 'database' in key:
                    if val == self.database:
                        databasekey = key
            databasekey = databasekey.rstrip('database')
            selected_databasekeys = [k for k in allkeys if databasekey in k]
            host = settings.value([k for k in selected_databasekeys if 'host' in k][0])
            port = settings.value([k for k in selected_databasekeys if 'port' in k][0])
            self.username = settings.value([k for k in selected_databasekeys if 'username' in k][0])
            self.password = settings.value([k for k in selected_databasekeys if 'password' in k][0])
            self.dsn = cora.makedsn(host, port, service_name=self.database)
            
            errorMessage = None
            if self.username != None and self.password != None:
                try:
                    self.check_connection()
                    self.get_data()
                except cora.DatabaseError as e:
                    errorObj, = e.args
                    erroMessage = errorObj.message
                    success = None
                    while success == 'false':
                        success, self.username, self.password, errorMessage = \
                            self.get_credentials(host, port, database, message=errorMessage)
                    if success == 'exit':
                        pass
                    elif success == 'true':
                        self.get_data()
            else:
                success, self.username, self.password, errorMessage = \
                    self.get_credentials(host, port, database, username=username, password=password)
                while success == 'false':
                    success, self.username, self.password, errorMessage = \
                        self.get_credentials(host, port, database, message=errorMessage)
                if success == 'exit':
                    pass
                elif success == 'true':
                    self.get_data()
    
    def get_data(self):
        pbs_ids = self.get_pbs_ids(self.selected_layer)
        df_pbs = self.get_peilbuizen(pbs_ids)
        #df_projecten = self.get_projecten(pbs_ids)
        #df_meetgegevens = self.get_meetgegevens(pbs_ids)
        print(df_meetgegevens)
        # Check if the directory still has to be made.
        if os.path.isdir(self.outputLocation) == False:
            os.mkdir(self.outputLocation)

        output_file_dir = os.path.join(self.outputLocation, self.fileName)
        if os.path.exists(output_file_dir):
            name, ext = self.fileName.split('.')
            i = 1
            while os.path.exists(os.path.join(output_location, name + '{}.'.format(i) + ext)):
                i += 1
            output_file_dir = os.path.join(self.outputLocation, name + '{}.'.format(i) + ext)
        print(output_file_dir)

        # Writing the data to excel sheets
        with pd.ExcelWriter(output_file_dir, engine='xlwt', mode='w') as writer:
            print('excelwriter')
            df_pbs.to_excel(writer, sheet_name='PRW_Peilbuizen')
            #df_projecten.to_excel(writer, sheet_name='PRW_Projecten')
            
            column = 0
            for pbs_id in df_meetgegevens['PBS_ID'].unique():
                df_temp = df_meetgegevens[('PBS_ID' == pbs_id)]
                df_temp = df_temp['DATUM_MEETING', 'ID', 'WNC_CODE','MEETWAARDE']
                columnIndex = pd.MultiIndex.from_product(
                    [[pbs_id]['ID', 'WNC_CODE', 'MEETWAARDE']])
                df_print = pd.DataFrame(df_temp, index='DATUM_MEETING', columns=columnIndex)
                df_print.to_excel(writer, sheet_name='PRW_Peilbuis_Meetgegevens', startcol=column)
                column = column + 5
        # Start the excel file
        os.startfile(output_file_dir)

        

    def get_credentials(self, host, port, database, username=None, password=None, message=None):
        uri = QgsDataSourceUri()

        uri.setConnection(host, port, database, username, password)
        connInfo = uri.connectionInfo()
        
        errorMessage = None
        (ok, user, passwd) = QgsCredentials.instance().get(connInfo, message=message)
        if ok:
            # check if connection works otherwise return 'false'
            try:
                self.check_connection()
                return 'true', user, passwd, errorMessage
            except cora.DatabaseError as e:
                errorObj, = e.args
                errorMessage = errorObj.message
                return 'false', user, passwd, errorMessage
        else:
            return 'exit', user, passwd, errorMessage
    
    def check_connection(self):
        # Cora.connect throws an exception/error when the username/password is wrong
        with cora.connect(
            user=self.username,
            password=self.password, 
            dsn=self.dsn
                ) as dbcon:
            pass
    
    def fetch(self, query, data):
        with cora.connect(
            user=self.username,
            password=self.password, 
            dsn=self.dsn
                ) as dbcon:
            
            cur = dbcon.cursor()
            cur.execute(query, data)
            fetched = cur.fetchall()
            description = cur.description
            return fetched, description
    
    # Getting the loc_id's from the Qgislayer
    def get_pbs_ids(self, qgisLayer):
        pbs_ids = []
        features = qgisLayer.selectedFeatures()

        if len(features) > 0:
            print(str(len(features)) + ' peilbuizen geselecteerd.')
            for f in features:
                try:
                    pbs_ids.append(f.attribute('ID'))
                except KeyError:
                    raise KeyError(
                        'This layer does not contain an attribute called pbs_id')
                except:
                    raise IOError(
                        'Something went wrong in selecting the attribute \'pbs_id\'')
            return pbs_ids
        else:
            raise KeyError('No features were selected in the layer')

    # Querying meetpunten
    def get_peilbuizen(self, pbs_ids):
        if isinstance(pbs_ids, (list, tuple, pd.Series)):
            if len(pbs_ids) > 0:
                if(all(isinstance(x, int) for x in pbs_ids)):
                    values = list(pbs_ids)
                    chunks = [values[x:x+1000] for x in range(0, len(values), 1000)]
                    df_list = []
                    for chunk in chunks:
                        values = chunk
                        bindValues = [':' + str(i+1) for i in range(len(values))]
                        query = 'SELECT * FROM prw_peilbuizen '\
                            + 'WHERE id IN ({})'.format(','.join(bindValues))
                        fetched, description = self.fetch(query, values)
                        if (0 < len(fetched)):
                            pbs_df = pd.DataFrame(fetched)
                            colnames = [desc[0] for desc in description]
                            pbs_df.columns = colnames
                            df_list.append(pbs_df)
                    pbs_df_all = pd.concat(df_list, ignore_index=True)
                    if pbs_df_all.empty != True:
                        return pbs_df_all
                    else:
                        raise ValueError(
                            'These selected geometry points do not contain valid pbs_ids: ' + str(values))
                else:
                    raise TypeError('not all inputs are integers')
            else:
                raise ValueError('No pbs_ids were supplied.')
        else:
            raise TypeError('Input is not a list or tuple')
    
    def get_meetgegevens(self, pbs_ids):
        if isinstance(pbs_ids, (list, tuple, pd.Series)):
            if len(pbs_ids) > 0:
                if(all(isinstance(x, int) for x in pbs_ids)):
                    values = list(pbs_ids)
                    chunks = [values[x:x+990] for x in range(0, len(values), 990)]
                    df_list = []
                    for chunk in chunks:
                        values = chunk
                        bindValues = [':' + str(i+1) for i in range(len(values))]
                        bindDate = [':dateMin', ':dateMax']
                        bindAll = bindValues + bindDate
                        values = values + [self.dateMin, self.dateMax]
                        bindDict = dict(zip(bindAll, values))
                        query = 'SELECT * FROM prw_meetgegevens ' + \
                            'WHERE datum_meeting BETWEEN TO_DATE(:dateMin, \'yyyy-mm-dd\') ' + \
                            'AND TO_DATE(:dateMax, \'yyyy-mm-dd\') ' + \
                            'AND pbs_id IN ({})'.format(','.join(bindValues))
                        print(query)
                        print(bindDict)
                        fetched, description = self.fetch(query, bindDict)
                        print('fetched')
                        if(len(fetched) > 0):
                            mtg_df = pd.DataFrame(fetched)
                            colnames = [desc[0] for desc in description]
                            mtg_df.columns = colnames
                            df_list.append(mtg_df)
                    mtg_df_all = pd.concat(df_list, ignore_index=True)
                    print(mtg_df_all)
                    if mtg_df_all.empty != True:
                        return mtg_df_all
                    else:
                        raise ValueError(
                            'Deze PBS_IDS hebben geen meetgegevens beschikbaar tussen '\
                                 + dateMin + ' en ' + dateMax + '\n PBS_IDS: ' + str(values))
                else:
                    raise TypeError('not all inputs are integers')
            else:
                raise ValueError('No pbs_ids were supplied.')
        else:
            raise TypeError('Input is not a list or tuple')