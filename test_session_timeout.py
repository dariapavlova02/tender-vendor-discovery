import streamlit as st
import time
from datetime import datetime

st.title("Session Timeout Test")

if "start_time" not in st.session_state:
    st.session_state.start_time = datetime.now()
    st.session_state.counter = 0

elapsed = (datetime.now() - st.session_state.start_time).total_seconds()

st.write(f"**Session active for:** {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
st.write(f"**Counter:** {st.session_state.counter}")

st.session_state.counter += 1

st.write("---")
st.write("**Session state contents:**")
for key, value in st.session_state.items():
    st.write(f"- `{key}`: {value}")

if st.button("Simulate long operation (15 seconds)"):
    with st.spinner("Running long operation..."):
        progress = st.progress(0)
        for i in range(15):
            time.sleep(1)
            progress.progress((i + 1) / 15)
    st.success(f"✅ Operation completed! Session still alive after {elapsed:.1f}s")

st.write("---")
st.info("💡 Leave this page open and check periodically. Counter should keep incrementing on refresh.")
