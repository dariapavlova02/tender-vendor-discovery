# Railway Deployment Guide

This guide walks you through deploying the Vendor AI Agent dashboard to Railway with Google OAuth authentication and PostgreSQL database migration.

## Architecture Overview

- **Single Docker Container**: Streamlit dashboard + pipeline execution
- **Railway PostgreSQL**: Managed database service
- **Google OAuth**: Authentication with email whitelist
- **Authorized User**: dashapavlova999@gmail.com

## Prerequisites

1. Railway account (https://railway.app)
2. Google Cloud Project with OAuth 2.0 credentials
3. Local SQLite database (`vendor_ai.db`) with parsed data
4. GitHub repository for automatic deployments

## Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create a new project or select existing one
3. Click **"Create Credentials" → "OAuth client ID"**
4. Choose **"Web application"**
5. Configure:
   - **Name**: Vendor AI Agent Dashboard
   - **Authorized redirect URIs**: `https://your-app-name.up.railway.app/oauth2callback` (update after deployment)
6. Save your **Client ID** and **Client Secret**

## Step 2: Create Railway Project

1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Click **"New Project"**
3. Choose **"Deploy from GitHub repo"**
4. Connect your repository: `vendor_ai_agent`
5. Railway will automatically detect the `Dockerfile` and `railway.json`

## Step 3: Add PostgreSQL Database

1. In your Railway project, click **"New"**
2. Select **"Database" → "Add PostgreSQL"**
3. Railway automatically provides `DATABASE_URL` environment variable
4. Note: Do NOT manually set DATABASE_URL - Railway handles this

## Step 4: Configure Environment Variables

1. In Railway project, go to your service → **"Variables"** tab
2. Add the following variables (use `.env.railway.example` as reference):

```bash
# Google OAuth (from Step 1)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# OAuth Redirect URI (replace with your Railway domain)
OAUTH_REDIRECT_URI=https://your-app-name.up.railway.app/oauth2callback

# Email Whitelist
ALLOWED_EMAILS=dashapavlova999@gmail.com

# OpenAI API Key (required for LLM analysis)
OPENAI_API_KEY=sk-your-openai-api-key

# Optional: Add other API keys if you have them
SAM_GOV_API_KEY=your-sam-gov-api-key
APOLLO_API_KEY=your-apollo-api-key
SERPER_API_KEY=your-serper-api-key
GOOGLE_PLACES_API_KEY=your-google-places-api-key
```

3. Click **"Save"** - Railway will automatically redeploy

## Step 5: Get Your Railway Domain

1. After deployment completes, Railway provides a public URL
2. Find it in: **Service Settings → "Domains"** tab
3. Copy the domain (e.g., `your-app-name.up.railway.app`)
4. Go back to [Google Cloud Console OAuth Credentials](https://console.cloud.google.com/apis/credentials)
5. Edit your OAuth client and update **Authorized redirect URIs**:
   - Replace temporary URL with: `https://your-actual-railway-domain.up.railway.app/oauth2callback`
6. Save changes

## Step 6: Migrate SQLite Data to PostgreSQL

**IMPORTANT**: Do this BEFORE using the dashboard for the first time to preserve your 443,499 vendors and 58,186 contacts.

### Option A: Local Migration (Recommended)

Run the migration script from your local machine:

```bash
# 1. Get PostgreSQL connection string from Railway
# Go to: Railway Project → PostgreSQL service → "Connect" tab
# Copy the "PostgreSQL Connection URL"

# 2. Set environment variable
export DATABASE_URL="postgresql://user:password@host:port/database"

# 3. Run migration script
poetry install  # Install dependencies if not already done
poetry run python scripts/migrate_sqlite_to_postgres.py

# Expected output:
# ✓ Source SQLite: vendor_ai.db (435 MB, 443,499 vendors)
# ✓ Target PostgreSQL: Connected
# ✓ Migrating vendors... [Progress bar]
# ✓ Migrating contacts... [Progress bar]
# ✓ Migration complete! (~10 minutes)
```

### Option B: Railway Console Migration

If you prefer to run migration on Railway:

```bash
# 1. Push migration script to GitHub
git add scripts/migrate_sqlite_to_postgres.py
git commit -m "Add database migration script"
git push

# 2. In Railway dashboard, open your service
# 3. Click "Settings" → "Deploy"
# 4. Under "Custom Start Command", temporarily change to:
python scripts/migrate_sqlite_to_postgres.py

# 5. Wait for migration to complete (check logs)
# 6. Revert "Custom Start Command" back to:
streamlit run src/vendor_ai_agent/dashboard.py
```

**Note**: Option A is recommended as it's faster and you can monitor progress locally.

## Step 7: Verify Deployment

1. Visit your Railway domain: `https://your-app-name.up.railway.app`
2. You should see **"🔐 Authentication Required"** page
3. Click **"Sign in with Google"**
4. Authenticate with `dashapavlova999@gmail.com`
5. After successful login, you'll see the dashboard

## Step 8: Test Database Connection

1. In the dashboard, go to **"Database Status"** section (if available)
2. Verify vendor/contact counts match your migrated data:
   - **Vendors**: ~443,499
   - **Contacts**: ~58,186
3. Try running a simple tender analysis to ensure pipeline works

## Troubleshooting

### Authentication Issues

**Problem**: "Access denied. Email not authorized"
- **Solution**: Verify `ALLOWED_EMAILS` in Railway environment variables includes your email

**Problem**: OAuth redirect error
- **Solution**: Check `OAUTH_REDIRECT_URI` matches your Railway domain exactly

### Database Issues

**Problem**: "Connection refused" or database errors
- **Solution**: Ensure PostgreSQL service is running in Railway and `DATABASE_URL` is auto-provided

**Problem**: Empty database after deployment
- **Solution**: Run migration script (Step 6) - data won't migrate automatically

### Deployment Issues

**Problem**: Build fails with "Poetry dependencies not installed"
- **Solution**: Ensure `pyproject.toml` and `poetry.lock` are committed to Git

**Problem**: Streamlit not starting
- **Solution**: Check Railway logs for errors. Verify `PORT` environment variable is used in startup command

## Adding More Authorized Users

To allow additional users:

1. Go to Railway → Your Service → **"Variables"**
2. Edit `ALLOWED_EMAILS`:
   ```
   ALLOWED_EMAILS=dashapavlova999@gmail.com,another.user@gmail.com,third.user@gmail.com
   ```
3. Save - Railway will automatically redeploy
4. New users can now sign in with their Google accounts

## Continuous Deployment

Railway automatically deploys when you push to GitHub:

```bash
# Make changes to code
git add .
git commit -m "Update dashboard feature"
git push origin main

# Railway automatically:
# 1. Detects push
# 2. Builds new Docker image
# 3. Deploys with zero downtime
# 4. Preserves PostgreSQL data
```

## Cost Considerations

- **Railway Free Tier**: $5 credit/month (sufficient for light usage)
- **PostgreSQL**: Included in free tier (up to 1GB storage)
- **Estimated costs** (if exceeding free tier):
  - Compute: ~$5-10/month (1 container, 512MB RAM)
  - Database: ~$5/month (PostgreSQL with backups)

## Security Best Practices

1. **Never commit secrets**: Use `.env` files only locally, never in Git
2. **Rotate OAuth credentials** periodically (every 6 months)
3. **Monitor access logs**: Check Railway logs for unauthorized access attempts
4. **Whitelist only trusted emails**: Keep `ALLOWED_EMAILS` minimal
5. **Use HTTPS only**: Railway provides automatic SSL certificates

## Backup Strategy

Railway PostgreSQL includes automatic backups:
- **Daily snapshots**: Last 7 days retained
- **Manual backups**: Go to PostgreSQL service → "Backups" tab
- **Restore**: Click on backup snapshot → "Restore"

**Recommendation**: Export critical data monthly via dashboard Excel export feature.

## Support

- **Railway Docs**: https://docs.railway.app
- **Google OAuth Docs**: https://developers.google.com/identity/protocols/oauth2
- **Project Issues**: Contact your development team

---

**Deployment Checklist**:
- [ ] Google OAuth credentials created
- [ ] Railway project set up with PostgreSQL
- [ ] Environment variables configured
- [ ] Railway domain added to OAuth redirect URIs
- [ ] SQLite data migrated to PostgreSQL
- [ ] Dashboard accessible and authentication working
- [ ] Test tender analysis pipeline execution
- [ ] Backup strategy in place
