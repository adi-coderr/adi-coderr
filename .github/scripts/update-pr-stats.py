#!/usr/bin/env python3
"""
Fetches PR stats for the authenticated GitHub user and updates README.md
with a table showing merged and open PRs per repository.
"""

import os
import re
import json
import urllib.request
import urllib.error

GITHUB_API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
USERNAME = os.environ.get("GITHUB_USERNAME", "")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "pr-stats-bot",
}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

# Markers in README.md
START_MARKER = "<!-- PR-STATS:START -->"
END_MARKER = "<!-- PR-STATS:END -->"


def gh_request(url):
    """Make a GET request to the GitHub API and return parsed JSON."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error fetching {url}: {e.code} {e.reason}")
        return []


def fetch_all_pages(base_url):
    """Paginate through all results from a GitHub API endpoint."""
    results = []
    page = 1
    while True:
        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}page={page}&per_page=100"
        data = gh_request(url)
        if not data:
            break
        results.extend(data)
        if len(data) < 100:
            break
        page += 1
    return results


def get_pr_stats(username):
    """
    Fetch all PRs authored by the user across all of GitHub.
    Returns a dict: { "owner/repo": {"merged": N, "open": N} }
    """
    stats = {}

    # Fetch merged PRs
    merged_prs = fetch_all_pages(
        f"{GITHUB_API}/search/issues?q=type:pr+author:{username}+is:merged"
    )
    # search/issues returns {"items": [...]}
    if isinstance(merged_prs, dict):
        merged_prs = merged_prs.get("items", [])

    for pr in merged_prs:
        repo_url = pr.get("repository_url", "")
        # repository_url looks like https://api.github.com/repos/owner/repo
        repo_name = "/".join(repo_url.split("/")[-2:])
        if repo_name not in stats:
            stats[repo_name] = {"merged": 0, "open": 0}
        stats[repo_name]["merged"] += 1

    # Fetch open PRs
    open_prs = fetch_all_pages(
        f"{GITHUB_API}/search/issues?q=type:pr+author:{username}+is:open"
    )
    if isinstance(open_prs, dict):
        open_prs = open_prs.get("items", [])

    for pr in open_prs:
        repo_url = pr.get("repository_url", "")
        repo_name = "/".join(repo_url.split("/")[-2:])
        if repo_name not in stats:
            stats[repo_name] = {"merged": 0, "open": 0}
        stats[repo_name]["open"] += 1

    return stats


def build_table(stats):
    """Build a markdown table from the PR stats dict."""
    if not stats:
        return "_No pull requests found yet. Start contributing!_ 🚀\n"

    # Sort repos: most total PRs first
    sorted_repos = sorted(
        stats.items(), key=lambda x: x[1]["merged"] + x[1]["open"], reverse=True
    )

    lines = []
    lines.append("| Repository | Merged 🟣 | Open 🟢 |")
    lines.append("|:-----------|----------:|--------:|")

    for repo, counts in sorted_repos:
        repo_link = f"[{repo}](https://github.com/{repo})"
        lines.append(f"| {repo_link} | {counts['merged']} | {counts['open']} |")

    # Summary row
    total_merged = sum(c["merged"] for c in stats.values())
    total_open = sum(c["open"] for c in stats.values())
    lines.append(f"| **Total** | **{total_merged}** | **{total_open}** |")

    return "\n".join(lines) + "\n"


def update_readme(table_content):
    """Replace content between markers in README.md."""
    readme_path = os.path.join(os.environ.get("GITHUB_WORKSPACE", "."), "README.md")

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Build the replacement block
    replacement = f"{START_MARKER}\n{table_content}{END_MARKER}"

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )

    if pattern.search(content):
        new_content = pattern.sub(replacement, content)
    else:
        # If markers don't exist, append before the end of file
        new_content = content.rstrip() + f"\n\n{replacement}\n"

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("✅ README.md updated successfully!")


def main():
    if not USERNAME:
        print("❌ GITHUB_USERNAME not set.")
        return

    print(f"📊 Fetching PR stats for @{USERNAME}...")
    stats = get_pr_stats(USERNAME)
    print(f"   Found PRs across {len(stats)} repositories.")

    table = build_table(stats)
    print("\nGenerated table:\n")
    print(table)

    update_readme(table)


if __name__ == "__main__":
    main()
