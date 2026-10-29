"""Generate neofetch-style profile cards (dark_mode.svg / light_mode.svg).

Run by .github/workflows/build.yml every day. Uses ACCESS_TOKEN (a personal
access token, optional — includes private-repo stats) or GITHUB_TOKEN.
Edit the CONFIG section below to change what the card says.
"""
import datetime as dt
import html
import json
import os
import sys
import time
import urllib.request

# ───────────────────────────── CONFIG ─────────────────────────────
USER = "tklee117"
HEADER = "tk@lee"
UPTIME_START = dt.date(2023, 9, 26)  # first day at Caltech
WIDTH = 60  # characters per info line

INFO = [
    ("OS", "Windows, Ubuntu 22.04, ROS 2 Humble"),
    ("Uptime", "{uptime}"),
    ("Host", "California Institute of Technology"),
    ("Kernel", "Electrical Engineering (Intelligent Systems)"),
    ("Minor", "Robotics, Control & Dynamical Systems"),
    ("Location", "Pasadena, CA"),
    None,
    ("Languages.Programming", "Python, C++, JavaScript"),
    ("Languages.Computer", "HTML, LaTeX, YAML"),
    ("Languages.Real", "English, Korean"),
    None,
    ("Research.Interests", "Multi-Robot Planning, Control"),
    ("Robotics.Stack", "ROS 2, MPPI, SLAM, Ergodic Search"),
]
CONTACT = [
    ("Email.School", "tlee2@caltech.edu"),
    ("GitHub", "tklee117"),
]
# ──────────────────────────────────────────────────────────────────

THEMES = {
    "dark": dict(bg="#161b22", text="#c9d1d9", key="#ffa657", value="#a5d6ff",
                 cc="#616e7f", add="#3fb950", dele="#f85149", art="ascii_dark.txt"),
    "light": dict(bg="#f6f8fa", text="#24292f", key="#953800", value="#0a3069",
                  cc="#c2cfde", add="#1a7f37", dele="#cf222e", art="ascii_light.txt"),
}

TOKEN = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")


