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
    
    print(f"DEBUG: Email User is set: {bool(EMAIL_ADDRESS)}")
    print(f"DEBUG: Email Pass is set: {bool(EMAIL_PASSWORD)}")

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
                full_link = f"https://apply.careers.microsoft.com{relative_link}"
                
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

def scrape_microsoft_ai(page, seen_jobs):
    AI_URL = "https://microsoft.ai/careers/?selected_regions=redmond-united-states"
    print(f"[*] Checking Microsoft AI Careers: {datetime.now().strftime('%H:%M:%S')}")
    new_count = 0
    target_roles = ["Software Engineer", "Applied Scientist", "Machine Learning", "Data"]
    
    try:
        # Navigate to filtered URL
        page.goto(AI_URL, timeout=60000)
        
        # Wait for potential content loading
        page.wait_for_timeout(5000)
        
        # Scroll to bottom to trigger lazy loading
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(3000)
        
        # Generic strategy: Find all links and filter by text
        links = page.locator("a").all()
        
        for link in links:
            try:
                text = link.inner_text().strip()
                href = link.get_attribute("href")
                
                if not href or "microsoft.ai" not in href and not href.startswith("/"):
                    continue
                    
                # Check if text matches any target role
                if any(role.lower() in text.lower() for role in target_roles):
                    # It's a job link! (Validation: usually job titles are link text)
                    if "careers" not in href and "job" not in href:
                         # Double check it's not a generic nav link like "Careers Home"
                         if len(text) < 5 or "Carrers" in text or "Home" in text: continue

                    job_id = href # Use full URL or unique part as ID
                    full_link = href
                    if href.startswith("/"):
                        full_link = f"https://microsoft.ai{href}"
                    
                    if job_id not in seen_jobs:
                        # Location Check via Parent Element
                        try:
                            parent_text = link.locator("xpath=..").inner_text().lower()
                            # Strict filter: Must contain Redmond or US/United States
                            # Logic: If it doesn't have "redmond" AND doesn't have "united states"/"usa", PROBABLY skip?
                            # But user said "Redmond, United States".
                            # Let's start with a broad text check for US markers.
                            
                            is_valid_location = False
                            for loc_marker in ["redmond", "united states", "usa", " us", ", us"]:
                                if loc_marker in parent_text:
                                    is_valid_location = True
                                    break
                            
                            if not is_valid_location:
                                # print(f"    [!] Skipped non-US job: {text}")
                                continue
                                
                            # If valid, use the parent text as location source roughly
                            location = "Redmond, United States" # Default since we verified it matches
                            if "redmond" not in parent_text and ("united states" in parent_text or "usa" in parent_text):
                                location = "United States"

                        except:
                            # If we can't verify location text, skip to be safe?
                            # Or assume URL filter worked? User says it doesn't.
                            continue

                        job_data = {
                            "id": job_id,
                            "title": text,
                            "company": "Microsoft AI",
                            "location": location,
                            "url": full_link
                        }
                        
                        send_email_notification(job_data)
                        send_discord_notification(job_data)
                        seen_jobs.append(job_id)
                        new_count += 1
                        print(f"    [+] Found AI Job: {text}")
                        
            except Exception as e:
                continue

    except Exception as e:
        print(f"[!] Microsoft AI scrape error: {e}")
        
    return new_count

def scrape_apple(page, seen_jobs):
    print(f"[*] Checking Apple Careers: {datetime.now().strftime('%H:%M:%S')}")
    new_count = 0
    
    for keyword in APPLE_KEYWORDS:
        try:
            # Construct search URL (Apply location filter in URL)
            # location=united-states-USA provides better filtering
            url = f"{APPLE_BASE_URL}?search={keyword}&sort=relevance&sort=date&location=united-states-USA"
            print(f"    [-] Searching for '{keyword}'...")
            
            page.goto(url, timeout=60000)
            
            try:
                page.wait_for_selector('h3 a', timeout=10000)
            except:
                print(f"    [!] No results or timeout for '{keyword}'")
                continue

            # Apple's results list
            results = page.locator('tbody#results tbody').all() # Sometimes structure varies, let's stick to rows
            # Using a more generic selector for the row to get both title and location
            # Usually: table#results > tbody (rows)
            # The title is in td.table-col-1 > a
            # The location is in td.table-col-2
            
            rows = page.locator('table#results tbody tr').all()
            
            for row in rows[:15]: 
                try:
                    title_link = row.locator('td.table-col-1 a').first
                    if not title_link.count(): continue
                    
                    title = title_link.inner_text().strip()
                    href = title_link.get_attribute('href')
                    
                    if not href: continue
                    
                    # Location Check
                    location_el = row.locator('td.table-col-2').first
                    location = location_el.inner_text().strip() if location_el.count() else "Unknown"
                    
                    # Strict filtering for US
                    if "United States" not in location and "USA" not in location and "US" not in location:
                        continue

                    job_id = href.split('/')[3] if len(href.split('/')) > 3 else href
                    full_link = f"https://jobs.apple.com{href}"
                    
                    if job_id not in seen_jobs:
                        job_data = {
                            "id": job_id,
                            "title": title,
                            "company": "Apple",
                            "location": location,
                            "url": full_link
                        }
                        
                        send_email_notification(job_data)
                        send_discord_notification(job_data)
                        seen_jobs.append(job_id)
                        new_count += 1
                        print(f"    [+] Found: {title} ({location})")
                        
                except Exception as e:
                    # print(f"Row error: {e}")
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
        
        # 3. Microsoft AI
        new_ms_ai = scrape_microsoft_ai(page, seen_jobs)
        print(f"[*] Microsoft AI: Found {new_ms_ai} new jobs.")
        
        if new_ms + new_apple + new_ms_ai > 0:
            print("[*] Updating database...")
            save_seen_jobs(seen_jobs)
        else:
            print("[*] No new jobs found.")
            
        browser.close()

if __name__ == "__main__":
    run_scraper()
