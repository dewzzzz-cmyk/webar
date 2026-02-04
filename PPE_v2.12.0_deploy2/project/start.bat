@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

title PPE Detection System v2.10.50

:: ================================================================
:: AUTO-REBUILD CHECK (v2.10.50)
:: При смене версии автоматически пересобирает контейнеры
:: ================================================================
set CURRENT_VERSION=2.10.50
set VERSION_FILE=.version_built

:: Проверяем нужна ли пересборка
set NEED_REBUILD=0
if not exist "%VERSION_FILE%" (
    set NEED_REBUILD=1
) else (
    set /p BUILT_VERSION=<"%VERSION_FILE%"
    if not "!BUILT_VERSION!"=="%CURRENT_VERSION%" (
        set NEED_REBUILD=1
    )
)

:: Если версия изменилась - автоматическая пересборка
if "!NEED_REBUILD!"=="1" (
    cls
    echo.
    echo  ================================================================
    echo       DETECTED NEW VERSION: %CURRENT_VERSION%
    echo  ================================================================
    echo.
    echo  Auto-rebuilding containers...
    echo  This takes 2-5 minutes [one time on update]
    echo.
    
    docker info >nul 2>&1
    if errorlevel 1 (
        echo  [!] Docker not running. Start Docker Desktop first.
        pause
        exit /b 1
    )
    
    echo [1/4] Stopping old containers...
    docker compose down >nul 2>&1
    
    echo [2/4] Rebuilding capture [RTSP optimization]...
    docker compose build --no-cache capture
    
    echo [3/4] Rebuilding api [WebSocket optimization]...
    docker compose build --no-cache api
    
    echo [4/4] Rebuilding dashboard...
    docker compose build --no-cache dashboard
    
    echo %CURRENT_VERSION%> "%VERSION_FILE%"
    
    echo.
    echo  ================================================================
    echo       REBUILD COMPLETE! Press any key...
    echo  ================================================================
    pause >nul
)


:MENU
cls
echo.
echo  ================================================================
echo             PPE DETECTION SYSTEM v2.10.50
echo  ================================================================
echo.
echo   === QUICK START ===
echo   [1] Start GPU
echo   [2] Start CPU
echo.
echo   === UPDATE (FAST - uses cache) ===
echo   [Q] Quick Restart (~5 sec)
echo   [U] Update API (~30 sec)
echo   [A] Update All (~1-2 min)
echo.
echo   === FULL INSTALL (SLOW - downloads all) ===
echo   [3] Full Install GPU (5-10 min)
echo   [4] Full Install CPU (5-10 min)
echo.
echo   === TOOLS ===
echo   [7] Stop
echo   [8] Status
echo   [9] Logs (interactive)
echo   [G] GPU Info
echo   [C] Clean (keeps cache)
echo   [D] Deep Clean (removes cache)
echo   [R] Reset Database
echo   [F] Fix Containers (resolve conflicts)
echo   [B] Browser
echo.
echo   === DIAGNOSTICS ===
echo   [L] Collect Logs (for AI analysis)
echo   [E] Export Full Diagnostics
echo   [T] Test All Services
echo.
echo   [0] Exit
echo.
echo  ================================================================
echo.

set /p choice="Select: "

if "%choice%"=="1" goto START_GPU
if "%choice%"=="2" goto START_CPU
if /i "%choice%"=="Q" goto QUICK_RESTART
if /i "%choice%"=="U" goto UPDATE_API
if /i "%choice%"=="A" goto UPDATE_ALL
if "%choice%"=="3" goto INSTALL_GPU
if "%choice%"=="4" goto INSTALL_CPU
if "%choice%"=="7" goto STOP
if "%choice%"=="8" goto STATUS
if "%choice%"=="9" goto LOGS
if /i "%choice%"=="G" goto GPU_INFO
if /i "%choice%"=="C" goto CLEAN
if /i "%choice%"=="D" goto DEEP_CLEAN
if /i "%choice%"=="R" goto RESET_DB
if /i "%choice%"=="F" goto FIX_CONTAINERS
if /i "%choice%"=="B" goto BROWSER
if /i "%choice%"=="L" goto COLLECT_LOGS
if /i "%choice%"=="E" goto EXPORT_DIAGNOSTICS
if /i "%choice%"=="T" goto TEST_SERVICES
if "%choice%"=="0" goto EXIT

