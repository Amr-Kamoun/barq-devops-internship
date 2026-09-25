#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT = os.getenv("COMPOSE_PROJECT_NAME", "barq-assessment")
RESULTS = []


def detect_public_port():
    if os.getenv("PUBLIC_PORT"):
        return os.environ["PUBLIC_PORT"]

    env_file = Path(".env")

    if env_file.exists():
        for raw_line in env_file.read_text().splitlines():
            line = raw_line.strip()

            if line.startswith("PUBLIC_PORT="):
                value = line.split("=", 1)[1].strip()
                return value.strip("'\"")

    return "8080"


PUBLIC_PORT = detect_public_port()
BASE_URL = os.getenv(
    "BASE_URL",
    f"http://127.0.0.1:{PUBLIC_PORT}",
)


def run(args, check=False, timeout=30):
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(args)}\n"
            f"{result.stdout}\n{result.stderr}"
        )

    return result


def compose(*args, check=False):
    return run(
        ["docker", "compose", "-p", PROJECT, *args],
        check=check,
    )


def report(name, ok, detail=None):
    RESULTS.append(bool(ok))

    prefix = "PASS" if ok else "FAIL"

    if detail:
        print(f"{prefix}: {name} [{detail}]")
    else:
        print(f"{prefix}: {name}")

    return bool(ok)


def http_request(path, method="GET", payload=None, timeout=5):
    data = None
    headers = {
        "Connection": "close",
    }

    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        method=method,
        headers=headers,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            return response.status, response.read().decode()

    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()

    except Exception as exc:
        return 0, str(exc)


def json_body(body):
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def service_names():
    result = compose(
        "config",
        "--services",
        check=True,
    )

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def container_id(service):
    return compose(
        "ps",
        "-q",
        service,
        check=True,
    ).stdout.strip()


def inspect_service(service):
    cid = container_id(service)

    if not cid:
        raise RuntimeError(
            f"No running container found for {service}"
        )

    result = run(
        ["docker", "inspect", cid],
        check=True,
    )

    return json.loads(result.stdout)[0]


def service_state(service):
    info = inspect_service(service)
    state = info["State"]

    if state.get("Status") != "running":
        return False, state.get("Status", "unknown")

    health = state.get("Health")

    if health:
        status = health.get("Status", "unknown")
        return status == "healthy", status

    return True, "running"


def wait_for_services(services, timeout=60):
    deadline = time.monotonic() + timeout
    last_states = {}

    while time.monotonic() < deadline:
        all_ready = True
        last_states = {}

        for service in services:
            try:
                ok, state = service_state(service)
            except Exception as exc:
                ok = False
                state = str(exc)

            last_states[service] = state

            if not ok:
                all_ready = False

        if all_ready:
            return True, last_states

        time.sleep(1)

    return False, last_states


def wait_for_ready(timeout=60):
    deadline = time.monotonic() + timeout
    last_status = 0

    while time.monotonic() < deadline:
        status, _ = http_request(
            "/ready",
            timeout=4,
        )

        last_status = status

        if status == 200:
            return True, status

        time.sleep(1)

    return False, last_status


def network_roles(service):
    info = inspect_service(service)

    network_names = set(
        info["NetworkSettings"]["Networks"].keys()
    )

    roles = set()
    unknown = set()

    for name in network_names:
        if name.endswith("_frontend"):
            roles.add("frontend")
        elif name.endswith("_backend"):
            roles.add("backend")
        else:
            unknown.add(name)

    return roles, unknown, network_names


def published_ports(service):
    info = inspect_service(service)

    ports = (
        info.get("NetworkSettings", {})
        .get("Ports", {})
        or {}
    )

    published = []

    for target, bindings in ports.items():
        if not bindings:
            continue

        for binding in bindings:
            published.append(
                {
                    "target": target,
                    "host_ip": binding.get(
                        "HostIp",
                        "",
                    ),
                    "host_port": binding.get(
                        "HostPort",
                        "",
                    ),
                }
            )

    return published


def observe_backends(apps, timeout=15):
    expected = set(apps)
    seen = set()
    deadline = time.monotonic() + timeout

    while (
        time.monotonic() < deadline
        and seen != expected
    ):
        status, body = http_request(
            "/instance",
            timeout=4,
        )

        if status == 200:
            data = json_body(body)

            if isinstance(data, dict):
                instance = data.get("instance_id")

                if instance:
                    seen.add(instance)

        time.sleep(0.1)

    return seen


