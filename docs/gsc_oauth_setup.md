# GSC OAuth Setup Guide

Google Search Console does not allow service accounts to be added as users.
The GSC agent authenticates as a real Google user account using OAuth 2.0 with
a long-lived refresh token.

You run the setup script **once locally**. It opens a browser, you log in,
and it prints three values you paste into Railway. The agent then uses those
values forever (until you revoke access).

---

## Step 1 — Create OAuth 2.0 Credentials in Google Cloud Console

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Select your project (`bookshopnearme-gsc` or whichever you created earlier)
3. Navigate to **APIs & Services → Credentials**
4. Click **+ Create Credentials → OAuth 2.0 Client ID**
5. If prompted to configure a consent screen:
   - User Type: **External**
   - App name: `BookShopNearMe GSC Agent`
   - User support email: your email
   - Developer contact: your email
   - Scopes: click **Add or remove scopes** → add `.../auth/webmasters.readonly`
   - Test users: add the Google account that owns the GSC property
   - Save and continue through remaining steps
6. Back on Create OAuth Client ID:
   - Application type: **Desktop app**
   - Name: `gsc-agent-local`
   - Click **Create**
7. Click **Download JSON** — save it as `client_secret.json` somewhere outside the repo

> The file must NOT be placed inside the repo directory — `.gitignore` blocks `*.json`
> but keep it completely separate to be safe.

---

## Step 2 — Install the Setup Dependency

```bash
cd /Users/mohammedwalidnazmi/bookshopnearme-platform
source .venv/bin/activate
pip install -e apps/gsc-agent
```

This installs `google-auth-oauthlib` which the setup script requires.

---

## Step 3 — Run the Setup Script

```bash
python scripts/gsc_oauth_setup.py --client-secrets /path/to/client_secret.json
```

What happens:
1. A local HTTP server starts on a random port
2. Your browser opens to Google's OAuth consent page
3. **Log in with the Google account that owns `https://bookshopnearme.lk/` in Search Console**
4. Click Allow
5. The browser redirects to localhost — the script captures the code
6. The script exchanges the code for tokens and prints them

---

## Step 4 — Copy the Output

The script prints three lines:

```
GSC_OAUTH_CLIENT_ID=123456789-abc.apps.googleusercontent.com
GSC_OAUTH_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxxx
GSC_OAUTH_REFRESH_TOKEN=1//xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Copy all three. Do not save them to a file or paste them into `.env`.

---

## Step 5 — Set Railway Environment Variables

Railway dashboard → your project → `gsc-agent` service → **Variables**:

| Variable | Value |
|---|---|
| `GSC_OAUTH_CLIENT_ID` | _(paste value from script output)_ |
| `GSC_OAUTH_CLIENT_SECRET` | _(paste value from script output)_ |
| `GSC_OAUTH_REFRESH_TOKEN` | _(paste value from script output)_ |
| `GSC_SITE_URL` | `https://bookshopnearme.lk/` |

Remove any leftover `GSC_CREDENTIALS_PATH` or `GSC_CREDENTIALS_B64` variables
if they were set previously.

---

## Step 6 — Redeploy and Verify

```bash
git push origin main
```

Then trigger a manual run:

```bash
railway run --service gsc-agent python -m gsc_agent.agent
```

Successful startup logs look like:

```
[AUTH] OAuth credentials loaded — client_id=123456789... refresh_token=********xxxx
[AUTH] Access token refresh successful
[AUTH] Search Console property accessible — url=https://bookshopnearme.lk/ permission=siteOwner
Dates to collect: ['2026-06-01', '2026-06-02', ...]
Saved 312 records for 2026-06-01
[COMPLETED] agent=gsc_agent duration=9.1s records=624
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No refresh token returned` | App was previously authorized | Go to [myaccount.google.com/permissions](https://myaccount.google.com/permissions), remove the app, re-run the script |
| `OAuth token refresh failed: invalid_grant` | Refresh token revoked or expired | Re-run `gsc_oauth_setup.py` and update Railway variables |
| `Site not found — 0 properties` | Wrong Google account used during OAuth | Re-run the script, log in with the account that **owns** the GSC property |
| `Site not found — N properties listed` | `GSC_SITE_URL` doesn't match exactly | Copy the URL exactly from the GSC property list including trailing slash |
| Browser doesn't open | Headless environment | Copy the URL printed to the terminal and open it manually |

---

## Refresh Token Lifecycle

- Refresh tokens do not expire unless revoked
- Revocation happens if: you change your Google account password, you remove app access at [myaccount.google.com/permissions](https://myaccount.google.com/permissions), or Google revokes it for inactivity (rare for active apps)
- If the agent logs `invalid_grant`, re-run `gsc_oauth_setup.py` and update the Railway variable

---

## Security Notes

- The refresh token grants read-only Search Console access (`webmasters.readonly`)
- It cannot modify your site, GSC settings, or any other Google service
- Store it only in Railway Variables — never in git, `.env`, or any file
