import json
import os
import re
import logging

logger = logging.getLogger("SymptoGuide")

# -------- Settings (dynamic paths) --------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

INPUT_FILE = os.path.join(PROJECT_ROOT, "data", "raw", "nhs_medicines", "nhs_medicines.json")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", "processed", "nhs_medicines_tagged.json")

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

def clean_medicine_text(text):
    if not text: return ""

    # 1. Remove "Resources" and External Links section (at the end of files)
    # This removes everything starting from "Useful resources" or "Related resources" to the end
    text = re.sub(r"Useful resources.*", "", text, flags=re.DOTALL)
    text = re.sub(r"Related resources.*", "", text, flags=re.DOTALL)

    # 2. Remove Emergency Boilerplate (Confuses AI diagnosis)
    # Removing "You can call 111", "Call 999", "Do not drive to A&E"
    text = re.sub(r"You can call 111.*", "", text)
    text = re.sub(r"If you're told to go to A&E.*", "", text)
    text = re.sub(r"Ask someone to drive you.*", "", text)
    
    # 3. Clean "Table of Contents" Headers (The "Shallow Data" problem)
    # In your Doxazosin example, these headers appear without content. We remove them to keep the text focused.
    headers_to_remove = [
        "Who can and cannot take it",
        "How and when to take it",
        "Taking it with other medicines",
        "Pregnancy, breastfeeding and fertility",
        "Common questions",
        "Related conditions",
        "About doxazosin", # Specific drug headers usually follow "About X" pattern
        "About " # Generic catcher
    ]
    
    for header in headers_to_remove:
        # We replace them with a space to avoid merging words
        text = text.replace(header, " ")

    # 4. Remove URL junk
    text = re.sub(r"www\.[a-zA-Z0-9\-\.]+\.[a-z]+", "", text)

    # 5. Collapse whitespace
    return " ".join(text.split())

def main():
    logger.info(f"Processing: {INPUT_FILE}")
    
    if not os.path.exists(INPUT_FILE):
        logger.error(f"File not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    final_data = []
    logger.info(f"Cleaning {len(data)} medicines...")

    for entry in data:
        name = entry.get('name', 'Unknown')
        raw_text = entry.get('text', '') or entry.get('description', '')
        url = entry.get('url', '')

        # Clean the text
        clean_text = clean_medicine_text(raw_text)

        # Skip if empty
        if len(clean_text) < 10:
            continue

        # Create Standard Entry
        processed_entry = {
            "entity_type": "medicine",  # <--- FIXED TAG
            "url": url,
            "source": "NHS",
            "name": name,
            "text": clean_text,
            # Context: "Medicine: Doxazosin. Usage: Treats high blood pressure..."
            "embedding_context": f"Medicine: {name}. Usage: {clean_text[:1000]}"
        }
        
        final_data.append(processed_entry)

    # Save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(final_data)} clean medicines to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()