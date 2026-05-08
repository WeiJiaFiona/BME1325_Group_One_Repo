import json
import os
import re
import logging

logger = logging.getLogger("SymptoGuide")

# -------- Settings (dynamic paths) --------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

INPUT_FILE = os.path.join(PROJECT_ROOT, "data", "raw", "nhs_symptoms", "nhs_symptoms_clean.json")
OUTPUT_FILE = os.path.join(PROJECT_ROOT, "data", "processed", "nhs_symptoms_tagged.json")

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

def clean_symptom_text(text):
    if not text: return ""

    # 1. Remove Image Junk (Alamy, Science Photo, huge URLs)
    lines = text.split('\n')
    clean_lines = []
    
    # We use a set to track the *previous* line to prevent duplicates
    last_line = ""
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line: continue
        
        # Skip Junk (Photos, Copyrights)
        if any(x in line for x in ["Alamy Stock Photo", "sciencephoto.com", "Crown copyright", "Page last reviewed"]):
            continue
        
        # Skip Tracking URLs
        if "http" in line and len(line) > 60:
            continue

        # 2. DEDUPLICATE: Skip if this line is exactly the same as the last one
        if line == last_line:
            continue
            
        clean_lines.append(line)
        last_line = line
    
    text = "\n".join(clean_lines)
    
    return text

def clean_title(name):
    # Fix titles like "Anosmia, see Lost or changed sense of smell"
    # We want just "Lost or changed sense of smell" or "Anosmia"
    # Usually the part AFTER "see" is the better common name
    if ", see " in name:
        parts = name.split(", see ")
        return parts[1] # Return the "Main" name
    return name

def main():
    logger.info(f"Processing: {INPUT_FILE}")
    
    if not os.path.exists(INPUT_FILE):
        logger.error("File not found.")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    final_data = []
    logger.info(f"Cleaning {len(data)} symptom guides...")

    for entry in data:
        raw_name = entry.get('name', 'Unknown')
        raw_text = entry.get('text', '')
        url = entry.get('url', '')

        # Clean Title
        clean_name = clean_title(raw_name)
        
        # Clean Text
        clean_text_content = clean_symptom_text(raw_text)

        # Skip empty
        if len(clean_text_content) < 50:
            continue

        # Create Standard Entry
        processed_entry = {
            "entity_type": "symptom_guide", # Specific tag for "Advice"
            "url": url,
            "source": "NHS",
            "name": clean_name,
            "text": clean_text_content,
            # Context: "Symptom Guide: Ankle Pain. Advice: Rest and raise..."
            "embedding_context": f"Symptom Guide: {clean_name}. Advice: {clean_text_content[:1000]}"
        }
        
        final_data.append(processed_entry)

    # Save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(final_data)} clean symptom guides to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()