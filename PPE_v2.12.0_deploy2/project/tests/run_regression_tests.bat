@echo off
REM ============================================================================
REM PPE Detection System - Test Runner
REM ============================================================================
REM Runs regression and integration tests
REM
REM Usage:
REM   run_regression_tests.bat          - Run all tests
REM   run_regression_tests.bat unit     - Run only unit/regression tests
REM   run_regression_tests.bat api      - Run only API integration tests
REM ============================================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================================
echo   PPE Detection System - Test Suite
echo ============================================================================
echo.

set TEST_TYPE=%1
if "%TEST_TYPE%"=="" set TEST_TYPE=all

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    exit /b 1
)

REM Install test dependencies
echo [*] Installing test dependencies...
pip install pytest pytest-asyncio httpx aiohttp -q

REM Set Python path
set PYTHONPATH=%~dp0..;%~dp0..\services\api;%PYTHONPATH%

if "%TEST_TYPE%"=="unit" goto unit_tests
if "%TEST_TYPE%"=="api" goto api_tests
if "%TEST_TYPE%"=="all" goto all_tests

:unit_tests
echo.
echo [*] Running Regression Tests (Unit)...
echo ============================================================================
python -m pytest "%~dp0regression" -v --tb=short
if errorlevel 1 (
    echo [FAILED] Regression tests failed
    set RESULT=1
) else (
    echo [PASSED] Regression tests passed
    set RESULT=0
)
if "%TEST_TYPE%"=="unit" goto end
goto api_tests

:api_tests
echo.
echo [*] Running API Integration Tests...
echo ============================================================================
echo [!] Note: Requires running API server at http://localhost:8000
echo.

REM Check if API is running
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [WARN] API server not running, skipping integration tests
    goto end
)

python -m pytest "%~dp0integration\test_training_v2_10_62.py" -v --tb=short
if errorlevel 1 (
    echo [FAILED] Integration tests failed
    set RESULT=1
) else (
    echo [PASSED] Integration tests passed
)
goto end

:all_tests
call :unit_tests
call :api_tests

:end
echo.
echo ============================================================================
if "%RESULT%"=="1" (
    echo   TEST RESULT: FAILED
) else (
    echo   TEST RESULT: PASSED
)
echo ============================================================================
echo.

exit /b %RESULT%
