# There will be metadata .xlsx files that need to be merged, the files will be in the folder named metadata

import pandas as pd
import os
input_folder = 'metadata'
metadata_files = [f for f in os.listdir(input_folder) if f.endswith('.xlsx')]
merged_metadata = pd.DataFrame()
for file in metadata_files:
    file_path = os.path.join(input_folder, file)
    df = pd.read_excel(file_path)
    merged_metadata = pd.concat([merged_metadata, df], ignore_index=True)
output_path = 'Metadata_FY2526.csv'
merged_metadata.to_csv(output_path, index=False)