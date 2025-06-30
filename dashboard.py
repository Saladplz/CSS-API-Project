import os
import streamlit as st
import pandas as pd
import requests
from io import BytesIO

# ---------------- CONFIG ---------------- #
DATASET_DIR = "datasets"
API_URL = "http://localhost:5000"

# Category keys → human‑readable names
CATEGORIES = {
    "health": "Health",
    "education": "Education",
    "marriage_and_divorce": "Marriage and Divorce",
    "births_and_deaths": "Births and Deaths",
    "mosques_and_endowments": "Mosques and Endowments",
    "justice_and_security": "Justice and Security",
    "labor_force": "Labor Force",
}

# Role‑based permissions
ROLES = {
    "Student": ["GET"],
    "Employee": ["GET"],
    "Supervisor": ["GET", "POST"],
    "Manager": ["GET", "POST", "DELETE"],
}

# Users (username → dict)
USERS = {
    "marwanaurak":  {"password": "123654",   "role": "Student",    "org": "aurak"},
    "ichrakstats":  {"password": "12345678", "role": "Manager",    "org": "rak statistics"},
    "saracourts":   {"password": "456321",   "role": "Supervisor",  "org": "courts department"},
    "kudomuni":     {"password": "50894069", "role": "Employee",   "org": "rak municipality"},
    "yaramuni":     {"password": "754754",   "role": "Manager",    "org": "rak municipality"},
    "karimcourts":  {"password": "19051003", "role": "Employee",   "org": "courts department"},
}

# Org → list of dataset directories
ORG_DIRS = {
    "aurak": ["education"],
    "rak statistics": list(CATEGORIES.keys()),  # all
    "courts department": ["justice_and_security", "marriage_and_divorce"],
    "rak municipality": ["health", "mosques_and_endowments"],
}

# ---------------- UTILITIES ---------------- #

def authenticate(username: str, password: str):
    user = USERS.get(username)
    if user and user["password"] == password:
        return user
    return None


def list_datasets(cat_key):
    path = os.path.join(DATASET_DIR, cat_key)
    if not os.path.isdir(path):
        return []
    return [f for f in os.listdir(path) if f.endswith(".xlsx")]


def load_dataset(cat_key, filename):
    fp = os.path.join(DATASET_DIR, cat_key, filename)
    if os.path.exists(fp):
        return pd.read_excel(fp), fp
    return None, None


def save_dataset(cat_key, file):
    dest = os.path.join(DATASET_DIR, cat_key, file.name)
    with open(dest, "wb") as f:
        f.write(file.getbuffer())
    return dest


def delete_dataset(cat_key, filename):
    fp = os.path.join(DATASET_DIR, cat_key, filename)
    if os.path.exists(fp):
        os.remove(fp)
        return True
    return False

# ---------------- STREAMLIT ---------------- #
st.set_page_config(page_title="Dataset Dashboard", layout="wide")

# Init session keys
for k in ("user", "role", "org", "last_action", "cmd_input", "selected_cmd_file"):
    st.session_state.setdefault(k, None)

# ---------- LOGIN PAGE ---------- #
if st.session_state.user is None:
    st.title("🔐 Login to Dataset Dashboard")
    uname = st.text_input("Username")
    pwd = st.text_input("Password", type="password")

    if st.button("Login"):
        user = authenticate(uname.strip(), pwd.strip())
        if user:
            st.session_state.user = uname.strip()
            st.session_state.role = user["role"]
            st.session_state.org = user["org"]
            st.rerun()
        else:
            st.error("Invalid credentials.")
    st.stop()

