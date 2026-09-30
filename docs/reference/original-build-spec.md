# Agentic AI Cyber Range
## Codex Build Specification

# 1. Objective

Implement a contained Agentic AI Cyber Range capable of coordinating specialized security agents against an intentionally vulnerable application.

The system must support the following MVP lifecycle:

```text
Create Assessment
↓
Reconnaissance
↓
Security Testing
↓
Candidate Finding
↓
Independent Verification
↓
Defensive Analysis
↓
Remediation
↓
Retesting
↓
Benchmarking
```

Do not implement unnecessary production infrastructure.

Prioritize:

1. modularity
2. clear interfaces
3. deterministic testing
4. safe execution boundaries
5. observable agent behavior
6. demo reliability

---

# 2. Security Boundary

This project is a contained cyber range.

Agent security tools MUST operate only against targets explicitly registered as part of the local lab environment.

Do not provide arbitrary Internet targets to agents.

Implement target validation before security tools execute.

Example allowed targets:

```text
vulnerable-web
vulnerable-api
localhost:<approved-port>
127.0.0.1:<approved-port>
```

Maintain an allowlist of range targets.

Reject targets outside the configured cyber range.

---

# 3. Repository Structure

Use approximately:

```text
agentic-cyber-range/
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── assessments/
│   │   │   ├── agents/
│   │   │   ├── findings/
│   │   │   ├── timeline/
│   │   │   ├── telemetry/
│   │   │   └── remediation/
│   │   ├── pages/
│   │   ├── types/
│   │   └── utils/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── agents/
│   │   │   ├── base.py
│   │   │   ├── commander.py
│   │   │   ├── recon.py
│   │   │   ├── authorization.py
│   │   │   ├── injection.py
│   │   │   ├── verifier.py
│   │   │   ├── log_analysis.py
│   │   │   └── remediation.py
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── tools/
│   │   ├── orchestration/
│   │   ├── repositories/
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
│
├── cyber_range/
│   ├── vulnerable_web/
│   ├── vulnerable_api/
│   ├── seed/
│   ├── ground_truth/
│   └── docker-compose.yml
│
├── shared/
│   └── schemas/
│
├── scripts/
├── docs/
├── tests/
├── .env.example
├── docker-compose.yml
├── CODEX_BUILD_SPEC.md
└── README.md
```

Do not create unnecessary abstractions.

---

# 4. Core Domain Models

Implement the following minimum concepts.

## AssessmentRun

```text
id
target_id
mode
status
started_at
completed_at
current_phase
metrics
```

Statuses:

```text
created
running
paused
completed
failed
```

---

## AgentExecution

```text
id
assessment_id
agent_name
task
status
started_at
completed_at
summary
```

Statuses:

```text
queued
running
completed
failed
```

---

## Endpoint

```text
id
assessment_id
method
path
parameters
authentication_required
discovered_by
```

---

## Finding

```text
id
assessment_id
agent_name
category
title
description
target
severity
confidence
status
evidence
created_at
```

Finding statuses:

```text
candidate
testing
verified
rejected
remediated
retest_failed
retest_passed
```

---

## Verification

```text
id
finding_id
verifier
result
confidence
evidence
notes
```

Results:

```text
verified
rejected
inconclusive
```

---

## SecurityEvent

```text
id
assessment_id
timestamp
source
event_type
request
response
severity
metadata
```

---

## Remediation

```text
id
finding_id
root_cause
file_path
original_code
proposed_code
explanation
status
```

---

# 5. Agent Interface

Every agent must implement a common abstraction.

Conceptually:

```python
class BaseAgent:
    name: str
    description: str

    async def execute(self, context: AgentContext) -> AgentResult:
        ...
```

AgentContext should include only required information.

Example:

```text
assessment_id
target
shared_state
task
available_tools
```

AgentResult:

```text
status
summary
findings
discoveries
events
recommended_actions
```

Agent implementations should not directly update UI state.

They return structured results.

The orchestration layer handles persistence and events.

---

# 6. Tool Interface

Tools must be separate from agents.

Example:

```python
class Tool:
    name: str

    async def execute(self, request):
        ...
```

Potential MVP tools:

```text
http_request
endpoint_probe
authenticated_request
log_reader
source_reader
retest_request
```

Every tool must:

