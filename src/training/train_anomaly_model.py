from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DEFAULT_FEATURE_COLS = [
    "temperature_c",
    "humidity_pct",
    "co2_ppm",
    "window_open",
    "temp_out",
    "humidity_out",
    "wind_speed",
    "is_raining",
    "hour_of_day",
]


def train_anomaly_model(
    telemetry_csv: str,
    model_path: str,
    contamination: float = 0.03,
    random_state: int = 42,
) -> dict[str, Any]:
    df = pd.read_csv(telemetry_csv)
    if df.empty:
        raise ValueError("No rows found in telemetry dataset.")

    missing = [col for col in DEFAULT_FEATURE_COLS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    X = df[DEFAULT_FEATURE_COLS].copy()
    X = X.apply(pd.to_numeric, errors="coerce").dropna()
    if len(X) < 50:
        raise ValueError(f"Not enough clean rows for anomaly training: {len(X)}")

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "iforest",
                IsolationForest(
                    n_estimators=300,
                    contamination=contamination,
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    pipeline.fit(X)

    inlier_ratio = float((pipeline.predict(X) == 1).mean())
    bundle: dict[str, Any] = {
        "feature_cols": list(DEFAULT_FEATURE_COLS),
        "model": pipeline,
        "contamination": contamination,
        "trained_rows": int(len(X)),
        "inlier_ratio_train": inlier_ratio,
    }

    out = Path(model_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out)
    return bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train unsupervised anomaly model for ventilation telemetry")
    parser.add_argument("--telemetry-csv", default="data/raw/sensor_data.csv")
    parser.add_argument("--model-path", default="models/anomaly_model.pkl")
    parser.add_argument("--contamination", type=float, default=0.03)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = train_anomaly_model(
        telemetry_csv=args.telemetry_csv,
        model_path=args.model_path,
        contamination=args.contamination,
        random_state=args.random_state,
    )
    print("Anomaly model training completed")
    print(f"- trained_rows: {result['trained_rows']}")
    print(f"- contamination: {result['contamination']}")
    print(f"- inlier_ratio_train: {result['inlier_ratio_train']:.3f}")
