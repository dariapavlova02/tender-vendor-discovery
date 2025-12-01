import os
import streamlit as st
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json
from datetime import datetime, timezone


ALLOWED_EMAILS = os.getenv("ALLOWED_EMAILS", "").split(",")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "https://your-app.railway.app/oauth2callback")


def get_google_oauth_flow():
    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=["openid", "https://www.googleapis.com/auth/userinfo.email"],
        redirect_uri=REDIRECT_URI
    )
    return flow


def is_authenticated():
    return st.session_state.get("authenticated", False)


def get_user_email():
    return st.session_state.get("user_email")


def refresh_token_if_needed():
    if not st.session_state.get("authenticated"):
        return
    
    token_expiry = st.session_state.get("credentials_expiry")
    refresh_token = st.session_state.get("credentials_refresh_token")
    
    if not token_expiry or not refresh_token:
        return
    
    if isinstance(token_expiry, str):
        token_expiry = datetime.fromisoformat(token_expiry)
    
    if datetime.now(timezone.utc) >= token_expiry:
        try:
            credentials = Credentials(
                token=st.session_state.get("credentials_token"),
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET
            )
            
            credentials.refresh(Request())
            
            st.session_state.credentials_token = credentials.token
            if credentials.expiry:
                st.session_state.credentials_expiry = credentials.expiry.isoformat()
            
        except Exception as e:
            st.error(f"Token refresh failed: {str(e)}")
            st.session_state.authenticated = False


def check_authentication():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    
    refresh_token_if_needed()
    
    query_params = st.query_params
    
    if "code" in query_params and not st.session_state.authenticated:
        try:
            flow = get_google_oauth_flow()
            flow.fetch_token(code=query_params["code"])
            
            credentials = flow.credentials
            
            import requests
            userinfo_response = requests.get(
                "https://www.googleapis.com/oauth2/v1/userinfo",
                headers={"Authorization": f"Bearer {credentials.token}"}
            )
            
            if userinfo_response.status_code == 200:
                user_info = userinfo_response.json()
                email = user_info.get("email")
                
                if email in ALLOWED_EMAILS:
                    st.session_state.authenticated = True
                    st.session_state.user_email = email
                    
                    st.session_state.credentials_token = credentials.token
                    if credentials.expiry:
                        st.session_state.credentials_expiry = credentials.expiry.isoformat()
                    if credentials.refresh_token:
                        st.session_state.credentials_refresh_token = credentials.refresh_token
                    
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.error(f"Access denied. Email {email} is not authorized.")
                    st.stop()
            else:
                st.error("Failed to retrieve user information.")
                st.stop()
                
        except Exception as e:
            st.error(f"Authentication error: {str(e)}")
            st.stop()
    
    if not st.session_state.authenticated:
        st.title("🔐 Authentication Required")
        st.write("Please sign in with your Google account to access the Vendor AI Agent Dashboard.")
        
        if st.button("Sign in with Google", type="primary"):
            flow = get_google_oauth_flow()
            authorization_url, state = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="select_account"
            )
            st.session_state.oauth_state = state
            st.markdown(f'<meta http-equiv="refresh" content="0;url={authorization_url}">', unsafe_allow_html=True)
            st.stop()
        
        st.stop()


def add_logout_button():
    if st.session_state.get("authenticated"):
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.session_state.user_email = None
                st.session_state.credentials_token = None
                st.session_state.credentials_expiry = None
                st.session_state.credentials_refresh_token = None
                st.rerun()