def api(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None)
    req.add_header("Authorization", f"bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, (json.loads(r.read() or b"null"))


def gql(query, **variables):
    _, j = api("https://api.github.com/graphql", {"query": query, "variables": variables})
    if j.get("errors"):
        raise RuntimeError(j["errors"])
    return j["data"]


def fetch_stats():
    d = gql("""query($login:String!){ user(login:$login){
        createdAt followers{totalCount}
        repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,REPOSITORY]){totalCount}
        repositories(first:100, ownerAffiliations:[OWNER]){totalCount nodes{stargazerCount}}
        all: repositories(first:100, ownerAffiliations:[OWNER,COLLABORATOR,ORGANIZATION_MEMBER]){nodes{nameWithOwner}}
    }}""", login=USER)["user"]
    stats = dict(
        repos=d["repositories"]["totalCount"],
        contributed=d["repositoriesContributedTo"]["totalCount"],
        stars=sum(n["stargazerCount"] for n in d["repositories"]["nodes"]),
        followers=d["followers"]["totalCount"],
    )

    # commits: sum yearly contribution totals since the account was created
    start = dt.datetime.fromisoformat(d["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    commits = 0
    while start < now:
        end = min(start.replace(year=start.year + 1), now)
        c = gql("""query($login:String!,$f:DateTime!,$t:DateTime!){ user(login:$login){
            contributionsCollection(from:$f,to:$t){totalCommitContributions restrictedContributionsCount}}}""",
                login=USER, f=start.isoformat(), t=end.isoformat())["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"]
        start = end
    stats["commits"] = commits

    # lines of code: your additions/deletions in every repo you can access
    add = dele = 0
    for n in d["all"]["nodes"]:
        for _ in range(6):
            try:
                status, j = api(f"https://api.github.com/repos/{n['nameWithOwner']}/stats/contributors")
            except Exception as e:  # noqa: BLE001
                print("skip", n["nameWithOwner"], e, file=sys.stderr)
                j, status = None, 0
                break
            if status == 200:
                break
            time.sleep(4)  # 202 = GitHub is still computing
        for a in (j if isinstance(j, list) else []):
            if a.get("author") and a["author"]["login"].lower() == USER.lower():
                add += sum(w["a"] for w in a["weeks"])
                dele += sum(w["d"] for w in a["weeks"])
    stats.update(loc=add - dele, add=add, dele=dele)
    return stats


def uptime(start, today=None):
    today = today or dt.date.today()
    y, m, d = today.year - start.year, today.month - start.month, today.day - start.day
    if d < 0:
        m -= 1
        prev = today.replace(day=1) - dt.timedelta(days=1)
        d += prev.day
    if m < 0:
        y -= 1
        m += 12
    p = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"  # noqa: E731
    return f"{p(y, 'year')}, {p(m, 'month')}, {p(d, 'day')}"


# ───────────────────────── SVG rendering ─────────────────────────
def span(cls, s):
    return f'<tspan class="{cls}">{html.escape(s)}</tspan>'


def kv_line(key, value):
    """'. Key: ....... value' padded to WIDTH characters."""
    head = f". {key}:"
    dots = WIDTH - len(head) - len(value) - 2
    dots = max(dots, 1)
    return (span("cc", ". ") + span("key", key) + ":" + span("cc", " " + "." * dots + " ")
            + span("value", value))


def section(title):
    rest = WIDTH - len(title) - 1
    return f'{html.escape(title)} {span("cc", "—" * (rest - 3) + "-—-")}'


def stat_pair(k1, v1, k2, v2, half=36):
    left_head = f". {k1}: "
    dots1 = max(half - len(left_head) - len(v1) - 1, 1)
    right_head = f" | {k2}: "
    dots2 = max(WIDTH - half - len(right_head) - len(v2) - 1, 1)
    return (span("cc", ". ") + span("key", k1) + ":" + span("cc", " " + "." * dots1 + " ") + span("value", v1)
            + " | " + span("key", k2) + ":" + span("cc", " " + "." * dots2 + " ") + span("value", v2))


def build_lines(s):
    up = uptime(UPTIME_START)
    lines = [section(HEADER)]
    for item in INFO:
        lines.append(span("cc", ".") if item is None else kv_line(item[0], item[1].format(uptime=up)))
    lines.append("")
    lines.append(section("- Contact"))
    lines += [kv_line(k, v) for k, v in CONTACT]
    lines.append("")
    lines.append(section("- GitHub Stats"))
    repos = f"{s['repos']} {{Contributed: {s['contributed']}}}"
    lines.append(stat_pair("Repos", repos, "Stars", f"{s['stars']:,}"))
    lines.append(stat_pair("Commits", f"{s['commits']:,}", "Followers", f"{s['followers']:,}"))
    loc_head = ". Lines of Code on GitHub: "
    tail = f"{s['loc']:,} ( {s['add']:,}++, {s['dele']:,}-- )"
    dots = max(WIDTH - len(loc_head) - len(tail), 1)
    lines.append(span("cc", ". ") + span("key", "Lines of Code on GitHub") + ":"
                 + span("cc", " " + "." * dots + " ") + span("value", f"{s['loc']:,}")
                 + " ( " + span("addColor", f"{s['add']:,}++") + ", "
                 + span("delColor", f"{s['dele']:,}--") + " )")
    return lines


def render(theme, stats):
    t = THEMES[theme]
    here = os.path.dirname(os.path.abspath(__file__))
    art = open(os.path.join(here, t["art"])).read().rstrip("\n").split("\n")
    lines = build_lines(stats)
    lh, fs, top = 20, 16, 30
    art_w = max(len(a) for a in art)
    info_x = 15 + int((art_w + 3) * fs * 0.6)
    width = info_x + int((WIDTH + 2) * fs * 0.6)
    height = top + max(len(art), len(lines)) * lh + 10
    art_y0 = top + max(0, (len(lines) - len(art)) // 2) * lh
    out = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,\'DejaVu Sans Mono\',monospace" '
        f'width="{width}px" height="{height}px" font-size="{fs}px">',
        "<style>",
        f".key {{fill: {t['key']};}} .value {{fill: {t['value']};}} .addColor {{fill: {t['add']};}} "
        f".delColor {{fill: {t['dele']};}} .cc {{fill: {t['cc']};}} "
        f"text, tspan {{white-space: pre;}}",
        "</style>",
        f'<rect width="{width}px" height="{height}px" fill="{t["bg"]}" rx="15"/>',
        f'<text x="15" y="{art_y0}" fill="{t["text"]}" class="ascii">',
    ]
    for i, a in enumerate(art):
        out.append(f'<tspan x="15" y="{art_y0 + i * lh}">{html.escape(a)}</tspan>')
    out.append("</text>")
    out.append(f'<text x="{info_x}" y="{top}" fill="{t["text"]}">')
    for i, ln in enumerate(lines):
        out.append(f'<tspan x="{info_x}" y="{top + i * lh}">{ln}</tspan>')
    out.append("</text>\n</svg>\n")
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) > 1:  # offline preview: python generate.py stats.json
        stats = json.load(open(sys.argv[1]))
    else:
        try:
            stats = fetch_stats()
        except Exception as e:  # keep the previous card if the API call fails
            print("Could not fetch stats:", e, file=sys.stderr)
            sys.exit(0)
    print(stats)
    here = os.path.dirname(os.path.abspath(__file__))
    for theme in THEMES:
        with open(os.path.join(here, f"{theme}_mode.svg"), "w") as f:
            f.write(render(theme, stats))
