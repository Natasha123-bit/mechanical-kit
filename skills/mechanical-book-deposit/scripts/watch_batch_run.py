#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盯一次沉淀跑批：交批信号 / 额度拒绝 / 两道预算线 / 卡死，任一命中即退出并可选微信通知。

为什么用时间窗而不是 session_id 聚合：子代理的调用落在 sess_subagent_* 名下，按主会话过滤会把
并行工作漏掉、把「在等子代理」误判成卡死；换新任务（一章一个新会话）也照样跟得住。

用法：
    python3 watch_batch_run.py --since 2026-10-25T03:56 \
        --budget 191500000 --notify-at 161500000 \
        --signal-dir /abs/books/handbook --signal-glob 'PAUSED-*.md' --signal-glob 'STOP-*.md' \
        [--db ~/.zcode/cli/db/db.sqlite] [--wechat weixin:xxx@im.wechat] \
        [--stall-min 20] [--interval 90] [--mark-dir <dir>]

两道线的口径：--budget 是**硬停**（总量 95%，留 5% 返工），--notify-at 是**只报账不停手**（85%）。
两者都是「本阶段累计」，换阶段时传剩余额度（总硬停线 − 已用），别传总预算。

两条不致命的异常：① `user concurrency limit exceeded`（超并发，重试即可）不按额度停机；
② 通知通道失效（iLink `session not ready (ret=-2)`）只写 `.notify-failed.log` 并继续，
交批结论以磁盘信号（PAUSED-*.md / 验收记录 / 进度表）为准，不依赖微信。