echo Invalid choice!
timeout /t 2 >nul
goto MENU

:COLLECT_LOGS
cls
echo.
echo  [L] COLLECT LOGS FOR AI ANALYSIS
echo  ================================================================
echo.

if not exist "logs" mkdir logs

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set LOG_FILE=logs\ppe_logs_%datetime:~0,8%_%datetime:~8,4%.txt

echo [*] Collecting logs to: %LOG_FILE%
echo.

echo ================================================================ > "%LOG_FILE%"
echo PPE DETECTION SYSTEM - DIAGNOSTIC LOG >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo Generated: %date% %time% >> "%LOG_FILE%"
echo Version: 2.10.49 >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo SYSTEM INFO >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo Computer: %COMPUTERNAME% >> "%LOG_FILE%"
echo User: %USERNAME% >> "%LOG_FILE%"
echo OS: >> "%LOG_FILE%"
ver >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo DOCKER VERSION >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker --version >> "%LOG_FILE%" 2>&1
docker compose version >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo CONTAINER STATUS >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker ps -a --filter "name=ppe_" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo API LOGS (last 100 lines) >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker logs ppe_api --tail 100 >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo DETECTOR LOGS (last 50 lines) >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker logs ppe_detector --tail 50 >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo DASHBOARD LOGS (last 30 lines) >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker logs ppe_dashboard --tail 30 >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo CAPTURE LOGS (last 30 lines) >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker logs ppe_capture --tail 30 >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo TRAINING LOGS (last 50 lines) >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker logs ppe_training --tail 50 >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo POSTGRES LOGS (last 30 lines) >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker logs ppe_postgres --tail 30 >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo REDIS LOGS (last 20 lines) >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker logs ppe_redis --tail 20 >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo HEALTH CHECK RESULTS >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo API Health: >> "%LOG_FILE%"
curl -s http://localhost:8000/health >> "%LOG_FILE%" 2>&1
echo. >> "%LOG_FILE%"

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo DISK USAGE (Docker) >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker system df >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo VOLUMES >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
docker volume ls --filter "name=ppe" >> "%LOG_FILE%" 2>&1

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo ENVIRONMENT (.env check) >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
if exist ".env" (
    echo .env file exists >> "%LOG_FILE%"
    echo Variables defined: >> "%LOG_FILE%"
    findstr /B /V "#" .env 2>nul >> "%LOG_FILE%"
) else (
    echo .env file NOT FOUND >> "%LOG_FILE%"
)

echo. >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"
echo END OF DIAGNOSTIC LOG >> "%LOG_FILE%"
echo ================================================================ >> "%LOG_FILE%"

echo.
echo  ================================================================
echo   LOG SAVED: %LOG_FILE%
echo  ================================================================
echo.
echo   To share with AI:
echo   1. Open file: %LOG_FILE%
echo   2. Select All (Ctrl+A)
echo   3. Copy (Ctrl+C)
echo   4. Paste into chat
echo.

start explorer logs
pause
goto MENU

:EXPORT_DIAGNOSTICS
cls
echo.
echo  [E] EXPORT FULL DIAGNOSTICS
echo  ================================================================
echo.

if not exist "diagnostics" mkdir diagnostics

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set DIAG_DIR=diagnostics\diag_%datetime:~0,8%_%datetime:~8,4%

mkdir "%DIAG_DIR%" 2>nul
mkdir "%DIAG_DIR%\logs" 2>nul
mkdir "%DIAG_DIR%\configs" 2>nul
mkdir "%DIAG_DIR%\docker" 2>nul

echo [1/6] Collecting container logs...
docker logs ppe_api --tail 500 > "%DIAG_DIR%\logs\api.log" 2>&1
docker logs ppe_detector --tail 300 > "%DIAG_DIR%\logs\detector.log" 2>&1
docker logs ppe_dashboard --tail 200 > "%DIAG_DIR%\logs\dashboard.log" 2>&1
docker logs ppe_capture --tail 200 > "%DIAG_DIR%\logs\capture.log" 2>&1
docker logs ppe_training --tail 300 > "%DIAG_DIR%\logs\training.log" 2>&1
docker logs ppe_postgres --tail 100 > "%DIAG_DIR%\logs\postgres.log" 2>&1
docker logs ppe_redis --tail 100 > "%DIAG_DIR%\logs\redis.log" 2>&1
docker logs ppe_alerter --tail 100 > "%DIAG_DIR%\logs\alerter.log" 2>&1

