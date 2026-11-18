---
title: ToolHoo Support Chatbot
emoji: 🛠️
colorFrom: orange
colorTo: red
sdk: streamlit
sdk_version: 1.53.0
app_file: app.py
pinned: false
short_description: RAG support chatbot answering product questions from a live catalog API
---

# Technical Support Chatbot (RAG)

Answers customer questions from *your* documentation instead of the model's
general knowledge. LangChain wires Google Gemini (LLM + embeddings) to a
local Chroma vector store. Streamlit is the internal UI.

```
config.py    settings, prompt, chunking parameters
gemini.py    LangChain Gemini chat model + embeddings
ingest.py    docs/ -> chunks -> LangChain Chroma
rag.py       retriever + LCEL answer chain (no UI dependency)
app.py       Streamlit chat interface
docs/        your source documents (.md, .txt, .pdf, .xlsx, .xlsm, .csv)
```

## Setup

```bash
python -m pip install -r requirements.txt
```

Get a free API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey),
then copy `.env.example` to `.env` and set `GEMINI_API_KEY`.

## Index your documents

Drop files into `docs/`, then:

```bash
python ingest.py
```

Re-running only embeds chunks whose text changed, and removes chunks left over
from edited files. Use `python ingest.py --reset` to rebuild from scratch —
required if you ever change `EMBED_MODEL` or `EMBED_DIM`, since old vectors
become incomparable with new ones.

## Run

```bash
python -m streamlit run app.py
```

**After every `python ingest.py`, press "Reload index" in the sidebar.** The
running app holds its vector index in memory; a browser refresh will not pick up
new chunks, and the sidebar count is misleading here — it reads fresh metadata
and will show the new total while searches still hit the old index. Restarting
the app works too.

## Website widget (floating bubble)

Streamlit is the internal tool. For your public site, run the API and drop one
script tag into any page:

```bash
python -m uvicorn server:app --port 8000
```

```html
<script src="http://localhost:8000/widget.js" defer
        data-api="http://localhost:8000"
        data-accent="#c2410c"
        data-title="ToolHoo Support"
        data-subtitle="Specs, pricing and stock"
        data-suggestions="Price of the 2.5 mm drill?|What point angle?"></script>
```

Open <http://localhost:8000/> for a demo product page with the widget on it.

- Bubble bottom-right; panel is 384×580, full-screen below 480px wide.
- Answers stream in token by token; sources collapse under each reply.
- Conversation survives page navigation via `sessionStorage`.
- Styles live in a **shadow root**, so your site's CSS cannot leak in and the
  widget's cannot leak out.
- Model output is escaped before a small fixed markdown subset is applied —
  never injected as raw HTML.

Before going live: set `ALLOWED_ORIGINS` in `.env` to your real domains, put
the API behind HTTPS, and add rate limiting — the endpoint spends API quota on
every request, so an open one is a bill waiting to happen.

Or test the retrieval loop in the terminal without the UI:

```bash
python rag.py
```

## How it works

1. **Ingest** — prose is split with LangChain `RecursiveCharacterTextSplitter`
   (~1200 characters, 200 overlap). Spreadsheets stay one labelled record per
   row (see below).
2. **Embed** — `GoogleGenerativeAIEmbeddings` (`gemini-embedding-001`, 768
   dimensions, `RETRIEVAL_DOCUMENT`) writes batches of 32 into `chroma_db/`
   under a content-hash id.
3. **Retrieve** — LangChain Chroma embeds the question as `RETRIEVAL_QUERY` and
   matches by cosine similarity. Chunks scoring below `MIN_SIMILARITY` (0.25)
   are dropped, so an off-topic question retrieves nothing rather than nonsense.
4. **Answer** — an LCEL chain (`ChatPromptTemplate` → `ChatGoogleGenerativeAI`)
   injects numbered context. The system prompt restricts the model to that
   context and requires `[n]` citations; with no context it is told to say it
   doesn't know.

## Spreadsheets and CSV

Excel and CSV files are indexed **one row per chunk**, rendered as labelled
records rather than raw grids:

```
[sheet Worksheet · row 2]
*SKU: D1GP125010
*Product Name: Twist Drill 1.00mm DIN 338 HSS GOLD-P Coated (YG-1)
*Regular Price: 242
```

