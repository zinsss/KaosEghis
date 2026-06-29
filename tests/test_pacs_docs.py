from pathlib import Path


def test_pacs_docs_reference_current_architecture() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    pacs_doc = (repo_root / "docs" / "kaoseghis-pacs.md").read_text(encoding="utf-8")
    readiness_doc = (repo_root / "PACS_PRODUCTION_READINESS.md").read_text(
        encoding="utf-8"
    )

    assert "KaosEghis-pacs communicates only through the KaosPACS local API." in pacs_doc
    assert "KaosEghis-pacs never writes directly to DICOM." in pacs_doc
    assert "KaosEghis-pacs never writes directly into Orthanc." in pacs_doc
    assert "Eghis DB access is read-only." in pacs_doc
    assert "resident registration number" in pacs_doc
    assert "audit logs intentionally exclude sensitive patient information" in pacs_doc.lower()
    assert "Plugins UI" in readiness_doc
    assert "Local audit" in readiness_doc
    assert "No authentication layer between KaosEghis and local KaosPACS" in readiness_doc
