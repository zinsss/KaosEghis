# KaosEghis-SOCL

Status: Planned  
Priority: High  
Module: KaosEghis  
Version: Design Draft

## Name

**SOCL — Subjective & Objective Composer for the Lazy**

> Less typing. Same thinking.

## Purpose

KaosEghis-SOCL is a physician-operated documentation composer for the Subjective (S) and Objective (O) portions of an encounter note.

It reduces repetitive typing by converting explicit physician selections into editable S/O text.

SOCL does not make clinical decisions and does not generate Assessment or Plan content.

## Scope

SOCL generates only:

- Subjective findings
- Objective findings
- Editable rendered S/O text
- Copy or paste actions into eGHIS through the Macro Engine

SOCL does not generate or suggest:

- Assessment
- Differential diagnosis
- Plan
- Orders
- Prescriptions
- Tests
- Imaging
- Referrals
- Clinical scores
- Billing or diagnostic codes

## Core principles

### Physician controlled

Every documented item originates from an explicit physician action.

SOCL never infers findings from other selections, patient speech, diagnoses, or prior notes.

### Unchecked means omitted

Unchecked items do not appear in the generated note.

Unchecked does not mean normal, abnormal, absent, or not examined. It means only that the item will not be documented by SOCL.

### Normal findings are explicit

Normal findings remain selectable because the physician may intentionally document them.

Examples:

- Tonsils normal
- Breath sounds clear bilaterally
- No acute distress
- Abdomen soft and non-tender

SOCL never auto-selects normal findings.

### Editable output

Generated text is always editable before transfer to eGHIS.

### Deterministic behavior

The same selections and inputs must produce the same output.

No AI inference, ambient listening, or probabilistic text generation is part of the core module.

## Encounter workflow

1. Open an encounter template, such as URI.
2. Ask the patient about the presenting complaint.
3. Select symptoms while listening.
4. Enter short details such as duration or custom text.
5. Continue to the focused physical-examination page.
6. Select only the findings the physician wants documented.
7. Review the generated S/O output.
8. Edit or append details when needed.
9. Copy S, O, or S/O to eGHIS through the Macro Engine.

## Example: URI

### Subjective page

Categories should be clinically grouped rather than presented as one unordered checklist.

#### Duration

- Today
- 2–3 days
- 1 week
- More than 1 week
- Custom

#### Constitutional

- Fever
- Chills
- Fatigue
- Myalgia
- Headache

#### Nasal

- Rhinorrhea
- Nasal obstruction
- Sneezing
- Postnasal drip

#### Throat and voice

- Sore throat
- Hoarseness
- Odynophagia

#### Respiratory

- Cough
- Sputum
- Dyspnea
- Wheezing
- Chest pain
- Hemoptysis

#### Additional text

Free-text entry for details not covered by the template.

### Objective page

#### General

- No acute distress
- Alert
- Well hydrated
- Febrile appearance

#### Nose

- Nasal mucosa normal
- Nasal mucosal swelling
- Rhinorrhea present

#### Pharynx

Mutually exclusive choices where appropriate:

- Not documented
- Normal
- Congested
- Erythematous
- Exudate
- Custom

#### Tonsils

- Not documented
- Normal
- Enlarged
- Exudative
- Asymmetric
- Status post tonsillectomy
- Custom

#### Cervical lymph nodes

- Not documented
- No palpable enlargement
- Tender enlargement
- Non-tender enlargement
- Custom

#### Breath sounds

- Not documented
- Clear bilaterally
- Wheezing
- Crackles
- Rhonchi
- Decreased
- Custom

## Generated example

Selections:

- Cough
- Fever
- Duration: 3 days
- Pharyngeal congestion
- Tonsils normal
- Breath sounds clear bilaterally

Rendered output:

```text
S) Cough and fever for 3 days.

O) Pharyngeal congestion.
   Tonsils normal.
   Breath sounds clear bilaterally.
```

Only selected items appear.

## Input controls

Use controls according to the clinical relationship between findings.

### Checkboxes

Use when findings may coexist independently.

Examples:

- Alert
- No acute distress
- Well hydrated

### Radio groups or single-select controls

Use when only one state should be documented.

Examples:

- Pharynx: normal / congested / exudative
- Breath sounds: clear / wheezing / crackles / decreased

### Editable structured fields

Use for short values:

- Duration
- Severity
- Laterality
- Location
- Character

### Free text

Every page must include a small free-text field for exceptional details.

## Rendering rules

- Preserve template order.
- Omit unchecked findings.
- Omit empty sections.
- Avoid repeating equivalent findings.
- Keep wording concise and physician-editable.
- Do not expand a finding beyond its configured phrase.
- Do not infer negatives.
- Do not infer normality.
- Do not infer anatomical side.

## Template model

Each encounter template should define:

- Template identifier
- Display name
- Subjective pages and categories
- Objective pages and categories
- Finding identifiers
- Control type
- Allowed values
- Rendered phrases
- Display order
- Optional default wording

Templates are authored and maintained only by the physician-owner.

## Initial templates

Recommended first set:

- URI
- Cough
- Sore throat
- Fever
- Headache
- Dizziness
- Abdominal pain
- Dyspepsia
- Low-back pain
- Joint pain

The initial release should prioritize workflow quality over template count.

## UI structure

```text
SOCL
├── Encounter template selector
├── Subjective page
├── Objective page
└── Final result
    ├── Editable S preview
    ├── Editable O preview
    ├── Copy S
    ├── Copy O
    ├── Copy S/O
    └── Send to eGHIS
```

## Relationship with the Macro Engine

SOCL owns structured documentation and rendering.

The Macro Engine owns:

- eGHIS window activation
- navigation to S and O fields
- clipboard or text insertion
- focus validation
- execution safety

SOCL must not directly automate eGHIS controls.

## Privacy and ownership

- Local-first storage
- No automatic cloud synchronization
- No ambient audio capture
- No patient-derived model training
- No shared template marketplace
- No automatic template distribution
- Templates are created and maintained by the physician-owner only

## Non-goals

SOCL is not:

- An EMR
- A clinical decision-support system
- An AI scribe
- A diagnosis assistant
- A treatment advisor
- An order-entry system
- A plan generator
- A billing assistant

## Mission statement

The physician listens, examines, and decides what belongs in the chart.

SOCL formats only the findings the physician explicitly selects.