echo [2/6] Collecting Docker info...
docker ps -a > "%DIAG_DIR%\docker\containers.txt" 2>&1
docker images > "%DIAG_DIR%\docker\images.txt" 2>&1
docker network ls > "%DIAG_DIR%\docker\networks.txt" 2>&1
docker volume ls > "%DIAG_DIR%\docker\volumes.txt" 2>&1
docker system df > "%DIAG_DIR%\docker\disk_usage.txt" 2>&1
docker compose config > "%DIAG_DIR%\docker\compose_config.txt" 2>&1

echo [3/6] Collecting system info...
echo System Info > "%DIAG_DIR%\system_info.txt"
echo =========== >> "%DIAG_DIR%\system_info.txt"
echo Computer: %COMPUTERNAME% >> "%DIAG_DIR%\system_info.txt"
echo User: %USERNAME% >> "%DIAG_DIR%\system_info.txt"
echo Date: %date% %time% >> "%DIAG_DIR%\system_info.txt"
systeminfo >> "%DIAG_DIR%\system_info.txt" 2>&1

echo [4/6] Checking GPU...
nvidia-smi > "%DIAG_DIR%\gpu_info.txt" 2>&1
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi >> "%DIAG_DIR%\gpu_info.txt" 2>&1

echo [5/6] Copying configs...
if exist "configs\cameras.yaml" copy "configs\cameras.yaml" "%DIAG_DIR%\configs\" >nul 2>&1
if exist "configs\zones.yaml" copy "configs\zones.yaml" "%DIAG_DIR%\configs\" >nul 2>&1
if exist "docker-compose.yml" copy "docker-compose.yml" "%DIAG_DIR%\configs\" >nul 2>&1

echo [6/6] Running health checks...
echo Health Check Results > "%DIAG_DIR%\health_check.txt"
echo ==================== >> "%DIAG_DIR%\health_check.txt"
echo. >> "%DIAG_DIR%\health_check.txt"
echo API Health: >> "%DIAG_DIR%\health_check.txt"
curl -s http://localhost:8000/health >> "%DIAG_DIR%\health_check.txt" 2>&1
echo. >> "%DIAG_DIR%\health_check.txt"
echo Training Status: >> "%DIAG_DIR%\health_check.txt"
curl -s http://localhost:8000/api/training/status >> "%DIAG_DIR%\health_check.txt" 2>&1

set SUMMARY_FILE=%DIAG_DIR%\SUMMARY_FOR_AI.txt
echo ================================================================ > "%SUMMARY_FILE%"
echo PPE DETECTION v2.10.30 - DIAGNOSTIC SUMMARY >> "%SUMMARY_FILE%"
echo ================================================================ >> "%SUMMARY_FILE%"
echo Generated: %date% %time% >> "%SUMMARY_FILE%"
echo. >> "%SUMMARY_FILE%"
echo === CONTAINER STATUS === >> "%SUMMARY_FILE%"
type "%DIAG_DIR%\docker\containers.txt" >> "%SUMMARY_FILE%"
echo. >> "%SUMMARY_FILE%"
echo === HEALTH CHECK === >> "%SUMMARY_FILE%"
type "%DIAG_DIR%\health_check.txt" >> "%SUMMARY_FILE%"
echo. >> "%SUMMARY_FILE%"
echo === API LOG (last 100 lines) === >> "%SUMMARY_FILE%"
docker logs ppe_api --tail 100 >> "%SUMMARY_FILE%" 2>&1
echo. >> "%SUMMARY_FILE%"
echo === DETECTOR LOG (last 50 lines) === >> "%SUMMARY_FILE%"
docker logs ppe_detector --tail 50 >> "%SUMMARY_FILE%" 2>&1

echo.
echo  ================================================================
echo   DIAGNOSTICS SAVED: %DIAG_DIR%
echo  ================================================================
echo.
echo   Quick share file: %DIAG_DIR%\SUMMARY_FOR_AI.txt
echo.

