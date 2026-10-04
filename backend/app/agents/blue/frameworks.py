"""Framework references for classifying blue incidents and prevention steps.

These mappings are analyst judgments for the access-control scenario, not
authoritative labels. ATT&CK describes adversary behavior; CWE and OWASP
describe the weakness; NIST CSF 2.0 categories place each response or
prevention step. NIST SP 800-61 Rev. 3 organizes incident response around the
CSF 2.0 Functions, so reports follow Detect, Respond, Recover, and Identify.
"""

SOURCES = {
    "NIST SP 800-61r3": "https://csrc.nist.gov/pubs/sp/800/61/r3/final",
    "NIST CSF 2.0": "https://www.nist.gov/cyberframework",
    "MITRE ATT&CK": "https://attack.mitre.org/",
    "CWE-639": "https://cwe.mitre.org/data/definitions/639.html",
    "OWASP API1:2023": "https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/",
}

CSF_CATEGORIES = {
    "DE.CM": "Continuous Monitoring",
    "DE.AE": "Adverse Event Analysis",
    "RS.MA": "Incident Management",
    "RS.AN": "Incident Analysis",
    "RS.CO": "Incident Response Reporting and Communication",
    "RS.MI": "Incident Mitigation",
    "RC.RP": "Incident Recovery Plan Execution",
    "ID.RA": "Risk Assessment",
    "ID.IM": "Improvement",
    "PR.AA": "Identity Management, Authentication, and Access Control",
    "PR.DS": "Data Security",
    "PR.PS": "Platform Security",
}

ATTACK_EXPLOIT_APP = {
    "framework": "MITRE ATT&CK",
    "id": "T1190",
    "name": "Exploit Public-Facing Application",
    "tactic": "Initial Access",
    "url": "https://attack.mitre.org/techniques/T1190/",
    "rationale": "A web route returned private records the caller was not authorized to read.",
}
ATTACK_VALID_ACCOUNTS = {
    "framework": "MITRE ATT&CK",
    "id": "T1078",
    "name": "Valid Accounts",
    "tactic": "Initial Access",
    "url": "https://attack.mitre.org/techniques/T1078/",
    "rationale": "The reads used a legitimately issued lab session, so login alone did not stop them.",
}
WEAKNESSES = (
    {
        "framework": "CWE",
        "id": "CWE-639",
        "name": "Authorization Bypass Through User-Controlled Key",
        "url": SOURCES["CWE-639"],
        "rationale": "The order ID in the request selected the record without an ownership check.",
    },
    {
        "framework": "OWASP API Security Top 10",
        "id": "API1:2023",
        "name": "Broken Object Level Authorization",
        "url": SOURCES["OWASP API1:2023"],
        "rationale": "Object-level authorization was missing on a route that takes a record ID.",
    },
)

# Each step names its CSF category and the references it draws on. `when` limits
# a step to incidents with that trait.
PREVENTION = (
    {"id": "enforce-ownership", "csf": "PR.AA", "kind": "code",
     "refs": ["OWASP API1:2023", "CWE-639"],
     "text": "Check that the session's user owns the record on every route that takes a record ID. Deny by default and reuse the same check as the protected control route."},
    {"id": "require-session", "csf": "PR.AA", "kind": "code", "when": "anonymous",
     "refs": ["OWASP API1:2023"],
     "text": "Require an authenticated session on every private-record route before looking up the record."},
    {"id": "regression-tests", "csf": "PR.PS", "kind": "test",
     "refs": ["OWASP API1:2023"],
     "text": "Keep the access checks as permanent tests: unauthorized user denied, each owner allowed, no session denied, protected route unchanged. Run them on every change."},
    {"id": "variant-review", "csf": "ID.RA", "kind": "review",
     "refs": ["CWE-639"],
     "text": "Review every other route that loads a record by ID for the same missing ownership check."},
    {"id": "keep-detection", "csf": "DE.CM", "kind": "detect",
     "refs": ["NIST SP 800-61r3"],
     "text": "Keep the cross-user read alert enabled after the fix. A new alert on the patched version means the fix failed."},
    {"id": "detect-probing", "csf": "DE.AE", "kind": "detect",
     "refs": ["NIST SP 800-61r3"],
     "text": "Add an alert for one session making repeated denied reads of other users' records, which can show someone searching for exposed IDs."},
    {"id": "containment-runbook", "csf": "RS.MI", "kind": "process", "when": "contained",
     "refs": ["NIST SP 800-61r3"],
     "text": "Keep session revocation as a fast containment step, and record that it does not fix the flaw. Shorter session lifetimes limit how long a stolen or misused session works."},
    {"id": "unpredictable-ids", "csf": "PR.DS", "kind": "code",
     "refs": ["OWASP API1:2023"],
     "text": "Use random, unpredictable record IDs as an extra layer. This makes guessing harder but never replaces the ownership check."},
    {"id": "lessons-learned", "csf": "ID.IM", "kind": "process",
     "refs": ["NIST SP 800-61r3", "NIST CSF 2.0"],
     "text": "Record what was detected, how long each step took, and what changed, then update tests, detections, and this runbook."},
)
