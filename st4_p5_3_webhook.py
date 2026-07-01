"""Stress Test 4 Phase 5.3 — Webhook / Integration Callback Storm.

Tests circuit-breaker behavior under outbound webhook failure conditions.

Mock server sleeps 30s or returns 500s; we fire 100 outbound webhooks.
A minimal circuit breaker trips after a configurable failure threshold,
stops sending, logs failures, and does NOT block the main thread.

This is a standalone test harness — no production code is modified.
The circuit breaker pattern is implemented inline to prove the
architecture holds when TaxFlow Pro adds production webhook support.

Run:
    set ST4_TEST_DB=st4_p53  (optional, only needed if testing DB integration)
    python st4_p5_3_webhook.py
"""
from __future__ import annotations

import os
import sys
import time
import json
import logging
import threading
import concurrent.futures
from dataclasses import dataclass, field
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional

# Force UTF-8 stdout to avoid cp1252 encoding errors on Windows console.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NUM_WEBHOOKS = 100
FAILURE_THRESHOLD = 5          # consecutive failures before breaker trips
RECOVERY_TIMEOUT = 10          # seconds before half-open probe
MOCK_SERVER_PORT = 9999
MOCK_SERVER_MODE = os.environ.get("ST4_P53_MOCK_MODE", "slow_500")  # slow_500 | 500 | slow_200 | timeout
MAIN_THREAD_BLOCK_LIMIT = 2.0  # seconds — main thread must not block longer than this
CONCURRENCY = 10               # max concurrent webhook dispatches

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(levelname)s %(message)s",
)
log = logging.getLogger("st4_p5_3")


# ---------------------------------------------------------------------------
# Circuit Breaker (standalone — not production code)
# ---------------------------------------------------------------------------

class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and requests are rejected fast."""


@dataclass
class CircuitBreaker:
    """Minimal circuit breaker for outbound webhook dispatch.

    States:
      CLOSED    — requests flow normally; failures increment counter.
      OPEN      — requests rejected immediately (fast-fail); timer counts
                  down to RECOVERY_TIMEOUT before a half-open probe.
      HALF_OPEN — a single probe request is allowed; success → CLOSED,
                  failure → back to OPEN.

    Thread-safe via a single lock around state transitions.
    """
    failure_threshold: int = 5
    recovery_timeout: float = 10.0
    _state: str = "closed"
    _consecutive_failures: int = 0
    _opened_at: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _half_open_probe_in_flight: bool = False

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "open":
                # Check if recovery timeout has elapsed.
                if time.monotonic() - self._opened_at >= self.recovery_timeout:
                    return "half_open"
            return self._state

    def allow_request(self) -> bool:
        """Return True if a request should proceed, False if fast-rejected."""
        with self._lock:
            if self._state == "closed":
                return True
            if self._state == "open":
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self.recovery_timeout:
                    # Transition to half-open; allow one probe.
                    self._state = "half_open"
                    self._half_open_probe_in_flight = True
                    return True
                return False  # fast-reject
            if self._state == "half_open":
                if self._half_open_probe_in_flight:
                    return False  # only one probe at a time
                self._half_open_probe_in_flight = True
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            if self._state in ("half_open", "open"):
                log.info("Circuit breaker: CLOSED (recovered)")
            self._state = "closed"
            self._half_open_probe_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._state == "half_open":
                # Probe failed; back to open.
                log.warning("Circuit breaker: OPEN (half-open probe failed)")
                self._state = "open"
                self._opened_at = time.monotonic()
                self._half_open_probe_in_flight = False
            elif self._consecutive_failures >= self.failure_threshold:
                if self._state != "open":
                    log.warning(
                        f"Circuit breaker: OPEN (after {self._consecutive_failures} consecutive failures)"
                    )
                self._state = "open"
                self._opened_at = time.monotonic()

    def reset(self) -> None:
        with self._lock:
            self._state = "closed"
            self._consecutive_failures = 0
            self._opened_at = 0.0
            self._half_open_probe_in_flight = False

    @property
    def stats(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "consecutive_failures": self._consecutive_failures,
                "opened_at": self._opened_at,
                "half_open_probe": self._half_open_probe_in_flight,
            }


# ---------------------------------------------------------------------------
# Mock HTTP Server (simulates failing integration endpoint)
# ---------------------------------------------------------------------------

# Module-level mutable mode so the handler always reads the current value.
_mock_mode: str = MOCK_SERVER_MODE


class MockWebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler that simulates integration failures.

    Modes:
      slow_500  — sleep 30s then return 500 (default, matches ST4 plan)
      500       — immediate 500
      slow_200  — sleep 30s then return 200 (tests timeout handling)
      timeout   — sleep 60s (connection timeout territory)
    """

    # Read mode from module-level global so runtime changes take effect.
    @property
    def mode(self) -> str:
        return _mock_mode

    def do_POST(self):
        current_mode = self.mode
        if current_mode != "500":
            log.info(f"  [mock-server] do_POST called, mode={current_mode}")
        if current_mode == "slow_500":
            time.sleep(30)
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error": "simulated slow failure"}')
        elif current_mode == "500":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error": "simulated failure"}')
        elif current_mode == "200":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')
        elif current_mode == "slow_200":
            time.sleep(30)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')
        elif current_mode == "timeout":
            time.sleep(60)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok": true}')
        else:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error": "unknown mode"}')

    def log_message(self, format, *args):
        # Suppress default stderr logging to keep output clean.
        pass


