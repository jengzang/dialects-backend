#!/bin/bash
# Gunicorn 安全重启脚本
# 确保旧进程被完全关闭后再启动新进程

PROJECT_DIR="/path/to/your/project"  # 修改为你的项目路径
LOG_FILE="/var/log/gunicorn_restart.log"
PID_FILE="/var/run/gunicorn.pid"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 停止所有 gunicorn 进程
stop_gunicorn() {
    log "=== 停止 Gunicorn ==="

    # 查找所有 gunicorn 进程
    PIDS=$(ps aux | grep -E "gunicorn.*serve:app" | grep -v grep | awk '{print $2}')

    if [ -z "$PIDS" ]; then
        log "没有运行中的 Gunicorn 进程"
        return 0
    fi

    log "找到进程: $PIDS"

    # 先尝试优雅关闭（SIGTERM）
    log "发送 SIGTERM 信号..."
    for PID in $PIDS; do
        kill -TERM "$PID" 2>/dev/null
    done

    # 等待 30 秒
    log "等待进程退出（最多 30 秒）..."
    for i in {1..30}; do
        REMAINING=$(ps aux | grep -E "gunicorn.*serve:app" | grep -v grep | wc -l)
        if [ "$REMAINING" -eq 0 ]; then
            log "✅ 所有进程已正常退出"
            return 0
        fi
        sleep 1
    done

    # 如果还有进程，强制杀掉（SIGKILL）
    REMAINING_PIDS=$(ps aux | grep -E "gunicorn.*serve:app" | grep -v grep | awk '{print $2}')
    if [ -n "$REMAINING_PIDS" ]; then
        log "⚠️ 仍有进程未退出，强制杀掉: $REMAINING_PIDS"
        for PID in $REMAINING_PIDS; do
            kill -9 "$PID" 2>/dev/null
        done
        sleep 2
    fi

    log "✅ Gunicorn 已停止"
}

# 启动 gunicorn
start_gunicorn() {
    log "=== 启动 Gunicorn ==="

    cd "$PROJECT_DIR" || {
        log "❌ 无法进入项目目录: $PROJECT_DIR"
        exit 1
    }

    # 启动 gunicorn
    nohup gunicorn -c gunicorn_config.py serve:app > /dev/null 2>&1 &
    NEW_PID=$!

    # 保存 PID
    echo "$NEW_PID" > "$PID_FILE"

    log "✅ Gunicorn 已启动 (PID: $NEW_PID)"

    # 等待 5 秒检查是否启动成功
    sleep 5
    if ps -p "$NEW_PID" > /dev/null; then
        log "✅ Gunicorn 运行正常"
    else
        log "❌ Gunicorn 启动失败"
        exit 1
    fi
}

# 主逻辑
main() {
    log "========================================="
    log "开始重启 Gunicorn"
    log "========================================="

    stop_gunicorn
    start_gunicorn

    log "========================================="
    log "重启完成"
    log "========================================="
    echo ""
}

main