start explorer "%DIAG_DIR%"
pause
goto MENU

:TEST_SERVICES
cls
echo.
echo  [T] TEST ALL SERVICES
echo  ================================================================
echo.

call :CHECK_DOCKER
if "!DOCKER_OK!"=="0" goto MENU

echo [*] Testing all services...
echo.

echo  [1/8] PostgreSQL...
docker exec ppe_postgres pg_isready -U ppe >nul 2>&1
if !errorlevel! equ 0 (
    echo       [OK] PostgreSQL is ready
) else (
    echo       [FAIL] PostgreSQL not responding
)

echo  [2/8] Redis...
docker exec ppe_redis redis-cli ping >nul 2>&1
if !errorlevel! equ 0 (
    echo       [OK] Redis is ready
) else (
    echo       [FAIL] Redis not responding
)

echo  [3/8] API Health...
curl -s http://localhost:8000/health >nul 2>&1
if !errorlevel! equ 0 (
    echo       [OK] API is healthy
) else (
    echo       [FAIL] API not responding
)

echo  [4/8] Dashboard...
curl -s -o nul http://localhost:3001 2>nul
if !errorlevel! equ 0 (
    echo       [OK] Dashboard is accessible
) else (
    echo       [FAIL] Dashboard not responding
)

echo  [5/8] API Docs...
curl -s -o nul http://localhost:8000/docs 2>nul
if !errorlevel! equ 0 (
    echo       [OK] API Docs available
) else (
    echo       [FAIL] API Docs not available
)

echo  [6/8] Training Module...
curl -s http://localhost:8000/api/training/status >nul 2>&1
if !errorlevel! equ 0 (
    echo       [OK] Training module responding
) else (
    echo       [WARN] Training module not responding
)

echo  [7/8] Detector...
docker ps --filter "name=ppe_detector" --filter "status=running" | findstr ppe_detector >nul 2>&1
if !errorlevel! equ 0 (
    echo       [OK] Detector container running
) else (
    echo       [FAIL] Detector container not running
)

echo  [8/8] GPU in Detector...
docker logs ppe_detector --tail 20 2>&1 | findstr /i "CUDA GPU device" >nul 2>&1
if !errorlevel! equ 0 (
    echo       [OK] GPU detected in logs
) else (
    echo       [INFO] GPU not mentioned in recent logs
)

echo.
echo  ================================================================
echo   TEST COMPLETE
echo  ================================================================
echo.
pause
goto MENU

:QUICK_RESTART
cls
echo.
echo  [Q] QUICK RESTART
echo  ================================================================
echo.

call :CHECK_DOCKER
if "!DOCKER_OK!"=="0" goto MENU

echo [*] Restarting services...
docker compose restart api capture detector 2>nul

timeout /t 3 >nul
call :HEALTH_CHECK
call :SHOW_URLS
pause
goto MENU

:UPDATE_API
cls
echo.
echo  [U] UPDATE API
echo  ================================================================
echo.

call :CHECK_DOCKER
if "!DOCKER_OK!"=="0" goto MENU

echo [1/4] Stopping API and Dashboard...
docker compose stop api dashboard

echo [2/4] Rebuilding API...
docker compose build api
if !errorlevel! neq 0 (
    echo [ERROR] API build failed!
    pause
    goto MENU
)

echo [3/4] Rebuilding Dashboard...
docker compose build dashboard
if !errorlevel! neq 0 (
    echo [ERROR] Dashboard build failed!
    pause
    goto MENU
)

echo [4/4] Starting services...
docker compose up -d api dashboard

timeout /t 5 >nul
call :HEALTH_CHECK
call :SHOW_URLS
pause
goto MENU

:UPDATE_ALL
cls
echo.
echo  [A] UPDATE ALL
echo  ================================================================
echo.

call :CHECK_DOCKER
if "!DOCKER_OK!"=="0" goto MENU
call :CHECK_ENV

echo [1/3] Stopping...
docker compose down
call :CLEAN_OLD_CONTAINERS

echo [2/3] Rebuilding...
docker compose build
if !errorlevel! neq 0 (
    echo [ERROR] Build failed!
    pause
    goto MENU
)

echo [3/3] Starting...
docker compose up -d

