# ADR 0012: Evidence System

**Decision:** Replace flat `resources[]` with a structured `EvidenceBundle` model for AI responses.

**Why:** Professional AI requires transparency into what knowledge was used, how it was retrieved, and how confident the system is. The old `ResourceItem` (type + title + snippet) was too flat to support confidence labels, retrieval method badges, developer-mode debugging, or the Evidence Drawer UX.

**Architecture:**

```
Assistant Response
    ↓
EvidenceBundle
    ├── answer_mode
    └── EvidenceItem[]
         ├── id, title, source_type
         ├── chunk (text used), chunk_index, total_chunks
         ├── confidence_label (high/medium/low)
         ├── retrieval_method (hybrid/vector/bm25/web/memory)
         ├── url, document_id
         ├── metadata (for arbitrary source-specific fields)
         └── developer fields (raw_score, reranker_score, latency, model)
```

**Key differences from `ResourceItem`:**

| Axis | Old `ResourceItem` | New `EvidenceItem` |
|------|-------------------|-------------------|
| Identity | type + title | UUID `id` |
| Confidence | none | `confidence_label: enum` → "High Confidence" / "Strong Match" / "Low Confidence" |
| Retrieval | implicit | `retrieval_method: enum` → badge shown in UI |
| Source context | none | `chunk_index / total_chunks` |
| Debugging | none | `raw_score`, `reranker_score`, `embedding_model` — hidden from public, shown in developer mode |
| Answer mode | embedded in response | `EvidenceBundle.answer_mode` |

**SSE streaming design:**

```
answer_token
    ↓
...
    ↓
evidence (arrives after full answer)
    ↓
[DONE]
```

Evidence arrives as its own SSE event (`type: "evidence"`) so it doesn't clutter token streaming. The frontend attaches it to the assistant message after receipt. Backward-compat `type: "resources"` event is still emitted.

**UI components:**

- `EvidenceBar` — collapsed "Sources (N)" bar below answer text; expandable list showing title, confidence label, and retrieval badge per evidence item
- `EvidenceDrawer` — right-side slide-over panel showing full chunk text, confidence, retrieval method, document ID, and developer scores (behind toggle)
- Highlight support — clicking an evidence item in the bar opens the drawer with the chunk displayed; users see exactly what text the model used

**Developer mode:**

Developer-specific fields (`raw_score`, `reranker_score`, `latency`, `embedding_model`) are excluded from the public SSE serialization. They appear only in an expandable "Developer Details" section within the Evidence Drawer, gated behind intentional toggle.

**Alternatives considered:**

1. *Inline citation markers in the answer text* — rejected because it clutters the reading experience and doesn't scale to multi-source answers
2. *Footer-only citations* — rejected because it doesn't support per-item confidence or drawer-based exploration
3. *Numeric confidence scores in public UI* — rejected; text labels ("High Confidence") are more interpretable than raw floats

**Consequences:**

- Frontend must handle two SSE events (`evidence` + `resources`) during migration; `resources` can be removed in a future release
- `EvidenceItem`'s `metadata` dict allows forward-compatible extension without model changes
- The Evidence Drawer UI pattern sets the stage for future "Show Retrieval Details" developer tools
- Backward compatibility maintained: old `resources` event still emitted, `ResourceItem` model kept
