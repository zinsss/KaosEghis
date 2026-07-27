# KaosEghis Procedures

Status: Planned  
Priority: High  
Module: KaosEghis  
Version: Design Draft

## Purpose

KaosEghis Procedures is a physician-operated visual procedure-documentation module.

Its first and only planned procedure for the initial implementation is **Trigger Point Injection (TPI)**.

The module captures:

- Patient-reported pain distribution
- Physician-marked injection sites
- Explicitly entered procedure details
- An editable procedure summary
- Optional physician-entered plan text
- A one-page visual PDF
- Optional archival in KaosPACS

The diagram is the primary visual record. Generated text is secondary and remains editable.

## Module structure

```text
KaosEghis
├── SOCL
├── Procedures
│   └── Trigger Point Injection
├── Macro Engine
├── Scheduler
├── PACS
└── Settings
```

Future procedure types may reuse the same mapping and PDF infrastructure, but they are outside the initial scope.

## Core principles

### Physician controlled

All pain markings, injection points, procedure details, and plan text originate from the physician.

The module never selects, recommends, or infers procedure locations.

### Visual first

The workflow is optimized for rapid visual recall during follow-up visits.

A physician should be able to open the prior PDF and understand within seconds:

- Where the patient reported pain
- Where injections were performed
- How many sites were injected
- What procedure details were recorded

### Original anatomical assets

The interaction may be inspired by familiar trigger-point mapping workflows, but all body and regional artwork must be original or properly licensed.

Do not copy artwork, maps, labels, or other assets from triggerpoints.net or another third-party source.

### Deterministic output

The same markings and entered details must produce the same rendered map and procedure text.

### No clinical decision support

Procedures never recommends:

- Whether a procedure is indicated
- Which area or muscle to inject
- Number of injection points
- Injectate
- Concentration
- Volume
- Needle
- Diagnosis
- Billing code
- Follow-up plan

The physician performs all clinical reasoning and supplies all procedure information.

## Initial workflow: Trigger Point Injection

### Step 1: open TPI

The physician launches:

```text
Procedures
└── Trigger Point Injection
```

### Step 2: whole-body pain map

Display original whole-body diagrams:

- Anterior view
- Posterior view

The physician paints or shades patient-reported pain areas in red.

Red means only:

> Patient-reported pain distribution selected by the physician.

Supported actions:

- Brush or region selection
- Erase
- Undo
- Clear
- Switch anterior/posterior view
- Select one or more anatomical regions for detail view

### Step 3: regional close-up

Selecting an affected region opens a larger original anatomical illustration.

Examples of possible regional maps:

- Posterior neck and upper trapezius
- Shoulder and periscapular region
- Thoracic paraspinal region
- Lumbar paraspinal region
- Gluteal region
- Upper extremity
- Lower extremity

The close-up preserves or reproduces the selected red pain distribution.

### Step 4: injection-site mapping

The same regional close-up contains both pain and injection information.

- Red shading: patient-reported pain
- Blue markers: actual injection sites

A separate injection-only diagram is unnecessary.

Supported actions:

- Click to add a blue injection marker
- Click or select a marker to remove it
- Drag a marker to correct its position
- Undo
- Clear injection markers
- Optional anatomical label assignment

Each blue marker represents one injected trigger point.

The marker count is calculated automatically, but the physician may correct structured labels or counts before finalization.

## Procedure details

All fields are explicit and editable.

Suggested fields:

- Procedure date and time
- Operator
- Procedure name
- Injectate
- Concentration
- Volume per point
- Total volume
- Needle specification
- Skin preparation
- Guidance method, if applicable
- Patient tolerance
- Immediate complications
- Additional procedure notes
- Manual plan text

Presets may be available for repetitive wording, but no preset is automatically selected.

## Procedure summary

The summary is rendered only from physician-entered data and mapped injection points.

Example:

```text
Trigger point injections were performed at 3 physician-marked sites in the
left upper trapezius region. The selected injectate was 0.5% lidocaine,
0.5 mL per site. The patient tolerated the procedure without an immediate
complication.
```

The physician must be able to edit the entire summary before copying or exporting it.

The renderer must not add claims that are not explicitly represented by a selected field or entered text.

## Plan field

The PDF may include a plan section, but it is strictly manual physician-authored text.

Procedures must not:

- Offer plan choices
- Suggest stretching, medication, follow-up, or precautions
- Infer a plan from the procedure
- Generate plan text automatically

An empty plan field is omitted from the PDF.

## One-page PDF design

The primary export is a simple one-page PDF optimized for rapid visual review.

Recommended layout:

```text
┌─────────────────────────────────────────────────────────────┐
│ Trigger Point Injection                                     │
│ Date / operator / patient identifiers                       │
├─────────────────────────────────────────────────────────────┤
│ Upper third: whole-body pain overview                       │
│ - anterior and/or posterior body view                       │
│ - red pain distribution                                    │
├─────────────────────────────────────────────────────────────┤
│ Middle third: regional close-up                             │
│ - red pain distribution                                    │
│ - blue injection markers                                   │
├─────────────────────────────────────────────────────────────┤
│ Lower third: procedure summary                             │
│ - number and location of sites                             │
│ - injectate and other entered details                      │
│ - tolerance/complication text when selected                │
│ - manual plan text when entered                            │
└─────────────────────────────────────────────────────────────┘
```

### Visual rules

- Red is always pain.
- Blue is always an injection site.
- Never reverse these colors.
- Include a small legend.
- Keep the background neutral and printable.
- Use clear line art rather than decorative illustration.
- Avoid dense text.
- Fit the record on one page whenever possible.
- Preserve readability in grayscale by adding shape or pattern distinctions where feasible.

