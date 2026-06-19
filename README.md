# Smart Ventilation AI

AI-assisted indoor ventilation control system using sensor fusion, weather context, and rule/model-based inference.

## Project Structure

- `src/` core application modules
- `data/raw/` incoming sensor and weather data
- `data/processed/` cleaned features for model training/inference
- `models/` serialized trained model artifacts
- `notebooks/` experimentation and training workflow
- `docs/` architecture and system documentation

## Quick Start

1. Create a virtual environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python src/main.py
   ```

## Notes

- Hardware sensor access is mocked by default in this scaffold.
- Replace placeholders with real drivers, credentials, and trained model.

## Raspberry Pi SSH Access

Use the following command from your computer terminal to connect to the Raspberry Pi:

```bash
ssh root@172.20.10.3 -p 2222
```
