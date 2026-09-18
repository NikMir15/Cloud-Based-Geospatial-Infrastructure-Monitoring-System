#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

FRONTEND_URL = os.getenv("GEO_FRONTEND_URL", "http://localhost:8080")
ARTIFACT_DIR = Path("/tmp/phase_7_0_e_browser")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

passed = 0
failed = 0
warnings = 0


def ok(message):
    global passed
    passed += 1
    print(f"✅ PASS: {message}")


def fail(message):
    global failed
    failed += 1
    print(f"❌ FAIL: {message}")


def warn(message):
    global warnings
    warnings += 1
    print(f"⚠️  WARN: {message}")


def check(condition, message):
    if condition:
        ok(message)
    else:
        fail(message)


print("=" * 72)
print("PHASE 7.0E — BROWSER / VISUAL REGRESSION")
print("=" * 72)
print(f"Frontend: {FRONTEND_URL}")
print()

console_errors = []
page_errors = []
predictive_responses = {}
failed_requests = []

predictive_patterns = (
    "/predictive/summary",
    "/predictive/anomalies/",
    "/predictive/trends/",
    "/predictive/risk/",
    "/anomaly-events",
)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
    )

    page = context.new_page()

    page.on(
        "console",
        lambda msg: (
            console_errors.append(msg.text)
            if msg.type == "error"
            else None
        ),
    )

    page.on(
        "pageerror",
        lambda exc: page_errors.append(str(exc)),
    )

    def capture_response(response):
        url = response.url

        for pattern in predictive_patterns:
            if pattern in url:
                predictive_responses[url] = response.status
                break

    def capture_failed_request(request):
        url = request.url
        if "localhost" in url or "127.0.0.1" in url:
            failed_requests.append(url)

    page.on("response", capture_response)
    page.on("requestfailed", capture_failed_request)

    try:
        response = page.goto(
            FRONTEND_URL,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        check(
            response is not None and response.status < 400,
            f"Dashboard document loads successfully ({response.status if response else 'no response'})",
        )

    except Exception as exc:
        fail(f"Dashboard navigation failed: {exc}")
        browser.close()
        print()
        print(f"Passed   : {passed}")
        print(f"Failed   : {failed}")
        print(f"Warnings : {warnings}")
        sys.exit(1)

    # Give asynchronous dashboard/API initialization time to settle.
    page.wait_for_timeout(8000)

    print()
    print("=" * 72)
    print("EXISTING UI REGRESSION")
    print("=" * 72)

    check(
        page.locator(".leaflet-container").count() > 0,
        "Leaflet map container still exists",
    )

    if page.locator(".leaflet-container").count():
        box = page.locator(".leaflet-container").first.bounding_box()
        check(
            box is not None and box["width"] > 300 and box["height"] > 200,
            "Leaflet map remains visibly sized",
        )

    check(
        page.locator("#automationReliabilitySection").count() == 1,
        "Phase 6.9 Automation + Reliability section preserved",
    )

    # These are intentionally text/marker based because earlier phase
    # containers use different IDs in the existing dashboard.
    html = page.content()

    check(
        "PHASE 6.6" in html,
        "Phase 6.6 UI marker preserved",
    )

    check(
        "PHASE 6.8" in html,
        "Phase 6.8 UI marker preserved",
    )

    print()
    print("=" * 72)
    print("PHASE 7.0E UI")
    print("=" * 72)

    phase70 = page.locator("#predictiveOperationsSection")

    check(
        phase70.count() == 1,
        "Phase 7.0E predictiveOperationsSection exists exactly once",
    )

    if phase70.count():
        check(
            phase70.first.is_visible(),
            "Phase 7.0E Predictive Operations section is visible",
        )

        try:
            phase70.first.scroll_into_view_if_needed()
            page.wait_for_timeout(1000)

            section_box = phase70.first.bounding_box()

            check(
                section_box is not None
                and section_box["width"] > 300
                and section_box["height"] > 100,
                "Phase 7.0E section has usable rendered dimensions",
            )

        except Exception as exc:
            fail(f"Could not inspect Phase 7.0E layout: {exc}")

    # Save evidence regardless of success/failure.
    try:
        page.screenshot(
            path=str(ARTIFACT_DIR / "dashboard-full.png"),
            full_page=True,
        )
        ok("Full dashboard screenshot captured")
    except Exception as exc:
        warn(f"Could not capture full dashboard screenshot: {exc}")

    if phase70.count():
        try:
            phase70.first.screenshot(
                path=str(ARTIFACT_DIR / "phase-7-0-e.png")
            )
            ok("Phase 7.0E section screenshot captured")
        except Exception as exc:
            warn(f"Could not capture Phase 7.0E screenshot: {exc}")

    print()
    print("=" * 72)
    print("PREDICTIVE NETWORK CONTRACT")
    print("=" * 72)

    for url, status in sorted(predictive_responses.items()):
        print(f"{status:3}  {url}")

    # Required aggregate route.
    summary_seen = any(
        "/predictive/summary" in url
        for url in predictive_responses
    )

    check(
        summary_seen,
        "Browser requested /predictive/summary",
    )

    # Asset-specific calls depend on a selected/available infrastructure asset.
    for pattern, label in (
        ("/predictive/anomalies/", "predictive anomaly"),
        ("/predictive/trends/", "predictive trend"),
        ("/predictive/risk/", "predictive risk"),
    ):
        matching = [
            status
            for url, status in predictive_responses.items()
            if pattern in url
        ]

        if matching:
            check(
                all(200 <= status < 300 for status in matching),
                f"Observed {label} browser requests return 2xx",
            )
        else:
            warn(
                f"No {label} asset request observed; "
                "this may require an asset selection"
            )

    event_matching = [
        status
        for url, status in predictive_responses.items()
        if "/anomaly-events" in url
    ]

    if event_matching:
        check(
            all(200 <= status < 300 for status in event_matching),
            "Observed anomaly-events browser requests return 2xx",
        )
    else:
        warn("No /anomaly-events browser request observed")

    predictive_bad = [
        (url, status)
        for url, status in predictive_responses.items()
        if status >= 400
    ]

    check(
        not predictive_bad,
        "No observed predictive browser API response returned HTTP >= 400",
    )

    print()
    print("=" * 72)
    print("JAVASCRIPT / REQUEST HEALTH")
    print("=" * 72)

    relevant_console_errors = [
        err for err in console_errors
        if "favicon" not in err.lower()
    ]

    if relevant_console_errors:
        for err in relevant_console_errors[:20]:
            print(f"JS ERROR: {err}")

    check(
        len(relevant_console_errors) == 0,
        "No significant browser console errors",
    )

    if page_errors:
        for err in page_errors[:20]:
            print(f"PAGE ERROR: {err}")

    check(
        len(page_errors) == 0,
        "No uncaught JavaScript page errors",
    )

    if failed_requests:
        for url in failed_requests[:20]:
            print(f"FAILED REQUEST: {url}")

    check(
        len(failed_requests) == 0,
        "No localhost dashboard requests failed at transport level",
    )

    browser.close()


print()
print("=" * 72)
print("PHASE 7.0E BROWSER RESULT")
print("=" * 72)
print(f"Passed   : {passed}")
print(f"Failed   : {failed}")
print(f"Warnings : {warnings}")
print(f"Evidence : {ARTIFACT_DIR}")

if failed:
    print()
    print("❌ Phase 7.0E browser verification FAILED")
    sys.exit(1)

print()
print("✅ Phase 7.0E browser verification PASSED")
sys.exit(0)
