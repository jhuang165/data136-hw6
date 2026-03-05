#!/usr/bin/env python3
import hashlib
import os
import time
from multiprocessing import Process, Event, Queue, cpu_count

CNET_ID = "jhuang165"
TARGET_PREFIX = "0" * 7  # 7 leading hex zeros

def worker(worker_id: int, stop: Event, out: Queue):
    # Different starting points per worker so they don't overlap.
    n = worker_id
    step = cpu_count()

    while not stop.is_set():
        nonce = str(n)
        h = hashlib.sha256((CNET_ID + nonce).encode("utf-8")).hexdigest()
        if h.startswith(TARGET_PREFIX):
            out.put((nonce, h))
            stop.set()
            return
        n += step

def main():
    stop = Event()
    out = Queue()
    procs = []
    t0 = time.time()

    for wid in range(cpu_count()):
        p = Process(target=worker, args=(wid, stop, out), daemon=True)
        p.start()
        procs.append(p)

    nonce, h = out.get()  # waits until found
    elapsed = time.time() - t0

    print("cnet_id:", CNET_ID)
    print("nonce:", nonce)
    print("sha256:", h)
    print(f"elapsed: {elapsed:.2f}s using {cpu_count()} processes")

    for p in procs:
        p.terminate()

if __name__ == "__main__":
    main()