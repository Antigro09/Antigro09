"""Render the profile's stats, top-languages, and trophy SVGs from GitHub API data.

Runs in Actions with GITHUB_TOKEN; writes dist/*.svg for publishing to the
output branch alongside the contribution snake.
"""

import json
import math
import os
import urllib.request

LOGIN = "Antigro09"
OUT_DIR = "dist"

CYAN = "#00D9FF"
NAVY = "#0A1220"
BORDER = "#1E3A5F"
MIST = "#8FB3C7"
GOLD = "#FFC533"
FONT = "'Fira Code','Cascadia Code','JetBrains Mono',Consolas,monospace"

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    pullRequests { totalCount }
    openIssues: issues(states: OPEN) { totalCount }
    closedIssues: issues(states: CLOSED) { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestReviewContributions
    }
    repositoriesContributedTo(
      first: 1
      contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
    ) { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER) {
      totalCount
      nodes {
        stargazerCount
        isFork
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch_user():
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={
            "Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def exponential_cdf(x):
    return 1 - 2 ** (-x)


def log_normal_cdf(x):
    return x / (1 + x)


def rank(stats):
    # Mirrors github-readme-stats' ranking: weighted CDFs over key metrics.
    params = [
        (stats["commits"], 250, 2, exponential_cdf),
        (stats["prs"], 50, 3, exponential_cdf),
        (stats["issues"], 25, 1, exponential_cdf),
        (stats["reviews"], 2, 1, exponential_cdf),
        (stats["stars"], 50, 4, log_normal_cdf),
        (stats["followers"], 10, 1, log_normal_cdf),
    ]
    total_weight = sum(w for _, _, w, _ in params)
    score = sum(w * cdf(v / m) for v, m, w, cdf in params) / total_weight
    percentile = (1 - score) * 100
    thresholds = [1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5]
    levels = ["S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"]
    level = levels[len([t for t in thresholds if percentile > t])]
    return level, percentile


STAT_ICONS = {
    "star": '<polygon points="8,1 10.2,5.8 15.2,6.3 11.4,9.7 12.5,14.7 8,12.1 3.5,14.7 4.6,9.7 0.8,6.3 5.8,5.8" fill="{c}"/>',
    "commit": '<circle cx="8" cy="8" r="3" fill="none" stroke="{c}" stroke-width="2"/><line x1="0" y1="8" x2="4.5" y2="8" stroke="{c}" stroke-width="2"/><line x1="11.5" y1="8" x2="16" y2="8" stroke="{c}" stroke-width="2"/>',
    "pr": '<circle cx="4" cy="3.5" r="2.2" fill="none" stroke="{c}" stroke-width="1.8"/><circle cx="4" cy="12.5" r="2.2" fill="none" stroke="{c}" stroke-width="1.8"/><line x1="4" y1="5.7" x2="4" y2="10.3" stroke="{c}" stroke-width="1.8"/><circle cx="12" cy="12.5" r="2.2" fill="none" stroke="{c}" stroke-width="1.8"/><path d="M12 10.3 V7 a3 3 0 0 0 -3 -3 h-1.5" fill="none" stroke="{c}" stroke-width="1.8"/>',
    "issue": '<circle cx="8" cy="8" r="6" fill="none" stroke="{c}" stroke-width="1.8"/><circle cx="8" cy="8" r="1.8" fill="{c}"/>',
    "contrib": '<rect x="1" y="1" width="6" height="6" rx="1" fill="{c}"/><rect x="9" y="1" width="6" height="6" rx="1" fill="{c}" opacity="0.6"/><rect x="1" y="9" width="6" height="6" rx="1" fill="{c}" opacity="0.6"/><rect x="9" y="9" width="6" height="6" rx="1" fill="{c}"/>',
}

FADE_CSS = ""


def render_stats_card(user, stats):
    name = esc(user.get("name") or LOGIN)
    level, percentile = rank(stats)
    rows = [
        ("star", "Total Stars Earned", stats["stars"]),
        ("commit", "Commits (past year)", stats["commits"]),
        ("pr", "Total PRs", stats["prs"]),
        ("issue", "Total Issues", stats["issues"]),
        ("contrib", "Contributed To", stats["contributed"]),
    ]
    body = []
    for i, (icon, label, value) in enumerate(rows):
        y = 62 + i * 25
        body.append(
            f'<g transform="translate(25,{y})">'
            f'<g transform="translate(0,-12)">{STAT_ICONS[icon].format(c=GOLD)}</g>'
            f'<text x="28" y="0" font-family="{FONT}" font-size="14" fill="{MIST}">{label}:</text>'
            f'<text x="285" y="0" font-family="{FONT}" font-size="14" font-weight="bold" fill="{CYAN}">{value}</text>'
            "</g>"
        )
    circumference = 2 * math.pi * 40
    progress = circumference * max(0.03, (100 - percentile) / 100)
    ring = (
        f"<g>"
        f'<circle cx="415" cy="97" r="40" fill="none" stroke="{BORDER}" stroke-width="7"/>'
        f'<circle cx="415" cy="97" r="40" fill="none" stroke="{CYAN}" stroke-width="7" '
        f'stroke-linecap="round" stroke-dasharray="{progress:.1f} {circumference:.1f}" '
        f'transform="rotate(-90 415 97)"/>'
        f'<text x="415" y="106" text-anchor="middle" font-family="{FONT}" font-size="26" '
        f'font-weight="bold" fill="{CYAN}">{level}</text></g>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195">'
        f"{FADE_CSS}"
        f'<rect x="0.5" y="0.5" width="494" height="194" rx="4.5" fill="{NAVY}" stroke="{BORDER}"/>'
        f'<text x="25" y="35" font-family="{FONT}" font-size="17" font-weight="bold" fill="{CYAN}">'
        f"{name} — GitHub Stats</text>"
        f"{''.join(body)}{ring}</svg>"
    )


def top_languages(user):
    totals = {}
    colors = {}
    for repo in user["repositories"]["nodes"]:
        if repo["isFork"]:
            continue
        for edge in repo["languages"]["edges"]:
            lang = edge["node"]["name"]
            totals[lang] = totals.get(lang, 0) + edge["size"]
            colors[lang] = edge["node"]["color"] or CYAN
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:8]
    total = sum(size for _, size in ranked) or 1
    return [(lang, size / total * 100, colors[lang]) for lang, size in ranked]


def render_langs_card(langs):
    bar_x, bar_w = 25, 290
    segments, x = [], bar_x
    for i, (_, pct, color) in enumerate(langs):
        width = bar_w * pct / 100
        segments.append(
            f'<rect x="{x:.1f}" y="50" width="{width:.1f}" height="10" fill="{color}"/>'
        )
        x += width
    legend = []
    for i, (lang, pct, color) in enumerate(langs):
        if len(lang) > 12:
            lang = lang[:11] + "…"
        col, row = divmod(i, 4)
        lx, ly = 25 + col * 155, 90 + row * 23
        legend.append(
            f"<g>"
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>'
            f'<text x="{lx + 17}" y="0" font-family="{FONT}" font-size="12" fill="{MIST}" '
            f'transform="translate(0,{ly})">{esc(lang)}</text>'
            f'<text x="{lx + 17}" y="0" dx="95" font-family="{FONT}" font-size="12" '
            f'font-weight="bold" fill="{CYAN}" transform="translate(0,{ly})">{pct:.1f}%</text></g>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="340" height="195" viewBox="0 0 340 195">'
        f"{FADE_CSS}"
        f'<rect x="0.5" y="0.5" width="339" height="194" rx="4.5" fill="{NAVY}" stroke="{BORDER}"/>'
        f'<text x="25" y="35" font-family="{FONT}" font-size="17" font-weight="bold" fill="{CYAN}">'
        f"Most Used Languages</text>"
        f'<clipPath id="bar"><rect x="{bar_x}" y="50" width="{bar_w}" height="10" rx="5"/></clipPath>'
        f'<g clip-path="url(#bar)">{"".join(segments)}</g>'
        f"{''.join(legend)}</svg>"
    )


TROPHY_THRESHOLDS = {
    "Commits": [2000, 1000, 500, 200, 100, 50, 20, 1],
    "Stars": [200, 100, 50, 30, 20, 10, 3, 1],
    "Followers": [100, 50, 25, 15, 10, 5, 2, 1],
    "Repos": [50, 40, 30, 20, 15, 10, 5, 1],
    "PRs": [100, 50, 25, 15, 10, 5, 2, 1],
    "Issues": [100, 50, 25, 15, 10, 5, 2, 1],
    "Contribs": [30, 20, 10, 7, 5, 3, 2, 1],
}
TROPHY_RANKS = ["SSS", "SS", "S", "AAA", "AA", "A", "B", "C"]


def trophy_rank(metric, value):
    for threshold, label in zip(TROPHY_THRESHOLDS[metric], TROPHY_RANKS):
        if value >= threshold:
            return label
    return "?"


def render_trophies(stats):
    tiles = [
        ("Commits", stats["commits"]),
        ("Stars", stats["stars"]),
        ("Followers", stats["followers"]),
        ("Repos", stats["repos"]),
        ("PRs", stats["prs"]),
        ("Issues", stats["issues"]),
        ("Contribs", stats["contributed"]),
    ]
    cup = (
        f'<g transform="translate(38,16)">'
        f'<path d="M6 0 h22 v10 a11 11 0 0 1 -22 0 z" fill="{GOLD}"/>'
        f'<path d="M6 2 h-5 a8 8 0 0 0 8 9 M28 2 h5 a8 8 0 0 1 -8 9" fill="none" stroke="{GOLD}" stroke-width="2.5"/>'
        f'<rect x="14.5" y="20" width="5" height="7" fill="{GOLD}"/>'
        f'<rect x="9" y="27" width="16" height="4" rx="1" fill="{GOLD}"/></g>'
    )
    parts = []
    for i, (metric, value) in enumerate(tiles):
        x = i * 116
        label = trophy_rank(metric, value)
        rank_color = CYAN if label != "?" else MIST
        parts.append(
            f'<g transform="translate({x},0)">'
            f'<rect x="0.5" y="0.5" width="109" height="119" rx="4.5" fill="{NAVY}" stroke="{BORDER}"/>'
            f"{cup}"
            f'<text x="55" y="72" text-anchor="middle" font-family="{FONT}" font-size="18" '
            f'font-weight="bold" fill="{rank_color}">{label}</text>'
            f'<text x="55" y="92" text-anchor="middle" font-family="{FONT}" font-size="11" fill="{MIST}">{metric}</text>'
            f'<text x="55" y="108" text-anchor="middle" font-family="{FONT}" font-size="11" '
            f'font-weight="bold" fill="{CYAN}">{value}</text></g>'
        )
    width = len(tiles) * 116 - 6
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="120" viewBox="0 0 {width} 120">'
        f"{FADE_CSS}{''.join(parts)}</svg>"
    )


def main():
    user = fetch_user()
    repos = [r for r in user["repositories"]["nodes"] if not r["isFork"]]
    stats = {
        "stars": sum(r["stargazerCount"] for r in repos),
        "commits": user["contributionsCollection"]["totalCommitContributions"],
        "reviews": user["contributionsCollection"]["totalPullRequestReviewContributions"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["openIssues"]["totalCount"] + user["closedIssues"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(f"{OUT_DIR}/stats-card.svg", "w") as f:
        f.write(render_stats_card(user, stats))
    with open(f"{OUT_DIR}/top-langs.svg", "w") as f:
        f.write(render_langs_card(top_languages(user)))
    with open(f"{OUT_DIR}/trophies.svg", "w") as f:
        f.write(render_trophies(stats))
    print("Generated cards:", stats)


if __name__ == "__main__":
    main()
