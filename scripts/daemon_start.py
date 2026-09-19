"""Double-fork daemon launcher so dev servers survive the tool session.

Usage:

    daemon_start.py CMD [ARGS...]

Set ``DAEMON_LOG=/path/to.log`` to capture the daemon's stdout/stderr
(default is /dev/null).
"""

import os
import sys


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit("usage: daemon_start.py CMD [ARGS...]")

    pid = os.fork()
    if pid == 0:
        # First child: new session, detach from controlling terminal.
        os.setsid()
        pid2 = os.fork()
        if pid2 == 0:
            # Grandchild: reparented to init, fully detached.
            log_path = os.environ.get("DAEMON_LOG") or os.devnull
            log_fd = os.open(log_path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
            os.dup2(log_fd, 0)
            os.dup2(log_fd, 1)
            os.dup2(log_fd, 2)
            if log_fd > 2:
                os.close(log_fd)
            os.execvp(args[0], args)
        os._exit(0)
    os.waitpid(pid, 0)


if __name__ == "__main__":
    main()