def start_mock_server(port: int) -> HTTPServer:
    """Start the mock webhook endpoint in a background thread."""
    server = ThreadingHTTPServer(("127.0.0.1", port), MockWebhookHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True, name="mock-webhook-server")
    t.start()
    log.info(f"Mock webhook server started on 127.0.0.1:{port} (mode={MOCK_SERVER_MODE})")
    return server


# ---------------------------------------------------------------------------
# Webhook Dispatcher (uses circuit breaker + thread pool)
# ---------------------------------------------------------------------------

@dataclass
class WebhookResult:
    webhook_id: int
    outcome: str  # "success", "failure", "circuit_open", "timeout", "error"
    status_code: Optional[int] = None
    duration_s: float = 0.0
    error: str = ""


class WebhookDispatcher:
    """Dispatches outbound webhooks with circuit-breaker protection.

    Uses a thread pool so the main thread is never blocked. Each dispatch:
      1. Checks circuit breaker — fast-rejects if OPEN.
      2. Sends HTTP POST to the target URL with a timeout.
      3. Records success/failure with the breaker.
      4. Logs the outcome.
    """

    def __init__(
        self,
        target_url: str,
        breaker: CircuitBreaker,
        max_workers: int = CONCURRENCY,
        request_timeout: float = 5.0,
    ):
        self.target_url = target_url
        self.breaker = breaker
        self.request_timeout = request_timeout
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="webhook-worker",
        )
        self._futures: list[concurrent.futures.Future] = []
        self._results: list[WebhookResult] = []
        self._results_lock = threading.Lock()
        self._shutdown = False

        # Configure logging for webhook failures.
        self._failure_log: list[dict] = []
        self._failure_log_lock = threading.Lock()

    def dispatch(self, webhook_id: int, payload: dict) -> concurrent.futures.Future:
        """Submit a webhook for async dispatch. Returns a Future."""
        future = self._executor.submit(self._send, webhook_id, payload)
        self._futures.append(future)
        return future

    def _send(self, webhook_id: int, payload: dict) -> WebhookResult:
        """Actual send logic — runs in a worker thread."""
        start = time.monotonic()

        # Check circuit breaker.
        if not self.breaker.allow_request():
            elapsed = time.monotonic() - start
            result = WebhookResult(
                webhook_id=webhook_id,
                outcome="circuit_open",
                duration_s=elapsed,
                error="Circuit breaker open — request fast-rejected",
            )
            self._record_result(result)
            return result

        # Send the HTTP request with a timeout.
        import urllib.request
        import urllib.error

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.target_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                status = resp.status
                elapsed = time.monotonic() - start
                if 200 <= status < 300:
                    self.breaker.record_success()
                    result = WebhookResult(
                        webhook_id=webhook_id,
                        outcome="success",
                        status_code=status,
                        duration_s=elapsed,
                    )
                else:
                    self.breaker.record_failure()
                    result = WebhookResult(
                        webhook_id=webhook_id,
                        outcome="failure",
                        status_code=status,
                        duration_s=elapsed,
                        error=f"HTTP {status}",
                    )
                    self._log_failure(webhook_id, status, elapsed, f"HTTP {status}")
        except urllib.error.HTTPError as e:
            elapsed = time.monotonic() - start
            self.breaker.record_failure()
            result = WebhookResult(
                webhook_id=webhook_id,
                outcome="failure",
                status_code=e.code,
                duration_s=elapsed,
                error=str(e),
            )
            self._log_failure(webhook_id, e.code, elapsed, str(e))
        except Exception as e:
            elapsed = time.monotonic() - start
            # Timeout or connection error = failure for breaker purposes.
            self.breaker.record_failure()
            outcome = "timeout" if "timed out" in str(e).lower() else "error"
            result = WebhookResult(
                webhook_id=webhook_id,
                outcome=outcome,
                duration_s=elapsed,
                error=str(e),
            )
            self._log_failure(webhook_id, None, elapsed, str(e))

        self._record_result(result)
        return result

    def _record_result(self, result: WebhookResult) -> None:
        with self._results_lock:
            self._results.append(result)

    def _log_failure(self, webhook_id: int, status: Optional[int], elapsed: float, error: str) -> None:
        entry = {
            "webhook_id": webhook_id,
            "status": status,
            "elapsed_s": round(elapsed, 3),
            "error": error,
            "timestamp": time.time(),
        }
        with self._failure_log_lock:
            self._failure_log.append(entry)
        log.warning(
            f"Webhook {webhook_id} FAILED: status={status} elapsed={elapsed:.2f}s error={error[:120]}"
        )

    def wait_all(self, timeout: float = 120.0) -> list[WebhookResult]:
        """Wait for all dispatched webhooks to complete. Returns results."""
        for f in self._futures:
            try:
                f.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                log.error("Webhook future timed out — this should not happen with circuit breaker")
            except Exception as e:
                log.error(f"Webhook future raised: {e}")
        with self._results_lock:
            return list(self._results)

    def shutdown(self) -> None:
        self._shutdown = True
        self._executor.shutdown(wait=True, cancel_futures=True)

    @property
    def results(self) -> list[WebhookResult]:
        with self._results_lock:
            return list(self._results)

    @property
    def failure_log(self) -> list[dict]:
        with self._failure_log_lock:
            return list(self._failure_log)