Repeating the column name in every record is what makes a row retrievable — a
bare `242,34,YG-1` chunk gives a question nothing to match against. Row numbers
are the real Excel row numbers, so a cited row can be found in the file. Rows
larger than `RECORD_MAX` are split at field boundaries, with the row tag and
first field repeated on each piece.

Import templates commonly park **dropdown vocabularies** in trailing columns.
They parse as data but describe the template, not your rows, and they bury real
content in noise. Restrict a file to its real columns in `SPREADSHEET_COLUMNS`
(`config.py`) using a 1-based inclusive range.

Excel's `~$name.xlsx` lock files are skipped automatically. Columns listed in
`DROP_HEADERS` (image paths, banners, SEO fields) are skipped everywhere — the
model cannot show an image in a text answer, so those values only dilute the
embedding.

## Gemini specifics worth knowing

- **`gemini-embedding-001`, not `-2`.** Passing a list to v2 returns a single
  aggregated vector for the whole list, which would silently corrupt batch
  ingestion. v1 returns one vector per input and supports `task_type`.
- **`task_type` is not decoration.** Documents and queries are embedded into
  deliberately different spaces; tagging them correctly improves retrieval.
- **Free daily quota is per model, and newer is smaller.** `gemini-3.5-flash`
  allows only 20 requests/day. Older Flash-Lite models are far more generous,
  which is why `gemini-3.1-flash-lite` is the default. See your real numbers at
  [aistudio.google.com/rate-limit](https://aistudio.google.com/rate-limit).
- **Model names churn, and listing does not imply access.** Confirmed working
  on this key: `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite`,
  `gemini-flash-lite-latest`, `gemma-4-26b-a4b-it`. Retired for new users:
  `gemini-2.5-flash`, `gemini-2.5-flash-lite`.
- **Rate limits.** `ChatGoogleGenerativeAI` retries transient 429s
  (`max_retries=8`). A large first ingest may still pause; re-run
  `python ingest.py` and it resumes from chunks already stored.
- **After switching to LangChain**, run `python ingest.py` again so prose is
  re-chunked with `RecursiveCharacterTextSplitter`. Use `--reset` if retrieval
  looks wrong — required if you change `EMBED_MODEL` or `EMBED_DIM`.
- **Free-tier data is used to improve Google's products.** If your `docs/`
  contain confidential customer or product material, use a paid key or a
  provider whose terms you have reviewed.

## Tuning

| Symptom | Change |
| --- | --- |
| Answers miss details spread across a doc | raise `TOP_K` in `config.py` |
| Answers pull in irrelevant text | raise `MIN_SIMILARITY` in `rag.py` |
| Chunks cut mid-procedure | raise `CHUNK_SIZE` / `CHUNK_OVERLAP` |
| Answers too terse or too chatty | edit `SYSTEM_PROMPT` in `config.py` |
| Need higher answer quality | set a larger `CHAT_MODEL` in `.env` |

## Production notes

- `chroma_db/` is a local directory. For multiple app instances, switch to a
  Chroma server or a hosted store (Pinecone, pgvector) — only `get_collection()`
  changes.
- Streamlit session state is per-browser-tab and lost on refresh. Persist
  conversations to a database if you need transcripts.
- Log questions where `retrieve()` returns nothing — that list is the best guide
  to which docs to write next.


## Local MySQL through Laravel

The chatbot now defaults to `DATA_SOURCE=mysql_api`. It reads products from
`TOOLHOO_API_URL=http://127.0.0.1:8001/api/chatbot` on each question.
The database is Laravel's configured local `toolmasterpk` database; it does not
sync automatically with the live website database. PDF ingestion is not needed
for product questions in this mode. Existing Chroma data is retained.

Start Laravel in one terminal:

```powershell
cd D:\xampp\htdocs\ToolHooApi\TooHooBackEnd
D:\xampp\php\php.exe artisan serve --host=127.0.0.1 --port=8001
```

Start the chatbot in another terminal:

```powershell
cd D:\Chatbot
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Local-only endpoints: `GET /api/chatbot/catalog` and `GET /api/chatbot/products`.
Product search supports category_id, brand_id, sku, q, in_stock, min_price,
max_price and exact filters such as `filters[0][field_id]=66` and
`filters[0][value]=3.00 mm`. Page size is capped at 30.
The catalog supplies category field IDs and allowed values to LangChain's
structured-output search chain. API queries are read-only.
