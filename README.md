# Gridiron IQ — 2026 NFL + FBS analytics

## Start locally

```bash
pip install -r requirements.txt
export CFBD_API_KEY='YOUR_COLLEGEFOOTBALLDATA_API_KEY'
python server.py
```
Open http://127.0.0.1:5000 in your browser. On Windows PowerShell use `$env:CFBD_API_KEY='...'`.

The server refreshes source data on first load, on clicking Refresh, and when its 6-hour cache expires. It does **not** run continuously when shut down. For continuous updates, deploy the Flask server to a persistent web host and configure a scheduler or uptime monitor. The UI alone is not a hosted service.

## Provenance
- NFL play-by-play and player stats: nflverse GitHub release parquet datasets. Check the release URLs in `server.py` if nflverse changes its release layout.
- FBS teams, advanced stats, season team and player stats, final scores: CollegeFootballData REST API.
- College advanced endpoint can expose PPA instead of EPA; **PPA is not relabeled as EPA**. Those columns remain empty unless a verified EPA field is provided.
- Player attribution differs by provider. FBS player API fields may differ, and a source error is reported in the Data Sources tab.
- No invented numbers or silent historical fallbacks.

## Important limitations
- This is a deployable starter app, not a deployed public URL. An API key and network access are required for CFBD data.
- NFL play-by-play game count and point differential are best-effort calculations and should be audited against final schedules before production use.
- Success-rate definitions and garbage-time filters differ by source.
- Backend requests are synchronous and may be slow on first load. Production deployments should use scheduled ETL, persistent database, rate limiting and authentication.
