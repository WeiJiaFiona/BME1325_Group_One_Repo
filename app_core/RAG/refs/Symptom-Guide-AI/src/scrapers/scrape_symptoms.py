import requests
from bs4 import BeautifulSoup
import json
import os
import time
import random
import string
import logging

# -------- Settings (dynamic paths) --------
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]

DATA_DIR = PROJECT_ROOT / "data" / "raw" / "mayo_clinic"
OUTPUT_FILE = DATA_DIR / "mayo_tests_procedures.json"

os.makedirs(DATA_DIR, exist_ok=True)

logger = logging.getLogger("SymptoGuide")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

def get_soup(url):
    for _ in range(3): # 3 Retries
        try:
            time.sleep(random.uniform(1.5, 3.0))
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "html.parser")
        except Exception:
            time.sleep(2)
    return None

def scrape_tests_index(letter):
    """Scrapes the A-Z list of Tests & Procedures."""
    url = f"https://www.mayoclinic.org/tests-procedures/index?letter={letter}"
    soup = get_soup(url)
    if not soup: return []

    links = []
    # Mayo structure for tests index
    container = soup.find("div", {"id": "index"}) or soup.find("div", class_="content-rail") or soup

    for a in container.find_all("a", href=True):
        # Look for links containing /tests-procedures/ and /about/
        if "/tests-procedures/" in a['href'] and "/about/" in a['href']:
            links.append({
                "test_name": a.get_text(strip=True),
                "url": "https://www.mayoclinic.org" + a['href']
            })
    return links

def scrape_test_details(url):
    """Extracts the 'Why it's done' or Definition of the test."""
    soup = get_soup(url)
    if not soup: return "N/A"

    # Content is usually in article body
    article = soup.find("div", class_="content") or soup.find("article")
    if not article: return "N/A"

    # Try to find the "Overview" or "Why it's done" section
    # Often the first few paragraphs describe the test
    paragraphs = article.find_all("p")
    
    definition_parts = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        # Filter junk
        if "Request an Appointment" in text or "Mayo Clinic" in text or len(text) < 30:
            continue
            
        definition_parts.append(text)
        if len(definition_parts) >= 3: # First 3 paragraphs are enough context
            break
            
    return " ".join(definition_parts)

def main():
    logger.info("Starting Scraping: Tests & Procedures...")
    
    all_tests_links = []
    
    # 1. Gather Links A-Z
    logger.info("[PHASE 1] Gathering Links...")
    for letter in string.ascii_uppercase:
        found = scrape_tests_index(letter)
        if found:
            all_tests_links.extend(found)
            logger.info(f"Letter {letter}: Found {len(found)} tests")
            
    # Remove duplicates
    unique_tests = list({v['url']: v for v in all_tests_links}.values())
    logger.info(f"Total Unique Tests Found: {len(unique_tests)}")

    # 2. Deep Scrape
    logger.info("[PHASE 2] Scraping Details...")
    final_data = []
    
    for idx, item in enumerate(unique_tests, 1):
        definition = scrape_test_details(item['url'])
        
        entry = {
            "test_name": item['test_name'],
            "url": item['url'],
            "description": definition,
            "source": "Mayo Clinic"
        }
        final_data.append(entry)
        
        logger.info(f"[{idx}/{len(unique_tests)}] {item['test_name']}")
        
        # Save regularly
        if idx % 10 == 0:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)

    # Final Save
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved {len(final_data)} tests to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()