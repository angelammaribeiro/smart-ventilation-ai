# System Description

Smart Ventilation AI collects indoor environmental telemetry (temperature, humidity, CO2, and window state), combines it with weather context, and recommends whether to ventilate.

## Functional Flow

1. Read sensor values from physical sensors (or mock fallback).
2. Fetch outside weather indicators.
3. Build an inference feature vector.
4. Predict comfort/air-quality risk.
5. Produce action recommendation (`open_window`, `close_window`, or `hold`).
6. Log and publish decision over MQTT.

## Non-Functional Goals

- Near real-time recommendations.
- Modular components for hardware replacement.
- Clear separation between data collection, inference, and communication.
