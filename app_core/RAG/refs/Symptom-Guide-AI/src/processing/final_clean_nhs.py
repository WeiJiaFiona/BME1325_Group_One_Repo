import json
import os
import re
import logging

logger = logging.getLogger("SymptoGuide")

# -------- Settings (dynamic paths) --------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

INPUT_FILE = os.path.join(PROJECT_ROOT, "data", "clean", "nhs", "cleaned_nhs_conditions_clean.json")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", "processed", "nhs_conditions_tagged.json")

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

def clean_nhs_text(text):
    if not text: return ""

    # 1. Remove Top Navigation
    text = text.replace("Back toConditions A to Z", "")
    text = text.replace("Back toHealth A to Z", "")

    # 2. Remove Footer (Dates & Copyright)
    # Regex: Finds "Page last reviewed" and removes everything after it
    text = re.sub(r"Page last reviewed:.*", "", text, flags=re.DOTALL)
    text = text.replace("© Crown copyright", "")

    # 3. Remove "Stock Photo" Links (The Alamy/Science Photo junk you showed)
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        # If line has stock photo keywords or looks like a huge URL, skip it
        if any(x in line for x in ["alamy.com", "Stock Photo", "sciencephoto.com", "imageid=", "jpg", "png"]):
            continue
        # Skip lines that are just long URLs (often tracking links)
        if line.strip().startswith("http") and len(line) > 50:
            continue
        
        clean_lines.append(line)
    
    text = "\n".join(clean_lines)

    # 4. Collapse extra spaces
    return " ".join(text.split())

def main():
    logger.info(f"Processing: {INPUT_FILE}")
    
    if not os.path.exists(INPUT_FILE):
        logger.error("File not found. Check path.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    final_data = []
    
    logger.info(f"Scanning {len(data)} raw entries...")

    for entry in data:
        title = entry.get('title', 'Unknown')
        url = entry.get('url', '')
        
        # ----------------------------------------------------
        # FILTER: Garbage Collection
        # ----------------------------------------------------
        # 1. Skip the "Phone Book" Index pages
        if "Conditions A to Z" in title:
            continue
        
        # 2. Skip Hash Links (e.g. nhs.uk/conditions/#a)
        if url.endswith("/#a") or url.endswith("/#b"):
            continue

        # ----------------------------------------------------
        # CLEAN: Text Processing
        # ----------------------------------------------------
        raw_content = entry.get('content', '')
        clean_content = clean_nhs_text(raw_content)

        # Skip if the page is empty after cleaning
        if len(clean_content) < 50:
            continue

        # ----------------------------------------------------
        # TAG: Add "entity_type" (The Enough Thinking Step)
        # ----------------------------------------------------
        processed_entry = {
            "entity_type": "condition",
            "url": url,
            "source": "NHS",   # <--- HERE IS YOUR SPECIFIC TAG
            "name": title,
            "text": clean_content,
            
            # We create a specific context string for the AI to read later
            "embedding_context": f"Medical Condition: {title}. Details: {clean_content[:1000]}"
        }
        
        final_data.append(processed_entry)

    # Save to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(final_data)} Clean Conditions to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()