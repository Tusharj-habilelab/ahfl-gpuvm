# Community 15: run_inference()

**Members:** 11

## Nodes

- **setup_and_first_inference** (`scripts_setup_and_first_inference_py`, File, degree: 10)
- **check_yolo_models()** (`scripts_setup_and_first_inference_py_check_yolo_models`, Function, degree: 2)
- **argparse** (`scripts_setup_and_first_inference_py_import_argparse`, Module, degree: 1)
- **gc** (`scripts_setup_and_first_inference_py_import_gc`, Module, degree: 1)
- **logging** (`scripts_setup_and_first_inference_py_import_logging`, Module, degree: 1)
- **os** (`scripts_setup_and_first_inference_py_import_os`, Module, degree: 1)
- **pathlib.Path** (`scripts_setup_and_first_inference_py_import_pathlib_path`, Module, degree: 1)
- **sys** (`scripts_setup_and_first_inference_py_import_sys`, Module, degree: 1)
- **init_paddle_ocr()** (`scripts_setup_and_first_inference_py_init_paddle_ocr`, Function, degree: 2)
- **main()** (`scripts_setup_and_first_inference_py_main`, Function, degree: 5)
- **run_inference()** (`scripts_setup_and_first_inference_py_run_inference`, Function, degree: 3)

## Relationships

- scripts_setup_and_first_inference_py → scripts_setup_and_first_inference_py_import_os (imports)
- scripts_setup_and_first_inference_py → scripts_setup_and_first_inference_py_import_sys (imports)
- scripts_setup_and_first_inference_py → scripts_setup_and_first_inference_py_import_gc (imports)
- scripts_setup_and_first_inference_py → scripts_setup_and_first_inference_py_import_argparse (imports)
- scripts_setup_and_first_inference_py → scripts_setup_and_first_inference_py_import_logging (imports)
- scripts_setup_and_first_inference_py → scripts_setup_and_first_inference_py_import_pathlib_path (imports)
- scripts_setup_and_first_inference_py → scripts_setup_and_first_inference_py_check_yolo_models (defines)
- scripts_setup_and_first_inference_py → scripts_setup_and_first_inference_py_init_paddle_ocr (defines)
- scripts_setup_and_first_inference_py → scripts_setup_and_first_inference_py_run_inference (defines)
- scripts_setup_and_first_inference_py → scripts_setup_and_first_inference_py_main (defines)
- scripts_setup_and_first_inference_py_run_inference → scripts_setup_and_first_inference_py_main (calls)
- scripts_setup_and_first_inference_py_main → scripts_setup_and_first_inference_py_check_yolo_models (calls)
- scripts_setup_and_first_inference_py_main → scripts_setup_and_first_inference_py_init_paddle_ocr (calls)
- scripts_setup_and_first_inference_py_main → scripts_setup_and_first_inference_py_run_inference (calls)

