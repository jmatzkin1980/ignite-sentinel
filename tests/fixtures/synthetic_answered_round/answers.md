# SYNTHETIC answered round — support-dashboard (not client data)

These answers are invented for a test. They answer the first `/gaps --top 8` round of the
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

### GAP-BRIEF-S3
- Answer: 3.1: Each Monday a team lead downloads three ticket exports and merges them in a spreadsheet. 3.3: The lead opens the dashboard, picks the week and reads the queue overview. 3.4: A queue is either normal or high risk; it changes state when the nightly refresh runs. 3.5: A queue becomes high risk after the nightly refresh finds the ageing threshold crossed, and returns to normal when it no longer is.
- Owner / source: Synthetic client round
- Evidence or reference: Synthetic answered-round fixture
- Decision status: confirmed

### GAP-BRIEF-S4
- Answer: 4.2: High-risk queues are shown first, with their name in bold. 4.4: Colours are never the only signal; every risk badge has a text label. 4.5: A one-page guide for team leads ships with the first slice.
- Owner / source: Synthetic client round
- Evidence or reference: Synthetic answered-round fixture
- Decision status: confirmed

### GAP-BRIEF-S5
- Answer: 5.0: The dashboard reads from the ticketing tool and stores nothing of its own beyond a nightly snapshot. 5.4: One snapshot row per queue and day, with open, resolved and aged ticket counts. 5.6: The only integration is the ticketing tool's read-only reporting export. 5.7: No public API; the dashboard page reads the snapshot directly. 5.8: The aged count shown on screen is the snapshot's aged column, unchanged. 5.9: A nightly job loads the export into the snapshot and retries once on failure. 5.10: The page may show data up to one day old; no cache beyond the snapshot. 5.13: No legacy system is replaced. 5.14: No events or messaging. 5.15: When the nightly load fails, the page shows the last good snapshot and its date. 5.18: Only team leads use it, about twenty people. 5.19: Current desktop browsers only. 5.20: The page sits behind the company sign-in. 5.21: English only. 5.22: No personal data is shown; ticket ids only. 5.23: Count page opens per week. 5.25: Not exposed outside the company network.
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
