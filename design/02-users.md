# User Personas

## Persona 1: AI Engineer

**Name:** Dr. Priya Sharma  
**Age:** 34  
**Background:** PhD in NLP, 6 years building and shipping LLM-based products. Previously at a mid-size AI startup.

### Goals
- Improve model accuracy and reduce undesirable behaviors
- Quickly identify regression causes after deployments
- Build evidence for why a model change is needed
- Ship improvements without breaking production

### Daily Workflow
- Start day by checking latest Continuous Evaluation report
- Review open Findings tagged to her team's models
- Drill into specific inference traces to validate findings
- Draft Recommendations and submit for review
- Launch A/B experiments comparing candidate vs. current configs
- Compare experiment results and decide whether to promote

### Pain Points
- Hard to isolate whether a degraded metric is from a model change or data drift
- Manual correlation of inference logs, metrics, and config changes is slow
- No single place to see the full lifecycle of a model behavior issue
- Reviews get blocked waiting for context that should be auto-attached

### Most Frequently Used Modules
- Evidence Engine
- Continuous Evaluation
- Recommendation Engine
- Experimentation Framework

### Information They Care About
- Per-model accuracy/precision/recall trends
- Finding severity and affected scope
- Experiment result comparisons (side-by-side)
- Lineage from inference trace → finding → recommendation → experiment

### Typical Decisions
- Whether a finding is actionable or noise
- Which recommendation to turn into an experiment
- Whether experiment results justify a config change
- Whether to approve or reject a peer's recommendation

---

## Persona 2: ML Engineer

**Name:** Marcus Chen  
**Age:** 29  
**Background:** MS in Machine Learning, 4 years in MLOps. Currently on the ML platform team.

### Goals
- Maintain evaluation pipelines and ensure they produce reliable signals
- Extend the Evidence Engine with new metric types
- Tune continuous evaluation thresholds to reduce false positives
- Ensure artifact lineage is complete and correct

### Daily Workflow
- Review evaluation pipeline runs and check for failures or data issues
- Inspect new Evidence artifacts to verify metric computation
- Adjust evaluation parameters based on feedback from AI Engineers
- Coordinate with Platform Engineer on data pipeline health
- Write evaluation specifications for new model capabilities

### Pain Points
- Evaluation pipelines depend on upstream data quality — no visibility into data issues
- False-positive findings erode team trust in the system
- Adding a new metric requires touching multiple systems
- Hard to reproduce a finding locally without the exact artifact context

### Most Frequently Used Modules
- Continuous Evaluation
- Evidence Engine
- Learning Ledger
- Capability Registry

### Information They Care About
- Evaluation pipeline health and latency
- Metric computation logs and intermediate results
- Evaluation threshold configurations
- Artifact schema versions and backward compatibility

### Typical Decisions
- Whether to adjust evaluation thresholds up or down
- Whether a metric anomaly is a real signal or pipeline artifact
- Which new capabilities need evaluation specs
- Whether to archive or reclassify stale findings

---

## Persona 3: Platform Engineer

**Name:** Anika Patel  
**Age:** 38  
**Background:** 12 years in infrastructure and backend engineering. Previously at a cloud observability startup.

### Goals
- Keep the runtime and Learning Ledger available and performant
- Ensure the Capability Registry is accurate and up to date
- Integrate new engines without breaking existing ones
- Maintain operational runbooks for incident response

### Daily Workflow
- Monitor system health via the Operations Control Plane
- Review capability registration requests from development teams
- Investigate any runtime anomalies surfaced by the platform
- Perform configuration snapshot reviews
- Triage any Learning Ledger write-path issues

### Pain Points
- No unified view of cross-capability dependency health
- Configuration drift between environments is hard to detect
- Incident root cause analysis requires stitching data from multiple views
- Adding a new engine requires manual capability registration

### Most Frequently Used Modules
- Operations Control Plane
- Configuration Management
- Runtime
- Capability Registry

### Information They Care About
- Service health metrics (latency, error rates, throughput)
- Configuration snapshot diffs
- Resource utilization per capability
- Lineage integrity (orphaned artifacts are a red flag)

### Typical Decisions
- Whether to scale a capability horizontally
- Whether a config change needs rollback
- Which capabilities to deprecate or archive
- Whether to accept or reject a new capability registration

---

## Persona 4: DevOps Engineer

**Name:** Jamie Ortiz  
**Age:** 31  
**Background:** 8 years in DevOps/SRE. Focused on automation, CI/CD, and incident response.

### Goals
- Automate every repeatable operational task
- Reduce manual intervention in configuration rollouts
- Ensure rollback plans exist before any change goes live
- Build monitoring and alerting for platform health

### Daily Workflow
- Check automated job execution results (snapshots, triggers, reports)
- Review pending Configuration Snapshots awaiting approval
- Update automation schedules and triggers
- Investigate any automation job failures
- Participate in recommendation approval workflow as a reviewer

### Pain Points
- Automation jobs depend on capabilities that may change their APIs
- Difficult to simulate a config change before approving it
- Rollback procedures are well-defined but manual
- Notification fatigue from too many finding types

### Most Frequently Used Modules
- Automation
- Configuration Management
- Operations Control Plane
- Artifact Explorer

### Information They Care About
- Automation job success/failure rates
- Config snapshot version history
- Trigger conditions and scheduled job timing
- Artifact size and storage utilization

### Typical Decisions
- Whether to approve or reject an automated config change
- Whether a failed automation job needs a runbook update
- Whether to add/remove/modify a trigger schedule
- Whether to archive old snapshots

---

## Persona 5: Engineering Manager

**Name:** Dr. Kenji Watanabe  
**Age:** 42  
**Background:** PhD in CS, 15 years leading AI/ML teams at enterprise companies.

### Goals
- Maintain audit trail for all production changes
- Ensure team is working on highest-impact improvements
- Track experimentation velocity and outcomes
- Demonstrate governance compliance to stakeholders

### Daily Workflow
- Review governance dashboard for pending approvals
- Check team metrics: findings reviewed, experiments launched, config changes
- Inspect audit log for any unapproved changes or policy violations
- Review weekly Continuous Evaluation summary report
- Approve high-impact recommendation or config changes

### Pain Points
- Hard to get a summary view of team activity without aggregating data
- Compliance audits require manual artifact trail reconstruction
- Cannot easily see which recommendations led to real improvements
- Needs to justify team resources with data on platform impact

### Most Frequently Used Modules
- Governance
- Operations Control Plane
- Configuration Management
- Artifact Explorer

### Information They Care About
- Audit trail completeness
- Recommendation → experiment → change conversion rate
- Mean time to respond to findings
- Team member contribution to reviews and approvals
- Governance policy compliance percentage

### Typical Decisions
- Whether to approve or defer a config change
- Whether to allocate resources to a new capability or improve an existing one
- Whether a governance policy needs updating
- Whether team velocity is acceptable for the current quarter
