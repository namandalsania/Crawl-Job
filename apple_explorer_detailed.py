
from playwright.sync_api import sync_playwright
import json
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Log requests to a file including method and post data
        def log_request(request):
            with open("apple_requests_detailed.txt", "a", encoding="utf-8") as f:
                entry = {
                    "url": request.url,
                    "method": request.method,
                    "post_data": request.post_data,
                    "headers": request.headers
                }
                f.write(json.dumps(entry) + "\n")

        page.on("request", log_request)
        
        print("Navigating...")
        # Add search params to ensure results
        page.goto("https://jobs.apple.com/en-us/search?search=Machine%20Learning&sort=relevance", timeout=60000)
        
        # Scroll to bottom to trigger lazy load
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(5)
        
        print("Closing...")
        browser.close()

if __name__ == "__main__":
    open("apple_requests_detailed.txt", "w").close() # Clear file
    run()
