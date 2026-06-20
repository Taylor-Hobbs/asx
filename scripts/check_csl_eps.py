"""One-off: verify CSL EPS values in golden labels against parsed doc text."""
import google.cloud.storage as storage
from asx_engine.config import load_settings
from asx_engine.parsing.pdf import PARSER_VERSION, ParsedDocument

settings = load_settings()
bucket = storage.Client(project=settings.gcp_project).bucket(settings.gcs_raw_bucket)

hashes = [
    ("03058873", "fae5b57f14b33d166fc565095a1e23ec9f3394e885afa13b917762758d281e59"),
    ("03058874", "76707846d52cbd919a64ccf6fa7677a28341b754b58164a5e912e4db625637dd"),
    ("03058876", "c66b7defd763266ca0908e797c36d9a2d7b71445b592f3b14b43443a0d212a87"),
]

for ann_id, h in hashes:
    blob = bucket.blob(f"parsed/{PARSER_VERSION}/{h}.json")
    text = ParsedDocument.model_validate_json(bytes(blob.download_as_bytes())).text()
    lines = text.split("\n")
    keywords = ["eps", "earnings per share", "per share", "cents per", "diluted", "basic"]
    eps_lines = [l.strip() for l in lines if any(kw in l.lower() for kw in keywords)]
    print(f"=== {ann_id} ({h[:12]}) ===")
    for l in eps_lines[:30]:
        if l:
            print(f"  {l}")
    print()
