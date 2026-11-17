# Optional image analysis

The normal application uses OpenCV prototype checks and an optional reference-image match. The only supported identification is **Iron and Folic Acid Tablets IP**. Without its genuine reference photo, package-like images go to manual review.

Copy a genuine, authorized reference image to `dataset/reference/iron_folic_acid_reference.jpg`. A visual match does not establish medicine authenticity.

Optional binary training data:

```text
dataset/
  train/
    medicine_back/
    other/
  validation/
    medicine_back/
    other/
```

Train by running `python intelligence/train.py` after installing a compatible TensorFlow package. Training requires real images in every class/split and writes `intelligence/model/trained_model.keras`. The classifier can help distinguish package-like images from other images, but cannot identify this medicine by itself. A separate reference match is still required. Evaluate against independent data; no performance is claimed by this project.