def main():
    print(
        "============================================================"
    )
    print(" BARQ Automated Validation")
    print(
        "============================================================"
    )
    print(f"Public URL: {BASE_URL}")
    print()

    try:
        config = compose(
            "config",
            "-q",
        )

        report(
            "Docker Compose configuration",
            config.returncode == 0,
        )

        services = service_names()

    except Exception as exc:
        report(
            "Docker Compose inspection",
            False,
            str(exc),
        )

        print()
        print("VALIDATION FAILED")
        return 1

    apps = sorted(
        service
        for service in services
        if service.startswith("app-")
    )

    report(
        "at least two application backends configured",
        len(apps) >= 2,
        ", ".join(apps) or "none",
    )

    required = {
        "nginx",
        "postgres",
        "redis",
    }

    report(
        "required infrastructure services configured",
        required.issubset(set(services)),
        ", ".join(sorted(services)),
    )

    ready, states = wait_for_services(
        services,
        timeout=60,
    )

    report(
        "containers running and health checks passing",
        ready,
        ", ".join(
            f"{name}={state}"
            for name, state in sorted(states.items())
        ),
    )

    ready, status = wait_for_ready(
        timeout=60,
    )

    report(
        "application readiness",
        ready,
        f"HTTP {status}",
    )

    print()
    print("--- HTTP endpoint checks ---")

    for path in (
        "/",
        "/health",
        "/ready",
        "/records",
        "/counter",
        "/instance",
    ):
        status, _ = http_request(path)

        report(
            f"GET {path}",
            status == 200,
            f"HTTP {status}",
        )

    validation_title = (
        f"validator-proof-{int(time.time())}"
    )

    status, body = http_request(
        "/records",
        method="POST",
        payload={
            "title": validation_title,
        },
    )

    report(
        "POST /records creates a record",
        status in {200, 201},
        f"HTTP {status}",
    )

    status, body = http_request("/records")
    records_data = json_body(body)

    created_record_visible = False

    if (
        status == 200
        and isinstance(records_data, dict)
    ):
        records = records_data.get("records", [])

        created_record_visible = any(
            isinstance(record, dict)
            and record.get("title") == validation_title
            for record in records
        )

    report(
        "GET /records lists newly created record",
        created_record_visible,
    )

    print()
    print("--- Backend identity checks ---")

    seen = observe_backends(
        apps,
        timeout=15,
    )

    report(
        "all configured application backends observed via NGINX",
        seen == set(apps),
        "seen="
        + (
            ",".join(sorted(seen))
            if seen
            else "none"
        ),
    )

    print()
    print("--- Network isolation checks ---")

    expected_networks = {
        "nginx": {"frontend"},
        "postgres": {"backend"},
        "redis": {"backend"},
    }

    for app in apps:
        expected_networks[app] = {
            "frontend",
            "backend",
        }

    backend_network_name = None

    for service, expected in expected_networks.items():
        try:
            roles, unknown, names = network_roles(
                service
            )

            ok = (
                roles == expected
                and not unknown
            )

            report(
                f"{service} network membership",
                ok,
                "roles="
                + ",".join(sorted(roles)),
            )

            if service == "postgres":
                for name in names:
                    if name.endswith("_backend"):
                        backend_network_name = name

        except Exception as exc:
            report(
                f"{service} network membership",
                False,
                str(exc),
            )

    if backend_network_name:
        try:
            result = run(
                [
                    "docker",
                    "network",
                    "inspect",
                    backend_network_name,
                ],
                check=True,
            )

            network_info = json.loads(
                result.stdout
            )[0]

            report(
                "backend network is internal",
                bool(network_info.get("Internal")),
                backend_network_name,
            )

        except Exception as exc:
            report(
                "backend network is internal",
                False,
                str(exc),
            )
    else:
        report(
            "backend network is internal",
            False,
            "backend network not found",
        )

    print()
    print("--- Host port exposure checks ---")

    exposures = {}
    exposure_errors = {}

    for service in services:
        try:
            exposures[service] = published_ports(
                service
            )
        except Exception as exc:
            exposures[service] = []
            exposure_errors[service] = str(exc)

    report(
        "host-port inspection completed for all services",
        not exposure_errors,
        (
            "all services inspected"
            if not exposure_errors
            else str(exposure_errors)
        ),
    )

    non_nginx_exposed = {
        service: ports
        for service, ports in exposures.items()
        if service != "nginx" and ports
    }

    report(
        "no app, PostgreSQL, or Redis host ports exposed",
        not non_nginx_exposed,
        (
            "none"
            if not non_nginx_exposed
            else str(non_nginx_exposed)
        ),
    )

    nginx_ports = exposures.get(
        "nginx",
        [],
    )

    nginx_port_ok = (
        len(nginx_ports) == 1
        and nginx_ports[0]["target"] == "80/tcp"
        and nginx_ports[0]["host_port"]
        == str(PUBLIC_PORT)
        and nginx_ports[0]["host_ip"]
        == "127.0.0.1"
    )

    report(
        "only NGINX publishes the expected loopback host port",
        nginx_port_ok,
        (
            str(nginx_ports)
            if nginx_ports
            else "no published NGINX port"
        ),
    )

    print()

    if all(RESULTS):
        print("VALIDATION PASSED")
        return 0

    failed = RESULTS.count(False)

    print(
        f"VALIDATION FAILED: "
        f"{failed} check(s) failed"
    )

    return 1


if __name__ == "__main__":
    sys.exit(main())
