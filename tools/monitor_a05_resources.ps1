param(
    [Parameter(Mandatory = $true)]
    [int]$ServerProcessId,
    [Parameter(Mandatory = $true)]
    [string]$Output,
    [int]$DurationSeconds = 180,
    [int]$IntervalMilliseconds = 500,
    [string]$StopFile = ""
)

$ErrorActionPreference = "Stop"
$watch = [System.Diagnostics.Stopwatch]::StartNew()
$samples = 0
$peakBackendWorkingSetBytes = 0L
$peakSystemRamUsedBytes = 0L
$peakGpuMemoryUsedMiB = 0
$nvidiaSmi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue

while ($watch.Elapsed.TotalSeconds -lt $DurationSeconds) {
    if ($StopFile -and (Test-Path -LiteralPath $StopFile)) {
        break
    }
    $backend = Get-Process -Id $ServerProcessId -ErrorAction SilentlyContinue
    if ($null -ne $backend) {
        $peakBackendWorkingSetBytes = [Math]::Max(
            $peakBackendWorkingSetBytes,
            [int64]$backend.WorkingSet64
        )
    }

    $os = Get-CimInstance Win32_OperatingSystem
    $usedBytes = [int64](($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) * 1KB)
    $peakSystemRamUsedBytes = [Math]::Max($peakSystemRamUsedBytes, $usedBytes)

    if ($null -ne $nvidiaSmi) {
        $gpuValues = & $nvidiaSmi.Source --query-gpu=memory.used --format=csv,noheader,nounits
        foreach ($gpuValue in $gpuValues) {
            $parsed = 0
            if ([int]::TryParse($gpuValue.Trim(), [ref]$parsed)) {
                $peakGpuMemoryUsedMiB = [Math]::Max($peakGpuMemoryUsedMiB, $parsed)
            }
        }
    }

    $samples += 1
    Start-Sleep -Milliseconds $IntervalMilliseconds
}

$result = [ordered]@{
    server_process_id = $ServerProcessId
    duration_seconds = [Math]::Round($watch.Elapsed.TotalSeconds, 3)
    interval_milliseconds = $IntervalMilliseconds
    samples = $samples
    peak_backend_working_set_mib = [Math]::Round($peakBackendWorkingSetBytes / 1MB, 2)
    peak_system_ram_used_gib = [Math]::Round($peakSystemRamUsedBytes / 1GB, 2)
    peak_gpu_memory_used_mib = $peakGpuMemoryUsedMiB
    gpu_probe_available = ($null -ne $nvidiaSmi)
}

$parent = Split-Path -Parent $Output
if ($parent) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
}
$result | ConvertTo-Json | Set-Content -Encoding utf8 -Path $Output
$result | ConvertTo-Json
