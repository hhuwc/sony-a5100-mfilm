@echo off
setlocal
if "%~3"=="" exit /b 2
set "MFILM_RAW=%~f1"
set "MFILM_PRINTS=%~f2"
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "MFILM_VS=%%i"
if not defined MFILM_VS exit /b 1
call "%MFILM_VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0.."
python prepare.py || exit /b 1
if not exist build\roll-desktop mkdir build\roll-desktop
cd build\roll-desktop
cl /nologo /O2 /std:c11 /Gy /D_CRT_SECURE_NO_WARNINGS /FI../../tests/windows_compat.h /I../filmos /I../../native ../../native/arw.c ../../tests/desktop_roll.c ../../tests/windows_port.c ../filmos/fos_dev.c ../filmos/fos_film.c ../filmos/fos_print.c ../filmos/fos_looks.c ../filmos/fos_jpeg.c ../filmos/fos_gfx.c /Fe:roll.exe /link /OPT:REF psapi.lib || exit /b 1
cd ..
if not exist "%MFILM_PRINTS%" mkdir "%MFILM_PRINTS%"
roll-desktop\roll.exe "%MFILM_RAW%" "%MFILM_PRINTS%" %3
