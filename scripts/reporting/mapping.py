import pandas as pd

metadata_df = pd.read_csv('Metadata_FY2324.csv', low_memory=False)            # Your metadata file
logs_df = pd.read_csv('final_merged_logs.csv')                # Merged Aadhaar masking logs

metadata_df['ATTACH_ID'] = metadata_df['ATTACH_ID'].astype(int).astype(str)
logs_df['ATTACH_ID'] = logs_df['ATTACH_ID'].astype(float).astype(int).astype(str)


merged_final = pd.merge(logs_df, metadata_df, how='left', on='ATTACH_ID')

merged_final.to_csv('final_joined_output.csv', index=False)

print("Left join complete. Output saved as 'final_joined_output.csv'")
