<!-- sentinel-artifact: v2 -->
# Project Brief — {project_id}

## 0. Header

### 0.1 How to read this document

Each statement carries its citation, an inferred mark or a pending mark.

### 0.2 Status, validity and sources

Draft compiled from the raw input and the closed gaps.

## 1. Overview

### 1.1 Identity and Value

Operations leads review risk queues before the daily meeting. [[raw § Objective # RAW-001 — supports: the objective of the release]]

### 1.2 The Core Pain

Preparing the daily meeting is manual. [[raw § Metric # RAW-001 — supports: manual preparation today]]

### 1.3 Success Metrics / Scope

Reduce manual preparation by 30 percent in the first release month. [[raw § Metric # RAW-001 — supports: the target]]

### 1.4 Starting Point and End Point

From a manual spreadsheet to a read-only dashboard.

### 1.5 Release Acceptance Criteria

The dashboard shows every open risk queue. [[gaps § GAP-ACCEPTANCE # GAP-ACCEPTANCE — supports: confirmed acceptance]]

## 2. Business Lens

### 2.1 Actors and Goals by Role

Operations leads review the queues. [[raw § Users # RAW-001 — supports: the actor]]

### 2.2 Critical Business Rules

A case that breaches the SLA flags its queue as high risk.

### 2.3 Main Use Case

The lead opens the dashboard before the meeting.

### 2.4 Business Need

Less time preparing, more time deciding.

### 2.5 Business Date and Calendar

⏳ PENDING (GAP-BUSINESS-CALENDAR)

## 3. Product Lens

### 3.1 As-Is Situation

Queues are exported by hand every morning.

### 3.2 To-Be Process

The dashboard reads the queue metrics directly.

### 3.6 Error Handling / Edge Cases

When the metrics service is unavailable, the risk status shows as unknown.

## 4. Design Lens

### 4.1 Screen Flow

A single read-only screen with one row per open queue.

### 4.4 Accessibility

⏳ PENDING DOMAIN (GAP-DESIGN-A11Y)

## 5. Technical Lens

### 5.1 Architecture and Integrations

The dashboard reads the existing queue metrics service.

### 5.7 API Contracts

⏳ PENDING DOMAIN (GAP-TECH-DATA-SOURCE)

### 5.11 Governance and Constraints

Dashboard access is recorded when audit logging is enabled. [[gaps § GAP-ACCEPTANCE # GAP-ACCEPTANCE — supports: the audit rule]]

### 5.16 Observability

Stale data shows a warning.

## 6. Release Agreements

### 6.1 In Scope

Read-only risk dashboard for open queues.

### 6.2 Out of Scope

Editing cases — OUT OF SCOPE — returns in a later release.

## 7. Dependencies and Open Questions

### 7.2 Open Items Seeded in the Body (⏳)

3 open items.

## 8. Assumptions

### 8.1 Assumptions List

None recorded.

## 9. Things to Build

### 9.1 Build List or Phases

1. Read-only queue dashboard.
