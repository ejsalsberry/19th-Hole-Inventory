# The 19th Hole Inventory (v1)

A simple local web app for daily bar inventory tracking using Python + SQLite.

## Version 1 goals covered
- Single-user local app (no login/auth)
- Tracks unopened bottles separately from opened bottles
- Stores one daily inventory record per product/date (updates existing if re-entered)
- Open-bottle weigh-in workflow with estimated ounces remaining
- Historical daily log view
- Restock/delivery entry tracking
- Low-stock alerts using ounce and unopened-bottle thresholds
- Forecast page with rolling-usage structure for 5-week planning
- CSV export + print-friendly inventory report

## Tech stack
- Python 3
- Flask
- SQLite

## Linux Mint setup (recommended first step)
Because you moved from Fedora to Mint, run this once:

```bash
./scripts/setup_mint.sh

cd ~/projects/19th-Hole-Inventory
mkdir -p scripts templates static

cat > requirements.txt <<'EOF'
Flask==3.0.3
