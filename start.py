# -*- coding: utf-8 -*-
"""
start.py — 科研助手 Agent 系统一键启动
同时拉起后端(uvicorn:8000)与前端(vite:5173)，按 Ctrl+C 停止。
用法：python start.py
"""
import os
import time
import socket
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "frontend")
PY = os.path.join(BACKEND, ".venv", "Scripts", "python.exe")


def wait_port(port, timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        try:
            s = socket.create_connection(("127.0.0.1", port), 1)
            s.close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


def main():
    if not os.path.exists(PY):
        print("未找到后端虚拟环境，请先在 backend 下创建 .venv 并安装 requirements.txt")
        return
    procs = []
    try:
        print("[1/2] 启动后端 (uvicorn:8000) ...")
        procs.append(subprocess.Popen(
            [PY, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=BACKEND))
        print("[2/2] 启动前端 (vite:5173) ...")
        if os.name == "nt":
            procs.append(subprocess.Popen(["npm.cmd", "run", "dev"], cwd=FRONTEND))
        else:
            procs.append(subprocess.Popen(["npm", "run", "dev"], cwd=FRONTEND))

        ok_b = wait_port(8000)
        ok_f = wait_port(5173)
        if ok_b and ok_f:
            print("\n✅ 科研助手 Agent 系统已启动：")
            print("   → 访问 http://localhost:5173")
            print("   后端接口：http://localhost:8000  (docs: /docs)")
        else:
            print("\n⚠ 未完全就绪：后端" + ("OK" if ok_b else "失败")
                  + " / 前端" + ("OK" if ok_f else "失败"))
        print("按 Ctrl+C 停止服务 ...")

        test_sec = float(os.environ.get("START_TEST_SECONDS", "0"))
        end = time.time() + test_sec if test_sec > 0 else None
        while True:
            time.sleep(1)
            if end and time.time() >= end:
                break
    except KeyboardInterrupt:
        print("\n正在停止 ...")
    finally:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        time.sleep(1)
        for p in procs:
            try:
                p.kill()
            except Exception:
                pass
        print("服务已停止")


if __name__ == "__main__":
    main()
