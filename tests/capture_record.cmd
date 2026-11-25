@echo off
setlocal
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "MFILM_VS=%%i"
if not defined MFILM_VS exit /b 1
call "%MFILM_VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cd /d "%~dp0.."
if not exist build\filmos\fos.h python prepare.py || exit /b 1
if not exist build\capture-tests mkdir build\capture-tests
cd build\capture-tests
cl /nologo /O2 /std:c11 /D_CRT_SECURE_NO_WARNINGS /FI../../tests/windows_compat.h /I../filmos /I../../native ../../tests/record_driver.c ../../native/capture_record.c /Fe:record.exe || exit /b 1
python ../../tests/capture_restart.py record.exe || exit /b 1
set "MFILM_JAVA=..\..\..\toolchain\jdk-11.0.25+9\bin"
"%MFILM_JAVA%\javac.exe" --release 8 -d . ../../src/org/mfilm/sony/CaptureFiles.java ../../src/org/mfilm/sony/ShutterFocus.java ../../tests/CaptureFilesTest.java ../../tests/ShutterFocusTest.java || exit /b 1
"%MFILM_JAVA%\java.exe" -cp . org.mfilm.sony.ShutterFocusTest || exit /b 1
"%MFILM_JAVA%\java.exe" -cp . org.mfilm.sony.CaptureFilesTest
