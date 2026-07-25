# User Workflows

---

## Workflow 1: Daily Operator Workflow

**Goal** — Quickly understand platform health, review new findings, address pending recommendations, and continue monitoring.

**Entry point** — Operator Dashboard (default landing page after login)

### Flow Diagram

```
┌─────────────┐
│  Dashboard   │
│  (Landing)   │
└──────┬──────┘
       │
       ▼
┌──────────────┐
│ Check Health  │
│  Panel        │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Review New   │
│  Findings    │  ───> [[WF2]]
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Review Pending│
│ Recommends   │  ───> [[WF3]]
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Check Running│
│ Experiments  │  ───> [[WF5]]
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Pending Config│
│  Approvals   │  ───> [[WF6]]
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Exit State   │
│ (Done/Idle)   │
└──────────────┘
```

### Steps

1. User opens the Operator Dashboard.
2. System displays health panel: green/yellow/red status per capability.
3. User scans Findings summary widget — checks count of new, critical, and acknowledged findings.
4. User clicks a high-severity finding to drill in (→ Workflow 2).
5. User returns to Dashboard and checks Recommendations widget — sees count of pending, approved, rejected.
6. User opens a pending recommendation to review (→ Workflow 3).
7. User checks Experiments widget — sees active experiments and their status.
8. User opens an experiment if results are ready (→ Workflow 5).
9. User checks Configuration widget — sees pending snapshot approvals.
10. User opens approval queue (→ Workflow 6).
11. User exits or continues monitoring.

### Exit State
Dashboard refreshed. All new items acknowledged, or user is aware of backlog.

### Success Criteria
- Operator visited every widget with pending items
- At least one finding reviewed or recommendation actioned
- Dashboard reflects current state after session

---

## Workflow 2: Reviewing Findings

**Goal** — Understand a finding, validate its evidence, and decide what to do about it.

**Entry point** — Findings list (from Dashboard widget or Findings workspace)

### Flow Diagram

```
┌─────────────┐
│ Finding List │
└──────┬──────┘
       │ click
       ▼
┌──────────────────┐
│ Finding Detail    │
│  ┌──────────────┐│
│  │ Evidence      ││
│  │  Timeline     ││
│  └──────────────┘│
│  ┌──────────────┐│
│  │ Lineage Graph ││
│  └──────────────┘│
└──────┬───────────┘
       │
       ├──── Acknowledge ────> Finding moves to "Acknowledged"
       │
       ├──── Dismiss ────────> Prompt reason → Finding moves to "Dismissed"
       │
       └──── Escalate ───────> Creates Recommendation → [[WF3]]
```

### Steps

1. User opens the Findings workspace.
2. System lists findings grouped by severity (Critical, High, Medium, Low).
3. User applies filters: time range, capability, model, status.
4. User clicks a finding to open its detail view.
5. System displays finding summary: title, severity, affected capability, timestamp, lineage.
6. System renders the Evidence Timeline — a chronological view of observations that triggered this finding.
7. System renders the Lineage Graph — upstream artifacts (inference traces, metrics) and downstream (recommendations already created).
8. User inspects individual evidence items — expands metric charts or raw data.
9. User takes one of three actions:
   - **Acknowledge**: marks finding as seen, no further action needed right now.
   - **Dismiss**: requires a reason (e.g., "false positive", "expected behavior").
   - **Escalate**: automatically creates a draft Recommendation pre-populated with this finding's lineage.
10. System records the action as a new artifact linked to the finding.

### Exit State
Finding has a decision artifact attached (Acknowledged, Dismissed, or Escalated → Recommendation).

### Success Criteria
- User can trace from finding to its root evidence in ≤ 3 clicks
- Action is recorded as an artifact with lineage back to the finding
- If escalated, a draft Recommendation exists

---

## Workflow 3: Reviewing Recommendations

**Goal** — Evaluate a proposed change, understand its evidence basis, and approve, reject, or request modifications.

**Entry point** — Recommendations workspace or pending widget on Dashboard

### Flow Diagram

```
┌─────────────────┐
│ Recommendations │
│  List           │
└──────┬──────────┘
       │ click
       ▼
┌──────────────────────┐
│ Recommendation Detail │
│  ┌──────────────────┐│
│  │ Evidence Summary ││
│  └──────────────────┘│
│  ┌──────────────────┐│
│  │ Proposed Change  ││
│  └──────────────────┘│
│  ┌──────────────────┐│
│  │ Risk Assessment  ││
│  └──────────────────┘│
└──────┬───────────────┘
       │
       ├── Approve ──────> Status: Approved → ready for experiment [WF4]
       │
       ├── Reject ───────> Prompt reason → Status: Rejected
       │
       └── Request Changes ──> Feedback → Status: Draft (author revises)
```