退出码：0 交批信号 / 3 额度或上游拒绝 / 4 卡死 / 5 到硬停线 / 130 被中断。
"""
from __future__ import annotations

import argparse
import glob
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta

QUOTA_PAT = ("quota", "insufficient", "exhaust", "余额", "额度", "402", "403",
             "rate_limit", "rate limit", "payment")


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def notify(target: str | None, mark_dir: str, text: str, tag: str) -> None:
    if not target:
        print(f"[{now()}] (未配 --wechat，跳过通知) {tag}", flush=True)
        return
    mark = os.path.join(mark_dir, f".notified-{tag}")
    if os.path.exists(mark):
        return
    # 通知通道会长期失效（iLink `session not ready (ret=-2)`），所以：
    # ① 重试只拉短退避，别把轮询卡住半小时；② 失败写盘，磁盘上的信号才是真相。
    for i in range(3):
        try:
            r = subprocess.run(["hermes", "send", "-t", target, text],
                               capture_output=True, text=True, timeout=90)
            if r.returncode == 0:
                open(mark, "w").write(now())
                print(f"[{now()}] 微信已通知（{tag}）", flush=True)
                return
            detail = (r.stderr or r.stdout)[-200:]
            print(f"[{now()}] 微信失败({i+1}/3)：{detail}", flush=True)
        except Exception as exc:  # noqa: BLE001
            detail = str(exc)
            print(f"[{now()}] 微信异常({i+1}/3)：{exc}", flush=True)
        time.sleep(20 * (i + 1))
    try:
        with open(os.path.join(mark_dir, ".notify-failed.log"), "a", encoding="utf-8") as fh:
            fh.write(f"{now()} {tag}\t{detail}\n")
    except OSError:
        pass
    print(f"[{now()}] 通知未送达（已记 .notify-failed.log，交批结论看磁盘信号）", flush=True)


def usage(db: str, t0_ms: int) -> dict:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)  # 只读；不要加 immutable=1（会跳过 -wal）
    try:
        n, inp, cr, out, tot, last, sess = c.execute(
            """SELECT count(*), coalesce(sum(input_tokens),0), coalesce(sum(cache_read_input_tokens),0),
                      coalesce(sum(output_tokens),0), coalesce(sum(provider_total_tokens),0),
                      max(started_at), count(DISTINCT session_id)
               FROM model_usage WHERE started_at>=?""", (t0_ms,)).fetchone()
        errs = c.execute(
            """SELECT error_type, error_code, error_message, started_at FROM model_usage
               WHERE started_at>=? AND (error_type IS NOT NULL OR error_code IS NOT NULL
                                        OR error_message IS NOT NULL)
               ORDER BY started_at DESC LIMIT 5""", (t0_ms,)).fetchall()
        model = c.execute(
            """SELECT provider_id, model_id, variant FROM model_usage
               WHERE started_at>=? ORDER BY started_at DESC LIMIT 1""", (t0_ms,)).fetchone()
        return {"n": n, "inp": inp, "cr": cr, "out": out, "tot": tot,
                "last": last, "sess": sess, "errs": errs, "model": model}
    finally:
        c.close()


def summary(u: dict) -> str:
    m = u.get("model") or ("?", "?", "?")
    return (f"累计 {u['tot']/1e6:.1f}M token（cacheRead {u['cr']/1e6:.1f}M）· 调用 {u['n']} · "
            f"{u['sess']} 路 · 模型 {m[1]}/{m[2]}")


def new_signals(signal_dir: str, patterns: list[str], t0_ms: int) -> list[str]:
    hits = []
    for pat in patterns:
        for p in glob.glob(os.path.join(signal_dir, pat)):
            if os.path.getmtime(p) * 1000 > t0_ms:
                hits.append(p)
    return sorted(hits)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="本阶段起跑时刻（ISO，本地时区）")
    ap.add_argument("--budget", type=int, required=True, help="硬停阈值（本阶段累计 token）")
    ap.add_argument("--notify-at", type=int, default=None, help="只报账不停手的阈值")
    ap.add_argument("--signal-dir", required=True)
    ap.add_argument("--signal-glob", action="append", default=None,
                    help="可重复；缺省盯 PAUSED-*.md 与 STOP-*.md（显式给出则只盯给出的）")
    ap.add_argument("--db", default=os.path.expanduser("~/.zcode/cli/db/db.sqlite"))
    ap.add_argument("--wechat", default=None, help="如 weixin:<id>@im.wechat；不给就只打屏")
    ap.add_argument("--stall-min", type=int, default=20)
    ap.add_argument("--interval", type=int, default=90)
    ap.add_argument("--mark-dir", default=None)
    a = ap.parse_args()

    a.signal_glob = a.signal_glob or ["PAUSED-*.md", "STOP-*.md"]
    t0_ms = int(datetime.fromisoformat(a.since).timestamp() * 1000)
    mark_dir = a.mark_dir or a.signal_dir
    print(f"[{now()}] 盯跑批 since={a.since} 硬停={a.budget/1e8:.2f}亿 "
          f"通知={('%.2f亿' % (a.notify_at/1e8)) if a.notify_at else '关'} "
          f"信号={a.signal_glob}", flush=True)

    last_n = -1
    while True:
        # 交件信号必须先查：它只依赖磁盘，不能被读库失败挡住
        # （2026-10-26 实测教训：db 在 WAL 下偶发「unable to open」，旧版先读库、
        #  读失败就 continue，结果 PAUSED-*.md 落盘 3 小时后仍没被发现）
        hits = new_signals(a.signal_dir, a.signal_glob, t0_ms)
        if hits:
            name = os.path.basename(hits[-1])
            print(f"[{now()}] ★ 交批信号 {[os.path.basename(h) for h in hits]}", flush=True)
            try:
                u = usage(a.db, t0_ms)
                print(summary(u), flush=True)
                body = f"【{name}】\n{summary(u)}\n落盘后由你验收。"
            except sqlite3.Error as exc:
                body = f"【{name}】\n（读库失败，账目未取到：{exc}）\n落盘后由你验收。"
            notify(a.wechat, mark_dir, body, tag=name.replace(".md", ""))
            return 0

        # WAL 下 sqlite 偶发「unable to open」：单次失败就 continue 会**跳过本轮的预算与额度判定**。
        # 2026-10-26 实测：21:53:59 那一轮读库失败，正好是该 20M 硬停线要触发的时刻，
        # 结果线被静默跨过（是人工 kill 才停下的）。改为短退避重试，全失败要显式喊出来。
        u = None
        for _try in range(4):
            try:
                u = usage(a.db, t0_ms)
                break
            except sqlite3.Error as exc:
                if _try == 3:
                    print(f"[{now()}] ★ 读库连续失败 4 次 —— 本轮预算/额度未判定（交批信号仍在查）：{exc}", flush=True)
                else:
                    time.sleep(0.5 * (2 ** _try))
        if u is None:
            time.sleep(a.interval)
            continue

        for et, ec, em, _ts in u["errs"]:
            blob = f"{et or ''} {ec or ''} {em or ''}".lower()
            # 并发超限不是额度：rate_limited 同时盖住两种含义，后者重试就好，别停机
            if "concurrency" in blob or "too many concurrent" in blob:
                if u["n"] != last_n:
                    print(f"[{now()}] 并发超限（不停机）：{et} {em}", flush=True)
                continue
            if any(k in blob for k in QUOTA_PAT):
                print(f"[{now()}] ★ 额度/上游拒绝：{et} {ec} {em}", flush=True)
                notify(a.wechat, mark_dir,
                       f"【跑批停了·额度或上游拒绝】{et} {ec}\n{summary(u)}\n按约定：不换模型、不续跑。",
                       tag="quota")
                return 3

        if a.notify_at and u["tot"] >= a.notify_at:
            print(f"[{now()}] ★ 到通知线 {u['tot']/1e8:.2f} 亿（继续跑）", flush=True)
            notify(a.wechat, mark_dir,
                   f"【到 85% 线 {u['tot']/1e8:.2f} 亿，按约定继续跑到硬停线】\n{summary(u)}",
                   tag="budget85")
            a.notify_at = None

        if u["tot"] >= a.budget:
            print(f"[{now()}] ★ 到硬停线 {u['tot']/1e8:.2f} 亿", flush=True)
            notify(a.wechat, mark_dir,
                   f"【到硬停线 {u['tot']/1e8:.2f} 亿，停手】\n{summary(u)}\n余额留给收尾与返工。",
                   tag="budget")
            return 5

        if u["last"] and (time.time() - u["last"] / 1000) > a.stall_min * 60:
            mins = int((time.time() - u["last"] / 1000) / 60)
            print(f"[{now()}] ★ 卡死 {mins} 分钟", flush=True)
            notify(a.wechat, mark_dir,
                   f"【跑批疑似卡死】{mins} 分钟无新调用\n{summary(u)}\n不擅自重启。", tag="stall")
            return 4

        if u["n"] != last_n:
            print(f"[{now()}] {summary(u)}", flush=True)
            last_n = u["n"]
        time.sleep(a.interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
