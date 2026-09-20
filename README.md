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

This creates `data\processed\contacts.sqlite3`, `data\output\contacts.csv`, and, when `pandas` and `openpyxl` are installed, `data\output\contacts.xlsx`. Re-running on the same MBOX is safe: emails, evidence, and applications are keyed by message and never duplicated, and review statuses are preserved.

You (the mailbox owner) are never stored as a contact. Your address is detected from Gmail's `Delivered-To` header and from the sender of messages labelled Sent. Add other addresses you use, such as a school address, to `OWNER_EMAILS` in `.env` or pass `--owner you@example.com`.

Useful commands:

```powershell
python -m contact_miner ingest --mbox data\raw\mail.mbox
python -m contact_miner analyze --mbox data\raw\mail.mbox --limit 100
python -m contact_miner deduplicate
python -m contact_miner export --output data\output
python -m contact_miner enrich --mbox data\raw\mail.mbox --model gpt-4o-mini
```

`analyze` is a dry run: it prints relevance signals and the contacts that would be stored, without writing anything. Start with `--limit 500` on a large mailbox to check the results before a full run.

The command defaults to `--no-llm` behavior. `enrich` is the only command that calls an LLM; it requires `OPENAI_API_KEY`, processes only relevant messages, and sends a bounded snippet. Configure `OPENAI_API_KEY` and `LLM_MODEL` in `.env` only when you intentionally enable that step. The provider validates the structured JSON response, uses a no-guess prompt, and returns no contact without an email.

## Streamlit review UI

```powershell
streamlit run app\streamlit_app.py
```

The UI shows:

- totals
- search, plus filters for company, contact type, review status, and minimum confidence
- contact details with the confidence explanation
- applications and evidence for each contact
- review statuses (approved, rejected, review, or do-not-contact) and notes, both saved to the database

`contact_status` is included in the CSV/Excel exports. Raw email bodies are not displayed.

## Data model and confidence

SQLite contains `emails`, `contacts`, `applications`, and `evidence`, with foreign keys and indexes for common filters. Email address is the primary identity key and is normalized case-insensitively. Evidence and application provenance remain attached when repeated observations are merged. Names alone never merge contacts.

Confidence is explainable. Each of these adds to the score with a stated reason: the source (sender signature, header, or body), an available name, an explicit company or role, domain support, and a professional domain. A company taken from a signature is reported as "explicitly stated"; one derived only from the email domain is reported as "inferred". Low-confidence rows remain available for review rather than being silently discarded. Generic `hr@`, `recruitment@`, `recrutement@`, `careers@`, and `jobs@` addresses are retained as `hr` contacts. The following are filtered out:

- automated senders (no-reply, notifications, alerts, bounces, newsletters, marketing)
- bulk mail (`List-Unsubscribe` / `Precedence: bulk`)
- recipient lists of mass mailings

A signature is attributed only to the message's sender. A name found in the body is attached to an address only when it sits directly before that address.

Each `applications` row records the company, the position (from the subject), internship vs job, the year, and a status inferred from the message: `applied` (your sent mail), `received`, `interview`, `offer`, or `rejected`.

## Tests

```powershell
python -m pytest
python -m compileall -q src app tests
```

Tests use synthetic messages only. If Excel dependencies are absent, CSV and SQLite still work.

## Extending the project

Add another LLM provider by implementing the `LLMProvider` protocol in `src/contact_miner/llm_extractor.py`. Outlook exports, Gmail API support, embeddings, and external company enrichment are deliberately outside the first local-first version.
