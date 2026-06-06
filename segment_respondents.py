import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import warnings
warnings.filterwarnings('ignore')

def segment_respondents(input_file, output_file=None):
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} respondents.")

    # Extract importance columns only (Q1_imp to Q67_imp)
    imp_cols = sorted(
        [c for c in df.columns if c.endswith('_imp') and c.startswith('Q')],
        key=lambda x: int(x.split('_')[0][1:])
    )
    print(f"Found {len(imp_cols)} importance columns.")

    X = df[imp_cols].fillna(df[imp_cols].mean())

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Test k=2 to 8, pick best by silhouette score
    print("\nFinding optimal number of segments...")
    print(f"{'k':>4} {'silhouette':>12} {'inertia':>12}")
    print("-" * 32)

    best_k = 2
    best_score = -1
    results = []

    for k in range(2, 9):
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        sil = silhouette_score(X_scaled, labels)
        inertia = km.inertia_
        results.append((k, sil, inertia))
        print(f"{k:>4} {sil:>12.4f} {inertia:>12.1f}")
        if sil > best_score:
            best_score = sil
            best_k = k

    print(f"\nBest k = {best_k} (silhouette = {best_score:.4f})")

    # Final clustering with best k
    km_final = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    df['segment'] = km_final.fit_predict(X_scaled) + 1  # 1-indexed

    # Profile each segment using metadata
    print("\nSegment profiles:")
    meta_cols = ['age', 'skill_level', 'position', 'stress_level', 'overall_satisfaction']
    meta_cols = [c for c in meta_cols if c in df.columns]

    for seg in sorted(df['segment'].unique()):
        seg_df = df[df['segment'] == seg]
        print(f"\n  Segment {seg} — {len(seg_df)} kids ({len(seg_df)/len(df)*100:.1f}%)")
        for col in meta_cols:
            if df[col].dtype in ['float64', 'int64']:
                print(f"    {col}: {seg_df[col].mean():.2f} avg")
            else:
                top = seg_df[col].value_counts().index[0]
                print(f"    {col}: mostly '{top}'")

    # Save output
    if output_file is None:
        base = input_file.replace('.csv', '')
        output_file = f"{base}_segments.csv"

    df.to_csv(output_file, index=False)
    print(f"\nDone! Saved to: {output_file}")
    print(f"New column 'segment' added — values 1 to {best_k}")

    return df

if __name__ == "__main__":
    import sys, os

    if len(sys.argv) < 2:
        print("Usage: python segment_respondents.py <input_file.csv> [output_file.csv]")
        print("Example: python segment_respondents.py results_all.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(input_file):
        print(f"Error: file '{input_file}' not found.")
        sys.exit(1)

    segment_respondents(input_file, output_file)