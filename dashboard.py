import os
import streamlit as st
import pandas as pd
import shutil
import requests
from io import BytesIO

# ------------- CONFIG -------------
DATASET_DIR = "datasets"
API_URL = "http://localhost:5000"
CATEGORIES = {
    "health": "Health",
    "education": "Education",
    "marriage_and_divorce": "Marriage and Divorce",
    "births_and_deaths": "Births and Deaths",
    "mosques_and_endowments": "Mosques and Endowments",
    "justice_and_security": "Justice and Security",
    "labor_force": "Labor Force"
}
ROLES = {
    "Student": ["GET"],
    "Supervisor": ["GET", "POST"],
    "Manager": ["GET", "POST", "DELETE"]
}

# ------------- UTILS (LOCAL) -------------
def list_datasets(category_key):
    category_path = os.path.join(DATASET_DIR, category_key)
    if not os.path.exists(category_path):
        return []
    return [f for f in os.listdir(category_path) if f.endswith(".xlsx")]

def load_dataset(category_key, filename):
    file_path = os.path.join(DATASET_DIR, category_key, filename)
    if os.path.exists(file_path):
        return pd.read_excel(file_path), file_path
    return None, None

def save_dataset(category_key, file):
    save_path = os.path.join(DATASET_DIR, category_key, file.name)
    with open(save_path, "wb") as f:
        f.write(file.getbuffer())
    return save_path

