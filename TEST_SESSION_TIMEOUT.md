# Session Timeout Testing Guide

## ✅ Changes Made

1. **`.streamlit/config.toml`** - Added `sessionIdleTimeout = 7200000` (2 hours)
2. **`auth.py`** - OAuth token persistence + auto-refresh mechanism
3. **`Dockerfile`** - Added session management ENV vars
4. **`railway.json`** - Healthcheck timeout: 300s → 7200s

---

## 🧪 Test Methods

### Method 1: Session Duration Test (5 minutes)

**Test the session timeout setting:**

```bash
streamlit run test_session_timeout.py
```

**What to test:**
1. Open the page, note the counter value
2. **DON'T INTERACT** with the page for 11-12 minutes
3. Refresh the page
4. **OLD (broken):** Counter resets to 0 (session expired after 10 min)
5. **NEW (fixed):** Counter continues incrementing (session still alive)

**Quick test:**
- Click "Simulate long operation (15 seconds)"
- Should complete successfully without session loss

---

### Method 2: OAuth Token Persistence Test (instant)

**Test OAuth credential storage:**

```bash
streamlit run test_oauth_token_persistence.py
```

**Test flow:**
1. Click "Simulate Login" → Check all 5 OAuth keys are set
2. Click "Simulate Token Expiry" → Token shows as expired
3. Refresh page → Auth check triggers `refresh_token_if_needed()`
4. Click "Clear Session" → All keys removed

**What to verify:**
- ✅ All OAuth keys persist in `st.session_state`
- ✅ Token expiry detection works
- ✅ Logout clears all credentials

---

### Method 3: Real Pipeline Test (15 minutes)

**Test with actual dashboard:**

```bash
streamlit run src/vendor_ai_agent/dashboard.py
```

**Test flow:**
1. Login with Google OAuth
2. Upload a document
3. Run pipeline (10-15 min processing)
4. **OLD (broken):** Session expires during processing, results lost
5. **NEW (fixed):** Session stays alive, results displayed successfully

---

### Method 4: Config Validation (instant)

**Verify config file settings:**

```bash
grep -A2 "\[runner\]" .streamlit/config.toml
```

**Expected output:**
```toml
[runner]
magicEnabled = true
fastReruns = true
sessionIdleTimeout = 7200000
```

**Verify timeout value:**
- 7200000 ms = 7200 seconds = 120 minutes = **2 hours** ✅

---

## 📊 Expected Results

### Before Fix:
- Session timeout: **10 minutes** (Streamlit default)
- OAuth tokens: **NOT stored** (only `authenticated` + `email`)
- Long pipeline: **FAILS** with session loss
- Healthcheck: **5 minutes**

### After Fix:
- Session timeout: **2 hours** (120 minutes)
- OAuth tokens: **STORED** (`token`, `expiry`, `refresh_token`)
- Token refresh: **AUTOMATIC** when expired
- Long pipeline: **SUCCEEDS** with results preserved
- Healthcheck: **2 hours**

---

## 🔍 Troubleshooting

### If session still expires:

1. **Check config file:**
   ```bash
   cat .streamlit/config.toml | grep sessionIdleTimeout
   ```
   Should show: `sessionIdleTimeout = 7200000`

2. **Check Streamlit is using the config:**
   - Restart Streamlit completely
   - Check logs for "Using config from .streamlit/config.toml"

3. **Check browser console:**
   - F12 → Console → Look for WebSocket disconnects
   - Should NOT see "Session expired" before 2 hours

### If OAuth tokens not persisting:

1. **Check session state:**
   - Run `test_oauth_token_persistence.py`
   - Verify all 5 keys are set after login

2. **Check auth.py changes:**
   ```bash
   grep "credentials_token" src/vendor_ai_agent/auth.py
   ```
   Should find 3+ lines storing tokens

---

## 🚀 Production Deployment

After testing locally, deploy to Railway:

```bash
git add .streamlit/config.toml
git add src/vendor_ai_agent/auth.py
git add Dockerfile
git add railway.json
git commit -m "Fix session timeout and OAuth token persistence"
git push
```

Railway will:
1. Build new Docker image with updated ENV vars
2. Use new `config.toml` with 2-hour timeout
3. Apply new healthcheck timeout (7200s)

---

## ⏱️ Timeline Comparison

| Event | OLD (broken) | NEW (fixed) |
|-------|--------------|-------------|
| Session timeout | 10 minutes | 2 hours |
| Pipeline duration | 10-15 minutes | 10-15 minutes |
| **Result** | ❌ TIMEOUT | ✅ SUCCESS |

---

## 📝 Quick Test Commands

```bash
# Test 1: Session duration
streamlit run test_session_timeout.py

# Test 2: OAuth persistence
streamlit run test_oauth_token_persistence.py

# Test 3: Config validation
grep sessionIdleTimeout .streamlit/config.toml

# Test 4: Real dashboard
streamlit run src/vendor_ai_agent/dashboard.py
```

**Fastest test:** Run Test 2 (OAuth persistence) - takes 30 seconds to verify tokens are stored correctly.
