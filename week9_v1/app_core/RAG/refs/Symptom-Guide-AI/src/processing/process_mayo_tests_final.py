import json
import os
import re
import logging

logger = logging.getLogger("SymptoGuide")

# -------- Settings (dynamic paths) --------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

INPUT_FILE = os.path.join(PROJECT_ROOT, "data", "raw", "mayo_clinic", "mayo_tests_procedures.json")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", "processed", "mayo_tests_tagged.json")

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

def clean_mayo_text(text):
    if not text: return ""

    # 1. Deduplicate Sentences (Fixes the "double paragraph" error seen in your data)
    # We split by ". " and only keep unique sentences.
    sentences = text.split('. ')
    seen = set()
    clean_sentences = []
    
    for s in sentences:
        s_clean = s.strip()
        if s_clean and s_clean not in seen:
            seen.add(s_clean)
            clean_sentences.append(s_clean)
    
    # Rejoin sentences
    text = ". ".join(clean_sentences)
    if not text.endswith("."): 
        text += "."
    
    # 2. Remove extra whitespace
    return " ".join(text.split())

def main():
    logger.info(f"Processing: {INPUT_FILE}")
    
    if not os.path.exists(INPUT_FILE):
        logger.error("Input file not found.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    final_data = []
    logger.info(f"Formatting {len(data)} tests...")

    for entry in data:
        # Get raw fields
        name = entry.get('test_name', 'Unknown')
        raw_desc = entry.get('description', '')
        url = entry.get('url', '')
        
        # Clean the text
        clean_desc = clean_mayo_text(raw_desc)
        
        # Skip if empty
        if len(clean_desc) < 20:
            continue

        # ---------------------------------------------------------
        #  BUILD THE EXACT STRUCTURE YOU REQUESTED
        # ---------------------------------------------------------
        processed_entry = {
            "entity_type": "test",             # Fixed tag
            "url": url,
            "source": "Mayo Clinic",
            "name": name,
            "text": clean_desc,
            # Create the special embedding string
            "embedding_context": f"Medical Test: {name}. Purpose: {clean_desc[:1000]}"
        }
        
        final_data.append(processed_entry)

    # Save to file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(final_data)} standardized tests to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()