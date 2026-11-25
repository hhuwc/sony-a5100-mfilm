@echo off
setlocal
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "MFILM_VS=%%i"
if not defined MFILM_VS exit /b 1
call "%MFILM_VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0.."
python prepare.py || exit /b 1
cd build
cl /nologo /O2 /std:c11 /Gy /D_CRT_SECURE_NO_WARNINGS /FI../tests/windows_compat.h /Ifilmos /I../native ../native/arw.c ../tests/develop.c ../tests/windows_port.c filmos/fos_dev.c filmos/fos_film.c filmos/fos_print.c filmos/fos_looks.c filmos/fos_jpeg.c filmos/fos_gfx.c /Fe:develop.exe /link /OPT:REF || exit /b 1
cl /nologo /O2 /std:c11 /D_CRT_SECURE_NO_WARNINGS ../native/arw.c ../tests/sensor_dump.c /Fe:sensor_dump.exe || exit /b 1
develop.exe "%~1" "%~2" %3 %4

