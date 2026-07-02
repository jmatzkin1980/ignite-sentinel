# Customer Support Insights Portal

## Objective

Build a customer support insights portal so support managers can review weekly complaint trends, identify top contact reasons, and export a summary for the Monday operations review.

## Users

Primary users are support managers. Secondary users are operations analysts who prepare the weekly review packet.

## Scope

In scope:

- Dashboard with weekly complaint volume, top contact reasons, and escalation counts.
- Filters for week, region, product line, and support channel.
- CSV export for the filtered view. CSV export includes raw customer comments and account notes.
- Read-only access for operations analysts.

Out of scope:

- Case management workflows.
- Automated customer notifications.
- Changes to the CRM record model.

## Success Criteria

- Support managers can identify the top five contact reasons for a selected week.
- Operations analysts can export a filtered CSV for the weekly review.
- The portal uses the existing corporate SSO group for access.
