# FaceGuard AI training pipeline (Phase 5)

Status: **code written; NOT executed.** PyTorch was not available when this was produced, so only the pure-Python parts
(`metrics.py`, `splits.py`) have been run and tested (`python -m pytest ai/tests`, vs scikit-learn). `data.py`, `model.py`,
`train.py` and `export.py` are syntax-checked only. **No model has been trained and no accuracy is claimed.**

## Data you must supply
A CSV manifest (paths relative to `--root`): `path,label[,identity,group,sha256]` with label `real` or `spoof`.
Use only data you are licensed and authorised to use (for example a public PAD dataset whose licence you have
checked, or consented in-house captures). Nothing is generated or downloaded by this code.
Include `identity` (person id) so the test split contains people never seen in training; without it the report says
`identity_disjoint: false` and generalisation claims are not valid.

## Run
```
pip install -r ai/requirements.txt
cd ai && python -m faceguard_ai.train --manifest data/manifest.csv --root data --out runs/exp1
python -m faceguard_ai.export runs/exp1/best.pt runs/exp1/model.onnx
```
Outputs: `train.log`, `config.json`, `split_report.json`, `history.json`, `best.pt`, `last.pt`, `test_metrics.json`.
The decision threshold is chosen on validation data and applied once to the held-out test split. The API uses the same
threshold at inference time (with an uncertainty band of `LIVENESS_UNCERTAINTY_MARGIN` around it).

## Use the model in the API
1. Prefer training on **face crops**: on the dataset page choose *Export face crops* (the API's own detector and crop
   function, so inputs at inference match exactly). Full-image exports also work but are more sensitive to framing.
2. Register `model.onnx`, `test_metrics.json` and `split_report.json` on the Models page (*Register a trained model*, set
   *Trained on* to match), or `python backend/scripts/register_model.py --run-dir runs/exp1 --name smallcnn --version 1.0.0 --crop face`.
3. Activate it on the Models page. Preprocessing in the API (`backend/app/services/inference.py`) is tested to be
   byte-identical to `faceguard_ai/data.preprocess`; keep them in sync if you change either.
Metrics: accuracy, precision, recall, F1, ROC AUC, APCER, BPCER, ACER, confusion matrix (1 = real, 0 = spoof).
