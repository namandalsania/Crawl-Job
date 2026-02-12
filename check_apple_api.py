
import requests

def try_url(url):
    print(f"Testing {url}...")
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            try:
                data = r.json()
                print("Success! JSON received.")
                # print(str(data)[:200]) # Preview
            except:
                print("Not JSON.")
        else:
            print("Failed.")
    except Exception as e:
        print(e)

endpoints = [
    "https://jobs.apple.com/api/v1/search",
    "https://jobs.apple.com/api/role/search",
    "https://jobs.apple.com/api/v1/job/search",
    "https://jobs.apple.com/api/v1/jobs/search",
    "https://jobs.apple.com/api/jobs/search"
]

for e in endpoints:
    try_url(e)
