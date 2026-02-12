import json
import time
import random
import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests # For sending the Discord notification
import smtplib
from email.message import EmailMessage


# --- CONFIGURATION ---
# 1. Go to Discord Server Settings -> Integrations -> Webhooks -> New Webhook -> Copy Webhook URL
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

if not WEBHOOK_URL:
    print("[!] Error: DISCORD_WEBHOOK_URL not set.")
    # sys.exit(1) # Commented out to allow running without Discord webhook

# 2. Define the Microsoft Jobs URL with your specific filters.
# I have pre-filled this for "Software Engineer" in the "United States". 
# IMPORTANT: Adjust the 'lc' (Location) or 'q' (Query) as needed.
MICROSOFT_URL = "https://apply.careers.microsoft.com/careers?domain=microsoft.com&hl=en&start=0&location=United+States&pid=1970393556659104&sort_by=timestamp&filter_include_remote=1&filter_profession=software+engineering&filter_seniority=Entry%2CMid-Level"

# Apple Config
APPLE_BASE_URL = "https://jobs.apple.com/en-us/search"
APPLE_KEYWORDS = ["Machine Learning", "ML", "Software", "Data"]

# File to store jobs we've already seen
DB_FILE = "seen_jobs.json"


def send_discord_notification(job):
    """Sends a push notification via Discord."""
    if not WEBHOOK_URL: return
    
    data = {
        "content": f"🚨 **NEW JOB DETECTED!** 🚨\n\n**{job['title']}**\nCompany: {job['company']}\nLocation: {job['location']}\n[Apply Now]({job['url']})"
    }
    try:
        requests.post(WEBHOOK_URL, json=data)
        print(f"[-] Discord notification sent for {job['id']}")
    except Exception as e:
        print(f"[!] Failed to send Discord notification: {e}")

def send_email_notification(job):
    # Credentials from Environment Variables
    EMAIL_ADDRESS = os.environ.get("EMAIL_USER")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASS") # The 16-char App Password
    
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("[!] Email credentials missing.")
        return

    msg = EmailMessage()
    msg['Subject'] = f"New Job: {job['title']} ({job['company']})"
    msg['From'] = "namandalsania12@gmail.com"
    msg['To'] = "namandalsania12@gmail.com" # Send to yourself
    
    body = (
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
        f"Apply Here: {job['url']}"
    )
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"[-] Email sent for {job['id']}")
    except Exception as e:
        print(f"[!] Email failed: {e}")

def load_seen_jobs():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_seen_jobs(jobs):
    with open(DB_FILE, 'w') as f:
        json.dump(jobs, f)

def scrape_microsoft(page, seen_jobs):
    print(f"[*] Checking Microsoft Careers: {datetime.now().strftime('%H:%M:%S')}")
    new_count = 0
    try:
        page.goto(MICROSOFT_URL, timeout=60000)
        page.wait_for_selector('div[data-test-id="job-listing"]', timeout=15000)
        
        job_cards = page.locator('div[data-test-id="job-listing"]').all()
        for card in job_cards[:15]:
            try:
                link_el = card.locator('a').first
                raw_text = link_el.inner_text()
                relative_link = link_el.get_attribute('href')
                full_link = f"https://apply.careers.microsoft.com/careers?start=0&pid={relative_link}"
                
                lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
                title = lines[0] if lines else 'N/A'
                job_id = relative_link
                
                if job_id not in seen_jobs:
                    job_data = {
                        "id": job_id,
                        "title": title,
                        "company": "Microsoft",
                        "location": "United States", 
                        "url": full_link
                    }
                    send_email_notification(job_data)
                    send_discord_notification(job_data)
                    seen_jobs.append(job_id)
                    new_count += 1
            except Exception as e:
                print(f"[!] Error Microsoft card: {e}")
                continue
    except Exception as e:
        print(f"[!] Microsoft scrape error: {e}")
    
    return new_count

def scrape_apple(page, seen_jobs):
    print(f"[*] Checking Apple Careers: {datetime.now().strftime('%H:%M:%S')}")
    new_count = 0
    
    for keyword in APPLE_KEYWORDS:
        try:
            # Construct search URL
            url = f"{APPLE_BASE_URL}?search={keyword}&sort=relevance"
            print(f"    [-] Searching for '{keyword}'...")
            
            page.goto(url, timeout=60000)
            
            # Apple jobs are lazy loaded or SSR. We look for the job title link.
            # Grid/List usually has `h3 a` for title.
            try:
                page.wait_for_selector('h3 a', timeout=10000)
            except:
                print(f"    [!] No results or timeout for '{keyword}'")
                continue

            # Get all job title links (which contain the ID in href)
            # Selector derived from inspection: `h3 a` inside table-col-1 or similar
            # In the user-provided HTML, title is inside `h3 > a`
            links = page.locator('h3 a').all()
            
            for link in links[:10]: # Check top 10
                try:
                    title = link.inner_text().strip()
                    href = link.get_attribute('href') # e.g. /en-us/details/200586650-3956/...
                    
                    if not href: continue
                    
                    # Extract unique ID (the number part)
                    # href format: /en-us/details/200586650-3956/machine-learning-engineer?team=MLAI
                    job_id = href.split('/')[3] if len(href.split('/')) > 3 else href
                    full_link = f"https://jobs.apple.com{href}"
                    
                    if job_id not in seen_jobs:
                        job_data = {
                            "id": job_id,
                            "title": title,
                            "company": "Apple",
                            "location": "United States", # Should extract from page if possible
                            "url": full_link
                        }
                        
                        # Get date to ensure it's "newest" if possible
                        # We just trust 'seen_jobs' since we poll frequently.
                        
                        send_email_notification(job_data)
                        send_discord_notification(job_data)
                        seen_jobs.append(job_id)
                        new_count += 1
                        print(f"    [+] Found: {title}")
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"[!] Apple scrape error for {keyword}: {e}")
            
    return new_count

def run_scraper():
    seen_jobs = load_seen_jobs()
    print(f"[*] Loaded {len(seen_jobs)} previously seen jobs.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 1. Microsoft
        new_ms = scrape_microsoft(page, seen_jobs)
        print(f"[*] Microsoft: Found {new_ms} new jobs.")
        
        # 2. Apple
        new_apple = scrape_apple(page, seen_jobs)
        print(f"[*] Apple: Found {new_apple} new jobs.")
        
        if new_ms + new_apple > 0:
            print("[*] Updating database...")
            save_seen_jobs(seen_jobs)
        else:
            print("[*] No new jobs found.")
            
        browser.close()

if __name__ == "__main__":
    run_scraper()