### Steps

1. User opens the Recommendations workspace.
2. System lists recommendations with status filter: Pending, Approved, Rejected, Draft.
3. User clicks a Pending recommendation.
4. System displays recommendation detail in three panels:
   - **Evidence Summary**: key findings and data that support this recommendation
   - **Proposed Change**: what config or behavior change is suggested
   - **Risk Assessment**: impact scope, rollback plan, confidence score
5. User expands the lineage graph to see the full chain from original inference.
6. User reviews the before/after comparison if available.
7. User takes action:
   - **Approve**: recommendation moves to Approved and is eligible for experiment design.
   - **Reject**: user provides reason; recommendation moves to Rejected.
   - **Request Changes**: user provides feedback; recommendation goes back to Draft.
8. System creates an artifact recording the decision and links it to the recommendation.

### Exit State
Recommendation has a decision artifact. If approved, it's available for experiment definition.

### Success Criteria
- User can trace recommendation → evidence → root inference in ≤ 4 clicks
- Risk assessment is visible without navigating away
- Decision is recorded with reason (for reject) or feedback (for changes)

---

## Workflow 4: Launching Experiments

**Goal** — Define an experiment to test a recommendation, configure variants, and launch it.

**Entry point** — Recommendation Detail → "Design Experiment" button

### Flow Diagram

```
┌────────────────────┐
│ Recommendation     │
│  Detail            │
└──────┬─────────────┘
       │ "Design Experiment"
       ▼
┌────────────────────┐
│ Experiment Designer │
│  ┌────────────────┐│
│  │ Baseline Config││
│  │ Candidate Config││
│  └────────────────┘│
│  ┌────────────────┐│
│  │ Metrics        ││
│  │ Duration       ││
│  └────────────────┘│
│  ┌────────────────┐│
│  │ Review & Launch││
│  └────────────────┘│
└──────┬─────────────┘
       │
       ▼
┌──────────────┐
│ Experiment   │
│  Running     │
└──────────────┘
```

### Steps

1. From an approved Recommendation, user clicks "Design Experiment".
2. System creates a draft ExperimentDefinition pre-populated with the recommendation's proposed change as the candidate.
3. System shows current configuration as the baseline variant.
4. User reviews and adjusts experiment parameters:
   - Variant configuration (baseline vs candidate)
   - Target metrics to measure
   - Duration and traffic allocation
   - Rollback conditions
5. User adds any additional variants if needed (e.g., A/B/C).
6. User clicks "Review" — system validates the experiment definition.
7. System displays a summary: variants, metrics, duration, traffic, rollback plan.
8. User clicks "Launch" — system starts the experiment.
9. System updates Recommendation status to "In Experiment".
10. System creates an ExperimentRun artifact with lineage to the ExperimentDefinition and Recommendation.

### Exit State
Experiment is running. Recommendation status updated. Artifact lineage established.

### Success Criteria
- Experiment definition is complete with baseline, candidate, metrics, duration
- Lineage: ExperimentDefinition → Recommendation → Finding → Evidence
- User can launch in ≤ 10 steps

---

## Workflow 5: Comparing Experiment Results

**Goal** — Analyze experiment results and decide whether to promote the candidate.

**Entry point** — Experiment workspace or Dashboard experiment widget

### Flow Diagram

```
┌──────────────────┐
│  Experiment      │
│  (Running/Done)  │
└──────┬───────────┘
       │ click
       ▼
┌──────────────────────┐
│ Experiment Detail     │
│  ┌──────────────────┐│
│  │ Metric Comparison││
│  │  (Side-by-Side)  ││
│  └──────────────────┘│
│  ┌──────────────────┐│
│  │ Statistical      ││
│  │  Significance    ││
│  └──────────────────┘│
│  ┌──────────────────┐│
│  │ Timeline         ││
│  │  (Metric over    ││
│  │   experiment     ││
│  │   duration)      ││
│  └──────────────────┘│
└──────┬───────────────┘
       │
       ├── Winner Declared ──> Creates DecisionCandidate → [[WF6]]
       │
       └── No Winner ───────> Recommendation needs revision
```

### Steps

