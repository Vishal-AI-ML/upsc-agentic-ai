UPSC AI - Admin dashboards backend (Cost / Monitoring / Experiments)
====================================================================

WHAT THIS ADDS
  These 5 files add the missing backend that powers the admin-only tabs
  (Cost, Monitoring, Experiments) which the frontend already has.

  src/api/admin_access.py        - admin allowlist helper (reads ADMIN_EMAILS)
  src/api/http_metrics_mw.py     - in-process request metrics (Monitoring data)
  src/api/routes/cost.py         - GET /cost/access, /cost/overview
  src/api/routes/monitoring.py   - GET /monitoring/access, /monitoring/overview
  src/api/routes/experiments.py  - GET /experiments/access, /experiments/overview

HOW TO INSTALL
  1. Extract this zip at the ROOT of your repo (upsc-agentic-ai/).
     It drops the files into src/api/ and src/api/routes/ automatically.
  2. Commit & push:
       git add src/api/admin_access.py src/api/http_metrics_mw.py \
               src/api/routes/cost.py src/api/routes/monitoring.py \
               src/api/routes/experiments.py
       git commit -m "feat(admin): add cost/monitoring/experiments dashboard routes"
       git push
  3. Render auto-deploys. Make sure ADMIN_EMAILS is set on Render:
       ADMIN_EMAILS=["vishalpaji4208@gmail.com"]
  4. Log out & log back in on the frontend -> the Cost, Monitoring and
     Experiments tabs appear for your admin account.

NOTES
  - No code changes needed in main.py: it already auto-loads these optional
    routers and the metrics middleware when the files are present.
  - Monitoring shows LIVE latency/throughput/error data.
  - Experiments shows REAL thumbs up/down feedback tallies from your DB.
  - Cost shows the correct dashboard shape but figures start at 0 until
    per-call token tracking is wired (a bigger, separate task).
