#!/usr/bin/env python3
"""Build the interactive marketing mix tool from run_mmm.py output.

Usage: python build_tool.py mmm.json --role ceo|cfo|marketing|analyst --out mmm_tool.html
"""
import json, os, sys

ROLES = ("ceo", "cfo", "marketing", "analyst")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("stop"):
        sys.exit("Analysis stopped: " + data["stop"])
    def arg(flag, default):
        i = sys.argv.index(flag) if flag in sys.argv else -1
        if i == len(sys.argv) - 1:
            print(f"{flag} needs a value. Using {default}.")
        return sys.argv[i + 1] if 0 <= i < len(sys.argv) - 1 else default
    role = arg("--role", "ceo").lower()
    if role not in ROLES:
        print(f"Unknown role '{role}', using ceo. Roles: " + ", ".join(ROLES))
        role = "ceo"
    out = arg("--out", "mmm_tool.html")
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
