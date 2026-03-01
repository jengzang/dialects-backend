# ========================================
# 静态文件部署脚本
# ========================================
# 用途：快速部署前端静态文件到服务器，无需重建 Docker 镜像
# 使用方法：
#   .\deploy_statics.ps1           # 部署所有静态文件
#   .\deploy_statics.ps1 -Single   # 仅部署 index.html 和 assets 目录
# ========================================

param(
    [switch]$Single = $false
)

$SERVER = "root@47.115.57.138"
$REMOTE_PATH = "/srv/myapp/statics"
$LOCAL_PATH = "app/statics"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "静态文件部署工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查本地静态文件目录是否存在
if (-not (Test-Path $LOCAL_PATH)) {
    Write-Host "错误: 本地静态文件目录不存在: $LOCAL_PATH" -ForegroundColor Red
    exit 1
}

if ($Single) {
    # 单文件模式：只上传 index.html 和 assets
    Write-Host "模式: 快速更新 (index.html + assets)" -ForegroundColor Yellow
    Write-Host ""

    Write-Host "1. 上传 index.html..." -ForegroundColor Green
    scp "$LOCAL_PATH/index.html" "${SERVER}:${REMOTE_PATH}/"

    Write-Host "2. 上传 assets 目录..." -ForegroundColor Green
    scp -r "$LOCAL_PATH/assets" "${SERVER}:${REMOTE_PATH}/"

} else {
    # 完整模式：打包上传所有文件
    Write-Host "模式: 完整部署 (所有静态文件)" -ForegroundColor Yellow
    Write-Host ""

    $ARCHIVE = "statics.tar.gz"

    Write-Host "1. 打包静态文件..." -ForegroundColor Green
    tar -czf $ARCHIVE -C app statics

    if (-not (Test-Path $ARCHIVE)) {
        Write-Host "错误: 打包失败" -ForegroundColor Red
        exit 1
    }

    $fileSize = (Get-Item $ARCHIVE).Length / 1MB
    Write-Host "   打包完成: $ARCHIVE ($([math]::Round($fileSize, 2)) MB)" -ForegroundColor Gray

    Write-Host "2. 上传到服务器..." -ForegroundColor Green
    scp $ARCHIVE "${SERVER}:/srv/myapp/"

    Write-Host "3. 在服务器上解压..." -ForegroundColor Green
    ssh $SERVER "cd /srv/myapp && tar -xzf $ARCHIVE && rm -f $ARCHIVE"

    Write-Host "4. 清理本地临时文件..." -ForegroundColor Green
    Remove-Item $ARCHIVE

    Write-Host "5. 验证部署..." -ForegroundColor Green
    ssh $SERVER "ls -lah /srv/myapp/statics/ | head -20"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "部署完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "提示:" -ForegroundColor Yellow
Write-Host "  - 静态文件已更新，无需重启容器" -ForegroundColor Gray
Write-Host "  - FastAPI 会实时读取新文件" -ForegroundColor Gray
Write-Host "  - Worker 重启不会覆盖外部文件" -ForegroundColor Gray
Write-Host ""
