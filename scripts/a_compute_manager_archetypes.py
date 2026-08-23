"""
a_compute_manager_archetypes.py

Reads data/raw_analytics/performance_patterns.json + data/derived/
draft_day_profiler.json + data/derived/superlatives.json, produces
data/raw_analytics/manager_archetypes.json.

MANAGER PLAYSTYLE CLUSTERING via hand-rolled k-means (no scikit-learn -
with only 15 data points, this is genuinely simple to implement
correctly, and avoids a heavy dependency for a small-scale problem).

FEATURES (4, chosen deliberately to stay small - with only 15 data
points, too many features leads to sparse/meaningless clusters even
at this small scale):
  1. win_pct                 - career win percentage
  2. retention_rate           - draft loyalty (unified across eras)
  3. trades_per_season         - trade frequency, NORMALIZED by tenure
                                  (a person over 8 years naturally
                                  makes more total trades than a
                                  2-year rookie - raw counts alone
                                  would just measure tenure, not
                                  behavior)
  4. coefficient_of_variation   - scoring volatility/consistency
                                  (from performance_patterns.json,
                                  already normalized for cross-era
                                  comparability)

All 4 features are Z-SCORE STANDARDIZED before clustering - k-means
uses Euclidean distance, and without standardization a feature with a
naturally larger numeric range (like trades_per_season) would
dominate the distance calculation purely due to scale, not because
it's actually more important.

K=4 clusters, with 10 random restarts (keeping the lowest-inertia
result) - k-means is sensitive to initialization, and restarts are
cheap at this tiny scale.

Cluster archetype LABELS are generated data-driven from each cluster's
centroid (which standardized feature deviates most from the overall
mean), not hardcoded to a fixed list - so labels stay meaningful even
if the underlying data/clusters shift in future seasons.

HONEST CAVEAT (stated directly in the output, not hidden): with only
15 managers, this is illustrative, not statistically robust. Small
sample clustering can be sensitive to a single data point.

Run with: python a_compute_manager_archetypes.py
"""

import json
import os
import random
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PERFORMANCE_PATH = os.path.join(SCRIPT_DIR, "..", "data", "raw_analytics", "performance_patterns.json")
DRAFT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "draft_day_profiler.json")
SUPERLATIVES_PATH = os.path.join(SCRIPT_DIR, "..", "data", "derived", "superlatives.json")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "..", "data", "raw_analytics", "manager_archetypes.json")

K = 4
N_RESTARTS = 10
MAX_ITERATIONS = 100

FEATURE_NAMES = ["win_pct", "retention_rate", "trades_per_season", "coefficient_of_variation"]


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def build_features(performance_data, draft_data, superlatives_data):
    career_stats = superlatives_data["career_records"]["all_managers"]
    draft_profiles = draft_data["manager_profiles"]
    perf_career = performance_data["career"]

    features = {}
    for cid, career in career_stats.items():
        draft = draft_profiles.get(cid)
        perf = perf_career.get(cid)
        if not draft or not perf:
            continue  # missing data for this manager in one of the three sources - exclude rather than guess

        years_played = len(career.get("years_played", []))
        trades_per_season = career.get("trades", 0) / years_played if years_played else 0

        if career.get("win_pct") is None or draft.get("retention_rate") is None or perf.get("coefficient_of_variation") is None:
            continue  # incomplete data - exclude rather than impute a fake value

        features[cid] = {
            "owner_name": career["owner_name"],
            "win_pct": career["win_pct"],
            "retention_rate": draft["retention_rate"],
            "trades_per_season": round(trades_per_season, 3),
            "coefficient_of_variation": perf["coefficient_of_variation"],
        }

    return features


def standardize(features):
    """Z-score standardize each feature across all managers. Returns
    (standardized_vectors, means, stdevs) - means/stdevs kept so we can
    interpret cluster centroids back in real units later."""
    n = len(features)
    cids = list(features.keys())

    means = {}
    stdevs = {}
    for fname in FEATURE_NAMES:
        values = [features[cid][fname] for cid in cids]
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        stdev = math.sqrt(variance) if variance > 0 else 1.0  # avoid divide-by-zero if a feature has zero variance
        means[fname] = mean
        stdevs[fname] = stdev

    vectors = {}
    for cid in cids:
        vectors[cid] = [(features[cid][f] - means[f]) / stdevs[f] for f in FEATURE_NAMES]

    return vectors, means, stdevs


# ---------------------------------------------------------------------------
# Hand-rolled k-means
# ---------------------------------------------------------------------------

