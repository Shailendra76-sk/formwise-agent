from __future__ import annotations

import atexit
import os
import platform
import shutil
import signal
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
            if platform.system() == "Windows":
                proc.terminate()
            else:
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
    creationflags = 0
    if platform.system() == "Windows":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    print(f"[START] {name}")
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=None,
        stderr=None,
        creationflags=creationflags,
    )
    PROCESSES.append(proc)


def api(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["X-User-ID"] = USER_ID
    r = requests.request(method, API_URL + path, headers=headers, timeout=30, **kwargs)
    if not r.ok:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        fail(f"{method} {path} -> HTTP {r.status_code}: {detail}")
    return r.json()


def main() -> None:
    print("=" * 68)
    print(" FORMwise — LOCAL DUMMY FORM LIVE DEMO")
    print(" Fake profile only | localhost only | NO real submission")
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
        print("[SETUP] Installing demo target dependencies...")
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

    fake_profile = {
        "full_name": "Demo User",
        "date_of_birth": "2000-01-02",
        "gender": "Male",
        "email": "demo.user@example.com",
        "phone": "9999999999",
    }
    print("\n[1/6] Loading FAKE profile data...")
    print("       Name: Demo User")
    print("       DOB : 2000-01-02")
    print("       Email: demo.user@example.com")
    print("       Mobile: 9999999999")
    api("PUT", "/v1/profile", json=fake_profile)
    api("POST", "/v1/knowledge/reindex")

    print("\n[2/6] Opening dummy form in a visible browser...")
    session = api("POST", "/v1/browser/sessions", json={"url": DEMO_URL})
    session_id = session["session_id"]
    print(f"       Session: {session_id}")

    print("\n[3/6] AI inspecting fields and creating a fill plan...")
    plan = api(
        "POST",
        "/v1/e2e/plan",
        json={"session_id": session_id, "instruction": "Fill this demo application using my stored profile."},
    )
    print(f"       Status: {plan.get('status')}")
    for item in plan.get("proposals", []):
        print(f"       - {item.get('field')}: mapped (approval={item.get('requires_approval')})")

    fills = []
    for item in plan.get("fills", []):
        if item.get("field") in {"captcha", "otp"}:
            continue
        fill_item = {
            "index": item["index"],
            "field": item["field"],
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
            approval_id = approval["approval_id"]
            api("POST", f"/v1/approvals/{approval_id}/approve")
            fill_item["approval_id"] = approval_id
        fills.append(fill_item)

    print("\n[4/6] Filling approved stored values...")
    result = api("POST", "/v1/e2e/fill", json={"session_id": session_id, "fills": fills})
    for item in result.get("filled", []):
        print(f"       FILLED: {item.get('field')}")
    print("       Submission allowed:", result.get("submission_allowed"))
    print("       Human gates:", result.get("human_required", []))

    if "captcha" in result.get("human_required", []):
        print("\n[5/6] CAPTCHA GATE — Formwise has STOPPED.")
        print("       Look at the browser: CAPTCHA is: 7 X 9 K 2")
        captcha = input("       Type CAPTCHA here: ").strip()
        gate = api("POST", f"/v1/workflows/unused/human", json={"kind": "captcha", "value": captcha}) if False else None
        # The generic workflow human endpoint needs a workflow id. For this direct E2E demo,
        # use the browser session itself through a temporary workflow-free Playwright gate below.
        # We intentionally do not automate CAPTCHA recognition.
        api("POST", "/v1/e2e/fill", json={"session_id": session_id, "fills": []})
        # Fill the human CAPTCHA directly through the browser-control endpoint is not exposed
        # by the E2E API, so the user should type it into the visible browser themselves.
        print("       Now enter the CAPTCHA manually in the visible browser.")

    # OTP is intentionally human-operated. The demo page's Send OTP button generates a
    # one-time code and prints it to the demo server console. The browser is visible, so the
    # user can click Send OTP, read the demo console, and type the OTP into the form.
    if "otp" in result.get("human_required", []):
        print("\n       OTP GATE — Formwise has STOPPED.")
        print("       Click 'Send OTP' in the visible dummy form.")
        print("       Read the DEMO OTP from the demo server console, then enter it manually.")

    print("\n[6/6] FINAL REVIEW")
    print("       Formwise will NEVER click the final Submit button.")
    print("       Review the visible browser now.")
    print("       FINAL SUBMIT: MANUAL ONLY — do NOT click it if you want the safe demo to stop here.")
    input("\nPress Enter after you have inspected the completed form... ")

    api("DELETE", f"/v1/browser/sessions/{session_id}")
    print("\n[DONE] Demo finished safely. No final Submit was clicked by Formwise.")
    print("       Fake profile values were used; no real personal data was required.")
    stop_processes()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[STOP] Demo interrupted by user.")
        stop_processes()