- validate inputs
- enforce target allowlisting
- return structured results
- return useful errors
- log execution

---

# 7. Orchestration

Implement an AssessmentOrchestrator.

Responsibilities:

1. initialize run
2. launch Commander
3. execute Recon
4. store discovered attack surface
5. launch appropriate specialist agents
6. collect candidate findings
7. send candidates to Verifier
8. store accepted/rejected findings
9. launch defensive analysis
10. prepare remediation
11. support retest
12. calculate metrics
13. complete assessment

Do not put all orchestration inside API routes.

---

# 8. Shared Security State

Create a centralized assessment state.

Example structure:

```json
{
  "assessment_id": "...",
  "target": {},
  "roles": [],
  "endpoints": [],
  "credentials": [],
  "candidate_findings": [],
  "verified_findings": [],
  "rejected_findings": [],
  "security_events": [],
  "attack_paths": []
}
```

Agents should read from this state through a defined service.

Avoid unrestricted mutation.

Prefer service methods such as:

```text
register_endpoint()
register_finding()
verify_finding()
register_event()
register_attack_relationship()
```

---

# 9. Commander Agent

Mission:

Coordinate the security assessment.

Inputs:

- target metadata
- discovered surface
- current findings
- agent availability

Responsibilities:

- decide what testing should occur next
- dispatch specialists
- identify missing coverage
- determine when assessment should stop

For the MVP, Commander decisions may use a combination of deterministic rules and LLM reasoning.

Do not make every orchestration decision dependent on an LLM.

---

# 10. Recon Agent

Mission:

Map the target application.

Identify:

- routes
- APIs
- forms
- parameters
- authentication surfaces
- role-specific functionality

Output structured Endpoint records.

Success condition:

The system contains enough attack-surface information to dispatch specialist agents.

---

# 11. Authorization Agent

Mission:

Identify access-control problems in the contained target.

Focus on known lab workflows.

Analyze differences between authorized and unauthorized requests.

Potential findings:

```text
IDOR
BOLA
privilege boundary failure
missing ownership validation
role access failure
```

Every discovered issue must be returned as a candidate Finding.

---

# 12. Injection Agent

Mission:

Identify unsafe server-side input handling within the lab.

Focus initially on the intentionally seeded challenge surfaces.

Return structured evidence.

Do not report a vulnerability solely from speculative model output.

---

# 13. Verification Agent

Mission:

Independently test candidate findings.

The verifier should receive:

- finding
- evidence
- relevant endpoint
- target context

It should NOT simply accept the original agent's conclusion.

Outputs:

```text
verified
rejected
inconclusive
```

Include:

- confidence
- evidence
- explanation

---

# 14. Blue-Team Agent

MVP agent:

**LogAnalysisAgent**

Mission:

Analyze telemetry generated during the assessment.

Inputs:

- HTTP logs
- application logs
- verified findings
- timestamps

Output:

- suspicious events
- classifications
- evidence
- associated finding

Where possible associate:

```text
agent action
↓
request
↓
application behavior
↓
log event
↓
blue-team detection
```

---

# 15. Remediation Agent

Mission:

Explain the vulnerability and propose a code-level remediation.

Inputs:

- verified finding
- relevant source
- evidence

Outputs:

```text
root cause
affected file
affected code
proposed replacement
explanation
recommended regression test
```

Do not automatically modify source code during the initial MVP.

First generate a patch proposal.

Automated application becomes a later task.

---

# 16. Retesting

Implement deterministic retesting when possible.

Store:

```text
original_result
patched_result
expected_result
actual_result
success
```

UI should clearly display:

```text
Before Patch
VULNERABLE

After Patch
PROTECTED
```

---

# 17. Ground Truth

Maintain seeded vulnerability information separately from agent-visible state.

Example:

```json
[
  {
    "id": "GT-001",
    "category": "broken_access_control",
    "endpoint": "/api/orders/{id}",
    "severity": "high"
  }
]
```

Do not expose ground truth to the red-team agents.

Ground truth is used only for evaluation.

---

# 18. Metrics Service

Implement:

```text
true_positives
false_positives
false_negatives
precision
recall
verification_accuracy
mean_discovery_time
remediation_success_rate
```

Definitions:

```text
precision = true positives / all reported positives

recall = true positives / seeded vulnerabilities
```

Handle zero denominators safely.

---

