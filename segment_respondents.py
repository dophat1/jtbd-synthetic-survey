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

    # Detect satisfaction columns
    sat_cols = sorted(
        [c for c in df.columns if c.endswith('_sat') and c.startswith('Q')],
        key=lambda x: int(x.split('_')[0][1:])
    )
    print(f"Found {len(sat_cols)} satisfaction columns.")
    print("Clustering on satisfaction scores (unmet needs approach — Ulwick ODI).")

    X = df[sat_cols].fillna(df[sat_cols].mean())
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Find best k
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

    # Profile each segmenta
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

    # Top 5 most unmet outcomes per segment (lowest satisfaction on important outcomes)
    print("\n  Top 5 most unmet outcomes per segment (lowest avg satisfaction):")
    imp_cols = sorted(
        [c for c in df.columns if c.endswith('_imp') and c.startswith('Q')],
        key=lambda x: int(x.split('_')[0][1:])
    )
    for seg in sorted(df['segment'].unique()):
        seg_df = df[df['segment'] == seg]
        # Compute opportunity score per outcome for this segment
        q_nums = sorted(set(int(c.split('_')[0][1:]) for c in sat_cols))
        opp_scores = {}
        for i in q_nums:
            imp = seg_df[f'Q{i}_imp'].mean()
            sat = seg_df[f'Q{i}_sat'].mean()
            opp_scores[f'Q{i}'] = round(imp + max(imp - sat, 0), 2)
        top5 = sorted(opp_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"\n  Segment {seg}:")
        for q, val in top5:
            print(f"    {q}: {val:.2f}")

    # Save
    if output_file is None:
        output_file = input_file.replace('.csv', '_segments.csv')

    df.to_csv(output_file, index=False)
    print(f"\nDone! Saved to: {output_file}")
    print(f"Column 'segment' added — values 1 to {best_k}")

    return df


if __name__ == "__main__":
    import sys, os

    if len(sys.argv) < 2:
        print("Usage: python segment_respondents.py <input_file.csv> [output_file.csv] [force_k]")
        print("Example: python segment_respondents.py results_all.csv results_segments.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    force_k = int(sys.argv[3]) if len(sys.argv) > 3 else None

    if not os.path.exists(input_file):
        print(f"Error: file '{input_file}' not found.")
        sys.exit(1)

    segment_respondents(input_file, output_file, force_k=force_k)
