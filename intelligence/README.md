# MEDCHECK - PI AI Module

This folder contains the optional experimental image-classification area.

## Intended structure

- `dataset/train/medicine_back/` : genuine rear-side medicine packaging examples
- `dataset/train/other/` : unrelated images for negative examples
- `dataset/validation/medicine_back/` : validation samples
- `dataset/validation/other/` : validation negatives
- `model/` : trained classifier output, if available

## Important note

The live MEDCHECK - PI demo does not claim to verify real medicine authenticity. The operator's REAL/FAKE choice is a demonstration result only, not a physical authenticity judgment.

If a true labelled dataset is not available, the app intentionally uses the prototype validation fallback and clearly labels it as `PROTOTYPE IMAGE VALIDATION — NOT A TRAINED AI MODEL`.

## Training

Run the experimental trainer when real image data is available:

```bash
python intelligence/train.py
```

## Prediction

When a trained model is present, use:

```bash
python intelligence/predict.py path/to/image.jpg
```
