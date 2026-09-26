"""Rebuild the sample outputs from the sample inputs.

Usage (repo root):  python examples/campaign-brief-builder/build_sample.py

Runs the same steps the skill runs: check with the rubric, build the brief, lint it, build the tool,
the Markdown brief and the requirements CSV. Standard library only.
"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "..", "skills", "campaign-brief-builder", "scripts")
P = lambda f: os.path.join(HERE, f)


def run(*args):
    subprocess.run([sys.executable, *args], check=True)


with tempfile.TemporaryDirectory() as d:
    res, br = os.path.join(d, "result.json"), os.path.join(d, "brief_result.json")
    run(os.path.join(SCRIPTS, "plan.py"), "check", P("sample_strategy.json"), "--rubric", P("sample_rubric.json"), "--json", res)
    run(os.path.join(SCRIPTS, "plan.py"), "brief", res, P("sample_brief.json"), "--json", br)
    run(os.path.join(SCRIPTS, "lint_brief.py"), br, "--strategy", P("sample_strategy.json"))
    run(os.path.join(SCRIPTS, "build_tool.py"), br, "--role", "ceo", "--out", P("sample_tool.html"),
        "--markdown", P("sample_brief.md"), "--csv", P("sample_requirements.csv"))
