import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import warnings
warnings.filterwarnings('ignore')

def segment_respondents(input_file, output_file=None, force_k=None):
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} respondents.")

    # Detect question numbers
    q_nums = sorted(set(
        int(c.split('_')[0][1:])
        for c in df.columns if c.startswith('Q') and '_' in c
    ))
    print(f"Found {len(q_nums)} outcomes (Q{q_nums[0]} to Q{q_nums[-1]}).")

    # ── Compute per-respondent opportunity score for each outcome ────
    # Ulwick: Opportunity = Importance + max(Importance - Satisfaction, 0)
    opp_cols = []
    for i in q_nums:
        imp = df[f'Q{i}_imp']
        sat = df[f'Q{i}_sat']
        col = f'Q{i}_opp'
        df[col] = imp + (imp - sat).clip(lower=0)
        opp_cols.append(col)

    print(f"Computed {len(opp_cols)} per-respondent opportunity scores.")

    # ── Cluster on opportunity scores ────────────────────────────────
    X = df[opp_cols].fillna(df[opp_cols].mean())
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print("\nFinding optimal number of segments (k=2 to 8)...")
    print(f"{'k':>4} {'silhouette':>12} {'inertia':>12}")
    print("-" * 32)

    best_k = 2
    best_score = -1

    for k in range(2, 9):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        sil = silhouette_score(X_scaled, labels)
        inertia = km.inertia_
        marker = " <-- best" if sil > best_score else ""
        print(f"{k:>4} {sil:>12.4f} {inertia:>12.1f}{marker}")
        if sil > best_score:
            best_score = sil
            best_k = k

    if force_k:
        print(f"\nMath suggests k={best_k}, forcing k={force_k} (domain decision)")
        best_k = force_k
    else:
        print(f"\nBest k = {best_k} (silhouette = {best_score:.4f})")

    # Final clustering
    km_final = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df['segment'] = km_final.fit_predict(X_scaled) + 1

    # ── Profile each segment ─────────────────────────────────────────
    print("\nSegment profiles:")
    meta_cols = [c for c in ['age', 'skill_level', 'position', 'stress_level',
                              'overall_satisfaction', 'coach_relationship',
                              'parent_support', 'current_mood'] if c in df.columns]

    for seg in sorted(df['segment'].unique()):
        seg_df = df[df['segment'] == seg]
        print(f"\n  Segment {seg} — {len(seg_df)} kids ({len(seg_df)/len(df)*100:.1f}%)")
        for col in meta_cols:
            if df[col].dtype in ['float64', 'int64']:
                print(f"    {col}: {seg_df[col].mean():.2f} avg")
            else:
                top = seg_df[col].value_counts().index[0]
                pct = seg_df[col].value_counts().iloc[0] / len(seg_df) * 100
                print(f"    {col}: mostly '{top}' ({pct:.0f}%)")

    # ── Top 5 most unmet outcomes per segment ────────────────────────
    print("\n  Top 5 unmet outcomes per segment (by avg opportunity score):")
    for seg in sorted(df['segment'].unique()):
        seg_df = df[df['segment'] == seg]
        opp_means = seg_df[opp_cols].mean().sort_values(ascending=False)
        print(f"\n  Segment {seg}:")
        for col, val in opp_means.head(5).items():
            print(f"    {col.replace('_opp','')}: {val:.2f}")

    # Drop temporary opp columns from output to keep file clean
    df_out = df.drop(columns=opp_cols)

    if output_file is None:
        output_file = input_file.replace('.csv', '_segments.csv')

    df_out.to_csv(output_file, index=False)
    print(f"\nDone! Saved to: {output_file}")
    print(f"Column 'segment' added — values 1 to {best_k}")

    return df_out


if __name__ == "__main__":
    import sys, os

    if len(sys.argv) < 2:
        print("Usage: python segment_respondents.py <input_file.csv> [output_file.csv] [force_k]")
        print("Example: python segment_respondents.py results_all.csv results_segments.csv 3")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    force_k = int(sys.argv[3]) if len(sys.argv) > 3 else None

    if not os.path.exists(input_file):
        print(f"Error: file '{input_file}' not found.")
        sys.exit(1)

    segment_respondents(input_file, output_file, force_k=force_k)