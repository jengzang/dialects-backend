"""
[RUN] 項目啟動腳本：負責啟動 FastAPI，支援開發模式與打包模式。
"""
import argparse
import os

# === Banner 配置 ===
_banner_printed = False  # 在启动时打印（只打一次）


def print_banner_once(style="minimal"):
    global _banner_printed

    def print_banner(style="minimal"):
        def _c(color_code):
            def _supports_color():
                # Windows 10+ 基本支持 ANSI；PyInstaller 控制台也通常可用
                return sys.stdout.isatty() and os.environ.get("TERM") != "dumb"

            return f"\033[{color_code}m" if _supports_color() else ""

        # 终端宽度
        width = shutil.get_terminal_size((80, 20)).columns
        width = max(50, min(width, 120))
        line = "=" * width

        title = f"🐍 {APP_NAME}"
        meta = f"開發者: {AUTHOR}   版本: {VERSION}   年月: {DATE_STR}"

        if style == "block":
            block = [
                "\n\n"
                "████    ████     ███    █      █████     ████    █████",
                "█   █     █     █   █   █      █         █         █  ",
                "█   █     █     █████   █      ████      █         █  ",
                "█   █     █     █   █   █      █         █         █  ",
                "████     ████   █   █   █████  █████     ████      █  ",
                "  D        I      A       L       E        C        T",
            ]

            print(_c("36") + "\n".join(block) + _c("0"))
            print(_c("1;37") + APP_NAME + _c("0"))
            print(f"{_c('90')}開發者: {AUTHOR} | 版本: {VERSION} | {DATE_STR}{_c('0')}")
            print()
            return

        if style == "boxed":
            # 方案 C
            content = [
                f"+{'-' * (width - 2)}+",
                f"| {APP_NAME}".ljust(width - 1) + "|",
                f"| 開發者: {AUTHOR}     版本: {VERSION}  {DATE_STR}".ljust(width - 1) + "|",
                f"+{'-' * (width - 2)}+",
            ]
            print(_c("34") + "\n".join(content) + _c("0"))
            return

        # 默认：方案 A 极简
        print(_c("36") + line + _c("0"))
        print(_c("1;37") + title + _c("0"))
        print(_c("90") + meta + _c("0"))
        print(_c("36") + line + _c("0"))

    if not _banner_printed:
        _banner_printed = True
        print_banner(style=style)


def parse_args():
    parser = argparse.ArgumentParser(description='启动 FastAPI 服务')
    parser.add_argument(
        '-r', '--run',
        type=str,
        nargs='?',  # 使位置参数变为可选，有默认值
        choices=['WEB', 'EXE', 'MINE'],
        default='WEB',
        help='运行模式: WEB (默认), EXE, MINE'
    )

    # === [新增] 是否打开浏览器参数 ===
    # action='store_true' 表示：如果命令行里写了 --no-browser，这就变成了 True
    # 默认没写，就是 False
    parser.add_argument(
        '-close', '--close-browser',
        action='store_true',
        help='禁止自動打開瀏覽器 (如果不加此參數，默認會打開)'
    )

    return parser.parse_args()


# 启动服务并自动打开浏览器
if __name__ == "__main__":
    # 4. 定义打开浏览器的函数
    def _open_browser(url: str):
        time.sleep(5)  # 稍微多等一点点，确保服务启动
        print(f"[INFO] 正在打开浏览器: {url}")
        webbrowser.open(url)


    args = parse_args()
    print(f"[INFO] 运行模式: {args.run}")
    # 设置环境变量，这样 config.py 就能读取到
    os.environ['_RUN_TYPE'] = args.run

    from common.config import _RUN_TYPE
    import time
    import threading
    import webbrowser
    import uvicorn
    from app.main import app
    from common.config import APP_NAME, AUTHOR, VERSION, DATE_STR, APP_URL
    import sys
    import shutil

    print_banner_once(style="block")  # 可选: "block" / "boxed" / "minimal"
    # print(_RUN_TYPE)
    # 逻辑：如果没有传入 --no-browser (args.no_browser 为 False)，则 should_open 为 True
    should_open_browser = not args.close_browser

    if _RUN_TYPE == 'MINE':
        if should_open_browser:
            # 跑在局域網ip地址上
            threading.Thread(target=_open_browser, args=(APP_URL,), daemon=True).start()
        uvicorn.run("run:app", host="0.0.0.0", port=5000, reload=True)

    elif _RUN_TYPE == 'EXE':
        if should_open_browser:
            threading.Thread(target=_open_browser, args=(APP_URL,), daemon=True).start()
        else:
            print("[INFO] 已通过参数跳过自动打开浏览器")
        uvicorn.run(app, host="127.0.0.1", port=5000, reload=False, workers=1)
        # uvicorn.run("run:app", host="localhost", port=5000, reload=True)
