import pandas as pd
import os

processed_folder = 'processed_logs'
merged_output_path = 'merged_logs.csv'

merged_df = pd.concat(
    [pd.read_csv(os.path.join(processed_folder, f)) for f in os.listdir(processed_folder) if f.endswith('.csv')],
    ignore_index=True
)

merged_df.to_csv(merged_output_path, index=False)
print(f"All processed files merged into: {merged_output_path}")
