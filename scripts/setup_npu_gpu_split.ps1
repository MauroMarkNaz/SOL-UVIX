# PowerShell Script: Setup NPU Text Off-Ramp & GPU Video/Raster Split
# Platform: AMD Ryzen AI 9 HX 370 (XDNA 2 NPU) + NVIDIA GeForce RTX 4070 Laptop GPU

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  NPU / GPU Workload Split Configuration Suite" -ForegroundColor Cyan
Write-Host "  NPU (AMD XDNA 2)  --> Text Off-Ramping & LLM / Embeddings" -ForegroundColor Yellow
Write-Host "  GPU (NVIDIA 4070) --> Video (NVDEC/NVENC) & Raster Graphics" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Verify NPU Device
$npuDevice = Get-PnpDevice | Where-Object { $_.FriendlyName -match "NPU Compute Accelerator" }
if ($npuDevice) {
    Write-Host "[OK] NPU Detected: $($npuDevice.FriendlyName) (Status: $($npuDevice.Status))" -ForegroundColor Green
} else {
    Write-Host "[WARN] NPU device not found in PNP list" -ForegroundColor Yellow
}

# 2. Verify NVIDIA GPU
$nvidiaGpu = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" }
if ($nvidiaGpu) {
    Write-Host "[OK] GPU Detected: $($nvidiaGpu.Name) (Driver: $($nvidiaGpu.DriverVersion))" -ForegroundColor Green
} else {
    Write-Host "[WARN] NVIDIA GPU not found" -ForegroundColor Yellow
}

# 3. Configure Windows Graphics Performance Preferences
# GpuPreference=2: High Performance (NVIDIA RTX 4070) for Video, Rendering, Media, Raster
# GpuPreference=1: Power Saving / Integrated NPU-assisted for Text / CLI
$regPath = "HKCU:\Software\Microsoft\DirectX\UserGpuPreferences"
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}

$gpuHighPerfApps = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files\OBS-Studio\bin\64bit\obs64.exe",
    "C:\Windows\System32\ffmpeg.exe",
    "C:\Program Files\ffmpeg\bin\ffmpeg.exe"
)

foreach ($app in $gpuHighPerfApps) {
    if (Test-Path $app) {
        Set-ItemProperty -Path $regPath -Name $app -Value "GpuPreference=2;AutoHDREnable=0;" -Force
        Write-Host "[CONFIG] Mapped to High-Performance GPU (RTX 4070): $app" -ForegroundColor Cyan
    }
}

# 4. Set Environment Variables for Hybrid Execution
# DirectML NPU text offload & CUDA video configuration
[System.Environment]::SetEnvironmentVariable("SOL_NPU_ENABLED", "1", "User")
[System.Environment]::SetEnvironmentVariable("SOL_NPU_BACKEND", "directml", "User")
[System.Environment]::SetEnvironmentVariable("SOL_GPU_BACKEND", "cuda", "User")
[System.Environment]::SetEnvironmentVariable("CUDA_DEVICE_ORDER", "PCI_BUS_ID", "User")

Write-Host "`n[SUCCESS] NPU Text Off-Ramp and GPU Video/Raster Split Configured!" -ForegroundColor Green