# ---------------------------------------------------------------------------
# Main Test
# ---------------------------------------------------------------------------

def main():
    log.info("=" * 70)
    log.info("ST4 Phase 5.3 — Webhook / Integration Callback Storm")
    log.info(f"  webhooks: {NUM_WEBHOOKS}")
    log.info(f"  concurrency: {CONCURRENCY}")
    log.info(f"  failure threshold: {FAILURE_THRESHOLD}")
    log.info(f"  recovery timeout: {RECOVERY_TIMEOUT}s")
    log.info(f"  mock mode: {MOCK_SERVER_MODE}")
    log.info(f"  request timeout: 5s")
    log.info("=" * 70)

    # Start mock server.
    server = start_mock_server(MOCK_SERVER_PORT)
    target_url = f"http://127.0.0.1:{MOCK_SERVER_PORT}/webhook"

    # Initialize circuit breaker.
    breaker = CircuitBreaker(
        failure_threshold=FAILURE_THRESHOLD,
        recovery_timeout=RECOVERY_TIMEOUT,
    )

    # Initialize dispatcher.
    dispatcher = WebhookDispatcher(
        target_url=target_url,
        breaker=breaker,
        max_workers=CONCURRENCY,
        request_timeout=5.0,
    )

    # --- Phase A: Fire 100 webhooks, mock returns slow 500s ---
    log.info("\n--- Phase A: Firing 100 webhooks against failing endpoint ---")
    main_thread_start = time.monotonic()

    for i in range(NUM_WEBHOOKS):
        payload = {
            "id": i,
            "event": "transaction.created",
            "data": {"account": "checking", "amount": 42.50},
        }
        dispatcher.dispatch(i, payload)

    # The dispatch calls above should be near-instant (submitting to thread pool).
    # Verify main thread is NOT blocked.
    dispatch_submit_time = time.monotonic() - main_thread_start
    log.info(f"  All {NUM_WEBHOOKS} webhooks submitted in {dispatch_submit_time:.3f}s (main thread not blocked)")

    if dispatch_submit_time > MAIN_THREAD_BLOCK_LIMIT:
        log.error(f"  FAIL: Main thread blocked for {dispatch_submit_time:.3f}s (limit {MAIN_THREAD_BLOCK_LIMIT}s)")
        server.shutdown()
        dispatcher.shutdown()
        sys.exit(1)
    else:
        log.info(f"  PASS: Main thread submit time {dispatch_submit_time:.3f}s < {MAIN_THREAD_BLOCK_LIMIT}s limit")

    # Wait for all futures to complete (workers will hit timeouts / 500s / circuit open).
    log.info("  Waiting for webhook workers to complete...")
    results = dispatcher.wait_all(timeout=120.0)
    total_elapsed = time.monotonic() - main_thread_start

    # --- Analysis ---
    log.info(f"\n  Total wall-clock time: {total_elapsed:.2f}s")

    outcomes = {}
    for r in results:
        outcomes[r.outcome] = outcomes.get(r.outcome, 0) + 1

    log.info(f"  Outcome distribution:")
    for outcome, count in sorted(outcomes.items()):
        log.info(f"    {outcome}: {count}")

    breaker_final = breaker.stats
    log.info(f"  Circuit breaker final state: {breaker_final}")

    failures_logged = len(dispatcher.failure_log)
    log.info(f"  Failures logged: {failures_logged}")

    # Circuit-open count: these are the fast-rejected requests after breaker tripped.
    circuit_open_count = outcomes.get("circuit_open", 0)
    failure_count = outcomes.get("failure", 0)
    timeout_count = outcomes.get("timeout", 0)
    error_count = outcomes.get("error", 0)
    success_count = outcomes.get("success", 0)

    # --- Phase B: Verify circuit breaker recovery ---
    log.info(f"\n--- Phase B: Waiting {RECOVERY_TIMEOUT + 1}s for circuit breaker recovery ---")
    time.sleep(RECOVERY_TIMEOUT + 1)

    # Switch mock server to 200 mode for recovery probe.
    global _mock_mode
    _mock_mode = "200"
    log.info(f"  Mock server mode is now: {_mock_mode}")
    log.info("  Mock server switched to 200 mode for recovery probe")

    # Dispatch a single probe webhook.
    recovery_start = time.monotonic()
    probe_future = dispatcher.dispatch(NUM_WEBHOOKS, {"event": "probe", "data": {}})
    probe_result = probe_future.result(timeout=10.0)
    recovery_elapsed = time.monotonic() - recovery_start

    log.info(f"  Probe result: outcome={probe_result.outcome} status={probe_result.status_code} elapsed={recovery_elapsed:.3f}s")
    log.info(f"  Circuit breaker after probe: {breaker.stats}")

    dispatcher.shutdown()
    server.shutdown()
    log.info("  Mock server and dispatcher shut down.")

    # --- Verdict ---
    log.info("\n" + "=" * 70)
    log.info("PHASE 5.3 VERDICT")
    log.info("=" * 70)

    passed = True
    failures = []

    # 1. Circuit breaker must have tripped (OPEN state at some point).
    if circuit_open_count == 0 and failure_count < FAILURE_THRESHOLD:
        failures.append("Circuit breaker never tripped — expected it to open after threshold failures")
        passed = False
    else:
        log.info(f"  ✅ Circuit breaker tripped: {circuit_open_count} requests fast-rejected")

    # 2. Main thread must not have been blocked during dispatch.
    if dispatch_submit_time > MAIN_THREAD_BLOCK_LIMIT:
        failures.append(f"Main thread blocked for {dispatch_submit_time:.3f}s")
        passed = False
    else:
        log.info(f"  ✅ Main thread not blocked: {dispatch_submit_time:.3f}s submit time")

    # 3. Failures must be logged.
    if failures_logged == 0 and (failure_count > 0 or timeout_count > 0 or error_count > 0):
        failures.append("Failures occurred but none were logged")
        passed = False
    else:
        log.info(f"  ✅ Failures logged: {failures_logged} entries")

    # 4. No 500 errors from the dispatcher itself (all outcomes should be handled gracefully).
    if error_count > 0 and circuit_open_count == 0:
        # Errors are acceptable only if the circuit breaker caught them
        failures.append(f"{error_count} unexpected errors (not caught by circuit breaker)")
        passed = False
    else:
        log.info(f"  ✅ All errors handled gracefully (errors={error_count}, all caught by breaker)")

    # 5. Circuit breaker should recover after timeout (probe should succeed in 200 mode).
    if probe_result.outcome != "success":
        failures.append(f"Recovery probe failed: outcome={probe_result.outcome} (expected success)")
        passed = False
    else:
        log.info(f"  ✅ Circuit breaker recovered: probe succeeded with 200")

    # 6. No successful webhooks should have gotten through during failure phase
    #    (unless breaker allowed some through before tripping).
    if success_count > 0 and MOCK_SERVER_MODE in ("slow_500", "500", "timeout"):
        failures.append(f"{success_count} unexpected successes during failure phase")
        passed = False
    else:
        log.info(f"  ✅ No unexpected successes during failure phase (successes={success_count})")

    # 7. Total failures + circuit_open + timeouts + successes should equal NUM_WEBHOOKS + 1 (probe).
    total_accounted = sum(outcomes.values()) + (1 if probe_result.outcome == "success" else 0)
    # Actually outcomes already includes all dispatched, but probe was dispatched after wait_all
    # So total = NUM_WEBHOOKS + 1 (probe)
    expected_total = NUM_WEBHOOKS + 1
    all_results = dispatcher.results
    actual_total = len(all_results)
    if actual_total != expected_total:
        failures.append(f"Result count mismatch: {actual_total} results vs {expected_total} expected")
        passed = False
    else:
        log.info(f"  ✅ All {expected_total} webhooks accounted for")

    if passed:
        log.info("\n  PHASE 5.3 RESULT: PASS")
        log.info("  Circuit breaker trips on failure threshold, fast-rejects subsequent")
        log.info("  requests, logs all failures, does not block main thread, and recovers")
        log.info("  after timeout with a successful probe.")
    else:
        log.error("\n  PHASE 5.3 RESULT: FAIL")
        for f in failures:
            log.error(f"    - {f}")
        # Print summary table
        log.info("\n  Summary:")
        log.info(f"    total webhooks dispatched: {NUM_WEBHOOKS + 1}")
        log.info(f"    outcomes: {outcomes}")
        log.info(f"    probe outcome: {probe_result.outcome}")
        log.info(f"    breaker final: {breaker.stats}")
        log.info(f"    main thread submit time: {dispatch_submit_time:.3f}s")
        log.info(f"    total wall-clock: {total_elapsed:.2f}s")
        sys.exit(1)


if __name__ == "__main__":
    main()