cd /data-disk/ahfl_deploy_gpu_new/ahfl-working-Gpu/

# 1. Check paddle.py — must show device="gpu:0", NOT use_gpu

grep -n "use_gpu\|device=" core/ocr/paddle.py

# 2. Check batch.py — must NOT have _staging or copy_object

grep -n "_staging\|copy_object\|DeleteObject" services/batch-processor/batch.py

# 3. Check logs dir exists

ls -ld logs/

# 4. GPU accessible

docker run --rm --gpus all ubuntu nvidia-smi | grep "Tesla T4"

# 5. Models mounted

ls /ahfl-models/*.pt

# 6. S3 raw bucket accessible (IAM check)

aws s3 ls 's3://ahfl-ams-raw-data-bucket-333813598364-ap-south-1-an/301025573/' --region ap-south-1 | head -3

# 7. S3 masked bucket WRITE accessible

aws s3 cp /dev/null 's3://ahfl-uat-ams-masked-data-bucket-333813598364-ap-south-1-an/_test_write' --region ap-south-1 && echo "WRITE OK"

# 8. DynamoDB accessible

aws dynamodb describe-table --table-name ahfl_processed_data --region ap-south-1 --query 'Table.TableStatus'




**Expected pass results:**

| Check           | Expected                                |
| --------------- | --------------------------------------- |
| paddle.py       | `device="gpu:0"` only, no `use_gpu` |
| batch.py        | zero matches for `_staging`           |
| logs/           | exists                                  |
| GPU             | Tesla T4 visible                        |
| models          | 4 `.pt` files                         |
| S3 raw          | lists files                             |
| S3 masked write | `WRITE OK`                            |
| DynamoDB        | `"ACTIVE"`                            |
