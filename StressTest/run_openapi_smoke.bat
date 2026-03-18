@echo off
setlocal

REM Usage:
REM   StressTest\run_openapi_smoke.bat
REM   StressTest\run_openapi_smoke.bat --max-endpoints 50

python StressTest\smoke\openapi_smoke.py %*

endlocal
