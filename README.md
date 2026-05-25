# ISAAC

Standalone Windows desktop app that watches a folder for incoming study materials — PDFs, handwritten notes, screenshots, voice memos — and automatically generates structured study outputs: Anki flashcards, concept summaries, and mock exam questions. Includes a background advisor that finds cross-course connections and a RAG chat for semantic queries across all stored content.

## Problem

Processing lecture materials into study-ready formats (flashcards, summaries, exam prep) is manual and repetitive. Each course, each week: read slides, write cards, connect concepts. StudyMind automates the full pipeline from dropping a file to having exportable study materials.

## Processing Pipeline

```
File dropped into watch_folder/
  -> Detect file type
  -> Route to extraction agent (OCR, PDF parse, Whisper, etc.)
  -> Extract clean text/markdown
  -> Match to configured course via exam planner
  -> LLM synthesizes: summary + flashcards + exam questions + memory hooks
  -> Export: Anki CSV, Markdown summaries, exam prep sheets
  -> Store extracted text in SQLite for RAG queries
```

## Pipeline Stages

### 1. Folder Watcher

`watchdog` observer monitors `watch_folder/`. On new file event:

1. Wait until file size stabilizes (prevents processing during copy/download).
2. Determine file type by extension.
3. Dispatch to appropriate processor.

### 2. Routing and Extraction

| File Type | Processor | Method |
|---|---|---|
| `.png`, `.jpg`, `.jpeg` | Handwriting Agent | LLM Vision API — extracts text from handwritten notes |
| `.png`, `.jpg` (diagrams) | Diagram Agent | LLM Vision API — interprets charts, graphs, mind-maps |
| `.pdf` | PDF Agent | PyMuPDF text extraction; scanned pages (no text layer) fall back to LLM Vision OCR |
| `.docx` | Word Agent | python-docx — text, tables, embedded content |
| `.mp3`, `.wav`, `.m4a` | Voice Agent | faster-whisper (local) or OpenAI Whisper API |

Each processor returns:

```python
class ProcessedContent(BaseModel):
    source_file: str
    content_type: Literal["handwriting", "diagram", "pdf", "word", "voice"]
    extracted_text: str
    metadata: dict              # page count, duration, dimensions, etc.
    timestamp: datetime
```

### 3. Course Matching

Exam planner compares extracted text against courses configured in `config.yaml`:

- Course name keywords
- Topic keywords per course
- Fuzzy string matching for flexibility

```python
class CourseMatch(BaseModel):
    course_name: str
    confidence: float           # 0.0 - 1.0
    matched_topics: list[str]
```

### 4. LLM Synthesis

For each matched course, the LLM generates:

```python
class StudyOutput(BaseModel):
    summary: str                        # Markdown concept summary
    flashcards: list[Flashcard]
    exam_questions: list[ExamQuestion]
    memory_hooks: list[str]             # Eselsbruecken / mnemonics

class Flashcard(BaseModel):
    question: str
    answer: str
    tags: list[str]                     # course, topic, difficulty

class ExamQuestion(BaseModel):
    question: str
    expected_answer: str
    difficulty: Literal["basic", "intermediate", "advanced"]
```

### 5. Export

| Output | Format | Location |
|---|---|---|
| Flashcards | CSV (standard Anki import: question, answer, tags) | `output/anki/` |
| Summaries | Markdown | `output/summaries/` |
| Exam prep | Markdown | `output/exam_prep/` |

### 6. SQLite Storage

