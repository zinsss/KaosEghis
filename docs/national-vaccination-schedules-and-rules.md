# National Vaccination Schedules and Rules

Last reviewed: 2026-08-21

## Purpose

This document defines how KaosEghis represents seasonal Korean national Influenza and
COVID vaccination-program rules. It is an implementation and operator reference, not
an independent clinical or reimbursement authority.

Official KDCA/NIP guidance, current public-health notices, and the vaccination system
remain authoritative. Before enabling a season in KaosEghis, the operator must compare
every date, birth boundary, exception, and count rule with the current official notice.

## Source Hierarchy

Use sources in this order:

1. Current-season KDCA national vaccination implementation guidance.
2. Current-season NIP Vaccination Assistant program pages and official amendments.
3. Local public-health-center instructions that validly apply to the clinic.
4. KaosEghis configuration, only after it has been reviewed against the above.

KaosEghis must never silently carry the previous season's dates into a new season.
Schedules remain disabled until reviewed and enabled explicitly.

## Current Publication Status

As of 2026-08-21, the reviewed official sources provide complete 2025-2026 seasonal
dates and general 2026 implementation rules. A final 2026-2027 schedule was not present
in the sources reviewed for this document. Therefore:

- the 2025-2026 dates below are historical reference values only
- they must not be activated as 2026-2027 operational dates
- the editable 2026-2027 KaosEghis schedule must remain disabled until the final KDCA
  notice is entered and independently checked

## Shared Daily Count Rules

The national limit is per examining physician, per day:

- Influenza: maximum 100 counted Influenza vaccinations
- COVID: maximum 100 counted COVID vaccinations

The two programs are counted separately. Within Influenza, counted elderly and counted
pediatric vaccinations share one Influenza total. KaosEghis must not create separate
100-dose totals for elderly and children.

The 2026 KDCA guidance excludes the following from the 100-person count:

- paid vaccinations
- local-government independent programs
- vaccinations accepted under an official program-period exception
- other NIP vaccinations
- qualifying managed visiting-vaccination schedules

KaosEghis therefore needs two independent decisions for every national-program
vaccination:

1. Is the patient eligible to proceed today?
2. Does this vaccination consume the program's daily count?

Eligibility and count consumption must not be represented by one boolean.

## Influenza Reference Schedule

The following table is the official 2025-2026 reference, not the next season's active
configuration:

| Group | Birth boundary | Opening | Closing |
| --- | --- | --- | --- |
| Child, two-dose target | 2012-01-01 through 2025-08-31, subject to age and history criteria | 2025-09-22 | 2026-04-30 |
| Child, one-dose target | Same supported child population | 2025-09-29 | 2026-04-30 |
| Pregnant person | Pregnancy confirmed, regardless of gestational age | 2025-09-29 | 2026-04-30 |
| Elderly, 75+ | Born on or before 1950-12-31 | 2025-10-15 | 2026-04-30 |
| Elderly, 70-74 | 1951-01-01 through 1955-12-31 | 2025-10-20 | 2026-04-30 |
| Elderly, 65-69 | 1956-01-01 through 1960-12-31 | 2025-10-22 | 2026-04-30 |

### Elderly Staged Opening

For the normal program path:

- before the 75+ opening, no elderly age group is open
- at the 75+ opening, counted 75+ vaccinations can proceed
- at the 70-74 opening, counted 75+ and 70-74 vaccinations can proceed
- at the 65-69 opening, all three elderly groups can proceed as counted vaccinations

If the shared Influenza count has reached 100, a counted elderly or pediatric
vaccination is blocked. A confirmed official exception is non-counted and is evaluated
separately from the cap.

### Program-Period Exceptions

The 2026 KDCA guidance allows an elderly vaccination during another elderly group's
program period only when a recognized patient-specific exception applies. Listed
categories include:

- registered residence in a qualifying island or remote/medically underserved area
- qualifying same-day treatment for an underlying or suddenly occurring condition
- an approved visiting-vaccination case under local-government/public-health-center
  management
- a qualifying disability or difficulty returning to the medical institution

The clinic being located in an eligible area does not by itself prove that every
patient qualifies. For the residence path, the patient's registered residence is the
relevant fact. KaosEghis must show an operator confirmation and require selection of a
recognized exception reason before allowing the non-counted exception path.

The application must not infer an exception from free-text address alone and must not
store a resident ID or full address merely to automate this decision.

### Pediatric One-Dose and Two-Dose Opening

For the 2025-2026 reference season, the two-dose target window opened before the
one-dose window. KDCA described the two-dose target as a child from 6 months to under
9 years who either:

- is receiving Influenza vaccination for the first time or has unknown prior history,
  or
- had received only one total Influenza dose by the season's specified history cutoff

KaosEghis cannot safely infer that history from age alone. During the early two-dose-
only window it must:

1. identify that the child is within the configured supported birth range
2. stop before label printing
3. instruct the operator to check the national vaccination system manually
4. proceed only after the operator confirms two-dose eligibility
5. consume the shared Influenza daily count after the successful completion checkpoint

After the one-dose window opens, that early-window confirmation is no longer required,
but normal age, date, count, and contraindication review still applies.

## COVID Reference Schedule

For 2025-2026, the reviewed NIP page listed:

| Group | Opening | Original closing |
| --- | --- | --- |
| 75+ | 2025-10-15 | 2026-04-30 |
| 70-74 | 2025-10-20 | 2026-04-30 |
| 65-69 | 2025-10-22 | 2026-04-30 |
| Immunocompromised and vulnerable-facility residents, age 6 months+ | 2025-10-15 | 2026-04-30 |

