#!/usr/bin/env python3
"""Stream a text G-code file to a Marlin printer over a POSIX serial port."""

from __future__ import annotations

import argparse
import os
import select
import signal
import sys
import termios
import time
from pathlib import Path


class MarlinSerial:
    def __init__(self, device: str, baud: int = 115200) -> None:
        baud_attr = getattr(termios, f"B{baud}", None)
        if baud_attr is None:
            raise ValueError(f"unsupported baud rate: {baud}")

        self.fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        attrs = termios.tcgetattr(self.fd)
        attrs[0] = 0
        attrs[1] = 0
        attrs[2] = termios.CLOCAL | termios.CREAD | termios.CS8
        attrs[3] = 0
        attrs[4] = baud_attr
        attrs[5] = baud_attr
        attrs[6][termios.VMIN] = 0
        attrs[6][termios.VTIME] = 1
        termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        termios.tcflush(self.fd, termios.TCIOFLUSH)
        self.buffer = b""

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

    def _readline(self, deadline: float) -> str | None:
        while time.monotonic() < deadline:
            for separator in (b"\n", b"\r"):
                if separator in self.buffer:
                    raw, self.buffer = self.buffer.split(separator, 1)
                    if raw:
                        return raw.decode("utf-8", errors="replace").strip()

            ready, _, _ = select.select([self.fd], [], [], 0.25)
            if ready:
                chunk = os.read(self.fd, 4096)
                if chunk:
                    self.buffer += chunk
        return None

    def command(self, command: str, timeout: float = 900.0) -> list[str]:
        os.write(self.fd, (command + "\n").encode("ascii"))
        deadline = time.monotonic() + timeout
        replies: list[str] = []

        while True:
            line = self._readline(deadline)
            if line is None:
                raise TimeoutError(f"timeout waiting for acknowledgement: {command}")
            replies.append(line)
            lowered = line.lower()
            if lowered == "ok" or lowered.startswith("ok "):
                return replies
            if "resend:" in lowered or lowered.startswith("error:"):
                raise RuntimeError(f"printer rejected {command!r}: {line}")


def gcode_commands(path: Path) -> list[str]:
    commands: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        command = raw.split(";", 1)[0].strip()
        if command:
            commands.append(command)
    return commands


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("device")
    parser.add_argument("gcode", nargs="?", type=Path)
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    printer: MarlinSerial | None = None
    interrupted = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal interrupted
        interrupted = True
        raise InterruptedError("print interrupted")

    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, stop)

    try:
        printer = MarlinSerial(args.device, args.baud)
        # Opening a CH340 serial device may reset the controller.
        time.sleep(3)
        termios.tcflush(printer.fd, termios.TCIFLUSH)

        identity = printer.command("M115", timeout=15)
        print("CONNECTED " + " | ".join(identity), flush=True)

        if args.gcode is None:
            print(" | ".join(printer.command("M105", timeout=10)), flush=True)
            return 0

        commands = gcode_commands(args.gcode)
        if not commands:
            raise ValueError("G-code file contains no commands")

        started = time.monotonic()
        print(f"PRINT_START commands={len(commands)} file={args.gcode.name}", flush=True)
        important = {"G28", "G29", "M104", "M109", "M140", "M190", "M400", "M84"}

        for index, command in enumerate(commands, start=1):
            if interrupted:
                raise InterruptedError("print interrupted")
            replies = printer.command(command)
            opcode = command.split(maxsplit=1)[0]
            if index == 1 or index % 500 == 0 or opcode in important:
                elapsed = int(time.monotonic() - started)
                detail = " | ".join(replies[-3:])
                print(
                    f"PROGRESS {index}/{len(commands)} elapsed={elapsed}s "
                    f"command={command!r} reply={detail}",
                    flush=True,
                )

        status = printer.command("M105", timeout=10)
        elapsed = int(time.monotonic() - started)
        print(f"PRINT_DONE elapsed={elapsed}s status={' | '.join(status)}", flush=True)
        return 0
    except BaseException as error:
        print(f"PRINT_ABORTED {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        if printer is not None and printer.fd >= 0:
            # Best-effort safe shutdown. Do not wait for acknowledgements here.
            for command in ("M104 S0", "M140 S0", "M107", "M84"):
                try:
                    os.write(printer.fd, (command + "\n").encode("ascii"))
                except OSError:
                    break
        return 1
    finally:
        if printer is not None:
            printer.close()


if __name__ == "__main__":
    raise SystemExit(main())
