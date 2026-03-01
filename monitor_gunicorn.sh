#!/bin/bash
# Gunicorn 进程监控和清理脚本
# 用途：检测并清理僵尸 Gunicorn 进程

LOG_FILE="/var/log/gunicorn_monitor.log"
MAX_WORKERS=4  # 最大允许的 worker 数量（master + 3 workers）

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 统计 gunicorn 进程数量
count_processes() {
    ps aux | grep -E "gunicorn.*serve:app" | grep -v grep | wc -l
}

# 获取所有 gunicorn 进程的 PID
get_all_pids() {
    ps aux | grep -E "gunicorn.*serve:app" | grep -v grep | awk '{print $2}'
}

# 获取 master 进程 PID
get_master_pid() {
    ps aux | grep -E "gunicorn.*serve:app" | grep "master" | grep -v grep | awk '{print $2}' | head -1
}

# 主逻辑
main() {
    log "=== 开始检查 Gunicorn 进程 ==="

    PROCESS_COUNT=$(count_processes)
    log "当前 Gunicorn 进程数: $PROCESS_COUNT"

    if [ "$PROCESS_COUNT" -gt "$MAX_WORKERS" ]; then
        log "⚠️ 检测到进程数超标！正在清理..."

        # 获取 master 进程
        MASTER_PID=$(get_master_pid)

        if [ -n "$MASTER_PID" ]; then
            log "保留 master 进程: $MASTER_PID"

            # 获取所有进程
            ALL_PIDS=$(get_all_pids)

            # 杀掉除 master 及其子进程外的所有进程
            for PID in $ALL_PIDS; do
                # 检查是否是 master 的子进程
                PPID=$(ps -o ppid= -p "$PID" 2>/dev/null | tr -d ' ')

                if [ "$PID" != "$MASTER_PID" ] && [ "$PPID" != "$MASTER_PID" ]; then
                    log "🔪 杀掉僵尸进程: $PID (父进程: $PPID)"
                    kill -9 "$PID" 2>/dev/null
                fi
            done

            log "✅ 清理完成"
        else
            log "❌ 未找到 master 进程，可能需要手动重启"
        fi
    else
        log "✅ 进程数正常"
    fi

    log "=== 检查完成 ==="
    echo ""
}

main
