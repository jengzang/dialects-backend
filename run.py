"""
🚀 項目啟動腳本：負責啟動 FastAPI，支援開發模式與打包模式。
"""
import socket
import time
import threading
import webbrowser
import uvicorn
from app.main import app
from common.config import _RUN_TYPE, APP_NAME, AUTHOR, VERSION, DATE_STR, APP_URL
import sys
import os
import shutil

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


# 启动服务并自动打开浏览器
if __name__ == "__main__":
    def _open_browser(url: str):
        time.sleep(1)
        webbrowser.open(url)
    print_banner_once(style="block")  # 可选: "block" / "boxed" / "minimal"
    if _RUN_TYPE == 'MINE':
        # 跑在局域網ip地址上
        threading.Thread(target=_open_browser, args=(APP_URL,), daemon=True).start()
        uvicorn.run("run:app", host="0.0.0.0", port=5000, reload=True)

    elif _RUN_TYPE == 'EXE':
        threading.Thread(target=_open_browser, args=(APP_URL,), daemon=True).start()
        uvicorn.run(app, host="127.0.0.1", port=5000, reload=False, workers=1)
