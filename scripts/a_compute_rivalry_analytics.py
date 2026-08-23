"""
a_compute_rivalry_analytics.py

Reads data/derived/rivalry_lanes.json, produces
data/raw_analytics/rivalry_analytics.json.

TWO ANALYSES:

1. STATISTICAL SIGNIFICANCE
   Some rivalries in rivalry_lanes.json have as few as 1-3 games -
   is a 5-0 record actually meaningful, or just noise given the small
   sample? Uses a two-sided binomial test against a fair-coin null
   hypothesis (p=0.5) to flag which rivalries have a win/loss split
   unlikely to occur by chance, vs. which are still statistically
   indistinguishable from a coin flip despite a lopsided-LOOKING record.
   Hand-rolled binomial math (closed-form, not iterative) - no scipy
   dependency needed for this specific test.

2. RIVALRY NETWORK ANALYSIS
   Treats all 15 managers as nodes and their 105 head-to-head
   histories as weighted edges (weight = games_played), using
   networkx to compute real centrality measures:
     - degree_centrality: how many DIFFERENT people you've faced
       (everyone should be ~equal here, given full round-robin coverage)
     - weighted_degree (total games played, across all rivalries):
       who has the most total head-to-head history, period
     - betweenness_centrality: who sits "between" the most other
       manager-pairs in the league's rivalry web (a real graph-theory
       measure, not just "most active")

Run with: python a_compute_rivalry_analytics.py
"""

import json
import os
import math
import networkx as nx

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RIVALRY_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "rivalry_lanes.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "raw_analytics", "rivalry_analytics.json")

MIN_GAMES_FOR_SIGNIFICANCE_CHECK = 3  # below this, flag as "sample too small" rather than compute a p-value that would be misleading


# ---------------------------------------------------------------------------
# Hand-rolled two-sided binomial test (closed-form, no scipy needed)
# ---------------------------------------------------------------------------

def binomial_coefficient(n, k):
    return math.comb(n, k)


def binomial_pmf(k, n, p=0.5):
    return binomial_coefficient(n, k) * (p ** k) * ((1 - p) ** (n - k))


def two_sided_binomial_pvalue(k, n, p=0.5):
    """
    Sum the probability of every outcome AT LEAST AS EXTREME as observing
    k successes out of n trials, under a fair-coin (p=0.5) null hypothesis.
    This is the standard two-sided binomial test definition.
    """
    observed_pmf = binomial_pmf(k, n, p)
    total = 0.0
    for i in range(n + 1):
        if binomial_pmf(i, n, p) <= observed_pmf + 1e-9:
            total += binomial_pmf(i, n, p)
    return min(total, 1.0)


# ---------------------------------------------------------------------------
# Statistical significance per rivalry
# ---------------------------------------------------------------------------

def compute_significance(matchups):
    results = []
    for m in matchups:
        total_decisive = m["wins_a"] + m["wins_b"]  # excludes ties from the binomial test
        if total_decisive < MIN_GAMES_FOR_SIGNIFICANCE_CHECK:
            results.append({
                "manager_a": m["manager_a"],
                "manager_b": m["manager_b"],
                "games_played": m["games_played"],
                "p_value": None,
                "significant": False,
                "note": "Sample too small (fewer than 3 decisive games) - not enough data to distinguish from random chance.",
            })
            continue

        k = max(m["wins_a"], m["wins_b"])
        p_value = round(two_sided_binomial_pvalue(k, total_decisive), 4)

        results.append({
            "manager_a": m["manager_a"],
            "manager_b": m["manager_b"],
            "games_played": m["games_played"],
            "wins_a": m["wins_a"],
            "wins_b": m["wins_b"],
            "p_value": p_value,
            "significant": p_value < 0.05,
            "note": (
                "This win/loss split is unlikely to be random chance (p < 0.05)."
                if p_value < 0.05 else
                "This record, while lopsided-looking, is statistically indistinguishable from a coin flip given the sample size."
            ),
        })

    return results


# ---------------------------------------------------------------------------
# Rivalry network analysis
# ---------------------------------------------------------------------------

def compute_network(matchups):
    """
    IMPORTANT FINDING: this league's rivalry graph is a COMPLETE graph -
    all 105 of 105 possible manager pairs have played each other at
    least once (confirmed: total_edges == 105 == C(15,2)). This makes
    betweenness centrality structurally meaningless - it measures who
    sits "between" other pairs on the shortest path, but in a complete
    graph every pair already has a direct connection, so there's never
    a real reason to route through a third person. Degree centrality is
    equally uninformative here - it would be a flat 1.0 for all 15
    managers, since everyone is connected to everyone.

    The only genuinely meaningful network-style signal for a COMPLETE
    weighted graph is total accumulated edge weight per node - i.e.
    total games played across ALL of a manager's rivalries combined.
    This is computed directly (no centrality algorithm needed for it
    to be correct), and IS a real, intuitive measure: who has
    accumulated the deepest cumulative head-to-head history, tenure
    and matchup frequency combined.
    """
    G = nx.Graph()
    for m in matchups:
        G.add_edge(m["manager_a"], m["manager_b"], weight=m["games_played"])

    weighted_degree = dict(G.degree(weight="weight"))

    nodes = []
    for name in G.nodes():
        nodes.append({
            "manager": name,
            "distinct_rivals": G.degree(name),
            "total_games_all_rivalries": weighted_degree[name],
        })

    nodes.sort(key=lambda n: n["total_games_all_rivalries"], reverse=True)

    return {
        "nodes": nodes,
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "is_complete_graph": G.number_of_edges() == (G.number_of_nodes() * (G.number_of_nodes() - 1)) // 2,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(RIVALRY_PATH) as f:
        rivalry_data = json.load(f)

    matchups = rivalry_data.get("matchups", [])

    significance = compute_significance(matchups)
    network = compute_network(matchups)

    significant_count = sum(1 for s in significance if s.get("significant"))

    output = {
        "significance": significance,
        "network": network,
        "notes": {
            "significance_method": "Two-sided binomial test (hand-computed, p=0.5 null hypothesis) on decisive games only (ties excluded). Rivalries with fewer than 3 decisive games are flagged as 'sample too small' rather than given a potentially misleading p-value.",
            "significant_rivalries_found": significant_count,
            "network_method": "This league's rivalry graph is a COMPLETE graph - all 105 of 105 possible manager pairs have played each other. This makes betweenness/degree centrality structurally meaningless (there's no 'bridging' role to measure when everyone already has a direct connection to everyone else), so those were deliberately NOT computed. The one genuinely meaningful signal for a complete weighted graph is total accumulated games across all of a manager's rivalries combined - who has the deepest cumulative head-to-head history, reflecting both tenure and matchup frequency.",
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote rivalry analytics: {len(significance)} rivalries checked, {significant_count} statistically significant, {network['total_nodes']} managers in network")


if __name__ == "__main__":
    main()
