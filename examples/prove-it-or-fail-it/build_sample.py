"""Rebuild the sample outputs from the sample inputs.

Usage (repo root):  python examples/prove-it-or-fail-it/build_sample.py

Runs the same steps the skill runs: the design with the rubric and the plan, the lint, the design tool, the
day-30 read, the lint of both readouts, and the read tool. Standard library only.
"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "..", "skills", "prove-it-or-fail-it", "scripts")
P = lambda f: os.path.join(HERE, f)


def run(*args):
    subprocess.run([sys.executable, "-B", *args], check=True)


with tempfile.TemporaryDirectory() as d:
    design, read = os.path.join(d, "design.json"), os.path.join(d, "read_day30.json")
    run(os.path.join(SCRIPTS, "verdict.py"), "design", P("sample_idea.json"), "--rubric", P("sample_rubric.json"),
        "--plan", P("sample_plan.json"), "--json", design, "--card", P("sample_card.json"))
    run(os.path.join(SCRIPTS, "lint_plan.py"), design, "--idea", P("sample_idea.json"), "--text", P("sample_readout_ceo.md"))
    run(os.path.join(SCRIPTS, "build_tool.py"), design, "--role", "ceo", "--out", P("sample_tool.html"), "--markdown", P("sample_test_plan.md"))
    run(os.path.join(SCRIPTS, "verdict.py"), "read", P("sample_card.json"), P("sample_results_day30.json"), "--json", read)
    run(os.path.join(SCRIPTS, "lint_plan.py"), read, "--text", P("sample_readout_day30_ceo.md"))
    run(os.path.join(SCRIPTS, "build_tool.py"), read, "--role", "ceo", "--out", P("sample_tool_day30.html"), "--markdown", P("sample_read_day30.md"))