KDCA subsequently extended the 2025-2026 high-risk COVID program through 2026-06-30.
This illustrates why dates must be editable and why KaosEghis must not hardcode a
season's original closing date as immutable.

COVID has its own 100-person daily count, separate from Influenza. Its eligible groups,
dose history rules, additional-dose guidance, products, and closing date may differ by
season. The COVID schedule must remain configurable and disabled until that season's
official plan is reviewed.

## KaosEghis Rule Evaluation Order

KaosEghis should evaluate a national-program vaccination in this order:

1. Confirm that the season is enabled and internally complete.
2. Derive the minimum transient birth date needed for configured group matching.
3. Match exactly one configured normal age/birth group.
4. Evaluate the configured group opening and closing dates.
5. If outside the normal group opening but within an allowed exception period, require
   an explicit patient-specific exception reason.
6. Determine whether the resulting path consumes the program count.
7. If counted, compare the appropriate shared daily total with 100 or the configured
   reviewed cap.
8. During the pediatric two-dose-only interval, require manual vaccination-history
   confirmation before label printing.
9. Show the operator the group, window, exception state, count treatment, total, and
   reason for any block.
10. Increment a count only at the configured successful completion checkpoint.

No preview, cancelled workflow, failed print, or failed external-system preparation may
increment a count.

## Decision Matrix

| Situation | Eligible | Counted | Operator action |
| --- | --- | --- | --- |
| Elderly before the first elderly opening | No | No | Wait for program opening |
| Elderly group whose normal opening has arrived | Yes | Yes | Apply shared Influenza cap |
| Younger elderly group before its opening, no confirmed exception | No | No | Verify official exception or wait |
| Younger elderly group before its opening, confirmed official exception | Yes | No | Record sanitized exception category |
| Child before two-dose opening | No | No | Wait for program opening |
| Child during two-dose-only interval, history not checked | Pending | Not yet | Check vaccination system manually |
| Confirmed eligible child during two-dose-only interval | Yes | Yes | Apply shared Influenza cap |
| Eligible child after one-dose opening | Yes | Yes | Apply shared Influenza cap |
| Counted Influenza total already 100 | No for counted path | N/A | Block counted Influenza vaccination |
| Confirmed non-counted program exception at total 100 | Yes | No | Proceed under verified exception |
| Paid Influenza | Outside national gate | No | Use private-vaccine workflow |

## Configuration Fields

### Influenza

- program year/reference label
- program enabled
- shared daily cap, normally 100 after annual review
- exception path enabled
- 75+, 70-74, and 65-69 opening dates
- elderly closing date
- elderly birth boundaries
- pediatric supported birth boundaries
- two-dose opening and closing dates
- one-dose opening and closing dates

### COVID

- program year/reference label
- program enabled
- separate COVID daily cap, normally 100 after annual review
- editable age/risk groups
- each group's opening and closing dates
- applicable birth boundaries where age-based
- current-season extension/amendment state

## Annual Activation Checklist

Before enabling either program:

- [ ] Obtain the final current-season KDCA/NIP notice.
- [ ] Confirm all supported groups and birth boundaries.
- [ ] Confirm every opening and closing date.
- [ ] Confirm pediatric one-dose/two-dose definitions and history cutoff.
- [ ] Confirm exception categories and local public-health-center instructions.
- [ ] Confirm the 100-person count rule and exclusions.
- [ ] Confirm whether a later amendment or extension supersedes the original dates.
- [ ] Enter values in Vaccine Settings.
- [ ] Independently review the saved values against the source.
- [ ] Run exact-boundary tests with non-real patient dates.
- [ ] Enable the program only after review.

## Privacy and Audit

Routine rule evaluation must not log or persist:

- resident registration number
- full birth date unless explicitly required by the approved local record model
- patient name
- phone or address
- diagnosis or EMR notes
- raw vaccination-system responses

A future exception audit may retain only a sanitized category, such as
`qualifying_residence`, `same_day_treatment`, `approved_visit`, or
`qualifying_disability`, plus non-identifying operational timestamps. It must not store
the evidence text or full address.

## Implementation Status

Implemented:

- editable single-current-season Influenza and COVID settings surfaces
- pure Influenza age/date/cap evaluation
- staged elderly opening logic
- non-counted exception result pending patient-specific confirmation
- pediatric early-window manual-check warning
- boundary and shared-cap tests

Not yet complete:

- explicit exception-reason confirmation UI
- persistent counted/non-counted completion ledger
- print-success checkpoint
- COVID age/risk-group evaluator
- current-season amendment tracking

Until those pieces are complete, the displayed local count is a preview aid and must
not be treated as the authoritative national-system count.

## Official References

- [2026 National Vaccination Guidance, KDCA](https://kdca.go.kr/bbs/kdca/55/307748/download.do)
- [2025-2026 Influenza Management Guidance, KDCA](https://www.kdca.go.kr/bbs/kdca/55/260163/download.do)
- [Influenza National Vaccination Program, NIP Vaccination Assistant](https://cert.kdca.go.kr/irhp/infm/goVcntInfo.do?menuCd=134&menuLv=1)
- [COVID Vaccination Program, NIP Vaccination Assistant](https://nip.kdca.go.kr/irhp/covd/goCov19Vcnt.do?menuCd=47&menuLv=4)
- [2025-2026 COVID Program Extension Notice, KDCA](https://www.kdca.go.kr/bbs/kdca/42/306366/download.do)
