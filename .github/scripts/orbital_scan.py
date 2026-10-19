"""Orbital scan: the contribution calendar as a HUD panel.

A ship flies along the top of the grid with a scan beam under it. As the beam
crosses a week, every day with contributions in that week flashes orange: a
target lock. Below the grid, a readout of the real totals.

Standard library only, so the workflow needs nothing installed.

    GITHUB_TOKEN=... GH_USER=Abubakr-Alsheikh python orbital_scan.py dist/orbital-scan.svg

Pass --data calendar.json to render from a saved GraphQL response instead.
"""
import json
import os
import sys
import urllib.request
from datetime import date

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel weekday } }
      }
    }
  }
}
"""

BG = "#020617"
LINE = "#1e293b"
GRID = "#0b1324"
SLATE4 = "#94A3B8"
SLATE5 = "#64748B"
WHITE = "#F1F5F9"
BLUE = "#3B82F6"
ORANGE = "#F97316"
MONO = "'JetBrains Mono','Cascadia Mono','SF Mono',Consolas,'Liberation Mono',Menlo,monospace"
LEVELS = {
    "NONE": "#0b1324",
    "FIRST_QUARTILE": "#1e3a8a",
    "SECOND_QUARTILE": "#1d4ed8",
    "THIRD_QUARTILE": "#3b82f6",
    "FOURTH_QUARTILE": "#93c5fd",
}

CYCLE = 12.0          # seconds per pass
SCAN_FROM, SCAN_TO = 0.06, 0.70   # share of the cycle the beam spends crossing the grid
CELL, GAP = 13, 3
STEP = CELL + GAP


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


def streaks(days):
    longest = current = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)
    # Current streak counts back from the last day, allowing today to be empty.
    tail = list(reversed(days))
    if tail and tail[0]["contributionCount"] == 0:
        tail = tail[1:]
    for d in tail:
        if d["contributionCount"] == 0:
            break
        current += 1
    return longest, current


def render(payload, login):
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    total = cal["totalContributions"]
    best = max(days, key=lambda d: d["contributionCount"])
    longest, current = streaks(days)

    cols = len(weeks)
    X0, Y0 = 72, 92
    grid_w = cols * STEP - GAP
    grid_h = 7 * STEP - GAP
    W = X0 + grid_w + 56
    H = Y0 + grid_h + 96

    scan_start = CYCLE * SCAN_FROM
    scan_len = CYCLE * (SCAN_TO - SCAN_FROM)

    cells, locks, css = [], [], []
    for c, week in enumerate(weeks):
        # Time the beam's centre crosses this column, minus the flash's rise.
        delay = scan_start + scan_len * (c + 0.5) / cols - CYCLE * 0.02
        css.append(f".k{c}{{animation-delay:{delay:.2f}s}}")
        for d in week["contributionDays"]:
            x = X0 + c * STEP
            y = Y0 + d["weekday"] * STEP
            fill = LEVELS.get(d["contributionLevel"], LEVELS["NONE"])
            stroke = f' stroke="{LINE}"' if d["contributionLevel"] == "NONE" else ""
            cells.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{fill}"{stroke}/>')
            if d["contributionCount"] > 0:
                locks.append(
                    f'<rect class="lock k{c}" x="{x - 1.5}" y="{y - 1.5}" width="{CELL + 3}" '
                    f'height="{CELL + 3}" fill="{ORANGE}" fill-opacity=".85" stroke="{ORANGE}"/>'
                )

    # Month labels on the first week of each month.
    months, last = [], None
    for c, week in enumerate(weeks):
        first = date.fromisoformat(week["contributionDays"][0]["date"])
        if first.month != last and c < cols - 1:
            if last is not None or first.day <= 7:
                months.append(
                    f'<text x="{X0 + c * STEP}" y="{Y0 - 12}" class="mono" font-size="10" '
                    f'letter-spacing="1" fill="{SLATE5}">{first.strftime("%b").upper()}</text>'
                )
            last = first.month
    day_labels = "".join(
        f'<text x="{X0 - 12}" y="{Y0 + r * STEP + 10}" text-anchor="end" class="mono" font-size="10" fill="{SLATE5}">{n}</text>'
        for r, n in ((1, "MON"), (3, "WED"), (5, "FRI"))
    )

    ship_y = Y0 - 46
    beam_top = ship_y + 10
    beam_h = Y0 + grid_h + 8 - beam_top
    pct = lambda f: f"{f * 100:.2f}%"
    legend_x = W - 56 - 5 * 16 - 74
    legend = "".join(
        f'<rect x="{legend_x + 42 + i * 16}" y="{H - 30}" width="12" height="12" fill="{c}"'
        f'{f" stroke={chr(34)}{LINE}{chr(34)}" if i == 0 else ""}/>'
        for i, c in enumerate(LEVELS.values())
    )
    best_day = date.fromisoformat(best["date"]).strftime("%d %b %Y").upper()

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">Orbital scan of {login}'s contributions</title>
  <desc id="d">{total} contributions in the last year. Best day: {best["contributionCount"]} on {best["date"]}. Longest streak: {longest} days. Current streak: {current} days.</desc>
  <style>
    .mono {{ font-family: {MONO}; }}
    .ship {{ animation: fly {CYCLE}s linear infinite; }}
    .flame {{ animation: flame .18s steps(2, end) infinite; }}
    .lock {{ opacity: 0; animation: lock {CYCLE}s linear infinite both; }}
    .blink {{ animation: blink 1.6s ease-in-out infinite; }}
    @keyframes fly {{
      0% {{ transform: translateX(-90px); opacity: 0; }}
      {pct(SCAN_FROM - 0.03)} {{ opacity: 1; }}
      {pct(SCAN_FROM)} {{ transform: translateX(0px); }}
      {pct(SCAN_TO)} {{ transform: translateX({grid_w}px); }}
      {pct(SCAN_TO + 0.06)} {{ transform: translateX({grid_w + 160}px); opacity: 0; }}
      100% {{ transform: translateX({grid_w + 160}px); opacity: 0; }}
    }}
    @keyframes lock {{ 0% {{ opacity: 0; }} 2% {{ opacity: 1; }} 9% {{ opacity: 0; }} 100% {{ opacity: 0; }} }}
    @keyframes flame {{ 50% {{ transform: scaleX(.55); }} }}
    @keyframes blink {{ 0%, 100% {{ opacity: .3; }} 50% {{ opacity: 1; }} }}
    {"".join(css)}
    @media (prefers-reduced-motion: reduce) {{
      .ship, .flame, .lock, .blink {{ animation: none; }}
      .ship {{ display: none; }}
    }}
  </style>
  <defs>
    <linearGradient id="beam" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{BLUE}" stop-opacity="0"/>
      <stop offset=".5" stop-color="{BLUE}" stop-opacity=".28"/>
      <stop offset="1" stop-color="{BLUE}" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" fill="{BG}" stroke="{LINE}"/>
  <g fill="none" stroke="{BLUE}" stroke-width="2">
    <path d="M6 28V6h22"/><path d="M{W - 28} 6h22v22"/>
    <path d="M6 {H - 28}v22h22"/><path d="M{W - 28} {H - 6}h22v-22"/>
  </g>

  <text x="{X0}" y="30" class="mono" font-size="12" letter-spacing="3" fill="{SLATE4}">&#9656; ORBITAL SCAN // CONTRIBUTION FIELD</text>
  <circle class="blink" cx="{W - 208}" cy="26" r="3.5" fill="{ORANGE}"/>
  <text x="{W - 40}" y="30" text-anchor="end" class="mono" font-size="12" letter-spacing="3" fill="{BLUE}">LAST 12 MONTHS</text>

  <!-- flight rail -->
  <line x1="{X0}" y1="{ship_y}" x2="{X0 + grid_w}" y2="{ship_y}" stroke="{LINE}" stroke-dasharray="2 6"/>

  {"".join(months)}
  {day_labels}
  <g>{"".join(cells)}</g>
  <g>{"".join(locks)}</g>

  <!-- ship and its scan beam travel together -->
  <g class="ship">
    <rect x="{X0 - 9}" y="{beam_top}" width="{CELL + 18}" height="{beam_h}" fill="url(#beam)"/>
    <line x1="{X0 + CELL / 2}" y1="{beam_top}" x2="{X0 + CELL / 2}" y2="{beam_top + beam_h}" stroke="{BLUE}" stroke-opacity=".5"/>
    <g transform="translate({X0 + CELL / 2} {ship_y})">
      <g class="flame" style="transform-origin: -10px 0px">
        <path d="M-10 -3 L-26 0 L-10 3 Z" fill="{ORANGE}"/>
      </g>
      <path d="M-12 -7 L14 0 L-12 7 L-7 0 Z" fill="{BG}" stroke="{BLUE}" stroke-width="1.6" stroke-linejoin="round"/>
      <rect x="-3" y="-1.5" width="5" height="3" fill="{ORANGE}"/>
    </g>
  </g>

  <!-- readout -->
  <line x1="{X0}" y1="{H - 52}" x2="{W - 40}" y2="{H - 52}" stroke="{LINE}"/>
  <text x="{X0}" y="{H - 20}" class="mono" font-size="12" letter-spacing="1" fill="{SLATE4}">TOTAL <tspan fill="{WHITE}">{total:,}</tspan>   ·   BEST DAY <tspan fill="{WHITE}">{best["contributionCount"]}</tspan> <tspan fill="{SLATE5}">{best_day}</tspan>   ·   LONGEST STREAK <tspan fill="{WHITE}">{longest}d</tspan>   ·   CURRENT <tspan fill="{ORANGE}">{current}d</tspan></text>
  <text x="{legend_x}" y="{H - 20}" class="mono" font-size="10" fill="{SLATE5}">LESS</text>
  {legend}
  <text x="{legend_x + 42 + 5 * 16 + 4}" y="{H - 20}" class="mono" font-size="10" fill="{SLATE5}">MORE</text>
</svg>
'''
    return svg


def main():
    args = sys.argv[1:]
    out = args[0] if args else "dist/orbital-scan.svg"
    login = os.environ.get("GH_USER", "Abubakr-Alsheikh")
    if "--data" in args:
        payload = json.load(open(args[args.index("--data") + 1], encoding="utf-8"))
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise SystemExit("GITHUB_TOKEN is not set")
        payload = fetch(login, token)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(payload, login))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
