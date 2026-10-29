#!/usr/bin/env python3
import os
import sys
import time
import socket
import signal

# 1. Grab the systemd notify socket from the environment
NOTIFY_SOCKET = os.environ.get("NOTIFY_SOCKET")

def notify_systemd(message: str):
    """Send sd_notify protocol messages to systemd."""
    if not NOTIFY_SOCKET:
        return
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        # Handle abstract sockets (if socket path starts with @)
        target = "\0" + NOTIFY_SOCKET[1:] if NOTIFY_SOCKET.startswith("@") else NOTIFY_SOCKET
        sock.sendto(message.encode(), target)
        sock.close()
    except Exception as e:
        sys.stderr.write(f"[WARN] Failed to notify systemd: {e}\n")

def handle_shutdown(signum, frame):
    sys.stdout.write("[INFO] Received termination signal. Exiting cleanly...\n")
    sys.stdout.flush()
    notify_systemd("STOPPING=1")
    sys.exit(0)

# Register clean shutdown handlers for SIGTERM and SIGINT
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

def main():
    sys.stdout.write("[INFO] Node Agent initializing...\n")
    sys.stdout.flush()
    time.sleep(1)

    # Tell systemd we are fully initialized and ready to serve
    notify_systemd("READY=1")
    sys.stdout.write("[INFO] Node Agent active. Starting watchdog heartbeat...\n")
    sys.stdout.flush()

    cycle = 0
    while True:
        cycle += 1
        # Send heartbeat to systemd
        notify_systemd("WATCHDOG=1")
        sys.stdout.write(f"[HEARTBEAT] Cycle {cycle}: System healthy.\n")
        sys.stdout.flush()
        
        # Sleep for 3 seconds (well within our 10-second watchdog window)
        time.sleep(3)

if __name__ == "__main__":
    main()
