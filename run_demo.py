from __future__ import annotations

import atexit
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Missing Python package: requests. Run: python -m pip install requests")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent
DEMO_DIR = ROOT / "demo-target-site"
BACKEND_DIR = ROOT / "backend"
DEMO_URL = "http://localhost:5000/"
API_URL = "http://127.0.0.1:8000"
USER_ID = "formwise-demo-user"
PROCESSES: list[subprocess.Popen] = []


def stop_processes() -> None:
    for proc in reversed(PROCESSES):
        if proc.poll() is not None:
            continue
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


atexit.register(stop_processes)


def fail(message: str) -> None:
    print(f"\n[ERROR] {message}")
    stop_processes()
    raise SystemExit(1)


def wait_for(url: str, timeout: int = 30) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.ok:
                return
            last = f"HTTP {r.status_code}"
        except Exception as exc:
            last = str(exc)
        time.sleep(0.5)
    fail(f"Timed out waiting for {url} ({last})")


def start_process(command: list[str], cwd: Path, env: dict[str, str], name: str) -> None:
    print(f"[START] {name}")
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == "Windows" else 0
    proc = subprocess.Popen(command, cwd=str(cwd), env=env, creationflags=creationflags)
    PROCESSES.append(proc)


def api(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-User-ID"] = USER_ID
    response = requests.request(method, API_URL + path, headers=headers, timeout=30, **kwargs)
    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        fail(f"{method} {path} -> HTTP {response.status_code}: {detail}")
    return response.json()


def main() -> None:
    print("=" * 68)
    print(" FORMwise — LOCAL DUMMY FORM LIVE DEMO")
    print(" Fake profile only | localhost only | NO automated final submit")
    print("=" * 68)

    if shutil.which("node") is None:
        fail("Node.js is required. Install Node.js, then run this script again.")
    if not (BACKEND_DIR / "requirements.txt").exists():
        fail("backend/requirements.txt was not found. Run this from the Formwise repo root.")

    demo_env = os.environ.copy()
    backend_env = os.environ.copy()
    backend_env.update(
        {
            "FORMWISE_ENVIRONMENT": "development",
            "FORMWISE_ALLOW_LEGACY_USER_HEADER": "true",
            "FORMWISE_BROWSER_HEADLESS": "false",
            "FORMWISE_BROWSER_ALLOW_LOCAL_DEMO_TARGET": "true",
            "FORMWISE_BROWSER_USE_ENABLED": "false",
            "FORMWISE_CORS_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
            "FORMWISE_STORAGE_ROOT": str(ROOT / ".demo_private_storage"),
            "FORMWISE_DATABASE_URL": f"sqlite:///{ROOT / '.demo_formwise.db'}",
        }
    )

    if not (DEMO_DIR / "node_modules").exists():
        print("[SETUP] Installing dummy form dependencies...")
        subprocess.run(["npm", "install", "--no-audit", "--no-fund"], cwd=DEMO_DIR, check=True)

    start_process(["node", "server.js"], DEMO_DIR, demo_env, "dummy form server :5000")
    wait_for(DEMO_URL)

    start_process(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        BACKEND_DIR,
        backend_env,
        "Formwise API :8000",
    )
    wait_for(API_URL + "/health")

    print("\n[1/6] Loading FAKE profile data...")
    fake_profile = {
        "full_name": "Demo User",
        "date_of_birth": "2000-01-02",
        "gender": "Male",
        "email": "demo.user@example.com",
        "phone": "9999999999",
    }
    print("       Name   : Demo User")
    print("       DOB    : 2000-01-02")
    print("       Email  : demo.user@example.com")
    print("       Mobile : 9999999999")
    api("PUT", "/v1/profile", json=fake_profile)
    api("POST", "/v1/knowledge/reindex")

    print("\n[2/6] Opening dummy form in a VISIBLE browser...")
    session = api("POST", "/v1/browser/sessions", json={"url": DEMO_URL})
    session_id = session["session_id"]
    print(f"       Session: {session_id}")

    print("\n[3/6] Inspecting fields and creating the fill plan...")
    plan = api(
        "POST",
        "/v1/e2e/plan",
        json={"session_id": session_id, "instruction": "Fill this dummy application using my stored profile."},
    )
    print(f"       Plan status: {plan.get('status')}")
    for item in plan.get("proposals", []):
        print(f"       - {item.get('field')}: mapped | approval={item.get('requires_approval')}")

    fills = []
    for item in plan.get("fills", []):
        field = item.get("field")
        if field in {"captcha", "otp"}:
            continue
        fill_item = {
            "index": item["index"],
            "field": field,
            "value": item["value"],
            "source_type": item.get("source_type"),
            "source_id": item.get("source_id"),
            "document_id": item.get("document_id"),
        }
        if item.get("requires_approval"):
            approval = api(
                "POST",
                "/v1/e2e/approvals",
                json={"session_id": session_id, "item": fill_item, "ttl_seconds": 600},
            )
            api("POST", f"/v1/approvals/{approval['approval_id']}/approve")
            fill_item["approval_id"] = approval["approval_id"]
        fills.append(fill_item)

    print("\n[4/6] Filling approved stored values...")
    result = api("POST", "/v1/e2e/fill", json={"session_id": session_id, "fills": fills})
    for item in result.get("filled", []):
        print(f"       FILLED: {item.get('field')}")
    print("       Submission allowed:", result.get("submission_allowed"))
    print("       Human gates:", result.get("human_required", []))

    if "captcha" in result.get("human_required", []):
        print("\n[5/6] CAPTCHA GATE — automation is STOPPED.")
        print("       The visible dummy form shows: 7 X 9 K 2")
        captcha = input("       Enter the CAPTCHA in this terminal: ").strip()
        api("POST", f"/v1/browser/sessions/{session_id}/human", json={"kind": "captcha", "value": captcha})
        print("       CAPTCHA accepted as a HUMAN-PROVIDED value.")

    if "otp" in result.get("human_required", []):
        print("\n       OTP GATE — automation is STOPPED.")
        print("       In the visible dummy form, click 'Send OTP'.")
        print("       The dummy server prints DEMO OTP in its console.")
        otp = input("       Enter that OTP in this terminal: ").strip()
        api("POST", f"/v1/browser/sessions/{session_id}/human", json={"kind": "otp", "value": otp})
        print("       OTP accepted as a HUMAN-PROVIDED value.")

    print("\n[6/6] FINAL REVIEW — MANUAL ONLY")
    inspection = api("GET", f"/v1/browser/sessions/{session_id}/inspect")
    print(f"       URL: {inspection.get('url')}")
    print(f"       Title: {inspection.get('title')}")
    print("       Formwise NEVER clicks the final Submit button.")
    print("       Review every field in the visible browser yourself.")
    input("\nPress Enter after review to close the demo (DO NOT click Submit)... ")

    api("DELETE", f"/v1/browser/sessions/{session_id}")
    print("\n[DONE] Safe dummy demo completed.")
    print("       No real personal data was used.")
    print("       Formwise did NOT click final Submit.")
    stop_processes()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[STOP] Demo interrupted by user.")
        stop_processes()
