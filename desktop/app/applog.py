from __future__ import annotations

import logging
import logging.handlers
import os
import sys

import paths
import version

log = logging.getLogger("tunekuo")
log.addHandler(logging.NullHandler())

_seen: dict = {}
_ready = False


def log_file() -> str:
    d = os.path.join(paths.config_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "tunekuo.log")


def _handler():
    try:
        return logging.handlers.RotatingFileHandler(
            log_file(), maxBytes=512 * 1024, backupCount=3, encoding="utf-8")
    except OSError:
        return logging.StreamHandler(sys.stderr)


def _excepthook(exc_type, exc, tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    try:
        log.error("未捕获的异常", exc_info=(exc_type, exc, tb))
    except Exception:
        pass


def setup() -> None:
    global _ready
    if _ready:
        return
    _ready = True
    log.setLevel(logging.DEBUG)
    handler = _handler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(handler)
    sys.excepthook = _excepthook
    log.info("启动 版本=%s python=%s 系统=%s 打包=%s",
             version.VERSION, sys.version.split()[0], sys.platform,
             getattr(sys, "frozen", False))


def install_tk_reporting(root) -> None:
    def report(exc, val, tb) -> None:
        try:
            log.error("界面回调异常", exc_info=(exc, val, tb))
        except Exception:
            pass
    root.report_callback_exception = report


def swallow(where: str) -> None:
    try:
        n = _seen.get(where, 0)
        _seen[where] = n + 1
        if n == 0:
            log.error("已忽略异常 %s", where, exc_info=True)
        elif n == 4:
            log.error("已忽略异常 %s 反复出现，同类不再逐条记录", where)
    except Exception:
        pass
