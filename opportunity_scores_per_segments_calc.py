import pandas as pd
import sys
import os

def opportunity_score(imp, sat):
    return round(imp + max(imp - sat, 0), 2)

def get_zone(opp):
    if opp >= 10:
        return 'hot zone'
    elif opp >= 8:
        return 'underserved'
    elif opp < 6:
        return 'overserved'
    else:
        return 'appropriately served'

def calculate_for_segment(df, label):
    q_nums = sorted(set(
        int(c.split('_')[0][1:])
        for c in df.columns if c.startswith('Q') and c.endswith('_imp')
    ))
    rows = []
    for i in q_nums:
        imp = df[f'Q{i}_imp'].mean()
        sat = df[f'Q{i}_sat'].mean()
        opp = opportunity_score(imp, sat)
        rows.append({
            'segment': label,
            'outcome': f'Q{i}',
            'importance': round(imp, 2),
            'satisfaction': round(sat, 2),
            'opportunity_score': opp,
            'zone': get_zone(opp)
        })
    return pd.DataFrame(rows).sort_values('opportunity_score', ascending=False)


def run(input_file, output_file=None):
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} respondents.")

    if 'segment' not in df.columns:
        print("Error: no 'segment' column found. Run segment_respondents.py first.")
        sys.exit(1)

    segments = sorted(df['segment'].unique())
    print(f"Found {len(segments)} segments: {segments}\n")

    all_results = []

    for seg in segments:
        seg_df = df[df['segment'] == seg]
        print(f"Segment {seg} — {len(seg_df)} kids")
        seg_scores = calculate_for_segment(seg_df, seg)
        all_results.append(seg_scores)

        hot = len(seg_scores[seg_scores.zone == 'hot zone'])
        under = len(seg_scores[seg_scores.zone == 'underserved'])
        print(f"  Hot zone: {hot} outcomes  |  Underserved: {under} outcomes")
        print(f"  Top 3 opportunities:")
        for _, row in seg_scores.head(3).iterrows():
            print(f"    {row.outcome}: {row.opportunity_score} ({row.zone})")
        print()

    combined = pd.concat(all_results, ignore_index=True)

    if output_file is None:
        output_file = input_file.replace('.csv', '_opp_per_segment.csv')

    combined.to_csv(output_file, index=False)
    print(f"Done! Saved to: {output_file}")
    print(f"Rows: {len(combined)} ({len(segments)} segments × 67 outcomes)")

    return combined


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python opportunity_scores_per_segment.py <segments_file.csv> [output_file.csv]")
        print("Example: python opportunity_scores_per_segment.py results_segments.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(input_file):
        print(f"Error: file '{input_file}' not found.")
        sys.exit(1)

    run(input_file, output_file)