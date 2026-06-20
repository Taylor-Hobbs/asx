"""Dump relevant sections of CSL investor presentation to verify what EPS is present."""
import google.cloud.storage as storage
from asx_engine.config import load_settings
from asx_engine.parsing.pdf import PARSER_VERSION, ParsedDocument

settings = load_settings()
bucket = storage.Client(project=settings.gcp_project).bucket(settings.gcs_raw_bucket)

h = "76707846d52cbd919a64ccf6fa7677a28341b754b58164a5e912e4db625637dd"
blob = bucket.blob(f"parsed/{PARSER_VERSION}/{h}.json")
text = ParsedDocument.model_validate_json(bytes(blob.download_as_bytes())).text()

keywords = ["eps", "earnings per share", "per share", "dividend", "cents", "diluted", "basic", "npat eps", "npata"]
lines = text.split("\n")
for i, l in enumerate(lines):
    if any(kw in l.lower() for kw in keywords):
        print(f"{i:4d}: {l.strip()}")
