#!/bin/bash
# Cron job script for nightly relationship refresh
# Add to crontab: 0 2 * * * /path/to/run_nightly_refresh.sh

cd "$(dirname "$0")/.."

# Activate virtual environment
source venv/bin/activate

# Run the nightly refresh
python app/tasks/nightly_refresh.py >> logs/nightly_refresh.log 2>&1

echo "Nightly refresh completed at $(date)" >> logs/nightly_refresh.log