# ---------- DASHBOARD HEADER ---------- #
allowed_dirs = ORG_DIRS.get(st.session_state.org, [])
st.sidebar.markdown(
    f"**User:** `{st.session_state.user}`\n\n"
    f"**Role:** `{st.session_state.role}`\n\n"
    f"**Org:** `{st.session_state.org}`",
)
if st.sidebar.button("🚪 Logout"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

st.title("📊 Public Dataset Dashboard")

col1, col2 = st.columns([1, 2])

# ---------- LEFT COLUMN : LOCAL NAV ---------- #
with col1:
    st.subheader("📁 Browse by Category")
    if not allowed_dirs:
        st.info("Your organization has no dataset access.")
    for cat_key in allowed_dirs:
        cat_name = CATEGORIES[cat_key]
        with st.expander(cat_name):
            files = list_datasets(cat_key)
            if not files:
                st.write("No datasets available.")
                continue

            sel = st.selectbox(
                f"Select file in {cat_name}", ["--"] + files, key=f"sel_{cat_key}"
            )
            if sel != "--":
                df, fp = load_dataset(cat_key, sel)
                if df is not None:
                    st.dataframe(df)
                    with open(fp, "rb") as f:
                        st.download_button(
                            "⬇️ Download", f, file_name=sel,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    if "DELETE" in ROLES[st.session_state.role]:
                        if st.button("🗑️ Delete", key=f"del_{cat_key}_{sel}"):
                            delete_dataset(cat_key, sel)
                            st.success("Deleted.")
                            st.rerun()
                else:
                    st.error("Load error.")

            if "POST" in ROLES[st.session_state.role]:
                up_file = st.file_uploader(
                    f"Upload to {cat_name}", type=["xlsx"], key=f"up_{cat_key}"
                )
                if up_file:
                    save_dataset(cat_key, up_file)
                    st.success("Uploaded!")
                    st.rerun()

# ---------- RIGHT COLUMN : COMMAND MODE ---------- #
with col2:
    st.subheader("💻 Command‑Line Input")
    action = st.selectbox("Action", ["GET", "POST", "DELETE"], key="action_sel")

    if st.session_state.last_action != action:
        st.session_state.last_action = action
        st.session_state.cmd_input = ""

    cmd = st.text_input("Command", st.session_state.cmd_input or "")
    st.session_state.cmd_input = cmd

    if cmd:
        if action not in ROLES[st.session_state.role]:
            st.error("🚫 Action not allowed for your role.")
            st.stop()
        parts = cmd.strip("/").split("/")
        if parts[0] != "datasets":
            st.error("Command must start with /datasets.")
            st.stop()

        # /datasets/<cat>
        if len(parts) == 2:
            _, cat = parts
            if cat not in allowed_dirs:
                st.error("🚫 Category not accessible for your org.")
                st.stop()
            if action == "GET":
                try:
                    r = requests.get(f"{API_URL}/datasets/{cat}")
                    if r.status_code == 200:
                        fls = r.json().get("files", [])
                        if fls:
                            for f in fls:
                                if st.button(f"📂 {f}", key=f"cmd_open_{cat}_{f}"):
                                    st.session_state.selected_cmd_file = (cat, f)
                                    st.rerun()
                        else:
                            st.info("No files in category.")
                    else:
                        st.error(r.text)
                except Exception as e:
                    st.error(str(e))
            elif action == "POST":
                upf = st.file_uploader("Upload .xlsx", type=["xlsx"], key=f"cmd_up_{cat}")
                if upf:
                    try:
                        files = {"file": (upf.name, upf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                        r = requests.post(f"{API_URL}/datasets/{cat}", files=files)
                        if r.status_code == 200:
                            st.success("Uploaded.")
                        else:
                            st.error(r.text)
                    except Exception as e:
                        st.error(str(e))
            elif action == "DELETE":
                r = requests.get(f"{API_URL}/datasets/{cat}")
                if r.status_code == 200:
                    fls = r.json().get("files", [])
                    del_sel = st.selectbox("Select file", ["--"] + fls, key=f"del_sel_{cat}")
                    if del_sel != "--":
                        if st.button("Confirm Delete", key=f"cmd_del_{cat}_{del_sel}"):
                            d = requests.delete(f"{API_URL}/datasets/{cat}/{del_sel}")
                            if d.status_code == 200:
                                st.success("Deleted.")
                            else:
                                st.error(d.text)
                else:
                    st.error(r.text)

        # /datasets/<cat>/<file>
        elif len(parts) == 3:
            _, cat, fname = parts
            if cat not in allowed_dirs:
                st.error("🚫 Category not accessible for your org.")
                st.stop()
            if action == "GET":
                try:
                    r = requests.get(f"{API_URL}/datasets/{cat}/{fname}")
                    if r.status_code == 200:
                        data = BytesIO(r.content)
                        df = pd.read_excel(data)
                        st.dataframe(df)
                        st.download_button("⬇️ Download", data, fname)
                    else:
                        st.error(r.text)
                except Exception as e:
                    st.error(str(e))
            elif action == "DELETE":
                if st.button("Confirm Delete", key=f"cmd_del_{cat}_{fname}"):
                    r = requests.delete(f"{API_URL}/datasets/{cat}/{fname}")
                    if r.status_code == 200:
                        st.success("Deleted.")
                    else:
                        st.error(r.text)
            else:
                st.error("POST only allowed at category level.")
        else:
            st.error("Invalid command format.")

# ---------- HANDLE FILE CLICK FROM COMMAND MODE ---------- #
if st.session_state.selected_cmd_file:
    cat, fname = st.session_state.selected_cmd_file
    try:
        r = requests.get(f"{API_URL}/datasets/{cat}/{fname}")
        if r.status_code == 200:
            data = BytesIO(r.content)
            df = pd.read_excel(data)
            st.dataframe(df)
            st.download_button("⬇️ Download", data, fname)
        else:
            st.error(r.text)
    except Exception as e:
        st.error(str(e))
    # Clear selection
    st.session_state.selected_cmd_file = None
