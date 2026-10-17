from __future__ import annotations

import json
import os
import socket
import threading
from typing import Callable, List, Optional

HOST = "127.0.0.1"
PORT = 45137
TIMEOUT = 0.6

class SingleInstance:
    def __init__(self, on_paths: Callable[[List[str]], None]):
        self.on_paths = on_paths
        self._sock: Optional[socket.socket] = None
        self._stop = False

    def acquire(self) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        try:
            s.bind((HOST, PORT))
            s.listen(8)
            s.settimeout(1.0)
        except OSError:
            try:
                s.close()
            except Exception:
                pass
            return False
        self._sock = s
        threading.Thread(target=self._serve, name="SingleInstance", daemon=True).start()
        return True

    def _serve(self) -> None:
        while not self._stop and self._sock is not None:
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                conn.settimeout(1.0)
                buf = b""
                while b"\n" not in buf and len(buf) < 65536:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                if buf:
                    try:
                        data = json.loads(buf.split(b"\n", 1)[0].decode("utf-8", "replace"))
                        paths = [p for p in data.get("paths", []) if isinstance(p, str)]
                        if paths:
                            self.on_paths(paths)
                    except Exception:
                        pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def release(self) -> None:
        self._stop = True
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

def send_to_primary(paths: List[str]) -> bool:
    payload = json.dumps({"paths": paths, "pid": os.getpid()}, ensure_ascii=False) + "\n"
    try:
        s = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
    except OSError:
        return False
    try:
        s.sendall(payload.encode("utf-8"))
        return True
    except OSError:
        return False
    finally:
        try:
            s.close()
        except Exception:
            pass
