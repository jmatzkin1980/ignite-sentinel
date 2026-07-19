# Traceability Matrix - [PROJECT_ID]

This matrix supports the Sentinel vNext golden thread. Source files remain authoritative; LanceDB memory is retrieval only.

## Edge Matrix

| Source | Source Type | Target | Target Type | Relation | Target Domain | Target Status |
| --- | --- | --- | --- | --- | --- | --- |
| `RAW-001` | raw_input | `REQ-001` | requirement | extracts | product | active |
| `RAW-001` | raw_input | `RU-001` | requirement_unit | decomposes_into | product | active |
| `RU-001` | requirement_unit | `REQ-001` | requirement | analyzes | product | active |
| `RAW-001` | raw_input | `RU-002` | requirement_unit | decomposes_into | product | active |
| `RU-002` | requirement_unit | `REQ-001` | requirement | analyzes | product | active |
| `RAW-001` | raw_input | `RU-003` | requirement_unit | decomposes_into | product | active |
| `RU-003` | requirement_unit | `REQ-001` | requirement | analyzes | product | active |
| `REQ-001` | requirement | `GAP-001` | gap_report | has_gap | product | open |
| `REQ-001` | requirement | `DEC-001` | decision_log | requires_decision | product | pending |
| `RAW-001` | raw_input | `SEED-001` | identity_seed_bank | produces_seed | product | active |
| `SEED-001` | identity_seed_bank | `REQ-001` | requirement | grounds | product | active |
| `RAW-001` | raw_input | `DISC-001` | discovery_log | analyzed_by | product | active |
| `DISC-001` | discovery_log | `GAP-001` | gap_report | identifies | product | open |
| `RAW-001` | raw_input | `DISC-002` | lens_review | scrutinized_by | product | active |
| `DISC-002` | lens_review | `GAP-001` | gap_report | raises | product | open |
| `SEED-001` | identity_seed_bank | `DISC-003` | knowledge_ledger | consolidated_by | product | active |
| `GAP-001` | gap_report | `DISC-003` | knowledge_ledger | consolidated_by | product | active |
| `DEC-001` | decision_log | `DISC-003` | knowledge_ledger | consolidated_by | product | active |
| `DISC-002` | lens_review | `DISC-003` | knowledge_ledger | informs | product | active |
| `DISC-003` | knowledge_ledger | `REQ-001` | requirement | grounds | product | active |
| `RAW-001` | raw_input | `DISC-004` | source_synthesis | summarized_by | product | active |
| `DISC-004` | source_synthesis | `REQ-001` | requirement | grounds | product | active |
| `CHG-001` | change | `DEC-002` | gap_resolution_report | produces | product | active |
| `CHG-001` | change | `GAP-001` | gap_report | resolves | product | open |
| `CHG-001` | change | `SEED-002` | identity_seed | confirms | quality | confirmed |
| `CHG-001` | change | `DEC-003` | decision | confirms | quality | confirmed |
| `CHG-001` | change | `REQ-002` | ears_requirement | normalizes | quality | confirmed |
| `DISC-002` | lens_review | `DISC-003` | knowledge_ledger | consolidated_by | product | active |
| `CHG-002` | change | `DEC-004` | gap_resolution_report | produces | product | active |
| `CHG-002` | change | `GAP-001` | gap_report | resolves | product | open |
| `CHG-002` | change | `SEED-002` | identity_seed | confirms | quality | confirmed |
| `CHG-002` | change | `DEC-003` | decision | confirms | quality | confirmed |
| `CHG-002` | change | `REQ-002` | ears_requirement | normalizes | quality | confirmed |
| `CHG-003` | change | `DEC-005` | gap_resolution_report | produces | product | active |
| `CHG-003` | change | `GAP-001` | gap_report | resolves | product | open |
| `CHG-003` | change | `SEED-002` | identity_seed | confirms | quality | confirmed |
| `CHG-003` | change | `DEC-003` | decision | confirms | quality | confirmed |
| `CHG-003` | change | `REQ-002` | ears_requirement | normalizes | quality | confirmed |
| `CHG-004` | change | `DEC-006` | gap_resolution_report | produces | product | active |
| `CHG-004` | change | `GAP-001` | gap_report | resolves | product | open |
| `CHG-004` | change | `SEED-002` | identity_seed | confirms | quality | confirmed |
| `CHG-004` | change | `DEC-003` | decision | confirms | quality | confirmed |
| `CHG-004` | change | `REQ-002` | ears_requirement | normalizes | quality | confirmed |
| `CHG-005` | change | `DEC-007` | gap_resolution_report | produces | product | active |
| `CHG-005` | change | `GAP-001` | gap_report | resolves | product | open |
| `CHG-005` | change | `SEED-002` | identity_seed | confirms | quality | confirmed |
| `CHG-005` | change | `DEC-003` | decision | confirms | quality | confirmed |
| `CHG-005` | change | `REQ-002` | ears_requirement | normalizes | quality | confirmed |
| `CHG-006` | change | `DEC-008` | gap_resolution_report | produces | product | active |
| `CHG-006` | change | `GAP-001` | gap_report | resolves | product | open |
| `CHG-006` | change | `SEED-002` | identity_seed | confirms | quality | confirmed |
| `CHG-006` | change | `DEC-003` | decision | confirms | quality | confirmed |
| `CHG-006` | change | `REQ-002` | ears_requirement | normalizes | quality | confirmed |
| `REQ-001` | requirement | `REQ-003` | project_brief | crystallizes | product | active |
| `SEED-001` | identity_seed_bank | `REQ-003` | project_brief | grounds | product | active |
| `DISC-002` | lens_review | `REQ-003` | project_brief | informs | product | active |
| `REQ-001` | requirement | `PRD-001` | prd | elaborates | product | active |
| `REQ-003` | project_brief | `PRD-001` | prd | elaborates | product | active |
| `PRD-001` | prd | `SPEC-001` | spec | agentizes | product | active |
| `PRD-001` | prd | `SPEC-U-001` | spec_unit | decomposes | product | evidence-backed |
| `SPEC-001` | spec | `SPEC-U-001` | spec_unit | indexes | product | evidence-backed |
| `SPEC-U-001` | spec_unit | `REQ-EARS-001` | ears_requirement | traces_to | product | confirmed |
| `PRD-001` | prd | `SPEC-U-002` | spec_unit | decomposes | product | evidence-backed |
| `SPEC-001` | spec | `SPEC-U-002` | spec_unit | indexes | product | evidence-backed |
| `SPEC-U-002` | spec_unit | `REQ-EARS-002` | ears_requirement | traces_to | product | confirmed |
| `PRD-001` | prd | `SPEC-U-003` | spec_unit | decomposes | product | evidence-backed |
| `SPEC-001` | spec | `SPEC-U-003` | spec_unit | indexes | product | evidence-backed |
| `SPEC-U-003` | spec_unit | `REQ-EARS-003` | ears_requirement | traces_to | product | confirmed |
| `PRD-001` | prd | `SPEC-U-004` | spec_unit | decomposes | product | evidence-backed |
| `SPEC-001` | spec | `SPEC-U-004` | spec_unit | indexes | product | evidence-backed |
| `SPEC-U-004` | spec_unit | `REQ-EARS-004` | ears_requirement | traces_to | product | confirmed |
| `PRD-001` | prd | `SPEC-U-005` | spec_unit | decomposes | product | evidence-backed |
| `SPEC-001` | spec | `SPEC-U-005` | spec_unit | indexes | product | evidence-backed |
| `SPEC-U-005` | spec_unit | `REQ-EARS-005` | ears_requirement | traces_to | product | confirmed |
| `PRD-001` | prd | `SPEC-U-006` | spec_unit | decomposes | product | evidence-backed |
| `SPEC-001` | spec | `SPEC-U-006` | spec_unit | indexes | product | evidence-backed |
| `SPEC-U-006` | spec_unit | `REQ-EARS-006` | ears_requirement | traces_to | product | confirmed |
| `SPEC-001` | spec | `EPIC-001` | epic | decomposes_to | product | active |
| `EPIC-001` | epic | `US-001` | user_story | contains | functional | active |
| `SPEC-001` | spec | `US-001` | user_story | decomposes_to | functional | active |
| `SPEC-U-001` | spec_unit | `US-001` | user_story | decomposes_to | functional | active |
| `US-001` | user_story | `AC-001` | acceptance_criteria | validated_by | quality | active |
| `EPIC-001` | epic | `US-002` | user_story | contains | functional | active |
| `SPEC-001` | spec | `US-002` | user_story | decomposes_to | functional | active |
| `SPEC-U-002` | spec_unit | `US-002` | user_story | decomposes_to | functional | active |
| `US-002` | user_story | `AC-002` | acceptance_criteria | validated_by | quality | active |
| `EPIC-001` | epic | `US-003` | user_story | contains | functional | active |
| `SPEC-001` | spec | `US-003` | user_story | decomposes_to | functional | active |
| `SPEC-U-003` | spec_unit | `US-003` | user_story | decomposes_to | functional | active |
| `US-003` | user_story | `AC-003` | acceptance_criteria | validated_by | quality | active |
| `EPIC-001` | epic | `US-004` | user_story | contains | functional | active |
| `SPEC-001` | spec | `US-004` | user_story | decomposes_to | functional | active |
| `SPEC-U-004` | spec_unit | `US-004` | user_story | decomposes_to | functional | active |
| `US-004` | user_story | `AC-004` | acceptance_criteria | validated_by | quality | active |
| `EPIC-001` | epic | `US-005` | user_story | contains | functional | active |
| `SPEC-001` | spec | `US-005` | user_story | decomposes_to | functional | active |
| `SPEC-U-005` | spec_unit | `US-005` | user_story | decomposes_to | functional | active |
| `US-005` | user_story | `AC-005` | acceptance_criteria | validated_by | quality | active |
| `EPIC-001` | epic | `US-006` | user_story | contains | functional | active |
| `SPEC-001` | spec | `US-006` | user_story | decomposes_to | functional | active |
| `SPEC-U-006` | spec_unit | `US-006` | user_story | decomposes_to | functional | active |
| `US-006` | user_story | `AC-006` | acceptance_criteria | validated_by | quality | active |
| `SPEC-001` | spec | `EPIC-002` | epic | decomposes_to | technical | active |
| `EPIC-002` | epic | `US-007` | user_story | contains | technical | active |
| `US-007` | user_story | `US-001` | user_story | enables | functional | active |
| `US-007` | user_story | `US-002` | user_story | enables | functional | active |
| `US-007` | user_story | `US-003` | user_story | enables | functional | active |
| `US-007` | user_story | `US-004` | user_story | enables | functional | active |
| `US-007` | user_story | `US-005` | user_story | enables | functional | active |
| `US-007` | user_story | `US-006` | user_story | enables | functional | active |
| `SPEC-001` | spec | `US-007` | user_story | decomposes_to | technical | active |
| `US-007` | user_story | `AC-007` | acceptance_criteria | validated_by | quality | active |
| `US-001` | user_story | `TC-001` | test_case | covered_by | quality | active |
| `US-002` | user_story | `TC-002` | test_case | covered_by | quality | active |
| `US-003` | user_story | `TC-003` | test_case | covered_by | quality | active |
| `US-004` | user_story | `TC-004` | test_case | covered_by | quality | active |
| `US-005` | user_story | `TC-005` | test_case | covered_by | quality | active |
| `US-006` | user_story | `TC-006` | test_case | covered_by | quality | active |
| `US-007` | user_story | `TC-007` | test_case | covered_by | quality | active |
| `US-001` | user_story | `QA-001` | backlog_readiness_audit | audited_by | quality | active |
| `US-002` | user_story | `QA-001` | backlog_readiness_audit | audited_by | quality | active |
| `US-003` | user_story | `QA-001` | backlog_readiness_audit | audited_by | quality | active |
| `US-004` | user_story | `QA-001` | backlog_readiness_audit | audited_by | quality | active |
| `US-005` | user_story | `QA-001` | backlog_readiness_audit | audited_by | quality | active |
| `US-006` | user_story | `QA-001` | backlog_readiness_audit | audited_by | quality | active |
| `US-007` | user_story | `QA-001` | backlog_readiness_audit | audited_by | quality | active |