timeout /t 10 >nul
call :HEALTH_CHECK
call :SHOW_URLS
pause
goto MENU

:START_GPU
cls
echo.
echo  [1] START GPU
echo  ================================================================
echo.

call :CHECK_DOCKER
if "!DOCKER_OK!"=="0" goto MENU
call :CHECK_ENV

echo [*] Checking GPU...
call :TEST_GPU
if "!GPU_OK!"=="0" (
    echo  [!] GPU not available. Use CPU mode instead? [y/n]
    set /p gpuchoice=""
    if /i "!gpuchoice!"=="y" goto START_CPU
    goto MENU
)
echo       GPU OK!

echo [*] Cleaning old containers...
call :CLEAN_OLD_CONTAINERS

echo [*] Starting with GPU...
docker compose up -d

timeout /t 5 >nul
call :HEALTH_CHECK
call :SHOW_URLS
pause
goto MENU

:START_CPU
cls
echo.
echo  [2] START CPU
echo  ================================================================
echo.

call :CHECK_DOCKER
if "!DOCKER_OK!"=="0" goto MENU
call :CHECK_ENV

echo [*] Stopping GPU services...
docker compose stop detector training 2>nul

echo [*] Cleaning old containers...
call :CLEAN_OLD_CONTAINERS

echo [*] Starting with CPU...
docker compose --profile cpu up -d

timeout /t 5 >nul
call :HEALTH_CHECK
call :SHOW_URLS
pause
goto MENU

:INSTALL_GPU
cls
echo.
echo  [3] FULL INSTALL GPU
echo  ================================================================
echo.
echo  Downloads ALL dependencies (3-5 GB)
echo  Time: 5-10 minutes
echo.
set /p confirm="Continue? [y/n]: "
if /i not "%confirm%"=="y" goto MENU

call :CHECK_DOCKER
if "!DOCKER_OK!"=="0" goto MENU

echo.
echo [*] Checking GPU...
call :TEST_GPU
if "!GPU_OK!"=="0" (
    echo  [!] GPU not detected. Use CPU mode instead? [y/n]
    set /p gpuchoice=""
    if /i "!gpuchoice!"=="y" goto INSTALL_CPU
    goto MENU
)
echo       GPU OK!

call :CHECK_ENV
call :CREATE_DIRS

echo.
echo [1/4] Stopping old containers...
docker compose down 2>nul
call :CLEAN_OLD_CONTAINERS
echo       Done

echo.
echo [2/4] Building (this takes 5-10 minutes)...
echo.
docker compose build --no-cache
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    goto MENU
)

echo.
echo [3/4] Starting with GPU...
docker compose up -d

echo.
echo [4/4] Waiting for services...
timeout /t 15 >nul

call :HEALTH_CHECK

echo.
echo  ================================================================
echo       INSTALL COMPLETE (GPU)
echo  ================================================================
echo.
call :SHOW_URLS
echo.
echo  Login: admin / admin123
echo.
pause
goto MENU

:INSTALL_CPU
cls
echo.
echo  [4] FULL INSTALL CPU
echo  ================================================================
echo.
echo  Downloads ALL dependencies (2-3 GB)
echo  Time: 5-10 minutes
echo.
set /p confirm="Continue? [y/n]: "
if /i not "%confirm%"=="y" goto MENU

call :CHECK_DOCKER
if "!DOCKER_OK!"=="0" goto MENU
call :CHECK_ENV
call :CREATE_DIRS

echo.
echo [1/4] Stopping old containers...
docker compose down 2>nul
call :CLEAN_OLD_CONTAINERS
echo       Done

echo.
echo [2/4] Building (this takes 5-10 minutes)...
echo.
docker compose build --no-cache
if !errorlevel! neq 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    goto MENU
)

echo.
echo [3/4] Starting with CPU...
docker compose --profile cpu up -d

echo.
echo [4/4] Waiting for services...
timeout /t 15 >nul

call :HEALTH_CHECK

echo.
echo  ================================================================
echo       INSTALL COMPLETE (CPU)
echo  ================================================================
echo.
call :SHOW_URLS
echo.
echo  Login: admin / admin123
echo.
pause
goto MENU

:STOP
cls
echo.
echo  [7] STOP
echo  ================================================================
echo.

