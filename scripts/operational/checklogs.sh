                                                                                                                                                                                                    
#!/bin/bash                                                                                                                                                                                         
export PYTHONPATH=/data/python-packages                                                                                                                                                                                                                                                                                                                                                                                                                          
cd /data/batches/3/utils || exit                                                                                                                                                                    
python3 export_logs.py                                                                                                                                                                              
python3 count_processed_files.py masking_logs_052024.csv                                                                                                                                            
cd /data/batches/4/utils || exit                                                                                                                                                                    
python3 export_logs.py                                                                                                                                                                              
python3 count_processed_files.py masking_logs_062024.csv 
cd /data/batches/1/utils || exit                                                                                                                                                                    
python3 export_logs.py                                                                                                                                                                              
python3 count_processed_files.py masking_logs_072024.csv                                                                                                                                            
cd /data/batches/5/utils || exit                                                                                                                                                                    
python3 export_logs.py                                                                                                                                                                              
python3 count_processed_files.py masking_logs_082024.csv                                                                                                                                            
cd /data/batches/6/utils || exit                                                                                                                                                                    
python3 export_logs.py                                                                                                                                                                              
python3 count_processed_files.py masking_logs_092024.csv                                                                                                                                            
cd /data/batches/7/utils || exit                                                                                                                                                                    
python3 export_logs.py                                                                                                                                                                              
python3 count_processed_files.py masking_logs_102024.csv                                                                                                                                            
cd /data/batches/8/utils || exit                                                                                                                                                                    
python3 export_logs.py                                                                                                                                                                              
python3 count_processed_files.py masking_logs_112024.csv 
cd /data/batches/11/utils || exit
python3 export_logs.py
python3 count_processed_files.py masking_logs_122024.csv
cd /data/batches/9/utils || exit
python3 export_logs.py
python3 count_processed_files.py masking_logs_012025_1.csv
cd /data/batches/10/utils || exit
python3 export_logs.py
python3 count_processed_files.py masking_logs_012025_2.csv
cd /data/batches/2/utils || exit                                                                                                                                                                    
python3 export_logs.py                                                                                                                                                                              
python3 count_processed_files.py masking_logs_022025_1.csv  
cd /data/batches/14/utils || exit
python3 export_logs.py
python3 count_processed_files.py masking_logs_022025_2.csv
cd /data/batches/15/utils || exit
python3 export_logs.py
python3 count_processed_files.py masking_logs_022025_3.csv
cd /data/batches/12/utils || exit
python3 export_logs.py
python3 count_processed_files.py masking_logs_032025_1.csv
cd /data/batches/13/utils || exit
python3 export_logs.py
python3 count_processed_files.py masking_logs_032025_2.csv