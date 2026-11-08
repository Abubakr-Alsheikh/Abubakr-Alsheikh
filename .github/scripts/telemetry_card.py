"""System telemetry: the profile's stats card, drawn here instead of fetched.

The README used to embed the public github-readme-stats instance. That
deployment is paused and answers 503, so the card showed as a broken image.
This script draws the same kind of card in the HUD style from one GraphQL
query and publishes it beside the orbital scan.

Numbers cover the last 12 months, the window GitHub's contribution calendar
uses. Languages are measured in bytes across the owner's public, non-fork
repositories, with markup, styles and notebooks left out so the bar shows the
code. The card is static: nothing on it moves.

Standard library only, so the workflow needs nothing installed.

    GITHUB_TOKEN=... GH_USER=Abubakr-Alsheikh python telemetry_card.py dist/telemetry.svg

Pass --data stats.json to render from a saved GraphQL response instead.
"""
import json
import os
import sys
import urllib.request
from collections import Counter

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar { totalContributions }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

BG = "#020617"
PANEL = "#0F172A"
LINE = "#1e293b"
SLATE4 = "#94A3B8"
SLATE5 = "#64748B"
WHITE = "#F1F5F9"
BLUE = "#3B82F6"
ORANGE = "#F97316"
MONO = "'JetBrains Mono','Cascadia Mono','SF Mono',Consolas,'Liberation Mono',Menlo,monospace"

# Not code: left out of the language bar.
NOT_CODE = {"HTML", "CSS", "SCSS", "Less", "Jupyter Notebook"}
# The bar's colours, strongest first, in the profile's palette.
RAMP = [ORANGE, BLUE, "#93C5FD", SLATE4, "#475569"]
SHOWN = 5

W, H = 495, 195


def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        payload = json.load(res)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload


def languages(repos):
    """The top languages as (name, share of all code bytes), largest first."""
    sizes = Counter()
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name not in NOT_CODE:
                sizes[name] += edge["size"]
    total = sum(sizes.values()) or 1
    return [(name, size / total) for name, size in sizes.most_common(SHOWN)]


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(user):
    cc = user["contributionsCollection"]
    metrics = [
        ("CONTRIBUTIONS", cc["contributionCalendar"]["totalContributions"], ORANGE),
        ("COMMITS", cc["totalCommitContributions"], WHITE),
        ("PULL REQUESTS", cc["totalPullRequestContributions"], WHITE),
        ("PUBLIC REPOS", user["repositories"]["totalCount"], WHITE),
    ]
    langs = languages(user["repositories"]["nodes"])

    pad = 24
    body = []
    # Frame, corner screws and the header.
    body.append(f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" fill="{BG}" stroke="{LINE}"/>')
    for x, y in ((4, 4), (W - 7, 4), (4, H - 7), (W - 7, H - 7)):
        body.append(f'<rect x="{x}" y="{y}" width="3" height="3" fill="#334155"/>')
    body.append(f'<rect x="{pad}" y="25" width="6" height="6" fill="{BLUE}"/>')
    body.append(f'<text x="{pad + 14}" y="31" class="mono" font-size="12" letter-spacing="3" fill="{SLATE4}">SYSTEM TELEMETRY</text>')
    body.append(f'<text x="{W - pad}" y="31" text-anchor="end" class="mono" font-size="10" letter-spacing="2" fill="{SLATE5}">LAST 12 MONTHS</text>')
    body.append(f'<line x1="{pad}" y1="44" x2="{W - pad}" y2="44" stroke="{LINE}"/>')

    # Four readouts in a row.
    cell = (W - 2 * pad) / len(metrics)
    for i, (label, value, colour) in enumerate(metrics):
        x = pad + i * cell
        if i:
            body.append(f'<line x1="{x - 10:.1f}" y1="58" x2="{x - 10:.1f}" y2="100" stroke="{LINE}"/>')
        body.append(f'<text x="{x:.1f}" y="67" class="mono" font-size="10" letter-spacing="1" fill="{SLATE5}">{label}</text>')
        body.append(f'<text x="{x:.1f}" y="96" class="mono" font-size="26" font-weight="600" fill="{colour}">{value:,}</text>')

    # Language bar: segments in proportion, the rest of the code in a dim tail.
    body.append(f'<line x1="{pad}" y1="116" x2="{W - pad}" y2="116" stroke="{LINE}"/>')
    body.append(f'<text x="{pad}" y="134" class="mono" font-size="10" letter-spacing="1" fill="{SLATE5}">LANGUAGES · PUBLIC CODE</text>')
    bar_w = W - 2 * pad
    body.append(f'<rect x="{pad}" y="143" width="{bar_w}" height="6" fill="{PANEL}"/>')
    x = pad
    for (name, share), colour in zip(langs, RAMP):
        w = bar_w * share
        body.append(f'<rect x="{x:.1f}" y="143" width="{max(w - 2, 1):.1f}" height="6" fill="{colour}"/>')
        x += w

    # Legend.
    x = pad
    for (name, share), colour in zip(langs, RAMP):
        label = f"{esc(name.upper())} {share * 100:.0f}%"
        body.append(f'<rect x="{x}" y="163" width="6" height="6" fill="{colour}"/>')
        body.append(f'<text x="{x + 11}" y="169" class="mono" font-size="10" fill="{SLATE4}">{label}</text>')
        x += 11 + len(label) * 6.1 + 13

    summary = ", ".join(f"{label.lower()} {value:,}" for label, value, _ in metrics)
    lang_text = ", ".join(f"{name} {share * 100:.0f}%" for name, share in langs)
    shapes = "\n  ".join(body)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="st sd">
  <title id="st">System telemetry</title>
  <desc id="sd">Last 12 months: {summary}. Languages in public code: {lang_text}.</desc>
  <style>.mono {{ font-family: {MONO}; }}</style>
  {shapes}
</svg>
'''


def main():
    args = sys.argv[1:]
    if "--data" in args:
        i = args.index("--data")
        payload = json.load(open(args[i + 1], encoding="utf-8"))
        del args[i : i + 2]
    else:
        payload = fetch(os.environ["GH_USER"], os.environ["GITHUB_TOKEN"])
    out = args[0]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(payload["data"]["user"]))
    print("written", out)


if __name__ == "__main__":
    main()