1. User opens the Experiments workspace and selects a completed experiment.
2. System displays the experiment summary: duration, variants, metrics tracked.
3. System shows the side-by-side metric comparison table:
   - Each metric with baseline value, candidate value, delta, and p-value.
4. System highlights statistically significant changes (p < 0.05).
5. User inspects the metric timeline chart — sees metric behavior over the experiment duration for each variant.
6. User drills into any metric to see the raw evidence data.
7. User decides:
   - **Declare Winner**: system creates a DecisionCandidate artifact with lineage to the experiment.
   - **No Winner**: system flags recommendation as needing revision; user adds notes.
8. If declaring winner, user selects which variant wins and provides rationale.
9. System records the decision as an artifact.

### Exit State
Experiment has a conclusion artifact. If a winner was declared, a DecisionCandidate exists ready for config change approval.

### Success Criteria
- User can compare metrics side-by-side with statistical significance
- Decision is recorded as an artifact with lineage
- Winner (or no-winner) is clearly documented

---

## Workflow 6: Approving Configuration Changes

**Goal** — Review a proposed config change, compare diffs, assess risk, and approve or reject.

**Entry point** — Configuration workspace → Pending Snapshots, or Dashboard approval widget

### Flow Diagram

```
┌──────────────────┐
│ Pending Config   │
│  Snapshots       │
└──────┬───────────┘
       │ click
       ▼
┌──────────────────────┐
│ Config Snapshot       │
│  Detail              │
│  ┌──────────────────┐│
│  │ Diff View        ││
│  │ (Before / After) ││
│  └──────────────────┘│
│  ┌──────────────────┐│
│  │ Decision Lineage ││
│  │ (Recommendation, ││
│  │  Experiment)     ││
│  └──────────────────┘│
│  ┌──────────────────┐│
│  │ Rollback Plan    ││
│  └──────────────────┘│
└──────┬───────────────┘
       │
       ├── Approve ───────> Config applied → New Snapshot active
       │
       └── Reject ───────> Config stays at current snapshot
```

### Steps

1. User opens the Configuration workspace → Pending Snapshots tab.
2. System lists configuration snapshots awaiting approval with metadata: author, created, linked recommendation/experiment.
3. User clicks a pending snapshot.
4. System displays a diff view showing what changed (side-by-side or unified diff).
5. System shows the decision lineage: Recommendation → Experiment → DecisionCandidate → this Snapshot.
6. User inspects the rollback plan (pre-defined reversal steps).
7. User reviews the change impact summary (affected capabilities, models, endpoints).
8. User approves or rejects:
   - **Approve**: system applies the snapshot as the active configuration. Creates a ConfigurationApplied artifact.
   - **Reject**: system marks snapshot as rejected. Creates a ConfigurationRejected artifact with user's reason.
9. System notifies the recommendation author of the outcome.
10. System creates an audit artifact recording the approval/rejection.

### Exit State
Snapshot is either Applied (new active config) or Rejected (current config unchanged). Audit trail updated.

### Success Criteria
- Diff is clearly visible and understandable
- Full lineage from config change back to original finding is accessible
- Approval/rejection is recorded with reasoning

---

## Workflow 7: Investigating Platform Health

**Goal** — Diagnose a platform issue using artifact lineage, health metrics, and operational data.

**Entry point** — Operations workspace or capability health indicator

### Flow Diagram

```
┌──────────────────┐
│  Operations      │
│  Control Plane   │
└──────┬───────────┘
       │ click capability
       ▼
┌──────────────────────┐
│ Capability Detail     │
│  ┌──────────────────┐│
│  │ Health Metrics   ││
│  │  (Latency,       ││
│  │   Error Rate,    ││
│  │   Throughput)    ││
│  └──────────────────┘│
│  ┌──────────────────┐│
│  │ Recent Artifacts ││
│  └──────────────────┘│
│  ┌──────────────────┐│
│  │ Related Findings ││
│  └──────────────────┘│
└──────┬───────────────┘
       │
       ▼
┌──────────────────┐
│  Investigate     │
│  (Drill via      │
│   Lineage)       │
└──────────────────┘
```

### Steps

1. User opens the Operations workspace.
2. System displays capability health summary: list of all registered capabilities with green/yellow/red status.
3. User clicks a capability (e.g., "Evidence Engine") to drill in.
4. System shows capability detail:
   - Health metrics panel (latency p50/p95/p99, error rate, throughput)
   - Recent artifacts panel (latest artifacts produced by this capability)
   - Related findings panel (open findings affecting this capability)
