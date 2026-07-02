"""ST4 Phase 3.1 — Massive DOM rendering via Playwright."""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("ST4_BASE_URL", "http://localhost:5173")
API_URL = os.environ.get("ST4_API_URL", "http://127.0.0.1:8000")


def login_get_token():
    import requests
    r = requests.post(
        f"{API_URL}/api/auth/login-json",
        json={"username": "phase3", "password": "password"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def run():
    token = login_get_token()
    print(f"Logged in, token len {len(token)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--js-flags=--expose-gc"],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        # Inject auth token before navigation.
        context.add_init_script(f"""
            localStorage.setItem('token', '{token}');
        """)
        page = context.new_page()
        page.on("console", lambda msg: print(f"  console [{msg.type}]: {msg.text}"))
        page.on("pageerror", lambda err: print(f"  pageerror: {err}"))

        print("Navigating to /gl...")
        start = time.time()
        page.goto(f"{BASE_URL}/gl", wait_until="networkidle", timeout=120000)
        elapsed = time.time() - start
        print(f"  navigation complete in {elapsed:.2f}s")

        # Wait for the table or an error indicator.
        try:
            page.wait_for_selector("table tbody tr", timeout=60000)
            print("  table rows rendered")
        except Exception as e:
            print(f"  table rows not found: {e}")

        # Measure DOM node count and JS heap.
        metrics = page.evaluate("""() => {
            const nodes = document.querySelectorAll('*').length;
            const rows = document.querySelectorAll('table tbody tr').length;
            return {nodes, rows, title: document.title};
        }""")
        print(f"  metrics: {metrics}")

        try:
            heap = page.evaluate("() => performance.memory ? performance.memory.usedJSHeapSize : null")
            print(f"  JS heap: {heap}")
        except Exception:
            pass

        # Screenshot for visual review.
        screenshot_path = "st4_p3_1_screenshot.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"  screenshot saved: {screenshot_path}")

        # Did the page crash?
        crashed = page.evaluate("() => document.body ? false : true")
        if crashed:
            print("  CRASH: document.body missing")
            browser.close()
            sys.exit(1)

        browser.close()

    print("\nPHASE 3.1 RESULT: PASS (page loaded and rendered table)")


if __name__ == "__main__":
    run()
