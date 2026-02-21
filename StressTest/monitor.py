"""
性能监控脚本 - 在压测期间监控系统资源
Performance Monitoring Script

使用方法:
    python monitor.py --pid <进程ID>

    # 或者自动查找 uvicorn 进程
    python monitor.py --auto

依赖安装:
    pip install psutil
"""

import psutil
import time
import argparse
import sys
from datetime import datetime
import json


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, pid, interval=1):
        self.pid = pid
        self.interval = interval
        self.process = None
        self.metrics = []

        try:
            self.process = psutil.Process(pid)
            print(f"✓ 找到进程: {self.process.name()} (PID: {pid})")
        except psutil.NoSuchProcess:
            print(f"✗ 找不到进程 PID: {pid}")
            sys.exit(1)

    def collect_metrics(self):
        """收集性能指标"""
        try:
            # CPU 使用率
            cpu_percent = self.process.cpu_percent(interval=0.1)

            # 内存使用
            mem_info = self.process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024  # 转换为 MB

            # 线程数
            num_threads = self.process.num_threads()

            # 打开的文件描述符数量
            try:
                num_fds = self.process.num_fds() if hasattr(self.process, 'num_fds') else len(self.process.open_files())
            except:
                num_fds = 0

            # 连接数
            try:
                connections = len(self.process.connections())
            except:
                connections = 0

            metric = {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(mem_mb, 2),
                "num_threads": num_threads,
                "num_fds": num_fds,
                "connections": connections
            }

            return metric

        except psutil.NoSuchProcess:
            print("✗ 进程已终止")
            return None
        except Exception as e:
            print(f"✗ 收集指标时出错: {e}")
            return None

    def run(self, duration=None):
        """运行监控"""
        print("\n" + "="*60)
        print("📊 性能监控开始")
        print("="*60)
        print(f"进程: {self.process.name()} (PID: {self.pid})")
        print(f"监控间隔: {self.interval}秒")
        if duration:
            print(f"监控时长: {duration}秒")
        print("按 Ctrl+C 停止监控")
        print("="*60 + "\n")

        print(f"{'时间':<20} {'CPU%':<10} {'内存(MB)':<12} {'线程':<8} {'连接':<8}")
        print("-" * 60)

        start_time = time.time()
        max_memory = 0
        max_cpu = 0

        try:
            while True:
                metric = self.collect_metrics()
                if metric is None:
                    break

                self.metrics.append(metric)

                # 更新最大值
                max_memory = max(max_memory, metric["memory_mb"])
                max_cpu = max(max_cpu, metric["cpu_percent"])

                # 打印当前指标
                print(f"{datetime.now().strftime('%H:%M:%S'):<20} "
                      f"{metric['cpu_percent']:<10.1f} "
                      f"{metric['memory_mb']:<12.1f} "
                      f"{metric['num_threads']:<8} "
                      f"{metric['connections']:<8}")

                # 检查是否达到监控时长
                if duration and (time.time() - start_time) >= duration:
                    break

                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n\n⚠ 监控被用户中断")

        # 打印统计摘要
        self.print_summary(max_cpu, max_memory)

        # 保存到文件
        self.save_metrics()

    def print_summary(self, max_cpu, max_memory):
        """打印统计摘要"""
        if not self.metrics:
            return

        avg_cpu = sum(m["cpu_percent"] for m in self.metrics) / len(self.metrics)
        avg_memory = sum(m["memory_mb"] for m in self.metrics) / len(self.metrics)

        print("\n" + "="*60)
        print("📈 性能统计摘要")
        print("="*60)
        print(f"采样次数: {len(self.metrics)}")
        print(f"\nCPU 使用率:")
        print(f"  平均: {avg_cpu:.2f}%")
        print(f"  峰值: {max_cpu:.2f}%")
        print(f"\n内存使用:")
        print(f"  平均: {avg_memory:.2f} MB")
        print(f"  峰值: {max_memory:.2f} MB")
        print("="*60 + "\n")

    def save_metrics(self):
        """保存指标到文件"""
        filename = f"performance_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.metrics, f, indent=2, ensure_ascii=False)
            print(f"✓ 性能数据已保存到: {filename}")
        except Exception as e:
            print(f"✗ 保存数据失败: {e}")


def find_uvicorn_process():
    """自动查找 uvicorn 进程"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and any('uvicorn' in str(arg).lower() for arg in cmdline):
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description='FastAPI 性能监控工具')
    parser.add_argument('--pid', type=int, help='要监控的进程 PID')
    parser.add_argument('--auto', action='store_true', help='自动查找 uvicorn 进程')
    parser.add_argument('--interval', type=int, default=1, help='采样间隔（秒），默认 1 秒')
    parser.add_argument('--duration', type=int, help='监控时长（秒），不指定则持续监控')

    args = parser.parse_args()

    # 确定要监控的 PID
    pid = args.pid
    if args.auto:
        pid = find_uvicorn_process()
        if pid is None:
            print("✗ 未找到 uvicorn 进程")
            print("提示: 请先启动 FastAPI 应用，或使用 --pid 手动指定进程 ID")
            sys.exit(1)
        print(f"✓ 自动找到 uvicorn 进程: PID {pid}")

    if pid is None:
        print("✗ 请使用 --pid 指定进程 ID 或使用 --auto 自动查找")
        parser.print_help()
        sys.exit(1)

    # 开始监控
    monitor = PerformanceMonitor(pid, interval=args.interval)
    monitor.run(duration=args.duration)


if __name__ == "__main__":
    main()