All content stored in `study_vault.db` for retrieval:

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    source_file TEXT NOT NULL,
    content_type TEXT NOT NULL,
    course TEXT,
    extracted_text TEXT NOT NULL,
    embedding_keywords TEXT,         -- comma-separated search terms
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE study_outputs (
    id INTEGER PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    output_type TEXT NOT NULL,       -- 'summary', 'flashcard', 'exam_question'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE suggestions (
    id INTEGER PRIMARY KEY,
    source_doc_ids TEXT NOT NULL,    -- comma-separated document IDs
    connection TEXT NOT NULL,
    study_tip TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Proactive Advisor

Background thread, runs every N minutes (configurable):

1. Scans `documents` table for content across different courses.
2. LLM identifies conceptual connections (e.g., a statistics concept from one course that maps to a case study in another).
3. Generates actionable suggestion with explanation.
4. Delivers via Windows toast notification.
5. Stores in `suggestions` table for dashboard display.

```python
class Suggestion(BaseModel):
    source_docs: list[int]          # document IDs
    connection: str                 # what links them
    study_tip: str                  # actionable recommendation
    created_at: datetime
```

## RAG Chat

Query flow via dashboard or API:

1. User submits a question.
2. Query planner generates 3-4 semantic search keywords from the question.
3. Keywords search against `documents.extracted_text` and `documents.embedding_keywords`.
4. Top-K relevant chunks retrieved.
5. Cross-document synthesizer: chunks + original question -> LLM -> coherent markdown answer.

## UI

- **System tray:** Green brain icon. Menu: Open watch folder, Dashboard, Settings, Quit.
- **Global hotkeys:**
  - `Ctrl+Shift+X` — Screenshot primary display (for OneNote / slide capture).
  - `Ctrl+Shift+R` — Toggle quick voice memo recording.
- **Screen overlay:** Processing status bar (Detecting / Extracting / Matching / Synthesizing / Done).
- **Toast notifications:** Completion alerts + proactive advisor suggestions.

## Config (`config.yaml`)

```yaml
llm:
  provider: "gemini"                    # "gemini" or "claude"
  gemini_model: "gemini-2.5-flash"
  claude_model: "claude-sonnet-4-6-20250514"

whisper:
  mode: "local"
  local_model: "base"

paths:
  watch_folder: "./watch_folder"
  output_dir: "./output"

courses:
  - name: "BWL Grundlagen"
    exam_date: "2026-07-15"
    topics: ["Bilanzierung", "Kostenrechnung", "Marketing"]
  - name: "Statistik"
    exam_date: "2026-07-20"
    topics: ["Regression", "Hypothesentest", "Wahrscheinlichkeit"]

proactive:
  interval_minutes: 30
  enabled: true

database:
  path: "./study_vault.db"
```

## Dependencies

```
watchdog
faster-whisper
sounddevice
soundfile
pydantic>=2.0
google-genai
anthropic
PyMuPDF
python-docx
pystray
Pillow
keyboard
PyYAML
```

## Module Structure

```
study_agent/
  main.py                       # Entry: tray icon, watcher start, hotkey registration
  config.yaml
  core/
    watcher.py                  # watchdog folder observer
    router.py                   # file type -> processor dispatch
    processors/
      handwriting.py            # LLM Vision OCR for handwritten notes
      diagram.py                # LLM Vision for charts and graphs
      pdf_processor.py          # PyMuPDF + vision fallback
      word_processor.py         # python-docx extraction
      voice.py                  # Whisper transcription
    exam_planner.py             # course matching logic
    synthesizer.py              # LLM study material generation
    exporter.py                 # Anki CSV, Markdown, exam sheet writers
    db.py                       # SQLite operations
    rag.py                      # query planner + retrieval + synthesis
    proactive.py                # background advisor thread
  models/
    content.py                  # ProcessedContent, CourseMatch
    study_material.py           # StudyOutput, Flashcard, ExamQuestion, Suggestion
  capture/
    screenshot.py               # Ctrl+Shift+X screen capture
    quick_record.py             # Ctrl+Shift+R voice memo
  ui/
    tray.py                     # System tray icon + menu
    overlay.py                  # Processing status overlay
    notification.py             # Desktop toasts
  tests/
    test_processors.py
    test_synthesizer.py
    test_exporter.py
    test_rag.py
    test_proactive.py
```
