#!/bin/bash
# ========================================
# 静态文件部署脚本
# ========================================
# 用途：快速部署前端静态文件到服务器，无需重建 Docker 镜像
# 使用方法：
#   ./deploy_statics.sh           # 部署所有静态文件
#   ./deploy_statics.sh --single  # 仅部署 index.html 和 assets 目录
# ========================================

SERVER="root@47.115.57.138"
REMOTE_PATH="/srv/myapp/statics"
LOCAL_PATH="app/statics"

echo "========================================"
echo "静态文件部署工具"
echo "========================================"
echo ""

# 检查本地静态文件目录是否存在
if [ ! -d "$LOCAL_PATH" ]; then
    echo "错误: 本地静态文件目录不存在: $LOCAL_PATH"
    exit 1
fi

if [ "$1" == "--single" ]; then
    # 单文件模式：只上传 index.html 和 assets
    echo "模式: 快速更新 (index.html + assets)"
    echo ""

    echo "1. 上传 index.html..."
    scp "$LOCAL_PATH/index.html" "${SERVER}:${REMOTE_PATH}/"

    echo "2. 上传 assets 目录..."
    scp -r "$LOCAL_PATH/assets" "${SERVER}:${REMOTE_PATH}/"

else
    # 完整模式：打包上传所有文件
    echo "模式: 完整部署 (所有静态文件)"
    echo ""

    ARCHIVE="statics.tar.gz"

    echo "1. 打包静态文件..."
    tar -czf "$ARCHIVE" -C app statics

    if [ ! -f "$ARCHIVE" ]; then
        echo "错误: 打包失败"
        exit 1
    fi

    FILE_SIZE=$(du -h "$ARCHIVE" | cut -f1)
    echo "   打包完成: $ARCHIVE ($FILE_SIZE)"

    echo "2. 上传到服务器..."
    scp "$ARCHIVE" "${SERVER}:/srv/myapp/"

    echo "3. 在服务器上解压..."
    ssh "$SERVER" "cd /srv/myapp && tar -xzf $ARCHIVE && rm -f $ARCHIVE"

    echo "4. 清理本地临时文件..."
    rm -f "$ARCHIVE"

    echo "5. 验证部署..."
    ssh "$SERVER" "ls -lah /srv/myapp/statics/ | head -20"
fi

echo ""
echo "========================================"
echo "部署完成！"
echo "========================================"
echo ""
echo "提示:"
echo "  - 静态文件已更新，无需重启容器"
echo "  - FastAPI 会实时读取新文件"
echo "  - Worker 重启不会覆盖外部文件"
echo ""
