# File: src/scrapers/scrape_nhs.py

import requests
from bs4 import BeautifulSoup
import json
import os
import time
import logging
from pathlib import Path
from urllib.parse import urljoin

logger = logging.getLogger("SymptoGuide")

# -------- Project Settings --------
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]

BASE_URL = "https://www.nhs.uk/conditions/"
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "nhs"
os.makedirs(DATA_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/115.0.0.0 Safari/537.36"
}

# -------- Helper Functions --------
def save_json(data, filename):
    """Save data as JSON to the output directory."""
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def scrape_page(url):
    """Fetch a page and extract its text content."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Page title
        title = soup.find("h1")
        title_text = title.get_text(strip=True) if title else ""

        # Main text content
        content_div = soup.find("div", class_="nhsuk-u-body-copy") or soup
        paragraphs = [p.get_text(strip=True) for p in content_div.find_all("p")]

        return {
            "url": url,
            "title": title_text,
            "content": "\n".join(paragraphs)
        }
    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return None

def get_all_conditions_links():
    """Fetch all condition links from the NHS conditions index page."""
    try:
        r = requests.get(BASE_URL, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        links = []

        for a in soup.find_all("a", href=True):
            href = a['href']
            # Only internal condition links
            if href.startswith("/conditions/") and href != "/conditions/":
                full_url = urljoin(BASE_URL, href)
                if full_url not in links:
                    links.append(full_url)
        return links
    except Exception as e:
        logger.error(f"Could not fetch condition links: {e}")
        return []

# -------- Main Scraper --------
def main():
    condition_links = get_all_conditions_links()
    logger.info(f"Found {len(condition_links)} conditions")

    all_data = []
    for idx, url in enumerate(condition_links, start=1):
        logger.info(f"Scraping {idx}/{len(condition_links)}: {url}")
        data = scrape_page(url)
        if data:
            all_data.append(data)
        time.sleep(1)  # Respect site rate limits

    # Save all data at once
    save_json(all_data, "nhs_conditions.json")
    logger.info("Scraping finished. Data saved in 'data/raw/nhs/nhs_conditions.json'")

if __name__ == "__main__":
    main()

