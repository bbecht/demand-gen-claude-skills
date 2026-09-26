#!/usr/bin/env python3
"""Build the interactive Pipeline Leak Finder tool from analyze.py output.

Usage: python build_tool.py result.json --role ceo|cro|revops|marketing --out leak_finder.html
"""
import json, os, sys

ROLES = ("ceo", "cro", "revops", "marketing")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("stop"):
        sys.exit("Analysis stopped: " + data["stop"])
    role = sys.argv[sys.argv.index("--role") + 1] if "--role" in sys.argv else "ceo"
    role = role if role in ROLES else "ceo"
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "leak_finder.html"
    tpl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "tool_template.html")
    with open(tpl_path, encoding="utf-8") as fh:
        tpl = fh.read()
    blob = json.dumps(data, default=str, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace("/*__DATA__*/null", blob).replace('/*__ROLE__*/"ceo"', json.dumps(role))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("Tool written to " + out)


if __name__ == "__main__":
    main()
