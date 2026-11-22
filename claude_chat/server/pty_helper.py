"""Run a command inside a pseudo-terminal and relay it over plain pipes.

Claude Code's sign-in (`claude setup-token`) is a terminal UI that only takes a
pasted code on a real TTY. The Node server cannot open one itself without a
native module, so it runs this helper: our stdin goes to the terminal, the
terminal's output comes back on our stdout. The window is made very wide
(PTY_COLS) so the long sign-in address is not wrapped.

Usage: python3 pty_helper.py <command> [args...]
"""
import fcntl
import os
import select
import signal
import struct
import sys
import termios


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print("usage: pty_helper.py <command> [args...]", file=sys.stderr)
        return 2
    cols = int(os.environ.get("PTY_COLS", "2000"))
    rows = int(os.environ.get("PTY_ROWS", "60"))

    master, slave = os.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    pid = os.fork()
    if pid == 0:
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        for fd in (0, 1, 2):
            os.dup2(slave, fd)
        if slave > 2:
            os.close(slave)
        os.close(master)
        try:
            os.execvp(argv[0], argv)
        except OSError as e:
            os.write(2, f"cannot run {argv[0]}: {e}\n".encode())
            os._exit(127)

    os.close(slave)
    signal.signal(signal.SIGTERM, lambda *_: (os.kill(pid, signal.SIGTERM), sys.exit(143)))

    inputs = [master, 0]
    status = 0
    while True:
        try:
            ready, _, _ = select.select(inputs, [], [], 0.5)
        except InterruptedError:
            continue
        if master in ready:
            try:
                data = os.read(master, 65536)
            except OSError:
                data = b""
            if not data:
                break
            os.write(1, data)
        if 0 in ready:
            data = os.read(0, 65536)
            if data:
                os.write(master, data)
            else:
                inputs.remove(0)
        done, st = os.waitpid(pid, os.WNOHANG)
        if done:
            status = os.waitstatus_to_exitcode(st)
            # drain what is left on the terminal
            while True:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                os.write(1, data)
            return status
    _, st = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(st)


if __name__ == "__main__":
    sys.exit(main())
