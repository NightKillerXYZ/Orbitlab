"""Headless smoke test for the wired Main UI (needs: pip install playwright && playwright install chromium).

Run the backend first (mock switches, no keys needed):
    $env:ORBITLAB_USE_MOCK_INTERPRETER='true'; $env:PYTHONPATH='phase4_backend'
    python -m uvicorn orbitlab_backend.api.app:app --port 8000

Then:  python scripts/ui_smoke.py
Writes phase4_backend/phase5_main_ui_smoke.png
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8000/"
PROMPT = "Put a 500 kg satellite in a circular orbit at 400 km altitude around Earth for 1 day"
OUT = Path(__file__).resolve().parent.parent / "phase4_backend" / "phase5_main_ui_smoke.png"


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(URL, wait_until="networkidle")
        page.fill("#promptInput", PROMPT)
        page.click("#chatForm .send-btn")
        # Final state is a run card in the Chat panel (success or failure both prove wiring).
        page.wait_for_selector(".chat-result", timeout=120000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT))
        print("saved", OUT)
        browser.close()


if __name__ == "__main__":
    main()