def euclidean_distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def kmeans_single_run(vectors, k, seed):
    rng = random.Random(seed)
    cids = list(vectors.keys())
    points = [vectors[cid] for cid in cids]

    centroids = rng.sample(points, k)
    assignments = [0] * len(points)

    for _ in range(MAX_ITERATIONS):
        new_assignments = []
        for p in points:
            distances = [euclidean_distance(p, c) for c in centroids]
            new_assignments.append(distances.index(min(distances)))

        if new_assignments == assignments:
            break
        assignments = new_assignments

        new_centroids = []
        for cluster_id in range(k):
            cluster_points = [points[i] for i in range(len(points)) if assignments[i] == cluster_id]
            if cluster_points:
                dim = len(cluster_points[0])
                centroid = [sum(p[d] for p in cluster_points) / len(cluster_points) for d in range(dim)]
                new_centroids.append(centroid)
            else:
                new_centroids.append(centroids[cluster_id])  # empty cluster - keep old centroid rather than crash
        centroids = new_centroids

    inertia = sum(
        euclidean_distance(points[i], centroids[assignments[i]]) ** 2
        for i in range(len(points))
    )

    return cids, assignments, centroids, inertia


def kmeans(vectors, k, n_restarts):
    """Runs multiple random-seeded restarts, keeps the lowest-inertia result."""
    best = None
    for seed in range(n_restarts):
        cids, assignments, centroids, inertia = kmeans_single_run(vectors, k, seed)
        if best is None or inertia < best[3]:
            best = (cids, assignments, centroids, inertia)
    return best


# ---------------------------------------------------------------------------
# Data-driven cluster labeling
# ---------------------------------------------------------------------------

def label_cluster(centroid):
    """
    Generates a descriptive label from which standardized feature(s)
    deviate most from the overall mean (which is ~0 after standardization).
    Not hardcoded to fixed archetypes - adapts to whatever the actual
    computed clusters look like.
    """
    deviations = list(zip(FEATURE_NAMES, centroid))
    deviations.sort(key=lambda x: abs(x[1]), reverse=True)
    top_feature, top_value = deviations[0]

    direction = "HIGH" if top_value > 0 else "LOW"

    labels = {
        ("win_pct", "HIGH"): "Winning Formula",
        ("win_pct", "LOW"): "Rebuilding",
        ("retention_rate", "HIGH"): "Steady Hand",
        ("retention_rate", "LOW"): "Active Trader",
        ("trades_per_season", "HIGH"): "Wheeler-Dealer",
        ("trades_per_season", "LOW"): "Set It and Forget It",
        ("coefficient_of_variation", "HIGH"): "High-Variance Gambler",
        ("coefficient_of_variation", "LOW"): "Mr. Consistent",
    }

    return labels.get((top_feature, direction), f"{direction} {top_feature.replace('_', ' ').upper()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    with open(PERFORMANCE_PATH) as f:
        performance_data = json.load(f)
    with open(DRAFT_PATH) as f:
        draft_data = json.load(f)
    with open(SUPERLATIVES_PATH) as f:
        superlatives_data = json.load(f)

    features = build_features(performance_data, draft_data, superlatives_data)

    if len(features) < K:
        print(f"WARNING: only {len(features)} managers have complete data - fewer than K={K}. Reduce K or check data sources.")
        return

    vectors, means, stdevs = standardize(features)
    cids, assignments, centroids, inertia = kmeans(vectors, K, N_RESTARTS)

    cluster_labels = [label_cluster(c) for c in centroids]

    managers_output = {}
    for i, cid in enumerate(cids):
        cluster_id = assignments[i]
        managers_output[cid] = {
            "owner_name": features[cid]["owner_name"],
            "cluster_id": cluster_id,
            "archetype": cluster_labels[cluster_id],
            "features": features[cid],
        }

    clusters_output = []
    for cluster_id in range(K):
        members = [cid for i, cid in enumerate(cids) if assignments[i] == cluster_id]
        clusters_output.append({
            "cluster_id": cluster_id,
            "archetype": cluster_labels[cluster_id],
            "member_count": len(members),
            "members": [features[cid]["owner_name"] for cid in members],
            "centroid_real_units": {
                fname: round(means[fname] + centroids[cluster_id][j] * stdevs[fname], 4)
                for j, fname in enumerate(FEATURE_NAMES)
            },
        })

    output = {
        "managers": managers_output,
        "clusters": clusters_output,
        "notes": {
            "method": f"Hand-rolled k-means (k={K}, {N_RESTARTS} random restarts, lowest inertia kept). Features are z-score standardized before clustering so no single feature's raw numeric scale dominates the distance calculation.",
            "features_used": FEATURE_NAMES,
            "caveat": f"With only {len(features)} managers, this clustering is ILLUSTRATIVE, not statistically robust. Small-sample clustering can be sensitive to a single data point, and cluster boundaries may shift meaningfully as more seasons/managers are added.",
            "label_method": "Archetype labels are generated from whichever standardized feature deviates most from the overall league mean for that cluster's centroid - not a fixed, hardcoded list, so labels stay meaningful even if underlying data shifts.",
        },
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote archetypes for {len(managers_output)} managers across {K} clusters to {OUTPUT_PATH}")
    for c in clusters_output:
        print(f"  Cluster {c['cluster_id']} ({c['archetype']}): {c['member_count']} members - {', '.join(c['members'])}")


if __name__ == "__main__":
    main()
