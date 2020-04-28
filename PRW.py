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
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QRegExp
from qgis.PyQt.QtGui import QIcon, QRegExpValidator
from qgis.PyQt.QtWidgets import QAction, QProgressDialog

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .PRW_dialog import PRW_Data_OpvragerDialog
from qgis.core import (
    QgsDataSourceUri, QgsCredentials,
    QgsTask, QgsApplication, QgsMessageLog, Qgis)

import os
import xlwt
import pandas as pd
import cx_Oracle as cora
import time



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
        if self.first_start:
            self.first_start = False
            self.dlg = PRW_Data_OpvragerDialog()
            self.dlg.OutputLocation.setStorageMode(1)
            self.dlg.OutputLocation.setFilePath(self.dlg.OutputLocation.defaultRoot())
            # Set a validator on the filename lineEdit so that no random signs can be put in.
            rx2 = QRegExp(r"^[\w\-. ]+$")
            filename_validator = QRegExpValidator(rx2)
            self.dlg.FileName.setValidator(filename_validator)


        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Extracting values from the dialog form
            self.selected_layer = self.dlg.MapLayerComboBox.currentLayer()
            self.dateMax = self.dlg.DateMax.date().toString('yyyy-MM-dd')
            self.dateMin = self.dlg.DateMin.date().toString('yyyy-MM-dd')
            self.fileName = self.dlg.FileName.text()
            self.outputLocation = self.dlg.OutputLocation.filePath()
            
            source = self.selected_layer.source()
            uri = QgsDataSourceUri(source)

            '''if uri.hasParam('database') is False:
                e = Error('De geselecteerde laag heeft geen database connectie.')
                raise e
                self.dlg.ErrorLabel.setLabelText(e)
                result = False
                self.dlg.show()
                return'''

            savedUsername = uri.hasParam('username')
            savedPassword = uri.hasParam('password')

            host = uri.host()
            port = uri.port()
            database = uri.database()
            self.username = uri.username()
            self.password = uri.password()
            self.dsn = cora.makedsn(host=host, port=port, service_name=database)
            
            errorMessage = None
            # If we have a username and password try to connect, otherwise ask for credentials
            # if the connection fails store the error and show dialog screen for credentials input
            if savedUsername is True and savedPassword is True:
                try:
                    self.check_connection()
                    self.run_task()
                except cora.DatabaseError as e:
                    errorObj, = e.args
                    errorMessage = errorObj.message
                    success = 'false'
                    while success == 'false':
                        success, errorMessage = \
                            self.get_credentials(host, port, self.database, message=errorMessage)
                    if success == 'exit':
                        pass
                    elif success == 'true':
                        self.run_task()
            else:
                success, errorMessage = \
                    self.get_credentials(host, port, self.database, username=self.username, password=self.password)
                while success == 'false':
                    success, errorMessage = \
                        self.get_credentials(host, port, self.database, username=self.username, password=self.password, message=errorMessage)
                if success == 'exit':
                    pass
                elif success == 'true':
                    self.run_task()

    def run_task(self):
        progDialog = QProgressDialog('Running Task in the background...', 'Cancel', 0, 100)
        self.task = HeavyLifting('PRW Database Bevraging', self)
        progDialog.canceled.connect(self.task.cancel)
        progDialog.show()
        self.task.begun.connect(lambda: progDialog.setLabelText('Begonnen met PRW peilbuisgegevens ophalen...'))
        self.task.progressChanged.connect(lambda: progDialog.setValue(self.task.progress()))
        QgsApplication.taskManager().addTask(self.task)      

    def get_credentials(self, host, port, database, username=None, password=None, message=None):
        '''Show a credentials dialog form to access the database. Checks credentials when clicked ok.'''
        uri = QgsDataSourceUri()
        uri.setConnection(host, port, database, username, password)
        connInfo = uri.connectionInfo()

        errorMessage = None
        # Pops up a Credentials dialog, ok returns True if 'ok' on the dialog is pressed
        (ok, user, passwd) = QgsCredentials.instance().get(connInfo, username, password, message)
        if ok:
            self.username = user
            self.password = passwd
            # check if connection works otherwise return 'false' and the error message
            try:
                self.check_connection()
                return 'true', errorMessage
            except cora.DatabaseError as e:
                errorObj, = e.args
                errorMessage = errorObj.message
                return 'false', errorMessage
        else:
            return 'exit', errorMessage
    
    def check_connection(self):
        '''Checks the Oracle database connection. 
        cx_Oracle.databaseError's are thrown out if the connection does not work.'''
        # Cora.connect throws an exception/error when the username/password is wrong
        with cora.connect(
            user=self.username,
            password=self.password, 
            dsn=self.dsn
        ):
            pass
    
    def fetch(self, query, data):
        '''Fetch queries with the data in bindValues.'''
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

    def get_pbs_ids(self, qgisLayer):
        '''Extract from the selected peilbuizen in the layer the id's.'''
        pbs_ids = []
        features = qgisLayer.selectedFeatures()

        if len(features) > 0:
            for f in features:
                try:
                    pbs_ids.append(f.attribute('ID'))
                except KeyError:
                    raise KeyError(
                        'Deze laag heeft geen attribute \'ID\'.')
            return pbs_ids
        else:
            raise KeyError('Geen features zijn geselecteerd in de aangewezen laag.')

    def get_peilbuizen(self, pbs_ids):
        '''Setting up the queries to fetch all data from the PRW_Peilbuizen table and processing the data as a pandas.DataFrame.'''
        if isinstance(pbs_ids, (list, tuple, pd.Series)):
            if len(pbs_ids) > 0:
                if(all(isinstance(x, int) for x in pbs_ids)):
                    val = list(pbs_ids)

                    # Bindvalues are used in the queries to prevent SQL-injection. 
                    # Queries with more than 1000 bindvalues raise an error in cx_Oracle, robustness is built in by creating chunks
                    # More info about bindvalues can be found in the cx_Oracle docs.
                    chunks = [val[x:x+1000] for x in range(0, len(val), 1000)]
                    df_list = []
                    for chunk in chunks:
                        values = chunk
                        bindValues = [':' + str(i+1) for i in range(len(values))] # Creates bindvalues list as [:1, :2, :3, ...]
                        
                        # Bindvalues are directly injected into the query.
                        query = 'SELECT id, buiscode||\'-\'||p.volgnummer PEILBUIS, buiscode_project, inw_diameter, hoogte_meetmerk, nul_meting, hoogte_maaiveld, bovenkant_filter, lengte_buis, hoogte_bov_buis, toel_afwijking, btp_code, meetmerk, plaatsbepaling, datum_start, datum_eind, datum_vervallen, ind_plaatsing, x_coordinaat, y_coordinaat, last_updated_by, last_update_date, created_by, creation_date, mat_code, geometrie '\
                            + 'FROM prw.prw_peilbuizen p '\
                            + 'WHERE id IN ({})'.format(','.join(bindValues))
                        fetched, description = self.fetch(query, values)
                        if (0 < len(fetched)):
                            pbs_df = pd.DataFrame(fetched)
                            colnames = [desc[0] for desc in description]
                            pbs_df.columns = colnames
                            df_list.append(pbs_df)
                    
                    # If df_list contains any dataframes
                    if df_list:
                        pbs_df_all = pd.concat(df_list, ignore_index=True)
                        return pbs_df_all
                    else:
                        raise ValueError(
                            'These selected PBS_ID\'s do not contain any valid: ' + str(val))
                else:
                    raise TypeError('not all inputs are integers')
            else:
                raise ValueError('No pbs_ids were supplied.')
        else:
            raise TypeError('Input is not a list or tuple')
    
    def get_meetgegevens(self, pbs_ids):
        '''This method sets up the queries to fetch all data from the PRW_Meetgegevens table.
        It will processing the data as a pandas.Dataframe.
        Argruments:
        - PBS_ID's 
        
        '''
        if isinstance(pbs_ids, (list, tuple, pd.Series)):
            if len(pbs_ids) > 0:
                if(all(isinstance(x, int) for x in pbs_ids)):
                    val = list(pbs_ids)
                    
                    # Bindvalues are used in the queries to prevent SQL-injection. 
                    # Queries with more than 1000 bindvalues raise an error in cx_Oracle, robustness is built in by creating chunks
                    # More info about bindvalues can be found in the cx_Oracle docs.
                    chunks = [val[x: x + 990] for x in range(0, len(val), 990)]
                    df_list = []
                    for chunk in chunks:
                        values = chunk
                        bindValues = [':' + str(i + 1) for i in range(len(values))] # Creates bindvalues list as [:1, :2, :3, ...]
                        bindDate = [':dateMin', ':dateMax']
                        
                        # Create a dictionary of all the bindvalues and values to relate them to eachother.
                        bindAll =  bindValues + bindDate
                        values = values + [self.dateMin, self.dateMax]
                        bindDict = dict(zip(bindAll, values))
                        
                        # Bindvalues are directly injected into the query.
                        query = 'SELECT mg.pbs_id, pb.buiscode||\'-\'||pb.volgnummer PEILBUIS, mg.wnc_code, mg.id, mg.datum_meting, mg.meetwaarde, mg.hoogte_meetmerk ' +\
                            'FROM PRW.prw_meetgegevens mg ' + \
                            'INNER JOIN PRW.prw_peilbuizen pb ON pb.id = mg.pbs_id ' + \
                            'WHERE mg.datum_meting BETWEEN TO_DATE(:dateMin, \'yyyy-mm-dd\') ' + \
                            'AND TO_DATE(:dateMax, \'yyyy-mm-dd\') ' + \
                            'AND mg.pbs_id IN ({})'.format(','.join(bindValues))
                        fetched, description = self.fetch(query, bindDict)
                        
                        if(len(fetched) > 0):
                            mtg_df = pd.DataFrame(fetched)
                            colnames = [desc[0] for desc in description]
                            mtg_df.columns = colnames
                            df_list.append(mtg_df)
                    
                    # If df_list contains any dataframes
                    if df_list:
                        mtg_df_all = pd.concat(df_list, ignore_index=True)
                        return mtg_df_all
                    else:
                        raise ValueError('Deze PBS_IDS hebben geen meetgegevens tussen '\
                            + self.dateMin + ' en ' + self.dateMax + '\n PBS_IDS: ' + str(val))
                else:
                    raise TypeError('not all inputs are integers')
            else:
                raise ValueError('No pbs_ids were supplied.')
        else:
            raise TypeError('Input is not a list or tuple')
    
    def PbStats(self, df_in, decimals=2):
        """This function creates standard statistics for datasets
        Arguments:
        - filename
        - desired decimal places (default = 2)
                
        """

        # Create empty dataframe with all desired statistics
        df_stats = pd.DataFrame(columns=['PEILBUIS','Aantal metingen', 'Start datum', 'Eind datum', 'Maximaal gemeten', '95-percentiel', 'Gemiddelde',
                                        '5-percentiel', 'Minimaal gemeten'], dtype='float')
        
        df_stats['PEILBUIS'] = df_in['PEILBUIS'].unique()  # Add all points to dataframe
        # WARNING: at this point, the datatypes are 'float', which is NOT desired for the date fields
            
        # Loop over individual locations and fill the fields
        for i, row in df_stats.iterrows():
            pb = row['PEILBUIS']      # Current location
            df2 = df_in.loc[df_in['PEILBUIS']==pb]         # Select part of full dataframe to calculate statistics
            df_stats.loc[df_stats['PEILBUIS']==pb, ['Maximaal gemeten']]    = df2['MEETWAARDE'].max()
            df_stats.loc[df_stats['PEILBUIS']==pb, ['95-percentiel']]       = df2['MEETWAARDE'].quantile(0.95)
            df_stats.loc[df_stats['PEILBUIS']==pb, ['Gemiddelde']]          = df2['MEETWAARDE'].mean()
            df_stats.loc[df_stats['PEILBUIS']==pb, ['5-percentiel']]        = df2['MEETWAARDE'].quantile(0.05)
            df_stats.loc[df_stats['PEILBUIS']==pb, ['Minimaal gemeten']]    = df2['MEETWAARDE'].min()
            df_stats.loc[df_stats['PEILBUIS']==pb, ['Aantal metingen']]     = df2['MEETWAARDE'].count()
            df_stats.loc[df_stats['PEILBUIS']==pb, ['Start datum']]         = df2['DATUM_METING'].min()
            df_stats.loc[df_stats['PEILBUIS']==pb, ['Eind datum']]          = df2['DATUM_METING'].max()
            
        # Conversion to desired formates
        df_stats['Aantal metingen'] = df_stats['Aantal metingen'].astype(int)
        
        dateformat = '%Y-%m-%d %H:%M:%S'
        df_stats['Start datum'] = pd.to_datetime(df_stats['Start datum'], format=dateformat)
        df_stats['Eind datum'] = pd.to_datetime(df_stats['Eind datum'], format=dateformat)

        # Round all 'float' columns to the desired number of decimals
        df_stats = df_stats.round(decimals)

        df_stats = df_stats.set_index('PEILBUIS')

        # Return transposed dataframe
        return df_stats

