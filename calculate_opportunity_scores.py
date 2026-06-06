import pandas as pd
import sys
import os

def calculate_opportunity_scores(input_file, output_file=None):
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} respondents.")

    # Auto-detect question numbers from column names
    q_nums = sorted(set(
        int(c.split('_')[0][1:])
        for c in df.columns if c.startswith('Q') and '_' in c
    ))
    print(f"Found {len(q_nums)} outcomes (Q{q_nums[0]} to Q{q_nums[-1]}).")

    # Calculate opportunity score for each question
    results = []
    for i in q_nums:
        imp_col = f'Q{i}_imp'
        sat_col = f'Q{i}_sat'

        if imp_col not in df.columns or sat_col not in df.columns:
            print(f"  Warning: columns missing for Q{i}, skipping.")
            continue

        imp = df[imp_col].mean()
        sat = df[sat_col].mean()
        opp = imp + max(imp - sat, 0)

        if opp >= 10:
            zone = 'hot zone'
        elif opp >= 8:
            zone = 'underserved'
        elif opp < 6:
            zone = 'overserved'
        else:
            zone = 'appropriately served'

        results.append({
            'outcome': f'Q{i}',
            'importance': round(imp, 2),
            'satisfaction': round(sat, 2),
            'opportunity_score': round(opp, 2),
            'zone': zone
        })

    # Sort by opportunity score descending
    opp_df = pd.DataFrame(results).sort_values('opportunity_score', ascending=False)

    # Determine output file name
    if output_file is None:
        base = os.path.splitext(input_file)[0]
        output_file = f"{base}_opportunity_scores.csv"

    opp_df.to_csv(output_file, index=False)
    print(f"\nDone! Saved to: {output_file}")
    print(f"\nSummary:")
    print(f"  Hot zone (>=10):          {len(opp_df[opp_df.zone == 'hot zone'])} outcomes")
    print(f"  Underserved (8-10):       {len(opp_df[opp_df.zone == 'underserved'])} outcomes")
    print(f"  Appropriately served:     {len(opp_df[opp_df.zone == 'appropriately served'])} outcomes")
    print(f"  Overserved (<6):          {len(opp_df[opp_df.zone == 'overserved'])} outcomes")
    print(f"\nTop 5 opportunities:")
    print(opp_df.head().to_string(index=False))

    return opp_df


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python calculate_opportunity_scores.py <input_file.csv> [output_file.csv]")
        print("Example: python calculate_opportunity_scores.py results.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(input_file):
        print(f"Error: file '{input_file}' not found.")
        sys.exit(1)

    calculate_opportunity_scores(input_file, output_file)