from __future__ import annotations

import functools
import http.server
import socketserver
import threading
from pathlib import Path

import pytest
from app.browser_agent import BrowserSafetyError, close_session, create_session, fill_control, inspect_session


@pytest.fixture(scope="module", autouse=True)
def local_demo_target_server():
    """Serve the static local demo form so this test needs no manual Node step."""
    public_dir = Path(__file__).resolve().parents[2] / "demo-target-site" / "public"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(public_dir))
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    server = ReusableTCPServer(("127.0.0.1", 5000), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

@pytest.mark.asyncio
async def test_local_demo_browser_can_inspect_and_fill_non_submit_controls():
    session=await create_session("demo-browser-user","http://localhost:5000/")
    try:
        inspection=await inspect_session(session)
        by_name={c.get("name"):c for c in inspection["controls"] if c.get("name")}
        assert {"fullName","dob","email","mobile","captcha","otp"}.issubset(by_name)
        await fill_control(session,by_name["fullName"]["index"],"Test Candidate")
        await fill_control(session,by_name["email"]["index"],"test@example.com")
        submit=next(c for c in inspection["controls"] if c.get("type")=="submit")
        with pytest.raises(BrowserSafetyError):
            await fill_control(session,submit["index"],"anything")
        assert inspection["submission_allowed"] is False
    finally:
        await close_session(session.session_id,"demo-browser-user")
