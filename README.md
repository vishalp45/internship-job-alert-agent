# Job Agent
Daily job/internship alert agent (free stack: GitHub Actions + Gemini free tier + email).

## Phase 1 checklist
- [ ] Private GitHub repo, push this folder
- [ ] Gmail: turn on 2-Step Verification, create an App Password, copy .env.example to .env and fill it
- [ ] python notify_email.py  (test email arrives)
- [ ] GitHub Secrets: EMAIL_ADDRESS, EMAIL_APP_PASSWORD, EMAIL_TO (later GOOGLE_API_KEY)
- [ ] Replace companies.csv rows with your real list
- [ ] python detect_ats.py, then fix any 'custom' rows by hand
- [ ] Phase 2: fetchers + filter + digest + daily.yml cron

Never commit .env. Copy .env.example to .env for local runs.
