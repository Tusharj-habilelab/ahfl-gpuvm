========================================================================
  AHFL MASKING ENGINE — MODEL METADATA REPORT
  Generated : 2026-03-24 19:52:19
  Models Dir: /Users/tusharjain/projects/AHFL-Masking 1.1/scripts/../services/masking-engine/models
========================================================================

========================================================================
  OVERVIEW
========================================================================
  Model                      Task       Classes       Params      Size  Inference
  --------------------------------------------------------------------
  main.pt                    detect     6          3,006,818     6.0 MB  ✓ OK
  best.pt                    detect     5          3,006,623     6.0 MB  ✓ OK
  front_back_detect.pt       detect     6          3,006,818     6.0 MB  ✓ OK
  yolov8n.pt                 detect     80         3,151,904     6.2 MB  ✓ OK

========================================================================
  MODEL: main.pt
========================================================================
  Role        : Primary detector — locates raw Aadhaar number regions and QR codes
  Env Var     : MODEL_MAIN
  File Path   : /Users/tusharjain/projects/AHFL-Masking 1.1/scripts/../services/masking-engine/models/main.pt
  File Size   : 5.97 MB

  [ Architecture ]
    Model Class      : DetectionModel
    Task             : detect
    Total Layers     : 23
    Total Parameters : 3,006,818
    Trainable Params : 0
    Detection Stride : [8.0, 16.0, 32.0]

  [ First Layer (Stem Conv) ]
    Input Channels   : 3
    Output Channels  : 16
    Kernel Size      : [3, 3]
    Stride           : [2, 2]

  [ Layer Type Breakdown ]
    C2f                            x8
    Conv                           x7
    Concat                         x4
    Upsample                       x2
    SPPF                           x1
    Detect                         x1

  [ Classes — 6 total ]
    [ 0]  aadhaar
    [ 1]  number
    [ 2]  qr
    [ 3]  number_anticlockwise
    [ 4]  number_inverse
    [ 5]  others

  [ Dummy Inference (640×640 black image) ]
    Status           : PASSED
    Boxes Detected   : 0

========================================================================
  MODEL: best.pt
========================================================================
  Role        : Masking state classifier — distinguishes masked vs unmasked regions
  Env Var     : MODEL_BEST
  File Path   : /Users/tusharjain/projects/AHFL-Masking 1.1/scripts/../services/masking-engine/models/best.pt
  File Size   : 5.95 MB

  [ Architecture ]
    Model Class      : DetectionModel
    Task             : detect
    Total Layers     : 23
    Total Parameters : 3,006,623
    Trainable Params : 0
    Detection Stride : [8.0, 16.0, 32.0]

  [ First Layer (Stem Conv) ]
    Input Channels   : 3
    Output Channels  : 16
    Kernel Size      : [3, 3]
    Stride           : [2, 2]

  [ Layer Type Breakdown ]
    C2f                            x8
    Conv                           x7
    Concat                         x4
    Upsample                       x2
    SPPF                           x1
    Detect                         x1

  [ Classes — 5 total ]
    [ 0]  is_number
    [ 1]  is_number_masked
    [ 2]  is_xx
    [ 3]  is_qr
    [ 4]  is_qr_masked

  [ Dummy Inference (640×640 black image) ]
    Status           : PASSED
    Boxes Detected   : 0

========================================================================
  MODEL: front_back_detect.pt
========================================================================
  Role        : Side classifier — identifies Aadhaar front / back face
  Env Var     : MODEL_FRONT_BACK
  File Path   : /Users/tusharjain/projects/AHFL-Masking 1.1/scripts/../services/masking-engine/models/front_back_detect.pt
  File Size   : 5.96 MB

  [ Architecture ]
    Model Class      : DetectionModel
    Task             : detect
    Total Layers     : 23
    Total Parameters : 3,006,818
    Trainable Params : 0
    Detection Stride : [8.0, 16.0, 32.0]

  [ First Layer (Stem Conv) ]
    Input Channels   : 3
    Output Channels  : 16
    Kernel Size      : [3, 3]
    Stride           : [2, 2]

  [ Layer Type Breakdown ]
    C2f                            x8
    Conv                           x7
    Concat                         x4
    Upsample                       x2
    SPPF                           x1
    Detect                         x1

  [ Classes — 6 total ]
    [ 0]  Aadhaar
    [ 1]  Front
    [ 2]  Back
    [ 3]  QR
    [ 4]  Number
    [ 5]  Other

  [ Dummy Inference (640×640 black image) ]
    Status           : PASSED
    Boxes Detected   : 0

