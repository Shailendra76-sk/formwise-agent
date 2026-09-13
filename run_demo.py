    print("=" * 72)

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
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        subprocess.run([npm_cmd, "install", "--no-audit", "--no-fund"], cwd=DEMO_DIR, check=True)

    start_process(["node", "server.js"], DEMO_DIR, demo_env, "dummy form server :5000")
    wait_for(DEMO_URL)

    start_process(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        BACKEND_DIR,
        backend_env,
        "Formwise API :8000",
    )
    wait_for(API_URL + "/health")

    print("\n[1/7] Loading FAKE profile data...")
    fake_profile = {
        "full_name": "Demo User",
        "date_of_birth": "2000-01-02",
        "gender": "Male",
        "email": "demo.user@example.com",
        "phone": "9999999999",
    }
    print("       Name   : Demo User")