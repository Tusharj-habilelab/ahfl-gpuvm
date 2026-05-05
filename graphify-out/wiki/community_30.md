# Community 30: YOLORunner

**Members:** 5

## Nodes

- **YOLORunner** (`core_models_yolo_runner_py_yolorunner`, Class, degree: 5)
- **.get_best()** (`core_models_yolo_runner_py_yolorunner_get_best`, Method, degree: 2)
- **.get_main()** (`core_models_yolo_runner_py_yolorunner_get_main`, Method, degree: 2)
- **.__init__()** (`core_models_yolo_runner_py_yolorunner_init`, Method, degree: 1)
- **.run_inference()** (`core_models_yolo_runner_py_yolorunner_run_inference`, Method, degree: 3)

## Relationships

- core_models_yolo_runner_py_yolorunner → core_models_yolo_runner_py_yolorunner_init (defines)
- core_models_yolo_runner_py_yolorunner → core_models_yolo_runner_py_yolorunner_get_main (defines)
- core_models_yolo_runner_py_yolorunner → core_models_yolo_runner_py_yolorunner_get_best (defines)
- core_models_yolo_runner_py_yolorunner → core_models_yolo_runner_py_yolorunner_run_inference (defines)
- core_models_yolo_runner_py_yolorunner_run_inference → core_models_yolo_runner_py_yolorunner_get_best (calls)
- core_models_yolo_runner_py_yolorunner_run_inference → core_models_yolo_runner_py_yolorunner_get_main (calls)

