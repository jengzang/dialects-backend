# 设置控制台编码为 UTF-8，解决中文乱码问题
# 必须在任何输出之前设置
$null = chcp 65001
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

# ================= 配置区域 =================
$SERVER_IP   = "47.115.57.138"
$SERVER_USER = "root"
$IMAGE_NAME  = "myapp"
$TAG         = "latest"
$TAR_FILE    = "myapp.tar"
$REMOTE_DIR  = "/srv"
$DOCKER_EXE  = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
$PASSWORD = "Yz031209@@"
# ===========================================

# --- 1. 检查并自动启动 Docker ---
Write-Host ">>> [0/6] 检查 Docker 状态..." -ForegroundColor Cyan

# 检查 Docker Desktop 进程是否在运行
$dockerProcess = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue

if (!$dockerProcess) {
    Write-Host "⚠️  Docker 未运行，正在尝试启动..." -ForegroundColor Yellow
    if (Test-Path $DOCKER_EXE) {
        Start-Process -FilePath $DOCKER_EXE
    } else {
        Write-Error "❌ 找不到 Docker Desktop，请确认安装路径: $DOCKER_EXE"
        exit
    }

    # 循环等待 Docker 引擎就绪
    Write-Host "⏳ 正在等待 Docker 引擎启动 (可能需要几十秒)..." -NoNewline
    $retries = 0
    while ($true) {
        # 尝试运行 docker info，如果不报错说明引擎好了
        docker info > $null 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " 就绪！" -ForegroundColor Green
            break
        }
        if ($retries -gt 60) { # 超过 2 分钟超时
            Write-Error "`n❌ Docker 启动超时，请手动检查。"
            exit
        }
        Start-Sleep -Seconds 2
        Write-Host "." -NoNewline
        $retries++
    }
} else {
    Write-Host "✅ Docker 正在运行" -ForegroundColor Green
}

# --- 2. 构建镜像 ---
Write-Host "`n>>> [1/6] 开始构建 Docker 镜像..." -ForegroundColor Cyan
docker build -t "${IMAGE_NAME}:${TAG}" .
if ($LASTEXITCODE -ne 0) { Write-Error "❌ 构建失败"; exit }

# --- 3. 导出镜像 ---
Write-Host ">>> [2/6] 导出镜像为 tar 包..." -ForegroundColor Cyan
docker save "${IMAGE_NAME}:${TAG}" -o $TAR_FILE
if ($LASTEXITCODE -ne 0) { Write-Error "❌ 导出失败"; exit }

# --- 4. 上传文件 ---
Write-Host ">>> [3/6] 上传 tar 包到服务器 ($SERVER_IP)..." -ForegroundColor Cyan

# 使用 pscp (PuTTY) 或 scp
# 如果没有安装 PuTTY，可以使用 SSH 密钥认证（推荐）
if (Get-Command pscp -ErrorAction SilentlyContinue) {
    # 使用 PuTTY 的 pscp
    echo y | pscp -pw $PASSWORD $TAR_FILE "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/"
} elseif (Get-Command sshpass -ErrorAction SilentlyContinue) {
    # 如果安装了 sshpass（通过 Cygwin 或 WSL）
    sshpass -p $PASSWORD scp $TAR_FILE "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/"
} else {
    # 使用原生 scp（需要手动输入密码或配置 SSH 密钥）
    Write-Host "提示: 请输入服务器密码" -ForegroundColor Yellow
    scp $TAR_FILE "${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/"
}

if ($LASTEXITCODE -ne 0) { Write-Error "❌ 上传失败"; exit }

# --- 5. 清理本地文件 ---
Write-Host ">>> [4/6] 清理本地临时文件..." -ForegroundColor Cyan
Remove-Item $TAR_FILE

# --- 6. 远程部署 (逻辑重写) ---
Write-Host ">>> [5/6] 远程连接服务器并执行部署..." -ForegroundColor Cyan

# 1. 构造远程执行的脚本 (使用 Here-String 语法)
# 注意：这里面的命令是发给 Linux 执行的，所以可以使用 || 和 Bash 语法
$RemoteScript = @"
    echo '--- 正在加载镜像 ---'
    docker load -i ${REMOTE_DIR}/${TAR_FILE}

    echo '--- 删除旧容器 (如果存在) ---'
    # 这里的 || true 在 Linux Bash 中有效，但在 PowerShell 本地会报错，所以必须包在字符串里发过去
    docker rm -f ${IMAGE_NAME} || true

    echo '--- 启动新容器 ---'
    docker run -d --name ${IMAGE_NAME} \
        -p 127.0.0.1:5000:5000 \
        -e FORWARDED_ALLOW_IPS='*' \
        -v /srv/myapp/data:/app/data \
        -v /srv/myapp/logs:/app/logs \
        ${IMAGE_NAME}:${TAG}

    echo '--- 清理服务器上的 tar 包 ---'
    rm ${REMOTE_DIR}/${TAR_FILE}
"@

# 2. 发送命令
# 使用 plink (PuTTY) 或 ssh
if (Get-Command plink -ErrorAction SilentlyContinue) {
    # 使用 PuTTY 的 plink
    echo y | plink -pw $PASSWORD "${SERVER_USER}@${SERVER_IP}" $RemoteScript
} elseif (Get-Command sshpass -ErrorAction SilentlyContinue) {
    # 如果安装了 sshpass
    sshpass -p $PASSWORD ssh "${SERVER_USER}@${SERVER_IP}" $RemoteScript
} else {
    # 使用原生 ssh（需要手动输入密码或配置 SSH 密钥）
    Write-Host "提示: 请输入服务器密码" -ForegroundColor Yellow
    ssh "${SERVER_USER}@${SERVER_IP}" $RemoteScript
}

# --- 7. 验证 ---
Write-Host ">>> [6/6] 部署完成！查看日志..." -ForegroundColor Green

if (Get-Command plink -ErrorAction SilentlyContinue) {
    echo y | plink -pw $PASSWORD "${SERVER_USER}@${SERVER_IP}" "docker logs --tail 20 -f ${IMAGE_NAME}"
} elseif (Get-Command sshpass -ErrorAction SilentlyContinue) {
    sshpass -p $PASSWORD ssh "${SERVER_USER}@${SERVER_IP}" "docker logs --tail 20 -f ${IMAGE_NAME}"
} else {
    Write-Host "提示: 请输入服务器密码" -ForegroundColor Yellow
    ssh "${SERVER_USER}@${SERVER_IP}" "docker logs --tail 20 -f ${IMAGE_NAME}"
}

Read-Host "按回车键退出..."