5. User notices elevated error rate — clicks a recent artifact to start lineage drill.
6. System shows the artifact's lineage graph — upstream dependencies and downstream consumers.
7. User navigates through the graph to identify root cause (e.g., upstream data source latency).
8. User takes action: creates a finding, opens a runbook, or escalates to team.

### Exit State
User has identified the root cause (or documented that investigation is ongoing).

### Success Criteria
- Health status is visible per capability from the top level
- User can drill from a health indicator → capability detail → artifact → lineage
- Root cause identification takes ≤ 5 navigations

---

## Workflow 8: Using the Artifact Explorer

**Goal** — Browse, search, and inspect artifacts across the entire platform.

**Entry point** — Artifact Explorer workspace (sidebar navigation)

### Flow Diagram

```
┌──────────────────┐
│ Artifact Explorer │
│  ┌──────────────┐│
│  │ Search Bar   ││
│  └──────────────┘│
│  ┌──────────────┐│
│  │ Filter Panel ││
│  │  Type        ││
│  │  Date Range  ││
│  │  Capability  ││
│  │  Status      ││
│  └──────────────┘│
│  ┌──────────────┐│
│  │ Results List ││
│  └──────────────┘│
└──────┬───────────┘
       │ click
       ▼
┌──────────────────────┐
│ Artifact Detail       │
│  ┌──────────────────┐│
│  │ Metadata         ││
│  │  (id, timestamp, ││
│  │   version, type) ││
│  └──────────────────┘│
│  ┌──────────────────┐│
│  │ Lineage Graph    ││
│  └──────────────────┘│
│  ┌──────────────────┐│
│  │ Raw Payload      ││
│  └──────────────────┘│
└──────┬───────────────┘
       │
       └── Navigate Lineage ──> Open Parent or Child artifact
```

### Steps

1. User opens the Artifact Explorer.
2. System shows recent artifacts with search bar and filter panel.
3. User searches by keyword, artifact ID, or filters by type/capability/date range.
4. System displays a paginated list of matching artifacts with summary info.
5. User clicks an artifact to view its detail page.
6. System shows:
   - **Metadata**: id, type, version, timestamp, capability, lineage reference.
   - **Lineage Graph**: interactive DAG showing parents and children.
   - **Raw Payload**: the full artifact data (JSON with formatting).
7. User can click a parent or child node in the lineage graph to navigate to that artifact.
8. User can export the artifact raw payload or share a direct link.

### Exit State
User has found the artifact they needed and either exported it or navigated to a related artifact.

### Success Criteria
- Any artifact is discoverable via search or filter in ≤ 3 actions
- Lineage graph is interactive and navigable
- Raw payload is accessible without leaving the page

---

## Workflow 9: Reviewing Continuous Evaluation Reports

**Goal** — Understand the system's self-assessment results over a time window.

**Entry point** — Continuous Evaluation workspace

### Flow Diagram

```
┌──────────────────┐
│  CE Dashboard    │
│  ┌──────────────┐│
│  │ Summary      ││
│  │  Scores      ││
│  └──────────────┘│
│  ┌──────────────┐│
│  │ Trend Chart  ││
│  └──────────────┘│
│  ┌──────────────┐│
│  │ Breakdown by ││
│  │  Capability  ││
│  └──────────────┘│
└──────┬───────────┘
       │ click score
       ▼
┌──────────────────┐
│  Evaluation      │
│  Detail          │
│  ┌──────────────┐│
│  │ Metrics      ││
│  └──────────────┘│
│  ┌──────────────┐│
│  │ Findings     ││
│  │  Generated   ││
│  └──────────────┘│
│  ┌──────────────┐│
│  │ Raw Report   ││
│  └──────────────┘│
└──────┬───────────┘
       │
       └── View Finding ──> [[WF2]]
```

### Steps

1. User opens the Continuous Evaluation workspace.
2. System displays the CE Dashboard:
   - Overall score for the current window
   - Trend chart (score over last N windows)
   - Breakdown table by capability (score + change vs prior window)
3. User scans for capabilities with declining scores.
4. User clicks a capability score to open evaluation detail.
5. System shows:
   - Full metrics for that capability
   - List of findings generated during this evaluation window
   - Link to the raw evaluation report artifact
6. User clicks a finding to review it (→ Workflow 2).
7. User can also compare two evaluation windows side-by-side.

### Exit State
User understands current evaluation state and has identified any areas needing attention.

### Success Criteria
- Score trend is immediately visible
- User can drill from a declining score → capability metrics → findings → evidence
- Side-by-side window comparison is available
