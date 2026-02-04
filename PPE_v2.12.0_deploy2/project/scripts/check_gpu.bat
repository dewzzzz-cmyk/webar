@echo off
echo ================================================================
echo PPE DETECTION SYSTEM - GPU DIAGNOSTICS
echo ================================================================
echo.

echo [1/5] Checking NVIDIA Driver...
nvidia-smi --version 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] NVIDIA driver not found!
    echo Install from: https://www.nvidia.com/drivers
    goto :end
)

echo.
echo [2/5] NVIDIA GPU Status:
nvidia-smi
echo.

echo [3/5] Checking Docker GPU support...
docker info | findstr "Runtimes"
echo.

echo [4/5] Testing GPU in Docker container...
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Docker GPU support not working!
    echo.
    echo To fix, install NVIDIA Container Toolkit:
    echo 1. Download from: https://github.com/NVIDIA/nvidia-container-toolkit
    echo 2. Or run in WSL2: 
    echo    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    echo    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey ^| sudo apt-key add -
    echo    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list ^| sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    echo    sudo apt-get update
    echo    sudo apt-get install -y nvidia-docker2
    echo    sudo systemctl restart docker
    goto :end
)
echo [OK] Docker GPU support working!
echo.

echo [5/5] Checking PPE detector GPU status...
docker exec ppe_detector python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}');" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] PPE detector not running or torch not available
)
echo.

echo ================================================================
echo DIAGNOSTICS COMPLETE
echo ================================================================

:end
pause
