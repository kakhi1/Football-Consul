import time
from playwright.sync_api import sync_playwright

def get_html():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.flashscore.com/football/world/world-championship/fixtures/", wait_until='domcontentloaded')
        
        try:
            page.wait_for_selector('.event__match', timeout=5000)
            html = page.locator('.event__match').first.inner_html()
            print(html)
        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    get_html()