def delete_dataset(category_key, filename):
    file_path = os.path.join(DATASET_DIR, category_key, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return True
    return False

# ------------- SESSION SETUP -------------
if "role" not in st.session_state:
    st.session_state.role = None

if "last_action" not in st.session_state:
    st.session_state.last_action = None

if not st.session_state.role:
    st.title("🔐 Select Your Role")
    role = st.selectbox("Choose your access level:", list(ROLES.keys()))
    if st.button("Enter Dashboard"):
        st.session_state.role = role
    st.stop()

# ------------- DASHBOARD -------------
st.set_page_config(page_title="Dataset Dashboard", layout="wide")
st.title("📊 Public Dataset Dashboard")
st.markdown(f"**Logged in as:** `{st.session_state.role}`")

col1, col2 = st.columns([1, 2])

# ------------- LEFT: LOCAL Category Navigation -------------
with col1:
    st.subheader("📁 Browse by Category")
    for cat_key, cat_label in CATEGORIES.items():
        with st.expander(cat_label):
            files = list_datasets(cat_key)
            if not files:
                st.info("No datasets available.")
                continue

            selected_file = st.selectbox(
                f"Select a file from {cat_label}:", 
                ["-- Select a file --"] + files,
                key=f"select_{cat_key}"
            )

            if selected_file != "-- Select a file --":
                df, path = load_dataset(cat_key, selected_file)
                if df is not None:
                    st.dataframe(df)
                    with open(path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download this file",
                            data=f,
                            file_name=selected_file,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                    if "DELETE" in ROLES[st.session_state.role]:
                        if st.button("🗑️ Delete this file", key=f"delete_{cat_key}_{selected_file}"):
                            delete_dataset(cat_key, selected_file)
                            st.success("File deleted.")
                            st.rerun()
                else:
                    st.error("Error loading file.")

            if "POST" in ROLES[st.session_state.role]:
                upload = st.file_uploader(f"Upload new dataset to {cat_label}:", type=["xlsx"], key=f"upload_{cat_key}")
                if upload:
                    save_dataset(cat_key, upload)
                    st.success(f"Uploaded {upload.name} to {cat_label}")
                    st.rerun()

# ------------- RIGHT: API-Driven Command Input -------------
with col2:
    st.subheader("💻 Command-Line Input")

    action = st.selectbox("Action", ["GET", "POST", "DELETE"])

    if st.session_state.last_action != action:
        st.session_state.last_action = action
        if "command_input" in st.session_state:
            del st.session_state["command_input"]

    if "command_input" not in st.session_state:
        st.session_state.command_input = ""

    command = st.text_input(
        "Enter command",
        value=st.session_state.command_input,
        key="command_text_input"
    )

    if command != st.session_state.command_input:
        st.session_state.command_input = command

    if command:
        if action not in ROLES[st.session_state.role]:
            st.error("🚫 Access Denied.")
        else:
            parts = command.strip("/").split("/")

            if len(parts) == 2:
                _, cat = parts
                if cat not in CATEGORIES:
                    st.error("Unknown category.")
                elif action == "GET":
                    try:
                        response = requests.get(f"{API_URL}/datasets/{cat}")
                        if response.status_code == 200:
                            files = response.json().get("files", [])
                            if files:
                                for file in files:
                                    if st.button(f"📂 {file}", key=f"cmd_{cat}_{file}"):
                                        st.session_state["selected_cmd_file"] = (cat, file)
                                        st.rerun()
                            else:
                                st.warning("No files in this category.")
                        else:
                            st.error(f"API Error: {response.text}")
                    except Exception as e:
                        st.error(f"Request failed: {e}")

                elif action == "POST":
                    file = st.file_uploader(f"Upload file to {CATEGORIES[cat]}:", type=["xlsx"], key=f"cmd_upload_{cat}")
                    if file:
                        try:
                            files = {'file': (file.name, file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                            response = requests.post(f"{API_URL}/datasets/{cat}", files=files)
                            if response.status_code == 200:
                                st.success(f"Uploaded {file.name}")
                                st.rerun()
                            else:
                                st.error(f"Upload failed: {response.text}")
                        except Exception as e:
                            st.error(f"Upload error: {e}")

                elif action == "DELETE":
                    response = requests.get(f"{API_URL}/datasets/{cat}")
                    if response.status_code == 200:
                        files = response.json().get("files", [])
                        selected_file = st.selectbox("Choose file to delete:", ["-- Select --"] + files)
                        if selected_file != "-- Select --":
                            if st.button("🗑️ Confirm Delete", key=f"confirm_delete_{cat}_{selected_file}"):
                                del_response = requests.delete(f"{API_URL}/datasets/{cat}/{selected_file}")
                                if del_response.status_code == 200:
                                    st.success("Deleted successfully.")
                                    st.rerun()
                                else:
                                    st.error(f"Delete failed: {del_response.text}")
                    else:
                        st.error("Could not fetch files.")

            elif len(parts) == 3:
                _, cat, filename = parts
                if cat not in CATEGORIES:
                    st.error("Unknown category.")
                elif action == "GET":
                    try:
                        response = requests.get(f"{API_URL}/datasets/{cat}/{filename}")
                        if response.status_code == 200:
                            df = pd.read_excel(BytesIO(response.content))
                            st.markdown(f"### File: `{filename}`")
                            st.dataframe(df)
                            st.download_button(
                                label="⬇️ Download this file",
                                data=response.content,
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.error(f"File not found: {response.text}")
                    except Exception as e:
                        st.error(f"Error fetching file: {e}")

                elif action == "DELETE":
                    if st.button("🗑️ Confirm Delete", key=f"direct_delete_{cat}_{filename}"):
                        del_response = requests.delete(f"{API_URL}/datasets/{cat}/{filename}")
                        if del_response.status_code == 200:
                            st.success("File deleted successfully.")
                            st.rerun()
                        else:
                            st.error(f"Delete failed: {del_response.text}")

                elif action == "POST":
                    st.error("POST requires category-level path only (e.g. `/datasets/education`)")

# ------------- Handle file click from command mode -------------
if "selected_cmd_file" in st.session_state:
    cat, file = st.session_state["selected_cmd_file"]
    try:
        response = requests.get(f"{API_URL}/datasets/{cat}/{file}")
        if response.status_code == 200:
            df = pd.read_excel(BytesIO(response.content))
            st.markdown(f"### File: `{file}`")
            st.dataframe(df)
            st.download_button(
                label="⬇️ Download this file",
                data=response.content,
                file_name=file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error("Error loading selected file.")
    except Exception as e:
        st.error(f"Exception loading selected file: {e}")
    del st.session_state["selected_cmd_file"]