docker compose down
docker compose --profile cpu down 2>nul

echo.
echo  [OK] All containers stopped.
echo.
pause
goto MENU

:STATUS
cls
echo.
echo  [8] STATUS
echo  ================================================================
echo.

echo  [Containers]
echo  ----------------------------------------------------------------
docker ps --format "table {{.Names}}\t{{.Status}}" 2>nul | findstr /i "ppe_"
if !errorlevel! neq 0 (
    echo  No PPE containers running
)

echo.
call :HEALTH_CHECK

echo.
echo  [GPU in Detector]
echo  ----------------------------------------------------------------
docker logs ppe_detector --tail 5 2>&1 | findstr /i "GPU CUDA device"

echo.
pause
goto MENU

:LOGS
cls
echo.
echo  [9] LOGS (Interactive)
echo  ================================================================
echo.
echo   [1] All        [6] Capture
echo   [2] API        [7] Training
echo   [3] Dashboard  [8] PostgreSQL
echo   [4] Detector   [9] Redis
echo   [5] Alerter    [0] Back
echo.
echo   [S] Save all logs to file
echo.

set /p logchoice="Select: "

if "%logchoice%"=="1" docker compose logs --tail 100 -f
if "%logchoice%"=="2" docker logs ppe_api --tail 100 -f
if "%logchoice%"=="3" docker logs ppe_dashboard --tail 100 -f
if "%logchoice%"=="4" docker logs ppe_detector --tail 100 -f
if "%logchoice%"=="5" docker logs ppe_alerter --tail 100 -f
if "%logchoice%"=="6" docker logs ppe_capture --tail 100 -f
if "%logchoice%"=="7" docker logs ppe_training --tail 100 -f
if "%logchoice%"=="8" docker logs ppe_postgres --tail 100 -f
if "%logchoice%"=="9" docker logs ppe_redis --tail 100 -f
if /i "%logchoice%"=="S" goto COLLECT_LOGS
if "%logchoice%"=="0" goto MENU

pause
goto LOGS

:GPU_INFO
cls
echo.
echo  [G] GPU INFO
echo  ================================================================
echo.

where nvidia-smi >nul 2>&1
if !errorlevel! neq 0 (
    echo  nvidia-smi not found!
    pause
    goto MENU
)

echo  [System GPU]
echo  ----------------------------------------------------------------
nvidia-smi
echo.

echo  [Docker GPU Test]
echo  ----------------------------------------------------------------
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
if !errorlevel! equ 0 (
    echo.
    echo  [OK] Docker GPU is working!
) else (
    echo.
    echo  [ERROR] Docker GPU not working
)

echo.
pause
goto MENU

:CLEAN
cls
echo.
echo  [C] CLEAN
echo  ================================================================
echo.
set /p confirm="Remove stopped containers? [y/n]: "
if /i not "%confirm%"=="y" goto MENU

docker compose down 2>nul
docker container prune -f
docker network prune -f

echo.
echo  [OK] Cleaned!
echo.
pause
goto MENU

:DEEP_CLEAN
cls
echo.
echo  [D] DEEP CLEAN
echo  ================================================================
echo.
echo  WARNING: Removes build cache!
echo.
set /p confirm="Type 'yes' to confirm: "
if /i not "%confirm%"=="yes" goto MENU

docker compose down 2>nul
docker container prune -f
docker image prune -a -f
docker builder prune -a -f

echo.
echo  [OK] Deep clean complete!
echo.
pause
goto MENU

:RESET_DB
cls
echo.
echo  [R] RESET DATABASE
echo  ================================================================
echo.
echo  WARNING: Deletes all data (violations, datasets)!
echo.
set /p confirm="Type 'yes' to confirm: "
if /i not "%confirm%"=="yes" goto MENU

echo.
echo [*] Stopping containers...
docker compose down 2>nul

echo [*] Removing old PPE containers (fixing conflicts)...
for /f "tokens=*" %%i in ('docker ps -aq --filter "name=ppe_" 2^>nul') do (
    docker rm -f %%i >nul 2>&1
)

echo [*] Removing PostgreSQL volume...
docker volume rm ppe_system_v2_new_postgres_data 2>nul

echo [*] Starting containers...
docker compose up -d

