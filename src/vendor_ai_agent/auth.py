import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import streamlit as st
from google_auth_oauthlib.flow import Flow

logger = logging.getLogger(__name__)

ALLOWED_EMAILS = [
    email.strip() for email in os.getenv("ALLOWED_EMAILS", "").split(",") if email.strip()
]
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "https://your-app.railway.app/oauth2callback")

SESSION_COOKIE_NAME = os.getenv("AUTH_SESSION_COOKIE", "vendor_ai_session")
SESSION_COOKIE_PATH = os.getenv("AUTH_SESSION_COOKIE_PATH", "/")
SESSION_COOKIE_SAMESITE = os.getenv("AUTH_SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_SECURE = os.getenv("AUTH_SESSION_COOKIE_SECURE", "true").lower() == "true"
try:
    SESSION_TTL_SECONDS = int(os.getenv("AUTH_SESSION_TTL_SECONDS", str(60 * 60 * 24 * 7)))
except ValueError:
    SESSION_TTL_SECONDS = 60 * 60 * 24 * 7
    logger.warning("Invalid AUTH_SESSION_TTL_SECONDS value. Falling back to 7 days.")

AUTH_COOKIE_SECRET = os.getenv("AUTH_COOKIE_SECRET") or GOOGLE_CLIENT_SECRET
if not AUTH_COOKIE_SECRET:
    AUTH_COOKIE_SECRET = secrets.token_urlsafe(32)
    logger.warning(
        "AUTH_COOKIE_SECRET is not set. Generated ephemeral secret; sessions will reset on restart."
    )
AUTH_COOKIE_SECRET_BYTES = AUTH_COOKIE_SECRET.encode("utf-8")


def get_google_oauth_flow() -> Flow:
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
        redirect_uri=REDIRECT_URI,
    )
    return flow


def is_authenticated() -> bool:
    return st.session_state.get("authenticated", False)


def get_user_email() -> str | None:
    return st.session_state.get("user_email")


def _emit_cookie_script(value: str, max_age: int) -> None:
    attributes = [
        f"Max-Age={max_age}",
        f"Path={SESSION_COOKIE_PATH}",
        f"SameSite={SESSION_COOKIE_SAMESITE}",
    ]
    if SESSION_COOKIE_SECURE:
        attributes.append("Secure")

    st.markdown(
        f"""
        <script>
        document.cookie = "{SESSION_COOKIE_NAME}={value}; {'; '.join(attributes)}";
        </script>
        """,
        unsafe_allow_html=True,
    )


def _queue_cookie_update(value: str, max_age: int, *, emit: bool = False) -> None:
    st.session_state["_auth_cookie_action"] = {"value": value, "max_age": max_age}
    if emit:
        _emit_cookie_script(value, max_age)


def _apply_queued_cookie_update() -> None:
    action = st.session_state.pop("_auth_cookie_action", None)
    if action:
        _emit_cookie_script(action["value"], action["max_age"])


def _encode_session_payload(payload: Dict[str, Any]) -> str:
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload_bytes).decode("ascii")
    signature = hmac.new(
        AUTH_COOKIE_SECRET_BYTES,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded_payload}.{signature}"


def _decode_session_cookie(raw_cookie: str) -> Dict[str, Any] | None:
    try:
        encoded_payload, signature = raw_cookie.split(".", 1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        AUTH_COOKIE_SECRET_BYTES,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        logger.warning("Auth cookie signature mismatch. Clearing cookie.")
        return None

    try:
        payload_bytes = base64.urlsafe_b64decode(encoded_payload.encode("ascii"))
        return json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None


def _clear_auth_cookie() -> None:
    _queue_cookie_update("", 0, emit=True)


def _write_auth_cookie(email: str) -> None:
    payload = {
        "email": email,
        "exp": (datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat(),
    }
    token = _encode_session_payload(payload)
    _queue_cookie_update(token, SESSION_TTL_SECONDS, emit=True)


def _hydrate_session_from_cookie() -> None:
    try:
        cookies = st.context.cookies
    except Exception:
        return

    try:
        raw_cookie = cookies[SESSION_COOKIE_NAME]
    except KeyError:
        return

    payload = _decode_session_cookie(raw_cookie)
    if not payload:
        _clear_auth_cookie()
        return

    email = payload.get("email")
    expires_at = payload.get("exp")

    if not email or not expires_at:
        _clear_auth_cookie()
        return

    try:
        expires_dt = datetime.fromisoformat(expires_at)
    except ValueError:
        _clear_auth_cookie()
        return

    if datetime.now(timezone.utc) >= expires_dt:
        _clear_auth_cookie()
        return

    st.session_state.authenticated = True
    st.session_state.user_email = email
    _write_auth_cookie(email)


def check_authentication() -> None:
    _apply_queued_cookie_update()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "user_email" not in st.session_state:
        st.session_state.user_email = None

    _hydrate_session_from_cookie()

    query_params = st.query_params

    if "code" in query_params and not st.session_state.authenticated:
        try:
            flow = get_google_oauth_flow()
            flow.fetch_token(code=query_params["code"])

            credentials = flow.credentials

            import requests

            userinfo_response = requests.get(
                "https://www.googleapis.com/oauth2/v1/userinfo",
                headers={"Authorization": f"Bearer {credentials.token}"},
                timeout=10,
            )

            if userinfo_response.status_code == 200:
                user_info = userinfo_response.json()
                email = user_info.get("email")

                if email in ALLOWED_EMAILS:
                    st.session_state.authenticated = True
                    st.session_state.user_email = email

                    st.query_params.clear()
                    _write_auth_cookie(email)
                    st.rerun()
                else:
                    st.error(f"Access denied. Email {email} is not authorized.")
                    st.stop()
            else:
                st.error("Failed to retrieve user information.")
                st.stop()

        except Exception as e:
            logger.exception("Authentication error")
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
                prompt="consent select_account",
            )
            st.session_state.oauth_state = state
            st.markdown(
                f'<meta http-equiv="refresh" content="0;url={authorization_url}">',
                unsafe_allow_html=True,
            )
            st.stop()

        st.stop()


def add_logout_button() -> None:
    if st.session_state.get("authenticated"):
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.session_state.user_email = None
                _clear_auth_cookie()
                st.rerun()
