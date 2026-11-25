"""Source plugin entry point; catalogue use needs only the host Python."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hss.mcp import serve

serve()
