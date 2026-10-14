"""Generate the compact AgentPad Rev.2 production package."""

import os
import runpy
from pathlib import Path

os.environ["AGENTPAD_REV"] = "2"
os.environ["AGENTPAD_SINGLE_PCB"] = "1"
os.environ.setdefault("AGENTPAD_PANEL_PROFILE_MODE", "continuous")
runpy.run_path(str(Path(__file__).with_name("generate_agentpad_rev1.py")), run_name="__main__")
