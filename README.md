# Internship Contact Miner

A local-first Python application that extracts professional contacts from historical internship and job-application emails exported as Gmail Takeout MBOX. It keeps the raw mailbox local, filters messages deterministically before any optional LLM step, stores normalized contacts in SQLite, and exports reviewable CSV/Excel files.

## Privacy model

No mailbox is uploaded automatically. Raw MBOX files belong in `data/raw/`, which is ignored by Git. The deterministic pipeline never calls an external service. Optional OpenAI enrichment sends only a bounded snippet from messages already classified as relevant; it does not send the MBOX, attachments, or the full mailbox. Do not put API keys or private exports in source control.

## Windows setup

```powershell
cd C:\Users\bacha\mail-miner
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[app,llm,dev]"
Copy-Item .env.example .env
New-Item -ItemType Directory -Force data\raw, data\processed, data\output
```

In Gmail, use Google Takeout, select Mail, export the archive, and place the extracted MBOX at `data\raw\mail.mbox`. The reader uses Python's standard `mailbox` and `email` libraries and skips malformed individual messages.

## Run the deterministic pipeline

```powershell
python -m contact_miner run-all --mbox data\raw\mail.mbox --no-llm
```

This creates `data\processed\contacts.sqlite3`, `data\output\contacts.csv`, and, when `pandas` and `openpyxl` are installed, `data\output\contacts.xlsx`.

Useful commands:

```powershell
python -m contact_miner ingest --mbox data\raw\mail.mbox
python -m contact_miner analyze --mbox data\raw\mail.mbox --limit 100
python -m contact_miner deduplicate
python -m contact_miner export --output data\output
```

The command defaults to `--no-llm` behavior. LLM provider plumbing is available in `llm_extractor.py` for an explicit future enrichment command; configure `OPENAI_API_KEY` and `LLM_MODEL` in `.env` only when you intentionally enable that step. The provider validates the structured JSON response, uses a no-guess prompt, and returns no contact without an email.

## Streamlit review UI

```powershell
streamlit run app\streamlit_app.py
```

The UI shows totals, search/filter controls, contact details, evidence, applications, and persisted review statuses: approved, rejected, review, or do-not-contact. Raw email bodies are not displayed by default.

## Data model and confidence

SQLite contains `emails`, `contacts`, `applications`, and `evidence`, with foreign keys and indexes for common filters. Email address is the primary identity key and is normalized case-insensitively. Evidence and application provenance remain attached when repeated observations are merged. Names alone never merge contacts.

Confidence is explainable: signature/header source, available name, explicit company/role, domain support, and professional-domain signals each contribute. Low-confidence rows remain available for review rather than being silently discarded. Generic `hr@`, `recruitment@`, `careers@`, and `jobs@` addresses are retained; automated notification/newsletter addresses are filtered.

## Tests

```powershell
python -m pytest
python -m compileall -q src app tests
```

Tests use synthetic messages only. If Excel dependencies are absent, CSV and SQLite still work.

## Extending the project

Add another LLM provider by implementing the `LLMProvider` protocol in `src/contact_miner/llm_extractor.py`. Outlook exports, Gmail API support, embeddings, and external company enrichment are deliberately outside the first local-first version.
