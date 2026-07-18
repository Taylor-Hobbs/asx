"""Apply hand-written golden labels for the 25 guidance documents.

Labels authored 2026-07-18 by Claude from parsed text per golden/guidance/
README.md conventions; Taylor audits >=20% against PDFs before the set is
trusted. S = (direction, metric, basis, period, range_low_aud, range_high_aud).
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def S(direction, metric, basis, period, lo=None, hi=None):
    return {"direction": direction, "metric": metric, "basis": basis,
            "period": period, "range_low_aud": lo, "range_high_aud": hi}


LABELS = {
    "b593bbe8": [  # SGP upgrades FY25
        S("upgrade", "FFO per security", "post-tax", "FY25"),
        S("upgrade", "MPC settlement volumes", None, "FY25"),
        S("affirmed", "Land Lease Communities settlements", None, "FY25"),
        S("affirmed", "Distribution per security", None, "FY25"),
    ],
    "52299438": [  # TLX Q2 2024
        S("upgrade", "revenue", None, "FY2024"),
        S("affirmed", "R&D expenditure", None, "2024"),
    ],
    "7355a948": [S("upgrade", "revenue", None, "FY 2025")],  # TLX Q3 2025
    "16a421f2": [S("upgrade", "Profit Growth", "Before Tax", "FY25")],  # TNE HY
    "bac3d698": [  # TNE AGM upgrade
        S("upgrade", "PBT growth", None, "FY26"),
        S("initiated", "ARR growth", None, "FY26"),
        S("initiated", "PBT growth", None, "H1 FY26"),
    ],
    "574e2bc6": [  # RMS quarterly presentation
        S("initiated", "Gold production", None, "FY25"),
        S("initiated", "AISC", None, "FY25"),
        S("initiated", "Exploration expenditure", None, "FY25", 40000000, 50000000),
    ],
    "97688298": [  # RMS FY25 guidance release
        S("initiated", "Gold production", None, "FY25"),
        S("initiated", "All-in sustaining cost (AISC)", None, "FY25"),
        S("initiated", "Growth capital", None, "FY25", 20000000, 30000000),
        S("initiated", "Exploration & Resource definition", None, "FY25",
          40000000, 50000000),
    ],
    "d0ec0fbe": [  # RMS 5-year pathway
        S("initiated", "Gold production", None, "FY26"),
        S("initiated", "AISC", None, "FY26"),
    ],
    "10176d57": [  # RMS Mar25 qtr refined
        S("upgrade", "Gold production", None, "FY25"),
        S("affirmed", "AISC", None, "FY25"),
    ],
    "3d5000d8": [  # RMS Mar26 qtr
        S("affirmed", "Gold production", None, "FY26"),
        S("downgrade", "AISC", None, "FY26"),
    ],
    "8667af79": [  # RWC tariffs
        S("initiated", "net cost impact of tariffs on operating earnings (EBITDA)",
          None, "FY26"),
        S("initiated", "direct impact of US tariffs on EBITDA", None, "FY27"),
        S("affirmed", "Americas external sales", None, "FY25"),
        S("downgrade", "Asia Pacific external sales", "excluding Holman", "FY25"),
        S("affirmed", "EMEA external sales", None, "FY25"),
        S("affirmed", "group external sales", None, "FY25"),
    ],
    "994fa303": [],  # RYM Q2 - tracking ahead, update to come: no statements
    "e9ea0b9a": [S("affirmed", "build guidance (retirement living units and aged care beds)",
                   None, "FY27")],  # RYM Q1 FY27
    "24c34d1a": [],  # RYM Q4 - completed period
    "07a55410": [  # RSG Syama
        S("affirmed", "Syama gold production", None, "2026"),
        S("downgrade", "Syama gold production", None, "Q2 2026"),
        S("affirmed", "Mako production", None, "full-year 2026"),
    ],
    "5ed55438": [],  # S32 2025 deck - JORC/feasibility targets only
    "45a90211": [],  # S32 2026 deck - same
    "5037db00": [  # SCG
        S("affirmed", "Funds from Operations", None, "2024"),
        S("affirmed", "Distributions", None, "2024"),
    ],
    "41b56969": [],  # RRL Jul25 - completed FY, guidance to come
    "5c723da7": [  # RRL FY27 guidance
        S("initiated", "Production", None, "FY27"),
        S("initiated", "All-In Sustaining Costs (AISC)", None, "FY27"),
        S("initiated", "Growth Capital", None, "FY27", 250000000, 270000000),
        S("initiated", "Exploration", None, "FY27", 80000000, 90000000),
        S("initiated", "McPhillamys", None, "FY27", 30000000, 35000000),
    ],
    "041db3d3": [],  # RRL top-end achieved - completed period
    "a4e71b80": [S("affirmed", "ORA sales", None, "FY26")],  # RYM Q3
    "9c144634": [  # SEK AGM
        S("affirmed", "Revenue", None, "FY25", 1020000000, 1140000000),
        S("affirmed", "EBITDA", None, "FY25", 430000000, 500000000),
        S("affirmed", "Adjusted NPAT", None, "FY25", 130000000, 180000000),
        S("upgrade", "total expenditure", None, "FY25", 760000000, 790000000),
        S("affirmed", "yield growth", None, "FY25"),
    ],
    "650bdff2": [],  # SEK/Xref business update - no guidance
    "0fbea995": [S("initiated", "Metal businesses EBIT", None, "Q1 FY25",
                   55000000, 55000000)],  # SGM
}

label_dir = Path("golden/guidance/labels")
applied = 0
for stub in label_dir.glob("*.json"):
    data = json.loads(stub.read_text(encoding="utf-8"))
    h8 = data["content_hash"][:8]
    if h8 not in LABELS:
        print(f"NO LABEL for {stub.name}")
        continue
    data["labels"] = {"statements": LABELS[h8]}
    data["status"] = "labeled"
    stub.write_text(json.dumps(data, indent=1), encoding="utf-8")
    applied += 1
print(f"applied {applied} labels ({sum(1 for v in LABELS.values() if not v)} empty-statement docs)")
