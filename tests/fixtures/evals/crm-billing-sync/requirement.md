# Client Request: CRM to Billing Synchronization

We need our CRM customer records synchronized into the billing platform. Today account managers copy data by hand and invoices go out with stale addresses.

The integration should push new and updated customer records through the existing billing API. Both systems already exist; the CRM exposes a REST endpoint for customer data.

The objective is that billing always works with current customer information. Users affected are the finance back office and the account managers who stop doing manual copies.

Scope: customer master data only. Product catalog and pricing stay out of scope.