timeout /t 10 >nul
call :HEALTH_CHECK

echo.
echo  [OK] Database reset!
echo.
pause
goto MENU

:FIX_CONTAINERS
cls
echo.
echo  [F] FIX CONTAINERS (Resolve Conflicts)
echo  ================================================================
echo.
echo  This will stop and remove ALL PPE containers to fix conflicts.
echo  Use this when you see "container name already in use" errors.
echo.
set /p confirm="Continue? [y/n]: "
if /i not "%confirm%"=="y" goto MENU

echo.
echo [1/4] Stopping all PPE containers...
for /f "tokens=*" %%i in ('docker ps -aq --filter "name=ppe_" 2^>nul') do (
    docker stop %%i >nul 2>&1
)

echo [2/4] Removing all PPE containers...
for /f "tokens=*" %%i in ('docker ps -aq --filter "name=ppe_" 2^>nul') do (
    docker rm -f %%i >nul 2>&1
)

echo [3/4] Cleaning up networks...
docker network prune -f >nul 2>&1

echo [4/4] Verifying cleanup...
set REMAINING=0
for /f %%i in ('docker ps -aq --filter "name=ppe_" 2^>nul') do set REMAINING=1

if !REMAINING!==0 (
    echo.
    echo  ================================================================
    echo   [OK] All PPE containers removed successfully!
    echo  ================================================================
    echo.
    echo   You can now start the system with options [1] or [2]
) else (
    echo.
    echo  [WARNING] Some containers may still exist.
    echo   Try running Docker Desktop and manually removing them.
)

echo.
pause
goto MENU

:BROWSER
start http://localhost:3001
timeout /t 1 >nul
goto MENU

:EXIT
echo  Bye!
exit /b 0

:CHECK_DOCKER
set DOCKER_OK=0
docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Docker not installed!
    pause
    goto :eof
)
docker info >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Docker not running!
    pause
    goto :eof
)
set DOCKER_OK=1
goto :eof

:TEST_GPU
set GPU_OK=0
echo       Testing Docker GPU access...
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi -L >nul 2>&1
if !errorlevel! equ 0 (
    set GPU_OK=1
)
goto :eof

:CHECK_ENV
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
    ) else (
        echo JWT_SECRET=change-this-secret-key-must-be-at-least-32-chars > .env
        echo POSTGRES_PASSWORD=ppe_secret >> .env
        echo POSTGRES_USER=ppe >> .env
        echo POSTGRES_DB=ppe_detection >> .env
        echo API_USERNAME=admin >> .env
        echo API_PASSWORD=admin123 >> .env
    )
)
goto :eof

:CREATE_DIRS
if not exist "models" mkdir models
if not exist "configs" mkdir configs
if not exist "logs" mkdir logs
if not exist "diagnostics" mkdir diagnostics
goto :eof

:HEALTH_CHECK
echo.
echo  [Health Check]
echo  ----------------------------------------------------------------
curl -s -o nul http://localhost:8000/health 2>nul
if !errorlevel! equ 0 (
    echo  API:        [OK] http://localhost:8000
) else (
    echo  API:        [--]
)
curl -s -o nul http://localhost:3001 2>nul
if !errorlevel! equ 0 (
    echo  Dashboard:  [OK] http://localhost:3001
) else (
    echo  Dashboard:  [--]
)
docker exec ppe_redis redis-cli ping >nul 2>&1
if !errorlevel! equ 0 (
    echo  Redis:      [OK]
) else (
    echo  Redis:      [--]
)
docker exec ppe_postgres pg_isready -U ppe >nul 2>&1
if !errorlevel! equ 0 (
    echo  PostgreSQL: [OK]
) else (
    echo  PostgreSQL: [--]
)
echo  ----------------------------------------------------------------
goto :eof

:CLEAN_OLD_CONTAINERS
REM Remove any conflicting PPE containers from previous installs
for /f "tokens=*" %%i in ('docker ps -aq --filter "name=ppe_" 2^>nul') do (
    docker rm -f %%i >nul 2>&1
)
goto :eof

:SHOW_URLS
echo  ================================================================
echo   Dashboard:  http://localhost:3001
echo   API:        http://localhost:8000
echo   API Docs:   http://localhost:8000/docs
echo  ================================================================
goto :eof
