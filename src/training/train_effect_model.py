from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error


ALLOWED_ACTIONS = ("open_window", "close_window")


@dataclass
class ActionModelResult:
    action: str
    train_size: int
    test_size: int
    mae_temp: float
    mae_humidity: float



def _time_split(df: pd.DataFrame, test_ratio: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_idx = int(len(df) * (1.0 - test_ratio))
    split_idx = max(1, min(split_idx, len(df) - 1))
    train = df.iloc[:split_idx].copy()
    test = df.iloc[split_idx:].copy()
    return train, test



def train_effect_models(
    pairs_csv: str,
    model_path: str,
    test_ratio: float = 0.2,
    min_samples_per_action: int = 30,
) -> list[ActionModelResult]:
    df = pd.read_csv(pairs_csv)
    if df.empty:
        raise ValueError("No rows found in pairs dataset.")

    required = {
        "timestamp_action",
        "action_label",
        "temperature_c",
        "humidity_pct",
        "pressure",
        "outdoor_temp_c",
        "outdoor_humidity_pct",
        "outdoor_pressure_hpa",
        "motion",
        "hour_of_day",
        "temperature_c_t_plus",
        "humidity_pct_t_plus",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["timestamp_action"] = pd.to_datetime(df["timestamp_action"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp_action"]).sort_values("timestamp_action").reset_index(drop=True)

    feature_cols = [
        "temperature_c",
        "humidity_pct",
        "pressure",
        "outdoor_temp_c",
        "outdoor_humidity_pct",
        "outdoor_pressure_hpa",
        "motion",
        "hour_of_day",
    ]
    target_cols = ["temperature_c_t_plus", "humidity_pct_t_plus"]

    model_bundle: dict[str, Any] = {
        "feature_cols": feature_cols,
        "target_cols": target_cols,
        "horizon_minutes": 10,
        "models": {},
    }

    results: list[ActionModelResult] = []

    for action in ALLOWED_ACTIONS:
        subset = df[df["action_label"] == action].copy()
        subset["motion"] = subset["motion"].astype(float)

        subset = subset.dropna(subset=feature_cols + target_cols)
        if len(subset) < min_samples_per_action:
            print(f"Skipping action {action}: only {len(subset)} samples (min {min_samples_per_action})")
            continue

        train_df, test_df = _time_split(subset, test_ratio=test_ratio)

        X_train = train_df[feature_cols]
        y_train = train_df[target_cols]
        X_test = test_df[feature_cols]
        y_test = test_df[target_cols]

        model = RandomForestRegressor(
            n_estimators=300,
            random_state=42,
            min_samples_leaf=2,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)

        pred = model.predict(X_test)
        mae_temp = mean_absolute_error(y_test["temperature_c_t_plus"], pred[:, 0])
        mae_humidity = mean_absolute_error(y_test["humidity_pct_t_plus"], pred[:, 1])

        model_bundle["models"][action] = model
        results.append(
            ActionModelResult(
                action=action,
                train_size=len(train_df),
                test_size=len(test_df),
                mae_temp=float(mae_temp),
                mae_humidity=float(mae_humidity),
            )
        )

    if not model_bundle["models"]:
        raise ValueError("No action models were trained. Check sample counts and labels.")

    out_path = Path(model_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_bundle, out_path)

    return results



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train counterfactual effect models for window actions")
    parser.add_argument("--pairs-csv", default="data/processed/state_action_pairs.csv")
    parser.add_argument("--model-path", default="models/effect_model.pkl")
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--min-samples-per-action", type=int, default=30)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_results = train_effect_models(
        pairs_csv=args.pairs_csv,
        model_path=args.model_path,
        test_ratio=args.test_ratio,
        min_samples_per_action=args.min_samples_per_action,
    )

    print("Training completed")
    for result in run_results:
        print(
            f"- action={result.action} train={result.train_size} test={result.test_size} "
            f"MAE_temp={result.mae_temp:.3f} MAE_humidity={result.mae_humidity:.3f}"
        )
