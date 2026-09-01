# KaosEghis-SOCL

Last updated: 2026-09-01

## Status

**First editable composition milestone implemented.**

SOCL means **Subjective & Objective Composer for the Lazy**. It is a local,
physician-controlled formatting tool for the Subjective (`S`) and Objective (`O`)
portions of an encounter note.

SOCL does not diagnose, recommend, infer, or select findings. Every rendered item must
come from an explicit physician checkbox selection. Unchecked means omitted; it does
not mean normal, negative, absent, or not examined.

## Current UI

SOCL is an independently movable KaosEghis-owned window with two pages:

- `Compose`
- `Edit vocabulary`

It opens from `Launcher -> Open SOCL` or the `SOCL` navigation action. The window can
remain on the patient-facing monitor while the main fixed-size KaosEghis window stays
on the operator monitor. Closing and reopening the application restores the last valid
SOCL screen position and size; an off-screen saved position is ignored safely.

### Compose

The compose page contains:

- a Subjective collection tree
- a Physical Examination collection tree
- an optional encounter-detail field beside every finding
- vertically centered compact rows when an encounter-detail field is visible
- Generate preview
- New / Clear
- independently editable Subjective and Objective previews
- Copy S
- Copy O
- Copy S/O

Nothing is selected by default. Opening SOCL or starting a new note cannot carry
selections or generated text from a previous encounter.

Generation is explicit. Editing a checkbox or detail field does not silently replace
the physician's current preview. `Generate preview` deterministically rebuilds the
preview from the current explicit selections; the physician may then edit the result
before copying it.

### Compact Composer

The popup Compose page uses the compact composer and deterministic renderer:

- separate `S` and `O` tabs
- two checkbox columns inside each clinical collection
- ordinary optional-detail fields remain hidden until their finding is checked
- free-text/other detail fields remain visible and typing in one checks its finding
- Generate, Copy, and Clear operate only on the current S or O domain

The compact layout changes presentation only. It does not persist encounter selections
or introduce clinical inference.

### Edit vocabulary

The vocabulary page supports local editing of both Subjective and Physical Exam data:

- add collection
- rename collection
- delete collection with confirmation
- move collection up or down
- add finding
- edit display label
- edit rendered phrase
- delete finding with confirmation
- move finding up or down
- restore the reviewed default catalog with confirmation

Changes are saved immediately to the local KaosEghis SQLite database. Restoring
defaults replaces vocabulary edits, but it does not affect macros, settings, PACS,
Flu, Vaccine, or EMR target records.

## Reviewed Default Catalog

The default Subjective collections are:

- Shared details
- Constitutional
- Nose/sinus
- Throat/oral/voice
- Respiratory
- Ear
- Eye
- Headache
- Dizziness
- Cardiovascular
- Upper GI
- Abdominal/bowel
- Urinary
- Musculoskeletal
- Neurologic
- Skin
- Sleep/mood
- Injury/wound
- Reproductive/genital
- Other

The default Physical Exam collections are:

- Vitals/general
- Head/face/sinus
- Eyes
- Ears
- Nose
- Mouth/pharynx
- Neck/thyroid/lymph
- Respiratory
- Cardiovascular
- Abdomen
- Musculoskeletal
- Neurologic
- Skin/wound
- Psychiatric
- GU/reproductive

The exact reviewed findings and their order are maintained in:

- `KaosEghis/db/socl_defaults.py`

The catalog intentionally includes a broad review set. The physician-owner can remove
rarely used groups, rename labels, adjust rendered wording, and reorder frequent groups
without changing source code.

## Rendering

Selected findings are grouped in catalog order. Example structure:

```text
S) Constitutional: fever: 3 days; fatigue.

O) Respiratory: breath sounds: clear bilaterally.
```

The renderer:

- preserves domain, collection, and finding order
- renders checked findings only
- includes an optional detail only when entered
- uses the locally editable rendered phrase
- omits empty sections
- does not add negative, normal, severity, duration, laterality, or diagnosis wording
- does not persist generated text

The output preview remains ordinary editable text. Copy uses the final edited preview,
not a hidden regenerated version.

## Persistence

SOCL adds local SQLite tables:

- `socl_collections`
- `socl_findings`
- `socl_metadata`

Only reusable vocabulary configuration is stored:

- Subjective or Objective domain
- collection name and order
- finding display label
- finding rendered phrase and order
- timestamps
- default catalog version marker

SOCL does **not** store:

- checked encounter selections
- encounter details
- generated S/O previews
- copied text history
- patient identity
- diagnosis, assessment, plan, orders, or prescriptions

## Safety Boundary

SOCL is not:

- clinical decision support
- a diagnosis or differential generator
- an Assessment/Plan generator
- an order-entry system
- a billing checklist
- an automatic review-of-systems generator
- evidence that an examination occurred

Normal or negative findings may exist in a physician-edited vocabulary, but they are
never preselected or inferred. The physician remains responsible for confirming that
every copied statement reflects the actual encounter.

This milestone copies text to the Windows clipboard only. It does not focus eGHIS,
paste into eGHIS, run a macro, or write to the eGHIS database. Future EMR transfer must
use the existing MacroRunner safety boundary and remain an explicit action.

## Source Organization

The initial structure was reviewed against authoritative classification and examination
frameworks:

- WHO ICPC-2 reason-for-encounter classification for general/family practice:
  <https://www.who.int/standards/classifications/other-classifications/international-classification-of-primary-care>
- CDC National Ambulatory Medical Care Survey reason-for-visit model:
  <https://www.cdc.gov/nchs/namcs/about/>
- CMS general multi-system examination framework:
  <https://www.cms.gov/sites/default/files/2021-08/97Docguidelines.pdf>

These sources organize the review catalog; they do not prescribe what must be selected
for an individual patient and are not used as automated medical rules.

## Tests

Automated coverage verifies:

- exact one-time default seeding
- vocabulary CRUD and persisted order changes
- restore-default behavior
- explicit-selection-only rendering
- optional detail rendering
- editable preview copied as edited
- no encounter selection persistence
- vocabulary editor controls
- SOCL top-level navigation

## Next Review

The physician-owner should now review the vocabulary in the running app and remove,
rename, reorder, or rewrite items based on the clinic's actual documentation style.
Only after that review should complaint-specific SOCL templates or MacroRunner-based
eGHIS transfer be considered.
