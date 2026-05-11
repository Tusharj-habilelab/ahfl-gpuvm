import pandas as pd
import os

input_folder = 'raw_logs'
output_folder = 'processed_logs'
os.makedirs(output_folder, exist_ok=True)

RAW_BUCKET = os.environ.get('RAW_BUCKET', '')
prefix_to_remove = f's3://{RAW_BUCKET}/' if RAW_BUCKET else ''

for filename in os.listdir(input_folder):
    if filename.endswith('.csv'):
        file_path = os.path.join(input_folder, filename)
        df = pd.read_csv(file_path)

        df['file_path'] = df['file_path'].str.replace(prefix_to_remove, '', regex=False)
        df['file_name'] = df['file_path'].str.split('/').str[-1]
        df['ATTACH_ID'] = df['file_path'].str.split('/').str[-2]
        df['APPLICATION_NO'] = df['file_path'].str.split('/').str[-3]
        df = df.drop(columns=['id'])

        df['createdAt'] = pd.to_datetime(df['createdAt'])
        df['updatedAt'] = pd.to_datetime(df['updatedAt'])
        df['total_pages'] = 1

        agg_df = df.groupby('file_path', as_index=False).agg({
            'is_aadhaar': 'sum',
            'is_number': 'sum',
            'is_number_masked': 'sum',
            'is_QR': 'sum',
            'is_QR_masked': 'sum',
            'is_XX': 'sum',
            'createdAt': 'min',
            'updatedAt': 'max',
            'number': 'sum',
            'hw_number': 'sum',
            'uid_table': 'sum',
            'error_while_processing': 'sum',
            'total_pages': 'sum',
            'file_name': 'first',
            'ATTACH_ID': 'first',
            'APPLICATION_NO': 'first'
        })

        output_path = os.path.join(output_folder, f'updated_{filename}')
        agg_df.to_csv(output_path, index=False)

        print(f"Processed: {filename} -> {output_path}")