========================================================================
  MODEL: yolov8n.pt
========================================================================
  Role        : Base pretrained YOLOv8n (COCO) — backbone / fallback
  Env Var     : MODEL_YOLO_N
  File Path   : /Users/tusharjain/projects/AHFL-Masking 1.1/scripts/../services/masking-engine/models/yolov8n.pt
  File Size   : 6.25 MB

  [ Architecture ]
    Model Class      : DetectionModel
    Task             : detect
    Total Layers     : 23
    Total Parameters : 3,151,904
    Trainable Params : 0
    Detection Stride : [8.0, 16.0, 32.0]

  [ First Layer (Stem Conv) ]
    Input Channels   : 3
    Output Channels  : 16
    Kernel Size      : [3, 3]
    Stride           : [2, 2]

  [ Layer Type Breakdown ]
    C2f                            x8
    Conv                           x7
    Concat                         x4
    Upsample                       x2
    SPPF                           x1
    Detect                         x1

  [ Classes — 80 total ]
    [ 0]  person
    [ 1]  bicycle
    [ 2]  car
    [ 3]  motorcycle
    [ 4]  airplane
    [ 5]  bus
    [ 6]  train
    [ 7]  truck
    [ 8]  boat
    [ 9]  traffic light
    [10]  fire hydrant
    [11]  stop sign
    [12]  parking meter
    [13]  bench
    [14]  bird
    [15]  cat
    [16]  dog
    [17]  horse
    [18]  sheep
    [19]  cow
    [20]  elephant
    [21]  bear
    [22]  zebra
    [23]  giraffe
    [24]  backpack
    [25]  umbrella
    [26]  handbag
    [27]  tie
    [28]  suitcase
    [29]  frisbee
    [30]  skis
    [31]  snowboard
    [32]  sports ball
    [33]  kite
    [34]  baseball bat
    [35]  baseball glove
    [36]  skateboard
    [37]  surfboard
    [38]  tennis racket
    [39]  bottle
    [40]  wine glass
    [41]  cup
    [42]  fork
    [43]  knife
    [44]  spoon
    [45]  bowl
    [46]  banana
    [47]  apple
    [48]  sandwich
    [49]  orange
    [50]  broccoli
    [51]  carrot
    [52]  hot dog
    [53]  pizza
    [54]  donut
    [55]  cake
    [56]  chair
    [57]  couch
    [58]  potted plant
    [59]  bed
    [60]  dining table
    [61]  toilet
    [62]  tv
    [63]  laptop
    [64]  mouse
    [65]  remote
    [66]  keyboard
    [67]  cell phone
    [68]  microwave
    [69]  oven
    [70]  toaster
    [71]  sink
    [72]  refrigerator
    [73]  book
    [74]  clock
    [75]  vase
    [76]  scissors
    [77]  teddy bear
    [78]  hair drier
    [79]  toothbrush

  [ Dummy Inference (640×640 black image) ]
    Status           : PASSED
    Boxes Detected   : 0

========================================================================
  CROSS-MODEL COMPARISON
========================================================================
  Input Resolution  : 640×640 (all models)
  Input Channels    : 3 — RGB (all models)
  Backbone          : YOLOv8n (all models)
  Strides           : [8, 16, 32] (all models)

  Model                       Layers      Params   Classes      Size
  -----------------------------------------------------------------
  main.pt                         23   3,006,818         6     6.0 MB
  best.pt                         23   3,006,623         5     6.0 MB
  front_back_detect.pt            23   3,006,818         6     6.0 MB
  yolov8n.pt                      23   3,151,904        80     6.2 MB

  Pipeline Order:
    1. front_back_detect.pt  →  classify Aadhaar side (Front/Back)
    2. main.pt               →  detect number + QR regions
    3. best.pt               →  verify masking state per region
    4. yolov8n.pt            →  base COCO backbone (not fine-tuned)

========================================================================
  END OF REPORT
========================================================================