## Outputs

Procedures produces three outputs:

### 1. Structured source data

The editable internal record containing:

- Diagram identifiers and versions
- Red pain regions or paths
- Blue injection coordinates
- Optional anatomical labels
- Procedure fields
- Edited procedure summary
- Manual plan text

### 2. Procedure note

Editable text suitable for copying into eGHIS.

### 3. Visual PDF

A rendered clinical procedure summary suitable for visual follow-up and optional KaosPACS archival.

## Suggested data model

```yaml
procedure_type: trigger_point_injection
anatomy_asset_version: v1
views:
  - view_id: posterior_whole_body
    pain_paths:
      - points: []
  - view_id: left_posterior_neck_closeup
    pain_paths:
      - points: []
    injection_points:
      - x: 0.42
        y: 0.31
        anatomical_label: left_upper_trapezius
      - x: 0.47
        y: 0.36
        anatomical_label: left_upper_trapezius
procedure:
  injectate: "0.5% lidocaine"
  volume_per_point_ml: 0.5
  total_volume_ml: 1.0
  needle: ""
  preparation: ""
  tolerance: ""
  immediate_complications: ""
summary_text: ""
plan_text: ""
```

Coordinates should be normalized to the underlying diagram dimensions so maps remain stable across display sizes and PDF rendering.

## Anatomical asset requirements

Initial implementation should use a restrained set of original vector diagrams.

Minimum assets:

- Whole body anterior
- Whole body posterior
- Posterior neck and upper back close-up
- Shoulder/periscapular close-up
- Thoracic and lumbar posterior close-up
- Gluteal close-up

Preferred format:

- SVG source
- Stable viewBox
- Named anatomical regions where useful
- Separate neutral line art from user-created overlays
- Versioned assets to preserve old records

Old records must continue rendering with the asset version used when they were created.

## User interface

```text
Trigger Point Injection
├── 1. Pain overview
│   ├── Anterior
│   ├── Posterior
│   ├── Paint red
│   ├── Erase
│   └── Select region
├── 2. Regional map
│   ├── Red pain overlay
│   ├── Add blue injection point
│   ├── Move/remove point
│   └── Point count
├── 3. Procedure details
│   ├── Injectate
│   ├── Volume
│   ├── Needle/preparation
│   ├── Tolerance/complications
│   └── Manual notes and plan
└── 4. Review and export
    ├── Editable procedure summary
    ├── PDF preview
    ├── Copy procedure note
    ├── Save PDF
    └── Upload to KaosPACS
```

## KaosPACS integration

PDF upload is optional.

KaosPACS should receive a generated PDF through a defined integration boundary rather than direct database access.

The upload workflow should:

1. Generate the final PDF.
2. Validate required patient and encounter identifiers.
3. Create appropriate DICOM metadata for the encapsulated document.
4. Send the document through the KaosPACS integration path.
5. Confirm success before marking the record archived.
6. Preserve the local structured source record independently of PACS upload status.

The exact DICOM encapsulated-PDF contract remains an implementation design item.

## Relationship with eGHIS

Procedures does not write directly to the eGHIS database.

The Macro Engine may:

- Activate the known eGHIS window
- Navigate to the appropriate chart field
- Paste the physician-reviewed procedure summary

PDF archival in KaosPACS and text transfer to eGHIS are separate actions with separate results.

## Follow-up use

During a later visit, the physician may open prior TPI PDFs from the patient timeline and rapidly compare:

- Previous pain distribution
- Previous injection locations
- Changes in treated regions
- Procedure details

A future version may display prior maps as overlays, but this is not required for the first implementation.

## Safety and record integrity

- Start every new procedure with an empty map.
- Never carry pain or injection markings into a new encounter automatically.
- Require explicit physician review before PDF generation.
- Allow correction before finalization.
- Record diagram asset version.
- Record generation timestamp.
- Do not silently modify a finalized PDF.
- A corrected record should generate a new version with an audit reference to the previous version.

## Initial implementation phases

### Phase 1: mapping prototype

- Whole-body posterior map
- One posterior neck/upper-back regional map
- Red pain painting
- Blue injection markers
- Undo and clear
- Structured local save

### Phase 2: procedure record

- Procedure detail fields
- Deterministic summary renderer
- Editable summary
- One-page PDF generation

### Phase 3: workflow integration

- eGHIS copy/paste through Macro Engine
- Additional original anatomical diagrams
- Local record history

### Phase 4: KaosPACS archival

- Encapsulated PDF contract
- Upload and status handling
- Patient timeline validation

## Future procedures

The module name permits future procedure types, but none are committed for the first release.

Possible future workflows may include:

- Joint injection
- Prolotherapy
- Tendon or tendon-sheath injection

Each future procedure requires its own clinical fields, diagrams, renderer, and review. It must not be treated as a trivial variant of TPI.

## Non-goals

KaosEghis Procedures is not:

- Clinical decision support
- An injection-site recommendation tool
- An anatomy teaching application
- Ultrasound guidance
- An Assessment or Plan generator
- An order-entry system
- A billing or coding assistant
- A replacement for physician documentation review

## Summary

KaosEghis Procedures provides a visual, physician-authored procedure record.

The initial Trigger Point Injection workflow combines a whole-body red pain overview, a close-up map with red pain and blue injection sites, an editable procedure summary, optional manual plan text, and a one-page PDF that may be archived in KaosPACS.