# 19. API

Implement approximately:

## Health

```text
GET /api/health
```

---

## Targets

```text
GET /api/targets
```

Returns registered cyber-range targets.

---

## Create Assessment

```text
POST /api/assessments
```

Request:

```json
{
  "target_id": "demo-app",
  "mode": "autonomous"
}
```

---

## Assessment Details

```text
GET /api/assessments/{id}
```

---

## Start Assessment

```text
POST /api/assessments/{id}/start
```

---

## Findings

```text
GET /api/assessments/{id}/findings
```

---

## Agent Executions

```text
GET /api/assessments/{id}/agents
```

---

## Timeline

```text
GET /api/assessments/{id}/events
```

---

## Telemetry

```text
GET /api/assessments/{id}/telemetry
```

---

## Remediation

```text
GET /api/findings/{finding_id}/remediation
```

```text
POST /api/findings/{finding_id}/remediation/generate
```

---

## Retest

```text
POST /api/findings/{finding_id}/retest
```

---

## Metrics

```text
GET /api/assessments/{id}/metrics
```

---

# 20. Frontend Pages

## Dashboard

Show:

- recent assessments
- target
- current status
- summary metrics

---

## New Assessment

Select:

- target
- mode

Primary action:

**Launch Assessment**

---

## Live Assessment

Main demo screen.

Display:

### Header

```text
Target
Status
Elapsed Time
Verified Findings
```

### Agent Activity

Cards for:

```text
Commander
Recon
Authorization
Injection
Verifier
Log Analysis
Remediation
```

Statuses:

```text
Waiting
Running
Complete
Failed
```

### Timeline

Chronological events.

### Findings

Candidate and verified vulnerabilities.

### Coverage

Endpoints and vulnerability categories.

---

## Finding Detail

Display:

- title
- severity
- confidence
- target
- evidence
- discovery agent
- verification
- defensive telemetry
- remediation
- retest

---

## Results

Display:

- discovered
- verified
- rejected
- false positives
- recall
- precision
- remediation results

---

# 21. Real-Time Updates

Prefer Server-Sent Events for the hackathon unless bidirectional real-time communication becomes necessary.

Potential endpoint:

```text
GET /api/assessments/{id}/stream
```

Event types:

```text
assessment.started
agent.started
agent.completed
endpoint.discovered
finding.created
finding.verified
finding.rejected
security_event.created
remediation.generated
retest.completed
assessment.completed
```

Frontend should use these events to update the demo without refreshing.

---

# 22. Mock-First Development

Frontend development must not wait for the agent system.

Create fixtures for:

```text
assessment
agents
findings
timeline
telemetry
metrics
```

Similarly, the agent layer should be testable without the frontend.

---

# 23. Tests

Minimum tests:

## Backend

- health endpoint
- assessment creation
- invalid target rejection
- finding creation
- verification transitions
- metrics calculations

## Agents

Use known fixtures.

Test:

```text
Recon parses expected endpoints
Verifier rejects unsupported finding
Verifier accepts reproducible finding
```

## Security Boundary

Required tests:

```text
allowed target accepted
external target rejected
invalid hostname rejected
unapproved port rejected
```

## Integration

At least one full test:

```text
create assessment
→ run simulated assessment
→ create finding
→ verify
→ calculate results
```

---

# 24. Demo Mode

Implement an explicit demo configuration.

Example:

```text
DEMO_MODE=true
```

Demo mode may:

- use deterministic agent fixtures where necessary
- simulate timing between agent events
- guarantee known challenge availability
- prevent unstable external dependencies

Demo mode must still represent the real architecture.

It should not be a completely disconnected fake UI.

---

# 25. Logging

Use structured logging.

Log:

```text
assessment_id
agent
tool
event
duration
status
```

Do not log sensitive secrets unnecessarily.

---

# 26. Error Handling

Agent failure must not crash the entire assessment.

Record:

```text
agent_failed
```

Allow the orchestrator to:

- retry
- skip
- continue
- mark assessment partially completed

Frontend should display failures gracefully.

---

# 27. Environment Variables

Create `.env.example`.

Potential variables:

```text
LLM_PROVIDER=
LLM_API_KEY=
DATABASE_URL=
CYBER_RANGE_ALLOWED_HOSTS=
DEMO_MODE=
LOG_LEVEL=
```

