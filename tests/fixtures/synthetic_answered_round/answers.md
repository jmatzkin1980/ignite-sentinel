# SYNTHETIC answered round — support-dashboard (not client data)

These answers are invented for a test. They answer the first `/gaps --top 5` round of the
support-dashboard eval fixture, so the test can prove the circuit round → answer → fewer `⏳` marks.
They measure the mechanism, not the real drop: that is measured on the first real project.

### GAP-BACKLOG-SLICING-READINESS
- Answer: The first slice is the read-only queue overview for the current quarter; ageing drill-down and export are deferred, and splitting the overview by metric would stop producing value.
- Owner / source: Synthetic client round
- Evidence or reference: Synthetic answered-round fixture
- Decision status: confirmed

### GAP-BRIEF-S1
- Answer: 1.2: Team leads assemble the weekly review by hand from three ticket exports. 1.4: Today they start from spreadsheets; at the end they open a single dashboard view.
- Owner / source: Synthetic client round
- Evidence or reference: Synthetic answered-round fixture
- Decision status: confirmed

### GAP-BRIEF-S2
- Answer: 2.3: A team lead opens the dashboard on Monday morning to prepare the weekly review. 2.4: Fewer hours of manual preparation before each review. 2.5: Weeks run Monday to Sunday in the support team's time zone.
- Owner / source: Synthetic client round
- Evidence or reference: Synthetic answered-round fixture
- Decision status: confirmed

### GAP-BUSINESS-RULES
- Answer: A queue is high risk when more than 10 percent of its open tickets are older than 5 business days; closed tickets never count toward ageing.
- Owner / source: Synthetic client round
- Evidence or reference: Synthetic answered-round fixture
- Decision status: confirmed

### GAP-CTP-EXCLUSION
- Answer: Editing tickets was excluded because the ticketing tool remains the system of record; it never comes back to this dashboard.
- Owner / source: Synthetic client round
- Evidence or reference: Synthetic answered-round fixture
- Decision status: confirmed