class HeavyLifting(QgsTask):
    """This shows how to subclass QgsTask"""

    def __init__(self, description, PRW_Data_Opvrager):
        QgsTask.__init__(self, description, QgsTask.CanCancel)
        self.PRW = PRW_Data_Opvrager
        self.exception = None
        self.MESSAGE_CATEGORY = 'PRW_Data_Opvrager'
    
    def run(self):
        """This function is where you do the 'heavy lifting' or implement
        the task which you want to run in a background thread. This function 
        must return True or False and should only interact with the main thread
        via signals"""
        try:
            result = self.get_data()
            if result:
                return True
            else:
                return False
        except Exception as e:
            self.exception = e
            return False

    def get_data(self):
        """ This function runs the heavy code in the background."""
        '''Fetch data and write it off to an excel file in the selected file location.'''
        self.setProgress(0)
        
        # Use the fetch functions to collect all the data
        pbs_ids         =   self.PRW.get_pbs_ids(self.PRW.selected_layer)
        pbs_ids         =   [int(x) for x in pbs_ids]
        
        self.setProgress(5)
        if self.isCanceled():
            return False

        df_pbs          =   self.PRW.get_peilbuizen(pbs_ids)
        
        self.setProgress(10)
        if self.isCanceled():
            return False
        
        df_meetgegevens =   self.PRW.get_meetgegevens(pbs_ids)

        self.setProgress(20)
        if self.isCanceled():
            return False

        # Calculate the statistics of the meetgegevens.
        df_pbStats      =   self.PRW.PbStats(df_meetgegevens)
        # Present the statistics with some peilbuis gegevens
        ond_filt        =   df_pbs['HOOGTE_MAAIVELD'].values - df_pbs['LENGTE_BUIS'].values
        bov_filt        =   df_pbs['HOOGTE_MAAIVELD'].values - df_pbs['LENGTE_BUIS'].values + df_pbs['BOVENKANT_FILTER'].values
        df_pbStats_pbs = pd.DataFrame(index=df_pbs['PEILBUIS'],
            columns=['Maaiveld', 'Bovenkant Peilbuis', 'Bovenkant Filter', 'Onderkant Filter'],
            data=zip(df_pbs['HOOGTE_MAAIVELD'].values, df_pbs['HOOGTE_BOV_BUIS'].values, bov_filt, ond_filt))
        df_pbStats_pbs = pd.concat([df_pbStats_pbs, df_pbStats], axis=1).T

        self.setProgress(40)
        if self.isCanceled():
            return False
        
        # Check if the directory has to be created.
        if os.path.isdir(self.PRW.outputLocation) is False:
            os.mkdir(self.PRW.outputLocation)

        fileNameExt = self.PRW.fileName + '.xlsx'
        # Check if the selected filename exists in the dir
        output_file_dir = os.path.join(self.PRW.outputLocation, fileNameExt)
        if os.path.exists(output_file_dir):
            name, ext = fileNameExt.split('.')
            i = 1
            while os.path.exists(os.path.join(self.PRW.outputLocation, name + '{}.'.format(i) + ext)):
                i += 1
            output_file_dir = os.path.join(self.PRW.outputLocation, name + '{}.'.format(i) + ext)

        # Writing the data to excel sheets
        with pd.ExcelWriter(output_file_dir, engine='xlsxwriter', mode='w',
                            datetime_format='dd-mm-yyyy',
                            date_format='dd-mm-yyyy') as writer:
            workbook = writer.book

            self.setProgress(50)
            if self.isCanceled():
                return False
            
            ## Adding the peilbuis tabel to an Excelsheet
            prw_pbs_sheetname = 'PRW_Peilbuizen'
            df_pbs.to_excel(writer, sheet_name=prw_pbs_sheetname, index=False, freeze_panes=(1, 2))
            meetgeg_sheet = writer.sheets[prw_pbs_sheetname]
            # Sets the width of each column
            i = 0
            for colname in df_pbs.columns:
                meetgeg_sheet.set_column(i, i, len(colname) * 1.3)
                i += 1

            self.setProgress(60)

            ## Adding the meetgegevens per peilbuis to the same Excelsheet
            chart = workbook.add_chart({'type': 'line'})
            prw_meetgeg_sheetname = 'PRW_Peilbuis_Meetgegevens'
            col = 0
            for pbs in df_meetgegevens['PEILBUIS'].unique():
                # Parsing data per Peilbuis
                df_temp = df_meetgegevens[df_meetgegevens['PEILBUIS'] == pbs]
                df_temp = df_temp[['DATUM_METING', 'MEETWAARDE']].dropna(subset=['MEETWAARDE'])
                # Write to Excelsheet
                df_temp.to_excel(writer, sheet_name=prw_meetgeg_sheetname, startcol=col, startrow=1, index=False)
                # Sets the width of the columns in Excel
                meetgeg_sheet = writer.sheets[prw_meetgeg_sheetname]
                meetgeg_sheet.freeze_panes(2, 0)
                meetgeg_sheet.write(0, col + 1, pbs)
                meetgeg_sheet.set_column(col, col, 15)
                meetgeg_sheet.set_column(col + 1, col + 2, 13)

                # Adding the meetgegevens series to a chart
                N = len(df_temp.index)
                chart.add_series({
                    'name':         ['PRW_Peilbuis_Meetgegevens', 0, col + 1],
                    'categories':   ['PRW_Peilbuis_Meetgegevens', 3, col, N + 3, col],
                    'values':       ['PRW_Peilbuis_Meetgegevens', 3, col + 1, N + 3, col + 1]
                })
                
                col = col + 3

                if self.isCanceled():
                    return False
        
            self.setProgress(80)
            if self.isCanceled():
                return False

            # Meetgegevens Chart formatting
            minGWS = float(min(df_meetgegevens['MEETWAARDE']))
            chart.set_x_axis({
                'name':             'Datum ',
                'name_font':        {'size': 14, 'bold': True},
                'date_axis':        True,
                'major_tick_mark':  'inside',
                'minor_tick_mark':  'none',
            })
            chart.set_y_axis({
                'name':             'Grondwaterstand in mNAP',
                'name_font':        {'size': 14, 'bold': True},
                'major_gridlines':  {'visible': True},
                'crossing':         minGWS//1,
                'min':              minGWS//1
            })
            chart.set_size({'x_scale': 2, 'y_scale': 1.5})
            chart.set_legend({'font': {'size': 12, 'bold': True}})
            chartsheet = workbook.add_chartsheet('Peilbuis Grafiek')
            chartsheet.set_chart(chart)
            
            self.setProgress(90)
            if self.isCanceled():
                return False
            
            # Adding the statistieken tabel to an Excelsheet
            prw_stat_sheetname = 'Peilbuizen Statistiek'
            df_pbStats_pbs.to_excel(writer, sheet_name=prw_stat_sheetname, freeze_panes=(1,1))
            prw_stat_sheet = writer.sheets[prw_stat_sheetname]
            prw_stat_sheet.set_column(0, 0, 25)
            prw_stat_sheet.set_column(1, len(df_pbStats_pbs.columns), 13)
        
        # Start the excel file
        os.startfile(output_file_dir)

        self.setProgress(100)
        return True

    def finished(self, result):
        """ This function is called automatically when the task is completed and is 
        called from the main thread so it is safe to interact with the GUI etc here"""
        if result:
            QgsMessageLog.logMessage(
                'Task "{name}" completed ' \
                'in {duration} seconds'.format(
                    name=self.description(),
                    duration=round(self.elapsedTime()/1000, 2)
                ), self.MESSAGE_CATEGORY, Qgis.Success)
        else:
            if self.exception is None:
                QgsMessageLog.logMessage(
                    'Task "{name}" not successful but without '\
                    'exception (probably the task was manually '\
                    'canceled by the user)'.format(
                        name=self.description()),
                    self.MESSAGE_CATEGORY, Qgis.Warning)
            else:
                QgsMessageLog.logMessage(
                    'Task "{name}" threw an Exception: {exception}'.format(
                        name=self.description(),
                        exception=self.exception),
                    self.MESSAGE_CATEGORY, Qgis.Critical)
                raise self.exception
    
    def cancel(self):
        QgsMessageLog.logMessage(
            'Task "{name}" canceled by the user\n'.format(
            name=self.description()
            ), self.MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()