
# SymptoGuide AI 🩺

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/AhmedAbdelhamed01/symptoguide-ai/workflows/Python%20Package/badge.svg)](https://github.com/AhmedAbdelhamed01/symptoguide-ai/actions)

An intelligent **Retrieval-Augmented Generation (RAG)** medical assistant built with **Streamlit**, **LangChain**, **Ollama**, and **Chroma** vector database. SymptoGuide gathers your symptoms through a natural conversation, searches a curated medical knowledge base, and provides structured health guidance.

⚠️ **DISCLAIMER**: This is a **research and educational prototype**. It is **NOT** a medical diagnostic tool. Always consult qualified healthcare professionals.

## ✨ Key Features

### 🧠 Smart Conversational AI
- **Stage-based conversation flow**: Automatically detects whether to ask questions, gather details, or provide assessments
- **System/Human message separation**: Proper prompt engineering with Ollama's chat format for natural, non-repetitive responses
- **Symptom accumulation**: Tracks all symptoms across the entire conversation for accurate context
- **Anti-hallucination rules**: Strict prompt constraints prevent inventing symptoms or mentioning rare diseases

### 🔍 RAG Pipeline
- **Semantic vector search** using Chroma DB and HuggingFace BGE embeddings
- **Smart category search** with relevance scoring and filtering
- **Medical knowledge from NHS & Mayo Clinic** (conditions, symptoms, medicines, tests)

### 🖼️ Multi-Modal Input
- **Image analysis** via Ollama vision models (LLaVA, SVLM) — upload medical test images
- **PDF processing** — upload medical documents for in-context analysis
- **Text chat** — describe symptoms naturally in plain language

### 🚨 Safety
- **Emergency detection** with keyword and regex pattern matching
- **Compound emergency detection** — cross-turn analysis for dangerous symptom combinations (cardiac, stroke, sepsis, anaphylaxis)
- **Automatic escalation** to emergency guidance when critical patterns are detected

### 💬 Chat Management
- **Auto-save conversations** — every message is persisted automatically
- **Chat history sidebar** — browse, load, and delete past conversations
- **New Chat button** — start fresh consultations with one click

## 📁 Project Structure

```
symptoguide-ai/
├── src/
│   ├── app/                             # Main application
│   │   ├── app.py                      # Streamlit UI + conversation routing
│   │   ├── config.py                   # Prompts, models, system identity
│   │   ├── llm_utils.py               # LLM chain builders (build_chain, build_chat_chain)
│   │   ├── medical_logic.py           # Emergency detection, intent classification
│   │   ├── vector_db.py               # Chroma DB loading + smart search
│   │   ├── chat_manager.py            # Conversation persistence (auto-save)
│   │   └── symptom_accumulator.py     # Cross-turn compound emergency detection
│   ├── processing/                     # Data cleaning pipeline
│   │   ├── process_nhs_symptoms_final.py
│   │   ├── process_mayo_tests_final.py
│   │   ├── clean_nhs_medicines_final.py
│   │   ├── final_clean_nhs.py
│   │   └── create_master_dataset.py
│   ├── scrapers/                       # Web scraping modules
│   │   ├── scrape_nhs.py
│   │   ├── scrape_nhs_medicines.py
│   │   ├── scrape_nhs_symptoms_clean.py
│   │   └── scrape_symptoms.py
│   └── Vector_db/                      # Vector database builder
│       └── create_vector_db.py
├── tests/
│   └── test_basic.py                   # 54 unit tests
├── data/                               # Scraped & processed data (.gitignored)
├── chroma_db/                          # Persisted vector DB (.gitignored)
├── chat_history/                       # Saved conversations (.gitignored)
├── requirements.txt
├── setup.cfg
├── pyproject.toml
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Ollama** installed and running ([ollama.com](https://ollama.com))
- Required Ollama models:
  ```bash
  ollama pull llama3
  ollama pull llava          # optional: for image analysis
  ```

### Installation

```bash
# Clone
git clone https://github.com/AhmedAbdelhamed01/symptoguide-ai.git
cd symptoguide-ai

# Create virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run

```bash
streamlit run src/app/app.py
```

Opens at `http://localhost:8501`

## 🏗️ Architecture

```
                    ┌──────────────────────┐
                    │   Streamlit UI       │
                    │   (app.py)           │
                    └──────┬───────────────┘
                           │
              ┌────────────┼──────────────┐
              │            │              │
    ┌─────────▼──────┐ ┌──▼────────┐ ┌───▼──────────┐
    │Emergency Check │ │  Stage    │ │ Image/PDF    │
    │(medical_logic) │ │Detection  │ │ Analysis     │
    └────────────────┘ │(app.py)   │ │ (Ollama      │
                       └──┬────────┘ │  Vision)     │
                          │          └──────────────┘
              ┌───────────┼───────────┐
              │           │           │
    ┌─────────▼───┐ ┌────▼─────┐ ┌──▼──────────┐
    │  Symptom    │ │  RAG     │ │ build_chat  │
    │Accumulation │ │ Search   │ │ _chain()    │
    │(LLM call)   │ │(Chroma)  │ │(System+Human│
    └─────────────┘ └──────────┘ │ messages)   │
                                  └─────────────┘
```

### Conversation Flow

1. **Emergency Check** → Fast keyword/regex scan for life-threatening symptoms
2. **Message Classification** → `is_conversational()` decides if RAG is needed
3. **Symptom Accumulation** → LLM extracts all symptoms from full conversation history
4. **Stage Detection** → `determine_stage()` returns GREETING / GATHERING / READY / FOLLOWUP
5. **Selective RAG** → Vector search only when medical content is present
6. **Response Generation** → `build_chat_chain()` with System + Human message separation

### Technology Stack

| Component | Technology |
|-----------|------------|
| **UI** | Streamlit |
| **LLM** | Ollama (llama3) / HuggingFace |
| **Vision** | Ollama (llava / svlm) |
| **RAG** | LangChain |
| **Vector DB** | Chroma + HuggingFace BGE-large-en-v1.5 |
| **Testing** | pytest (54 tests) |

## 📊 Data Pipeline

```bash
# Step 1: Scrape medical data
python src/scrapers/scrape_nhs.py
python src/scrapers/scrape_nhs_medicines.py
python src/scrapers/scrape_nhs_symptoms_clean.py

# Step 2: Clean & process
python src/processing/process_nhs_symptoms_final.py
python src/processing/process_mayo_tests_final.py
python src/processing/clean_nhs_medicines_final.py
python src/processing/create_master_dataset.py

# Step 3: Build vector database
python src/Vector_db/create_vector_db.py
```

## 🧪 Testing

```bash
pytest -q                    # Quick run
pytest -v --tb=short         # Verbose with short tracebacks
```

**54 tests** covering: emergency detection, context request detection, symptom extraction, project structure validation.

## ⚙️ Configuration

Edit `src/app/config.py` to customize:

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_MODEL` | `llama3` | Ollama model for text generation |
| `EMBED_MODEL` | `BAAI/bge-large-en-v1.5` | HuggingFace embedding model |
| `DB_DIR` | `chroma_db/` | Vector database path |

For HuggingFace cloud models, set in `.env`:
```bash
HUGGINGFACEHUB_API_TOKEN=your_token_here
```

## 🔒 Security & Privacy

- `chroma_db/`, `data/`, `logs/`, `chat_history/` are `.gitignored`
- `.env` files are `.gitignored`
- No user data is transmitted externally when using Ollama locally

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 👤 Authors

- **Ahmed Abdelhamed** — Core development
- Developed as part of **CSAI 810: Topics in Artificial Intelligence** (Queen's University)

## 🙏 Acknowledgments

- [NHS](https://www.nhs.uk/) — Open medical data
- [Mayo Clinic](https://www.mayoclinic.org/) — Test/procedure information
- [LangChain](https://python.langchain.com/) — RAG orchestration
- [Chroma](https://www.trychroma.com/) — Vector database
- [Streamlit](https://docs.streamlit.io/) — UI framework
- [Ollama](https://ollama.com/) — Local LLM inference

## 📄 License

MIT License — see [LICENSE](LICENSE).

## ⚠️ Medical Disclaimer

This software is an **educational and research tool only**. It is **NOT** a substitute for professional medical advice, diagnosis, or treatment. **Always consult a qualified healthcare professional.**

---

**Last Updated**: February 2026  
**Version**: 2.0.0  
**Status**: Research/Educational Prototype
