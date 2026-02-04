@echo off
REM =============================================================================
REM PPE Detection System - Test Runner (Windows)
REM =============================================================================
REM 
REM Usage:
REM   run_tests.bat              - Run all tests
REM   run_tests.bat unit         - Run only unit tests
REM   run_tests.bat integration  - Run only integration tests  
REM   run_tests.bat coverage     - Run with coverage report
REM   run_tests.bat quick        - Quick smoke tests
REM
REM =============================================================================

setlocal enabledelayedexpansion

echo ======================================
echo   PPE Detection System - Test Runner
echo ======================================
echo.

set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..

cd /d "%PROJECT_DIR%"

if "%1"=="" goto all
if "%1"=="unit" goto unit
if "%1"=="integration" goto integration
if "%1"=="coverage" goto coverage
if "%1"=="quick" goto quick
if "%1"=="install" goto install
goto unknown

:unit
echo Running unit tests...
python -m pytest tests/unit/ -v --tb=short
goto done

:integration
echo Running integration tests...
python -m pytest tests/integration/ -v --tb=short
goto done

:all
echo Running all tests...
python -m pytest tests/ -v --tb=short
goto done

:coverage
echo Running tests with coverage...
python -m pytest tests/ --cov=services --cov-report=html:tests/coverage_html --cov-report=term-missing -v --tb=short
echo.
echo Coverage report generated: tests\coverage_html\index.html
goto done

:quick
echo Running quick smoke tests...
python -m pytest tests/unit/test_training_api.py -v --tb=short -x -q
goto done

:install
echo Installing test dependencies...
pip install -r tests\requirements.txt
goto done

:unknown
echo Unknown command: %1
echo Usage: run_tests.bat [unit^|integration^|coverage^|quick^|install]
exit /b 1

:done
echo.
echo Tests completed!
exit /b 0
