@echo off

::--------------------------------------------------------
::-- Constant parameters. Edit to match your plugin
::--------------------------------------------------------
set "PLUGINNAME=SpatialDecision"
set "QGISDIR=.qgis2"
set "PY_FILES=__init__.py spatial_decision.py spatial_decision_dockwidget.py utility_functions.py"
set "UI_FILES=spatial_decision_dockwidget_base.ui"
set "EXTRAS=metadata.txt icon.png"
set "EXTRADIR=icons"
set "COMPILED_RESOURCE_FILES=resources.py"
set "HELP=help"

call :deploy
exit /b

::--------------------------------------------------------
::-- Function section starts below here
::--------------------------------------------------------
:compile
pyrcc4 -o resources_rc.py resources.qrc
exit /b

:deploy
if exist "%UserProfile%\%QGISDIR%\python\plugins\%PLUGINNAME%" rmdir /S/Q "%UserProfile%\%QGISDIR%\python\plugins\%PLUGINNAME%"
mkdir "%UserProfile%\%QGISDIR%\python\plugins\%PLUGINNAME%
for %%a in (%PY_FILES%) do (copy "%%~a" "%UserProfile%\%QGISDIR%\python\plugins\%PLUGINNAME%")
for %%a in (%UI_FILES%) do (copy "%%~a" "%UserProfile%\%QGISDIR%\python\plugins\%PLUGINNAME%")
for %%a in (%COMPILED_RESOURCE_FILES%) do (copy "%%~a" "%UserProfile%\%QGISDIR%\python\plugins\%PLUGINNAME%")
for %%a in (%EXTRAS%) do (copy "%%~a" "%UserProfile%\%QGISDIR%\python\plugins\%PLUGINNAME%")
xcopy "i18n" "%UserProfile%\%QGISDIR%\python\plugins\%PLUGINNAME%\i18n\" /S
xcopy "%HELP%" "%UserProfile%\%QGISDIR%\python\plugins\%PLUGINNAME%\%HELP%\" /S
xcopy "%EXTRADIR%" "%UserProfile%\%QGISDIR%\python\plugins\%PLUGINNAME%\%EXTRADIR%\" /S
exit /b

