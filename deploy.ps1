# ============================================================
# TTS 服务部署脚本 (Windows PowerShell)
#
# 前置条件：
#   1. 本机已安装 ssh 和 scp 命令（Windows 10+ 自带）
#   2. 服务器 172.31.8.3:2220 已安装 Docker
#
# 使用方式：
#   .\deploy.ps1                       # 部署全部服务
#   .\deploy.ps1 -Service teleai       # 只部署 TeleAI
#   .\deploy.ps1 -SkipUpload           # 跳过上传，直接构建（服务器已有文件时）
# ============================================================

param(
    [string]$Server     = "172.31.8.3",
    [string]$SshPort    = "2220",
    [string]$User       = "root",
    [string]$RemoteDir  = "/opt/tts",
    [string]$Service    = "",           # 留空 = 全部
    [switch]$SkipUpload = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$SshTarget   = "${User}@${Server}"
$SshOpts     = "-p $SshPort"

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  TTS 服务部署" -ForegroundColor Cyan
Write-Host "  目标: ${SshTarget}:${SshPort}" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# ---------- 1. 上传项目文件 ----------
if (-not $SkipUpload) {
    Write-Host "`n[1/3] 上传项目文件..." -ForegroundColor Yellow

    # 先确保远程目录存在
    ssh $SshOpts $SshTarget "mkdir -p ${RemoteDir}"

    # 打包需要上传的文件（排除不必要的内容）
    $tarFile = "$env:TEMP\tts-deploy.tar.gz"
    Write-Host "  打包项目中..."

    $excludePatterns = @(
        "__pycache__", "*.pyc", ".git", ".venv", "venv",
        "*.mp3", "*.wav", "*.flac", ".vscode", ".idea"
    )

    # 生成 tar 排除参数
    $excludeArgs = ($excludePatterns | ForEach-Object { "--exclude=$_" })

    # 打包
    Push-Location $ProjectRoot
    tar -czf $tarFile $excludeArgs `
        tts_common `
        tts `
        edge-tts `
        tts4sherpav1.0 `
        Dockerfile `
        docker-compose.yml `
        .dockerignore 2>$null

    Pop-Location

    # 上传
    Write-Host "  上传到服务器..."
    scp -P $SshPort $tarFile "${SshTarget}:${RemoteDir}/deploy.tar.gz"

    # 解压
    Write-Host "  解压..."
    ssh $SshOpts $SshTarget "cd ${RemoteDir} && tar -xzf deploy.tar.gz && rm -f deploy.tar.gz"

    Remove-Item $tarFile -Force -ErrorAction SilentlyContinue
    Write-Host "  上传完成。" -ForegroundColor Green
}
else {
    Write-Host "`n[1/3] 跳过上传。" -ForegroundColor Yellow
}

# ---------- 2. 检查 Docker 环境 ----------
Write-Host "`n[2/3] 检查 Docker 环境..." -ForegroundColor Yellow

$dockerCheck = ssh $SshOpts $SshTarget "docker --version 2>&1 && docker compose version 2>&1"
Write-Host $dockerCheck

if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: 服务器未安装 Docker，请先安装。" -ForegroundColor Red
    Write-Host ""
    Write-Host "安装 Docker（服务器上执行）：" -ForegroundColor Yellow
    Write-Host "  curl -fsSL https://get.docker.com | sh"
    Write-Host "  systemctl enable docker --now"
    exit 1
}

# ---------- 3. 构建并启动 ----------
Write-Host "`n[3/3] 构建并启动服务..." -ForegroundColor Yellow

if ($Service) {
    ssh $SshOpts $SshTarget "cd ${RemoteDir} && docker compose build $Service && docker compose up -d $Service"
} else {
    ssh $SshOpts $SshTarget "cd ${RemoteDir} && docker compose build && docker compose up -d"
}

# ---------- 4. 显示状态和 Token ----------
Write-Host "`n========== 服务状态 ==========" -ForegroundColor Cyan
ssh $SshOpts $SshTarget "cd ${RemoteDir} && docker compose ps"

Write-Host "`n========== 启动 Token ==========" -ForegroundColor Cyan
ssh $SshOpts $SshTarget "cd ${RemoteDir} && docker compose logs 2>&1 | grep -A1 'API Token' || echo '启动中，稍后运行: docker compose logs | grep API Token'"

Write-Host @"

================================================
  部署完成！
================================================

服务地址:
  TeleAI:  http://172.31.8.3:8000
  Edge:    http://172.31.8.3:7899
  Sherpa:  http://172.31.8.3:7898

Swagger:   http://172.31.8.3:8000/docs

================================================
"@ -ForegroundColor Cyan
