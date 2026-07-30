"""Shared rich theme for the viz scripts.

Every scripts/viz/ renderer imports its console, box style, and named styles
from here so the screenshots read as one family. Keep this file free of any
script-specific logic — it is width, colour, and box choices only.
"""

from rich import box
from rich.console import Console
from rich.theme import Theme

# All viz output fits a 100-column terminal — matches the repo's line-length
# and keeps screenshots consistently sized.
CONSOLE_WIDTH = 100

# One box style for every table in the family.
TABLE_BOX = box.SIMPLE_HEAVY

# Named styles, so scripts say what a value MEANS and the palette lives here:
#   gain / regression / flat — deltas and directional changes
#   gain_dim                 — quiet success (e.g. accuracy already above target)
#   warning                  — recoverable failure classes (e.g. missed fields)
#   champion                 — the highlighted best row
#   accent                   — headers and titles
#   muted                    — provenance lines, footnotes, empty cells
THEME = Theme(
    {
        "gain": "green",
        "gain_dim": "dim green",
        "regression": "red",
        "warning": "yellow",
        "flat": "dim",
        "champion": "bold",
        "accent": "bold cyan",
        "muted": "dim",
    }
)


def make_console() -> Console:
    """The one Console the viz scripts render to."""
    return Console(width=CONSOLE_WIDTH, theme=THEME)
