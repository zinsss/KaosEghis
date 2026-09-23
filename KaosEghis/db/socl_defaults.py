from __future__ import annotations


SOCL_CATALOG_VERSION = "1"

SOCL_DEFAULT_COLLECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("subjective", "Shared details", (
        "onset", "duration", "frequency", "course", "recurrence", "location",
        "laterality", "severity", "quality", "aggravating factors",
        "relieving factors", "triggers", "associated symptoms",
        "explicit negatives", "custom free text",
    )),
    ("subjective", "Constitutional", (
        "fever", "chills", "fatigue", "weakness", "myalgia", "appetite loss",
        "weight change", "night sweats",
    )),
    ("subjective", "Nose/sinus", (
        "rhinorrhea", "congestion", "sneezing", "postnasal drip",
        "facial pressure/pain", "smell change", "epistaxis",
    )),
    ("subjective", "Throat/oral/voice", (
        "sore throat", "odynophagia", "dysphagia", "hoarseness", "oral lesion",
        "dry mouth",
    )),
    ("subjective", "Respiratory", (
        "cough", "dry/productive cough", "sputum", "dyspnea", "wheezing",
        "pleuritic pain", "hemoptysis",
    )),
    ("subjective", "Ear", (
        "otalgia", "fullness", "hearing change", "tinnitus", "discharge",
    )),
    ("subjective", "Eye", (
        "redness", "pain", "itching", "discharge", "tearing", "blurred vision",
        "diplopia", "photophobia", "foreign-body sensation",
    )),
    ("subjective", "Headache", (
        "headache", "facial pain", "nausea", "vomiting", "photophobia",
        "phonophobia", "aura", "visual change", "neck pain",
    )),
    ("subjective", "Dizziness", (
        "vertigo", "lightheadedness", "imbalance", "presyncope", "syncope",
        "positional symptoms", "nausea",
    )),
    ("subjective", "Cardiovascular", (
        "chest pain/discomfort", "palpitations", "exertional dyspnea", "orthopnea",
        "nocturnal dyspnea", "edema", "syncope",
    )),
    ("subjective", "Upper GI", (
        "epigastric pain", "heartburn", "regurgitation", "nausea", "vomiting",
        "bloating", "belching", "early satiety",
    )),
    ("subjective", "Abdominal/bowel", (
        "abdominal pain", "diarrhea", "constipation", "stool change",
        "hematochezia", "melena", "mucus", "tenesmus",
    )),
    ("subjective", "Urinary", (
        "dysuria", "frequency", "urgency", "nocturia", "hematuria",
        "suprapubic pain", "flank pain", "hesitancy", "weak stream", "incontinence",
    )),
    ("subjective", "Musculoskeletal", (
        "regional pain", "stiffness", "swelling", "warmth", "limited movement",
        "weakness", "radiation", "injury",
    )),
    ("subjective", "Neurologic", (
        "focal weakness", "numbness", "paresthesia", "tremor", "gait change",
        "speech change", "confusion", "seizure-like event",
    )),
    ("subjective", "Skin", (
        "rash", "itching", "pain", "burning", "swelling", "color change", "lesion",
        "bruising", "discharge", "hair/nail change",
    )),
    ("subjective", "Sleep/mood", (
        "insomnia", "hypersomnia", "snoring", "witnessed apnea", "depressed mood",
        "anxiety", "irritability", "anhedonia", "poor concentration",
    )),
    ("subjective", "Injury/wound", (
        "mechanism", "pain", "swelling", "bleeding", "movement limitation",
        "numbness", "wound discharge",
    )),
    ("subjective", "Reproductive/genital", (
        "menstrual change", "abnormal bleeding/discharge", "pelvic pain",
        "pregnancy concern", "genital pain/discharge",
    )),
    ("subjective", "Other", (
        "patient's own wording", "unrestricted custom text",
    )),
    ("objective", "Vitals/general", (
        "BP", "pulse", "respiration", "temperature", "oxygen saturation", "weight",
        "alertness", "distress", "hydration", "overall appearance",
    )),
    ("objective", "Head/face/sinus", (
        "symmetry", "swelling", "lesion", "mass", "frontal/maxillary tenderness",
    )),
    ("objective", "Eyes", (
        "lids", "conjunctiva", "sclera", "pupils", "light response",
        "extraocular movement", "discharge", "visual acuity",
    )),
    ("objective", "Ears", (
        "external ear", "tragal/mastoid tenderness", "canal", "cerumen",
        "tympanic membrane", "effusion", "discharge",
    )),
    ("objective", "Nose", (
        "mucosa", "turbinates", "septum", "discharge", "obstruction", "bleeding",
    )),
    ("objective", "Mouth/pharynx", (
        "oral mucosa", "teeth/gums", "tongue", "palate", "pharyngeal erythema",
        "exudate", "tonsil size/asymmetry", "uvula",
    )),
    ("objective", "Neck/thyroid/lymph", (
        "neck symmetry", "ROM", "rigidity", "mass", "thyroid enlargement/tenderness",
        "cervical nodes",
    )),
    ("objective", "Respiratory", (
        "respiratory effort", "accessory-muscle use", "chest expansion",
        "breath sounds", "wheeze", "crackles", "rhonchi", "decreased sounds",
    )),
    ("objective", "Cardiovascular", (
        "rate", "rhythm", "heart sounds", "murmur", "peripheral pulses",
        "capillary refill", "edema", "skin temperature",
    )),
    ("objective", "Abdomen", (
        "contour", "bowel sounds", "softness/rigidity", "tenderness by location",
        "guarding", "rebound", "mass", "liver/spleen", "CVA tenderness",
    )),
    ("objective", "Musculoskeletal", (
        "inspection", "focal tenderness", "swelling", "warmth", "active/passive ROM",
        "strength", "gait", "complaint-specific tests",
    )),
    ("objective", "Neurologic", (
        "orientation", "speech", "cranial nerves", "motor strength", "sensation",
        "reflexes", "coordination", "gait/balance",
    )),
    ("objective", "Skin/wound", (
        "location", "morphology", "distribution", "size", "color", "warmth",
        "tenderness", "blanching", "fluctuance", "drainage",
    )),
    ("objective", "Psychiatric", (
        "appearance", "behavior", "speech", "mood", "affect", "thought process",
        "attention", "orientation",
    )),
    ("objective", "GU/reproductive", (
        "complaint-specific external findings", "complaint-specific pelvic findings",
        "complaint-specific prostate findings",
    )),
)
