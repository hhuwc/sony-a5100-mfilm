@echo off
setlocal
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "MFILM_VS=%%i"
if not defined MFILM_VS exit /b 1
call "%MFILM_VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0.."
python prepare.py || exit /b 1
if not exist build\finder-tests mkdir build\finder-tests
cd build\finder-tests
set "MFILM_CL=/nologo /O2 /std:c11 /Gy /D_CRT_SECURE_NO_WARNINGS /I../../tests /FIwindows_compat.h"
set "MFILM_UP=../../../mfilm-canon-film-simulation/ml-dev/filmos"
cl %MFILM_CL% /I../filmos /I../../native ../../tests/finder_test.c ../../native/finder_hud.c ../filmos/fos_hud.c ../filmos/fos_gfx.c ../filmos/fos_film.c /Fe:finder.exe /link /OPT:REF || exit /b 1
finder.exe ../assets/ML/DATA/FOSFONT.BIN || exit /b 1
cl %MFILM_CL% %MFILM_UP%/sim/hudtest.c %MFILM_UP%/sim/fonts.c %MFILM_UP%/fos_hud.c %MFILM_UP%/fos_gfx.c %MFILM_UP%/fos_film.c /Fe:upstream.exe /link /OPT:REF || exit /b 1
set "MFILM_JAVA=../../../toolchain/jdk-11.0.25+9/bin"
"%MFILM_JAVA%/javac.exe" --release 8 -d . ../../src/org/mfilm/sony/SonyFinderMeter.java ../../tests/SonyFinderMeterTest.java || exit /b 1
"%MFILM_JAVA%/java.exe" -cp . org.mfilm.sony.SonyFinderMeterTest || exit /b 1
python ../../tests/compare_finder.py %*
