# Stitch Prompt: OwnLearn

> Generate the knowledge base and continuous learning module for Own Platform.
>
> **Context:** This prompt assumes `stitch/00-master-context.md` as the foundation. Read it first.
>
> **Priority:** Sprint 2

---

## Design Goal

Generate OwnLearn — the knowledge base where documents are uploaded, managed, and indexed for RAG (Retrieval-Augmented Generation).

OwnLearn is a document management interface for AI engineers. It should feel like a simplified document library: upload, browse, search, inspect chunk details, and monitor indexing status.

---

## Screen Information

| Property | Value |
|---|---|
| **Recipe** | B — Collection + Inspector |
| **Route** | `/knowledge` |
| **Primary users** | AI Engineer, ML Engineer |
| **Primary goal** | Upload documents, manage knowledge base, view chunk details, check indexing status |

---

## Layout Structure

```
┌──────────────────────────────────────────────────────────────┐
│  Header: Knowledge Base · [Upload] [Filter by type ▼]        │
├──────────────────────────────────────────────────────────────┤
│  Index Status Banner (conditional)                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ⚙ Indexing in progress · 3 of 12 documents indexed    │ │
│  └────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│  Document List                                              │
│  ┌──────────┬────────┬───────────┬──────────┬───────────┐  │
│  │ Name     │ Type   │ Chunks    │ Status   │ Uploaded  │  │
│  ├──────────┼────────┼───────────┼──────────┼───────────┤  │
│  │ spec.pdf │ PDF    │ 24        │ Indexed  │ 2h ago    │  │
│  │ notes.md │ MD     │ 8         │ Indexed  │ 1d ago    │  │
│  │ manual   │ TXT    │ 15        │ Pending  │ 30m ago   │  │
│  │ ...      │ ...    │ ...       │ ...      │ ...       │  │
│  └──────────┴────────┴───────────┴──────────┴───────────┘  │
├──────────────────────────────────────────────────────────────┤
│  Upload Modal (overlay)                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Drop files here or click to browse                    │ │
│  │  Supported: PDF, TXT, MD, CSV                          │ │
│  │  ┌────────────────────────────────────────────────┐   │ │
│  │  │ spec.pdf · 2.4 MB · [Uploading ████████░░ 80%] │   │ │
│  │  └────────────────────────────────────────────────┘   │ │
│  │  [Cancel]  [Upload]                                    │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Chunk Detail (inline or side panel)

Clicking a document row reveals chunk details:

```
┌──────────────────────────────────────────────────────────────┐
│  Document: spec.pdf · 24 chunks · Indexed                    │
├──────────────────────────────────────────────────────────────┤
│  Chunk list (scrollable)                                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ #1 "The platform supports continuous evaluation..."    │ │
│  │ Characters: 512 · Tokens: 128 · Position: 0–512      │ │
│  │ [View in context]                                       │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │ #2 "Evaluation windows are configurable..."            │ │
│  │ Characters: 480 · Tokens: 120 · Position: 512–992     │ │
│  │ [View in context]                                       │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## Sections Detail

### Document List
- **Content:** Table with name, type badge (PDF/TXT/MD), chunk count, indexing status badge (Indexed/Pending/Error), upload timestamp.
- **Sort:** By name, upload date, status, type.
- **Filter:** By file type, indexing status.
- **Search:** By document name.
- **Interaction:** Click row → expand/reveal chunk details inline. Click "X" → delete document (with confirmation).

### Upload Flow
1. Click "Upload" button in header.
2. Upload modal opens: drag-and-drop zone or file browser.
3. Supported types: PDF, TXT, MD, CSV. Max file size indicated.
4. Upload progress shown per file (progress bar + filename).
5. After upload: document appears in list with "Pending" status (indexing in background).
6. Error: "Upload failed. [Retry]" with reason.

### Index Status Banner
- **Visible when:** Any document has "Pending" or "Indexing" status.
- **Content:** "Indexing in progress · X of Y documents indexed."
- **Dismissible:** Yes (collapses to subtle indicator).

### Chunk Details
- **Access:** Click row or "View chunks" action on a document.
- **Content:** List of chunks with preview text (first 100 chars), character/token count, position in document.
- **Interaction:** "View in context" → show surrounding chunks. Copy chunk text.

---

## States

### Loading
- Table skeleton with 5 rows.
- Upload button skeleton (icon placeholder).

### Empty (no documents)
- "No documents uploaded. Upload PDF, TXT, or MD files to populate the knowledge base."
- Upload CTA button prominent.
- Supported types list shown as reference.

### Error (load failed)
- "Failed to load documents. [Retry]"
- Inline within table area.

### Error (upload failed)
- Upload modal: "Upload failed. [Retry]"
- Specific file shows error badge.

### Indexing in progress
- Banner visible: "Indexing in progress."
- Document row shows "Pending" status with subtle spinner.

### Indexing complete
- "All documents indexed." banner auto-dismisses after 5s.
- Document row shows "Indexed" badge with checkmark.

---

## Visual Design Constraints

- **Table:** Clean, minimal. Type badges: colored by file type (PDF=red, TXT=blue, MD=green).
- **Status badges:** Indexed = green, Pending = yellow with spinner, Error = red.
- **Upload zone:** Dashed border. Accent color on drag hover. File type icons.
- **Typography:** Document name: 14px medium. Metadata: 12px secondary. Chunk preview: 13px mono for text.
- **Spacing:** Table rows: 48px height. Upload modal: 24px padding. Chunk items: 12px vertical gap.

---

## Deliverables

Generate:
1. **Knowledge Base default** — populated document list with status badges
2. **Knowledge Base empty** — no documents, upload CTA
3. **Upload modal** — drag-and-drop zone with file progress
4. **Chunk detail** — expanded document with chunk list
5. **Indexing in progress** — banner visible, pending badges
6. **Dark mode variants** for each
