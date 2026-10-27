#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""daemonize —— 让子进程真正脱离调用方（关 Hermes / /new / 压缩都带不走它）。

macOS 没有 setsid(1)，用 fork + setsid + execvp 自己做：

    python3 daemonize.py /bin/sh -c 'exec node ~/.hermes/cache/scratch/zcli/zcode.cjs -p "$(cat dispatch.md)" --cwd books/handbook'

约定：
- 打印子进程 pid 后立刻返回（调用方可以放心地把它当前台命令跑）。
- 子进程 PPID=1，Hermes 的「后台任务」列表里永远看不到它 —— 这是设计，查活在用 `ps -o pid,ppid,etime,command -p <pid>`。
- 不给参数时打印用法并退出 2。
"""
import os
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
        return 2
    cmd = sys.argv[1:]
    pid = os.fork()
    if pid > 0:                      # 父进程：报 pid 就走
        print(pid)
        return 0
    os.setsid()                      # 子进程：新会话，脱离控制终端
    if os.fork() > 0:                # 二次 fork，确保不是会话首进程
        os._exit(0)
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    try:
        os.execvp(cmd[0], cmd)
    finally:
        os._exit(127)


if __name__ == "__main__":
    sys.exit(main())
