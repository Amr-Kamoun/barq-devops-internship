#!/usr/bin/env python3

import subprocess
import urllib.request
import time
import sys


URL = "http://127.0.0.1:8080/instance"


def request():
    try:
        with urllib.request.urlopen(URL, timeout=3) as r:
            return r.read().decode()
    except Exception:
        return None


def run(cmd):
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )


def main():

    print("Stopping app-01")

    run(
        "docker compose -p barq-assessment stop app-01"
    )

    time.sleep(5)

    success = 0
    failures = 0

    for _ in range(20):

        result = request()

        if result:
            success += 1
            print("PASS", result)

        else:
            failures += 1
            print("FAIL")

        time.sleep(0.5)

    print(
        f"Traffic results: success={success} failures={failures}"
    )

    print("Restoring app-01")

    run(
        "docker compose -p barq-assessment start app-01"
    )

    time.sleep(15)

    recovery_results = []

    for _ in range(20):
        result = request()

        if result:
            recovery_results.append(result)

        time.sleep(0.5)

    app01_seen = any(
        "app-01" in r
        for r in recovery_results
    )

    app02_seen = any(
        "app-02" in r
        for r in recovery_results
    )

    if app01_seen and app02_seen:
        print(
            "RECOVERY PASS: both backends serving"
        )
        print(
            recovery_results
        )
        return 0

    print(
        "RECOVERY FAILED"
    )
    print(
        recovery_results
    )
    return 1


if __name__=="__main__":
    sys.exit(main())
