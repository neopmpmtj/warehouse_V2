#!/usr/bin/env python3
"""Capture pt-PT user-manual screenshots from a running CentCompras dev server.

Usage:
  .venv/bin/python scripts/capture_manual_screenshots.py [--base http://127.0.0.1:8000]

Writes PNGs to docs/user-manuals/pt/screenshots/ (same basenames as EN).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "user-manuals" / "pt" / "screenshots"

WAREHOUSE_EMAIL = "warehouse.admin@centcompras.dev"
BRANCH_EMAIL = "branch.manager.north@centcompras.dev"
PASSWORD = "devpass123"


def login(page, base: str, email: str) -> None:
    page.goto(f"{base}/accounts/login/")
    page.fill('input[name="username"]', email)
    page.fill('input[name="password"]', PASSWORD)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def set_pt(page) -> None:
    page.evaluate("""() => {
        localStorage.setItem('cc-lang', 'pt');
        document.documentElement.lang = 'pt-PT';
    }""")


def shot(page, path: Path, *, full_page: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=full_page)
    print(f"saved {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Login page (no session)
        page.goto(f"{base}/accounts/login/")
        page.wait_for_load_state("networkidle")
        shot(page, OUT_DIR / "00-login.png", full_page=False)

        # Warehouse flows in pt-PT
        login(page, base, WAREHOUSE_EMAIL)
        set_pt(page)

        page.goto(f"{base}/")
        page.wait_for_load_state("networkidle")
        page.evaluate(
            """() => {
                const sel = document.getElementById('pref-language');
                if (sel) { sel.value = 'pt'; sel.dispatchEvent(new Event('change')); }
            }"""
        )
        page.wait_for_timeout(500)
        shot(page, OUT_DIR / "01-dashboard.png")

        routes = {
            "02-items.png": "/manage/items/",
            "03-catalog.png": "/manage/catalog/",
            "04-purchase-orders.png": "/manage/purchase-orders/",
            "05-goods-receipts.png": "/manage/goods-receipts/",
            "06-approval-limits.png": "/manage/approval-limits/",
            "07-internal-requests.png": "/manage/internal-requests/",
            "12-warehouse-threads.png": "/manage/threads/",
        }
        for name, route in routes.items():
            page.goto(f"{base}{route}")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(800)
            shot(page, OUT_DIR / name)

        # Settings popover on item console
        page.goto(f"{base}/manage/items/")
        page.wait_for_load_state("networkidle")
        page.click("#settings-toggle")
        page.wait_for_timeout(400)
        shot(page, OUT_DIR / "08-settings-popover.png", full_page=False)

        # Branch threads (branch user)
        context.clear_cookies()
        page = context.new_page()
        login(page, base, BRANCH_EMAIL)
        set_pt(page)
        page.goto(f"{base}/branch/threads/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)
        shot(page, OUT_DIR / "09-branch-threads.png")

        # Close dialog — select first thread if present, open close dialog
        page.wait_for_selector("#thread-body tr", timeout=10000)
        rows = page.locator("#thread-body tr")
        if rows.count() > 0:
            rows.first.click()
            page.wait_for_timeout(800)
            close_btn = page.locator("#close-thread-btn")
            if close_btn.count() and close_btn.is_visible():
                close_btn.click()
                page.wait_for_timeout(500)
                shot(page, OUT_DIR / "11-thread-close-dialog.png", full_page=False)
            else:
                print("skip 11-thread-close-dialog.png (close button not visible)")
        else:
            print("skip 11-thread-close-dialog.png (no threads)")

        browser.close()

    missing = [
        f.name
        for f in sorted(OUT_DIR.glob("*.png"))
    ]
    print(f"done: {len(missing)} screenshots in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
