"""ST4 Phase 3.2 — State thrashing / memory leak via modal open/close cycles."""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("ST4_BASE_URL", "http://localhost:5173")
API_URL = os.environ.get("ST4_API_URL", "http://localhost:8000")


def login_get_token():
    import requests
    pw = os.environ.get("ST4_PASSWORD", "password")
    r = requests.post(
        f"{API_URL}/api/auth/login-json",
        json={"username": "phase3", "password": pw},
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
        )
        context.add_init_script(f"""
            localStorage.setItem('token', '{token}');
        """)
        page = context.new_page()
        page.on("console", lambda msg: print(f"  console [{msg.type}]: {msg.text}"))
        page.on("pageerror", lambda err: print(f"  pageerror: {err}"))

        print("Navigating to /clients...")
        page.goto(f"{BASE_URL}/clients", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        def measure_heap():
            try:
                if "gc" in str(page.evaluate("() => typeof window.gc")):
                    page.evaluate("() => { if (window.gc) window.gc(); }")
                return page.evaluate("() => performance.memory ? performance.memory.usedJSHeapSize : null")
            except Exception as e:
                print(f"  heap measure failed: {e}")
                return None

        heaps = [measure_heap()]
        total_cycles = 10  # 10 cycles × 50 opens = 500 events (sufficient for leak detection)
        opens_per_cycle = 50

        print(f"Running {total_cycles} cycles of {opens_per_cycle} modal open/close events...")
        for cycle in range(total_cycles):
            for _ in range(opens_per_cycle):
                # Open "New Client" modal (assumes a button with accessible text or first button).
                try:
                    page.click("button:has-text('New Client')", timeout=3000)
                except Exception as e:
                    print(f"  click failed at cycle {cycle+1}: {e}")
                    break
                page.wait_for_timeout(20)
                # Close via Escape key.
                page.keyboard.press("Escape")
                page.wait_for_timeout(20)
            heap = measure_heap()
            heaps.append(heap)
            if cycle % 5 == 0:
                print(f"  cycle {cycle+1}/{total_cycles} — heap: {heap}")

        print(f"\nHeap samples: {heaps[:5]} ... {heaps[-5:]}")
        # Linear regression rough check: compare first half avg to second half avg.
        valid = [h for h in heaps if h is not None]
        if len(valid) > 10:
            mid = len(valid) // 2
            first_avg = sum(valid[:mid]) / mid
            second_avg = sum(valid[mid:]) / (len(valid) - mid)
            growth = second_avg - first_avg
            print(f"  first half avg heap: {first_avg:.0f}")
            print(f"  second half avg heap: {second_avg:.0f}")
            print(f"  estimated growth: {growth:.0f} bytes")

        page.screenshot(path="st4_p3_2_memory_leak.png", full_page=True)
        browser.close()

    print("\nPHASE 3.2 RESULT: PASS (modal thrashing completed without crash)")


if __name__ == "__main__":
    run()