Never commit actual secrets.

---

# 28. Docker

Root `docker-compose.yml` should launch:

```text
frontend
backend
vulnerable-web
vulnerable-api
database-if-required
```

Goal:

```bash
docker compose up --build
```

should start the complete demonstration environment.

---

# 29. Codex Working Rules

When implementing this repository:

1. Read this specification before making architectural changes.
2. Work on only the assigned task.
3. Do not rewrite unrelated modules.
4. Preserve existing interfaces unless the task explicitly changes them.
5. Add/update tests for implemented behavior.
6. Run relevant tests before declaring completion.
7. Report files changed.
8. Report tests executed.
9. Report unresolved issues.
10. Do not silently introduce dependencies.
11. Do not bypass cyber-range target restrictions.
12. Prefer simple implementations over speculative abstractions.

---

# 30. Exact First 10 Codex Tasks

## Task 1 — Repository Bootstrap

Create:

- frontend
- backend
- cyber_range
- tests
- documentation
- environment configuration

Acceptance:

```text
frontend starts
backend starts
GET /api/health succeeds
```

Do not implement agents yet.

---

## Task 2 — Core Domain Models

Implement:

- AssessmentRun
- AgentExecution
- Endpoint
- Finding
- Verification
- SecurityEvent
- Remediation

Add validation and tests.

---

## Task 3 — Target Registry and Security Boundary

Implement allowed targets.

Reject arbitrary destinations.

Acceptance:

```text
registered range target → allowed
internet target → rejected
unapproved local port → rejected
```

---

## Task 4 — Cyber Range MVP

Create the intentionally vulnerable demo application.

Seed the first known vulnerabilities.

Create:

- demo users
- role differences
- ground-truth metadata
- application logging

Do not expose ground truth through application routes.

---

## Task 5 — Assessment APIs

Implement:

```text
POST /assessments
GET /assessments/{id}
POST /assessments/{id}/start
```

Assessment may initially run a simulated orchestrator.

---

## Task 6 — Agent Framework + Recon

Implement:

- BaseAgent
- AgentContext
- AgentResult
- tool abstraction
- ReconAgent

Test against the local cyber range.

Acceptance:

Recon produces structured Endpoint records.

---

## Task 7 — Live Dashboard

Implement the primary frontend assessment view using mocked data first.

Show:

- assessment status
- agents
- timeline
- findings
- metrics placeholders

Then connect assessment API.

---

## Task 8 — First Security Specialist

Implement AuthorizationAgent.

Use the seeded access-control challenge.

Required lifecycle:

```text
Recon
→ Authorization Test
→ Candidate Finding
```

Do not implement additional specialists until this works.

---

## Task 9 — Verification

Implement VerificationAgent.

Required lifecycle:

```text
Candidate Finding
→ Independent Test
→ Verified / Rejected
```

Persist verification evidence.

Update dashboard in real time.

---

## Task 10 — Complete Golden Vertical Slice

Implement:

```text
Assessment Started
↓
Recon
↓
Authorization Agent
↓
Candidate Vulnerability
↓
Verifier
↓
Verified Finding
↓
Log Analysis
↓
Remediation Recommendation
↓
Retest
↓
Metrics
```

Acceptance:

The entire workflow can be demonstrated from the frontend without manually modifying application state.

DO NOT BEGIN MAJOR STRETCH FEATURES UNTIL TASK 10 IS RELIABLE.

---

# 31. Tasks After MVP

Once Task 10 works:

### Task 11
InjectionAgent

### Task 12
Improved blue-team telemetry

### Task 13
Attack graph

### Task 14
Automatic remediation application

### Task 15
AuthenticationAgent

### Task 16
API Security Agent

### Task 17
Business Logic Agent

### Task 18
Strategist Agent

### Task 19
Replay system

### Task 20
Benchmark dashboard

---

# 32. Definition of Implementation Complete

The implementation is hackathon-ready when:

```text
docker compose up
```

starts the system and a user can:

1. open the dashboard
2. select the demo range
3. launch an assessment
4. watch agents operate
5. see an actual seeded vulnerability discovered
6. see it independently verified
7. inspect associated defensive telemetry
8. view its root cause
9. view remediation
10. trigger a retest
11. see the fixed behavior
12. view evaluation metrics

Anything beyond this is a stretch goal.