## Artifact Registry

| Node ID | Type | Domain | Status | Path |
| --- | --- | --- | --- | --- |
| `RAW-001` | raw_input | product | active | `workspaces/[PROJECT_ID]/00_raw/raw.md` |
| `REQ-001` | requirement | product | active | `workspaces/[PROJECT_ID]/02_requirements/requirements.md` |
| `RU-001` | requirement_unit | product | active | `workspaces/[PROJECT_ID]/01_discovery/requirement_units.md` |
| `RU-002` | requirement_unit | product | active | `workspaces/[PROJECT_ID]/01_discovery/requirement_units.md` |
| `RU-003` | requirement_unit | product | active | `workspaces/[PROJECT_ID]/01_discovery/requirement_units.md` |
| `GAP-001` | gap_report | product | open | `workspaces/[PROJECT_ID]/01_discovery/gaps.md` |
| `DEC-001` | decision_log | product | pending | `workspaces/[PROJECT_ID]/01_discovery/decisions.md` |
| `SEED-001` | identity_seed_bank | product | active | `workspaces/[PROJECT_ID]/01_discovery/identity_seeds.md` |
| `DISC-001` | discovery_log | product | active | `workspaces/[PROJECT_ID]/01_discovery/discovery_log.md` |
| `DISC-002` | lens_review | product | active | `workspaces/[PROJECT_ID]/01_discovery/lens_review.md` |
| `DISC-003` | knowledge_ledger | product | active | `workspaces/[PROJECT_ID]/01_discovery/knowledge_state.md` |
| `DISC-004` | source_synthesis | product | active | `workspaces/[PROJECT_ID]/01_discovery/source_synthesis.md` |
| `CHG-001` | change | product | pending | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-1.md` |
| `DEC-002` | gap_resolution_report | product | active | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-1_gap_resolution_report.md` |
| `SEED-002` | identity_seed | quality | confirmed | `workspaces/[PROJECT_ID]/01_discovery/identity_seeds.md` |
| `DEC-003` | decision | quality | confirmed | `workspaces/[PROJECT_ID]/01_discovery/decisions.md` |
| `REQ-002` | ears_requirement | quality | confirmed | `workspaces/[PROJECT_ID]/02_requirements/requirements.md` |
| `CHG-002` | change | product | pending | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-2.md` |
| `DEC-004` | gap_resolution_report | product | active | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-2_gap_resolution_report.md` |
| `CHG-003` | change | product | pending | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-3.md` |
| `DEC-005` | gap_resolution_report | product | active | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-3_gap_resolution_report.md` |
| `CHG-004` | change | product | pending | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-4.md` |
| `DEC-006` | gap_resolution_report | product | active | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-4_gap_resolution_report.md` |
| `CHG-005` | change | product | pending | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-5.md` |
| `DEC-007` | gap_resolution_report | product | active | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-5_gap_resolution_report.md` |
| `CHG-006` | change | product | pending | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-6.md` |
| `DEC-008` | gap_resolution_report | product | active | `workspaces/[PROJECT_ID]/07_changes/00_client_responses/answer-6_gap_resolution_report.md` |
| `REQ-003` | project_brief | product | active | `workspaces/[PROJECT_ID]/02_requirements/project-brief.md` |
| `PRD-001` | prd | product | active | `workspaces/[PROJECT_ID]/03_specs/prd.md` |
| `SPEC-001` | spec | product | active | `workspaces/[PROJECT_ID]/03_specs/specs.md` |
| `SPEC-U-001` | spec_unit | product | evidence-backed | `workspaces/[PROJECT_ID]/03_specs/units/SPEC-U-001.md` |
| `REQ-EARS-001` | ears_requirement | product | confirmed | `workspaces/[PROJECT_ID]/02_requirements/requirements.md` |
| `SPEC-U-002` | spec_unit | product | evidence-backed | `workspaces/[PROJECT_ID]/03_specs/units/SPEC-U-002.md` |
| `REQ-EARS-002` | ears_requirement | product | confirmed | `workspaces/[PROJECT_ID]/02_requirements/requirements.md` |
| `SPEC-U-003` | spec_unit | product | evidence-backed | `workspaces/[PROJECT_ID]/03_specs/units/SPEC-U-003.md` |
| `REQ-EARS-003` | ears_requirement | product | confirmed | `workspaces/[PROJECT_ID]/02_requirements/requirements.md` |
| `SPEC-U-004` | spec_unit | product | evidence-backed | `workspaces/[PROJECT_ID]/03_specs/units/SPEC-U-004.md` |
| `REQ-EARS-004` | ears_requirement | product | confirmed | `workspaces/[PROJECT_ID]/02_requirements/requirements.md` |
| `SPEC-U-005` | spec_unit | product | evidence-backed | `workspaces/[PROJECT_ID]/03_specs/units/SPEC-U-005.md` |
| `REQ-EARS-005` | ears_requirement | product | confirmed | `workspaces/[PROJECT_ID]/02_requirements/requirements.md` |
| `SPEC-U-006` | spec_unit | product | evidence-backed | `workspaces/[PROJECT_ID]/03_specs/units/SPEC-U-006.md` |
| `REQ-EARS-006` | ears_requirement | product | confirmed | `workspaces/[PROJECT_ID]/02_requirements/requirements.md` |
| `EPIC-001` | epic | product | active | `workspaces/[PROJECT_ID]/04_backlog/EPIC-001.md` |
| `US-001` | user_story | functional | active | `workspaces/[PROJECT_ID]/04_backlog/US-001.md` |
| `AC-001` | acceptance_criteria | quality | active | `workspaces/[PROJECT_ID]/04_backlog/US-001.md` |
| `US-002` | user_story | functional | active | `workspaces/[PROJECT_ID]/04_backlog/US-002.md` |
| `AC-002` | acceptance_criteria | quality | active | `workspaces/[PROJECT_ID]/04_backlog/US-002.md` |
| `US-003` | user_story | functional | active | `workspaces/[PROJECT_ID]/04_backlog/US-003.md` |
| `AC-003` | acceptance_criteria | quality | active | `workspaces/[PROJECT_ID]/04_backlog/US-003.md` |
| `US-004` | user_story | functional | active | `workspaces/[PROJECT_ID]/04_backlog/US-004.md` |
| `AC-004` | acceptance_criteria | quality | active | `workspaces/[PROJECT_ID]/04_backlog/US-004.md` |
| `US-005` | user_story | functional | active | `workspaces/[PROJECT_ID]/04_backlog/US-005.md` |
| `AC-005` | acceptance_criteria | quality | active | `workspaces/[PROJECT_ID]/04_backlog/US-005.md` |
| `US-006` | user_story | functional | active | `workspaces/[PROJECT_ID]/04_backlog/US-006.md` |
| `AC-006` | acceptance_criteria | quality | active | `workspaces/[PROJECT_ID]/04_backlog/US-006.md` |
| `EPIC-002` | epic | technical | active | `workspaces/[PROJECT_ID]/04_backlog/EPIC-002-cross-cutting-enablers.md` |
| `US-007` | user_story | technical | active | `workspaces/[PROJECT_ID]/04_backlog/US-007.md` |
| `AC-007` | acceptance_criteria | quality | active | `workspaces/[PROJECT_ID]/04_backlog/US-007.md` |
| `TC-001` | test_case | quality | active | `workspaces/[PROJECT_ID]/05_quality/TC-001.md` |
| `TC-002` | test_case | quality | active | `workspaces/[PROJECT_ID]/05_quality/TC-002.md` |
| `TC-003` | test_case | quality | active | `workspaces/[PROJECT_ID]/05_quality/TC-003.md` |
| `TC-004` | test_case | quality | active | `workspaces/[PROJECT_ID]/05_quality/TC-004.md` |
| `TC-005` | test_case | quality | active | `workspaces/[PROJECT_ID]/05_quality/TC-005.md` |
| `TC-006` | test_case | quality | active | `workspaces/[PROJECT_ID]/05_quality/TC-006.md` |
| `TC-007` | test_case | quality | active | `workspaces/[PROJECT_ID]/05_quality/TC-007.md` |
| `QA-001` | backlog_readiness_audit | quality | active | `workspaces/[PROJECT_ID]/05_quality/backlog_readiness_audit.md` |

## Coverage Review

- Requirements should connect to discovery, specs, backlog, acceptance criteria, tests, changes, and audits as applicable.
- User stories without requirement/spec ancestry should be treated as health risks.
- Changes should point to impacted downstream nodes.
