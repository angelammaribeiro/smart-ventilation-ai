from __future__ import annotations

import argparse
from dataclasses import dataclass

import pandas as pd


ALLOWED_ACTIONS = {"open_window", "close_window"}


@dataclass
class BuildStats:
    total_labels: int
    total_pairs: int
    dropped_unknown_action: int
    dropped_missing_context: int
    dropped_missing_future: int



def build_pairs(
    telemetry_csv: str,
    labels_csv: str,
    output_csv: str,
    horizon_minutes: int = 10,
    max_context_age_seconds: int = 120,
    max_future_offset_seconds: int = 120,
) -> BuildStats:
    telemetry = pd.read_csv(telemetry_csv)
    labels = pd.read_csv(labels_csv)

    telemetry["timestamp"] = pd.to_datetime(telemetry["timestamp"], utc=True, errors="coerce")
    labels["timestamp"] = pd.to_datetime(labels["timestamp"], utc=True, errors="coerce")

    telemetry = telemetry.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    labels = labels.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    dropped_unknown_action = 0
    dropped_missing_context = 0
    dropped_missing_future = 0

    rows: list[dict] = []

    for _, label_row in labels.iterrows():
        action = str(label_row.get("action_label", "")).strip()
        if action not in ALLOWED_ACTIONS:
            dropped_unknown_action += 1
            continue

        t_action = label_row["timestamp"]

        context = telemetry[telemetry["timestamp"] <= t_action]
        if context.empty:
            dropped_missing_context += 1
            continue

        context_row = context.iloc[-1]
        context_age = (t_action - context_row["timestamp"]).total_seconds()
        if context_age > max_context_age_seconds:
            dropped_missing_context += 1
            continue

        t_target = t_action + pd.Timedelta(minutes=horizon_minutes)
        telemetry["future_gap"] = (telemetry["timestamp"] - t_target).abs().dt.total_seconds()
        future_candidates = telemetry.sort_values("future_gap")
        future_row = future_candidates.iloc[0]

        if float(future_row["future_gap"]) > max_future_offset_seconds:
            dropped_missing_future += 1
            continue

        rows.append(
            {
                "timestamp_action": t_action.isoformat(),
                "action_label": action,
                "temperature_c": context_row.get("temperature_c"),
                "humidity_pct": context_row.get("humidity_pct"),
                "pressure": context_row.get("pressure"),
                "outdoor_temp_c": context_row.get("outdoor_temp_c"),
                "outdoor_humidity_pct": context_row.get("outdoor_humidity_pct"),
                "outdoor_pressure_hpa": context_row.get("outdoor_pressure_hpa"),
                "motion": context_row.get("motion"),
                "hour_of_day": int(t_action.hour),
                "temperature_c_t_plus": future_row.get("temperature_c"),
                "humidity_pct_t_plus": future_row.get("humidity_pct"),
            }
        )

    output = pd.DataFrame(rows)
    if not output.empty:
        output = output.dropna(subset=["temperature_c", "humidity_pct", "temperature_c_t_plus", "humidity_pct_t_plus"])
    output.to_csv(output_csv, index=False)

    return BuildStats(
        total_labels=len(labels),
        total_pairs=len(output),
        dropped_unknown_action=dropped_unknown_action,
        dropped_missing_context=dropped_missing_context,
        dropped_missing_future=dropped_missing_future,
    )



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build state-action-next_state training pairs")
    parser.add_argument("--telemetry-csv", default="data/raw/ha_telemetry.csv")
    parser.add_argument("--labels-csv", default="data/processed/action_labels.csv")
    parser.add_argument("--output-csv", default="data/processed/state_action_pairs.csv")
    parser.add_argument("--horizon-minutes", type=int, default=10)
    parser.add_argument("--max-context-age-seconds", type=int, default=120)
    parser.add_argument("--max-future-offset-seconds", type=int, default=120)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    stats = build_pairs(
        telemetry_csv=args.telemetry_csv,
        labels_csv=args.labels_csv,
        output_csv=args.output_csv,
        horizon_minutes=args.horizon_minutes,
        max_context_age_seconds=args.max_context_age_seconds,
        max_future_offset_seconds=args.max_future_offset_seconds,
    )
    print("Build completed:")
    print(f"- labels: {stats.total_labels}")
    print(f"- pairs: {stats.total_pairs}")
    print(f"- dropped unknown action: {stats.dropped_unknown_action}")
    print(f"- dropped missing context: {stats.dropped_missing_context}")
    print(f"- dropped missing future: {stats.dropped_missing_future}")
