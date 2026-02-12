
from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Listen for network requests
        page.on("request", lambda request: open("apple_requests.txt", "a").write(f"{request.url}\n"))
        
        # Navigate to Apple Jobs
        print("Navigating to Apple Jobs...")
        page.goto("https://jobs.apple.com/en-us/search?search=Machine%20Learning&sort=relevance", timeout=60000)
        
        
        # Save HTML content
        with open("apple.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        
        browser.close()

if __name__ == "__main__":
    run()
