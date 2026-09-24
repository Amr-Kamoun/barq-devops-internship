#!/usr/bin/env python3

import subprocess
import sys
import time
import urllib.request
import json


BASE_URL = "http://127.0.0.1:8080"


def run(cmd):
    return subprocess.run(
        cmd,
        shell=True,
        text=True,
        capture_output=True
    )


def check(name, condition):
    if condition:
        print(f"PASS: {name}")
        return True
    else:
        print(f"FAIL: {name}")
        return False


def wait_ready(timeout=60):
    start = time.time()

    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(
                f"{BASE_URL}/ready",
                timeout=3
            ) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass

        time.sleep(2)

    return False


def request(path):
    try:
        with urllib.request.urlopen(
            f"{BASE_URL}{path}",
            timeout=5
        ) as response:
            return response.status, response.read().decode()

    except Exception as e:
        return 0, str(e)


def main():

    results = []

    results.append(
        check(
            "docker compose services running",
            run(
                "docker compose -p barq-assessment ps"
            ).returncode == 0
        )
    )

    results.append(
        check(
            "application readiness",
            wait_ready()
        )
    )


    for endpoint in [
        "/",
        "/health",
        "/ready",
        "/records",
        "/counter",
        "/instance"
    ]:
        status, _ = request(endpoint)

        results.append(
            check(
                f"endpoint {endpoint}",
                status == 200
            )
        )


    ports = run(
        'docker ps --format "{{.Names}} {{.Ports}}"'
    ).stdout


    results.append(
        check(
            "only nginx exposes host port",
            "127.0.0.1:8080->80/tcp" in ports
            and "15432" not in ports
            and "16379" not in ports
        )
    )


    if all(results):
        print("\nVALIDATION PASSED")
        return 0

    print("\nVALIDATION FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
