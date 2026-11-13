# Prototype inventory — P

Every visible element and every JavaScript copy literal of the ingested HTML prototypes, by screen. The audit and the manual cite these ids; an element that is not here does not exist.

## F-01 — `00_raw/claims-portal.html`

### S1 Outside any screen

Screen key: `page` · line 10

| Id | Kind | Text | Line | Starts hidden |
|---|---|---|---|---|
| S1-E01 | link | My claims | 10 | no |
| S1-E02 | link | File a claim | 10 | no |

### S2 Sign in

Screen key: `sign-in` · line 12

| Id | Kind | Text | Line | Starts hidden |
|---|---|---|---|---|
| S2-E01 | heading | Sign in | 13 | no |
| S2-E02 | label | Email | 14 | no |
| S2-E03 | field | you@example.com | 15 | no |
| S2-E04 | label | Password | 16 | no |
| S2-E05 | field | Password | 17 | no |
| S2-E06 | button | Continue | 18 | no |
| S2-E07 | message | The email or the password is not right. | 19 | yes |

### S3 My claims

Screen key: `claims` · line 22

| Id | Kind | Text | Line | Starts hidden |
|---|---|---|---|---|
| S3-E01 | heading | My claims | 23 | no |
| S3-E02 | column | Claim | 25 | no |
| S3-E03 | column | Filed on | 25 | no |
| S3-E04 | column | Status | 25 | no |
| S3-E05 | column | Amount | 25 | no |
| S3-E06 | message | You have not filed any claim yet. | 28 | yes |
| S3-E07 | button | File a claim | 29 | no |

### S4 File a claim (starts hidden)

Screen key: `new-claim` · line 32

| Id | Kind | Text | Line | Starts hidden |
|---|---|---|---|---|
| S4-E01 | heading | File a claim | 33 | yes |
| S4-E02 | label | What happened? | 34 | yes |
| S4-E03 | field | Describe the incident | 35 | yes |
| S4-E04 | label | Kind of claim | 36 | yes |
| S4-E05 | field | Kind of claim | 37 | yes |
| S4-E06 | option | Car accident | 38 | yes |
| S4-E07 | option | Home damage | 39 | yes |
| S4-E08 | option | Theft | 40 | yes |
| S4-E09 | label | Attachments | 42 | yes |
| S4-E10 | field | Attachments | 43 | yes |
| S4-E11 | button | Submit claim | 44 | yes |
| S4-E12 | message | Your claim was filed. We will review it in two business days. | 45 | yes |

### JavaScript copy

| Id | Text | Line |
|---|---|---|
| JS-01 | Submitted | 50 |
| JS-02 | Under review | 51 |
| JS-03 | Approved, payment on its way. | 52 |
| JS-04 | Rejected: see the reason in the claim. | 53 |
| JS-05 | The attachment is larger than 10 MB. | 55 |
| JS-06 | Your session expired. Sign in again. | 55 |
