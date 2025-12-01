import streamlit as st
from datetime import datetime, timezone, timedelta

st.title("OAuth Token Persistence Test")

if "test_mode" not in st.session_state:
    st.session_state.test_mode = True

st.write("## Current Session State")

oauth_keys = ["authenticated", "user_email", "credentials_token", "credentials_expiry", "credentials_refresh_token"]

for key in oauth_keys:
    value = st.session_state.get(key, "NOT SET")
    st.write(f"- **{key}:** `{value}`")

st.write("---")

st.write("## Test Actions")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Simulate Login"):
        st.session_state.authenticated = True
        st.session_state.user_email = "test@example.com"
        st.session_state.credentials_token = "test_token_12345"
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        st.session_state.credentials_expiry = expiry.isoformat()
        st.session_state.credentials_refresh_token = "refresh_token_67890"
        st.success("✅ Simulated login complete!")
        st.rerun()

with col2:
    if st.button("Simulate Token Expiry"):
        expired = datetime.now(timezone.utc) - timedelta(minutes=5)
        st.session_state.credentials_expiry = expired.isoformat()
        st.warning("⚠️ Token expired!")
        st.rerun()

with col3:
    if st.button("Clear Session"):
        for key in oauth_keys:
            st.session_state.pop(key, None)
        st.info("🗑️ Session cleared!")
        st.rerun()

st.write("---")

if st.session_state.get("credentials_expiry"):
    expiry_str = st.session_state.credentials_expiry
    if isinstance(expiry_str, str):
        expiry = datetime.fromisoformat(expiry_str)
        now = datetime.now(timezone.utc)
        
        if now >= expiry:
            st.error(f"❌ Token EXPIRED {(now - expiry).total_seconds():.0f} seconds ago")
            st.write("**Expected behavior:** `refresh_token_if_needed()` should refresh the token")
        else:
            remaining = (expiry - now).total_seconds()
            st.success(f"✅ Token valid for {remaining:.0f} seconds ({remaining/60:.1f} minutes)")

st.write("---")
st.info("💡 **Test flow:** Simulate Login → Wait or Simulate Expiry → Refresh page to trigger auth check")
