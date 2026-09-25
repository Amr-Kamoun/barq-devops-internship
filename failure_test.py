#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


PROJECT = os.getenv("COMPOSE_PROJECT_NAME", "barq-assessment")
TARGET = os.getenv("FAILURE_TARGET", "app-01")


def detect_public_port():
    if os.getenv("PUBLIC_PORT"):
        return os.environ["PUBLIC_PORT"]

    env_file = Path(".env")
    if env_file.exists():
        for raw_line in env_file.read_text().splitlines():
            line = raw_line.strip()
            if line.startswith("PUBLIC_PORT="):
                return line.split("=", 1)[1].strip()

    return "8080"


BASE_URL = os.getenv(
    "BASE_URL",
    f"http://127.0.0.1:{detect_public_port()}",
)


def compose(*args, check=False):
    result = subprocess.run(
        ["docker", "compose", "-p", PROJECT, *args],
        capture_output=True,
        text=True,
    )

    if check and result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        raise RuntimeError(
            f"docker compose {' '.join(args)} failed"
        )

    return result


def get_app_services():
    result = compose("config", "--services", check=True)

    return sorted(
        service
        for service in result.stdout.splitlines()
        if service.startswith("app-")
    )


def request_instance():
    request = urllib.request.Request(
        f"{BASE_URL}/instance",
        headers={"Connection": "close"},
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=4,
        ) as response:
            data = json.loads(response.read().decode())

        return True, data.get("instance_id"), None

    except Exception as exc:
        return False, None, str(exc)


def wait_for_health(service, timeout=45):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        container = compose(
            "ps",
            "-q",
            service,
            check=True,
        ).stdout.strip()

        if container:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "-f",
                    "{{if .State.Health}}"
                    "{{.State.Health.Status}}"
                    "{{else}}"
                    "{{.State.Status}}"
                    "{{end}}",
                    container,
                ],
                capture_output=True,
                text=True,
            )

            state = result.stdout.strip()

            if (
                result.returncode == 0
                and state in {"healthy", "running"}
            ):
                return True

        time.sleep(1)

    return False


def main():
    backends = get_app_services()

    if TARGET not in backends:
        print(
            f"FAIL: target {TARGET} not found in "
            f"backends {backends}"
        )
        return 1

    survivors = set(backends) - {TARGET}

    if not survivors:
        print("FAIL: no surviving backend exists")
        return 1

    print(f"Public URL: {BASE_URL}")
    print(f"Backends: {', '.join(backends)}")
    print(f"Failure target: {TARGET}")
    print()

    availability_ok = False
    recovery_ok = False

    try:
        print(f"Stopping {TARGET}")
        compose("stop", TARGET, check=True)

        time.sleep(2)

        successes = 0
        failures = 0
        served_by = set()

        print("Testing public availability during outage...")

        for number in range(1, 21):
            ok, instance, error = request_instance()

            if ok:
                successes += 1
                served_by.add(instance)

                print(
                    f"PASS {number:02d}: served by {instance}"
                )
            else:
                failures += 1

                print(
                    f"FAIL {number:02d}: {error}"
                )

            time.sleep(0.25)

        print()
        print(
            f"Traffic results: "
            f"success={successes} failures={failures}"
        )

        print(
            "Instances observed during outage: "
            + ", ".join(sorted(served_by))
        )

        availability_ok = (
            failures == 0
            and TARGET not in served_by
            and bool(served_by & survivors)
        )

        if availability_ok:
            print(
                "AVAILABILITY PASS: all public requests "
                "were served by surviving backend(s)"
            )
        else:
            print(
                "AVAILABILITY FAIL: client-visible "
                "failure or invalid routing detected"
            )

    finally:
        print()
        print(f"Restoring {TARGET}")

        compose("start", TARGET, check=True)

        if not wait_for_health(TARGET):
            print(
                f"RECOVERY FAIL: {TARGET} did not become "
                "healthy before timeout"
            )
        else:
            print(f"{TARGET} is healthy")
            print(
                "Proving recovered backend serves "
                "public traffic..."
            )

            for number in range(1, 61):
                ok, instance, error = request_instance()

                if ok:
                    print(
                        f"RECOVERY {number:02d}: "
                        f"served by {instance}"
                    )

                    if instance == TARGET:
                        recovery_ok = True
                        break
                else:
                    print(
                        f"RECOVERY {number:02d}: "
                        f"request failed: {error}"
                    )

                time.sleep(0.25)

            if recovery_ok:
                print(
                    f"RECOVERY PASS: recovered backend "
                    f"{TARGET} served public traffic"
                )
            else:
                print(
                    f"RECOVERY FAIL: recovered backend "
                    f"{TARGET} was not observed"
                )

    print()

    if availability_ok and recovery_ok:
        print("FAILURE TEST PASSED")
        return 0

    print("FAILURE TEST FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
