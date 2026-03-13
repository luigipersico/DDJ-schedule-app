import streamlit as st
import json
import datetime
import requests

# 1. Define working days
DAYS = ["Monday (just in case)", "Tuesday", "Wednesday", "Thursday", "Friday"]

# --- CLOUD DATABASE SETUP ---
BIN_ID = st.secrets["BIN_ID"]
API_KEY = st.secrets["API_KEY"]
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}"

def load_data():
    headers = {"X-Master-Key": API_KEY}
    response = requests.get(JSONBIN_URL, headers=headers)
    if response.status_code == 200:
        data = response.json().get("record", {})
        # Safety net: Initialize global config if it doesn't exist yet
        if "__CONFIG__" not in data:
            data["__CONFIG__"] = {"TCV_OFF_RANGES": [], "PUBLISHED_SCHEDULE": []}
        return data
    return {}

def save_data(data):
    headers = {"Content-Type": "application/json", "X-Master-Key": API_KEY}
    requests.put(JSONBIN_URL, json=data, headers=headers)

# --- Load the database ---
db = load_data()
config = db.get("__CONFIG__", {"TCV_OFF_RANGES": [], "PUBLISHED_SCHEDULE": []})

# --- Build the Web Page ---
st.set_page_config(page_title="DDJ Schedule", page_icon="🇨🇭", layout="centered")

# --- DYNAMIC MONTHLY THEME ---
current_month = datetime.datetime.now().month
monthly_emojis = {1: "❄️", 2: "🏔️", 3: "🌱", 4: "🥚", 5: "🌷", 6: "☀️", 7: "🐄", 8: "🇨🇭", 9: "🍇", 10: "🍂", 11: "🫕", 12: "🎄"}
st.markdown(
    f"""<style>.stApp {{ background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><text x='50%' y='50%' font-size='40' text-anchor='middle' dominant-baseline='middle' opacity='0.08'>{monthly_emojis.get(current_month, "📅")}</text></svg>"); }}</style>""",
    unsafe_allow_html=True
)

st.title("SPC DDJ Portal")

# Remove the hidden config profile from the user list!
phd_names = [name for name in db.keys() if name != "__CONFIG__"]
phd_names.sort()

phd_names.insert(0, "--- Select your name ---")
phd_names.insert(1, "I am a NEW PhD (Add me)") 

selected_name = st.selectbox("Who are you?", phd_names)

# --- HANDLE SELECTION ---
if selected_name == "I am a NEW PhD (Add me)":
    current_user = st.text_input("Enter your Full Name (and press Enter):")
    current_schedule = {"AM": [True, True, True, True, True], "PM": [True, True, True, True, True]}
    if not current_user:
        st.info("☝️ Please type your name above and press Enter.")
        st.stop()
elif selected_name != "--- Select your name ---":
    current_user = selected_name
    current_schedule = db[current_user]
else:
    current_user = None
    st.stop()

# --- VERSION 2.0: THE SIDEBAR STATS ---
if current_user and current_user != "I am a NEW PhD (Add me)":
    with st.sidebar:
        st.header(f"📊 {current_user.split()[0]}'s Stats")
        st.divider()
        
        shifts = current_schedule.get("historical_shifts", 0)
        months = current_schedule.get("active_months", 1)
        ratio = shifts / months if months > 0 else 0
        
        st.metric("Total Completed Shifts", shifts)
        st.metric("Active Months in SPC", months)
        st.metric("Fairness Ratio", f"{ratio:.2f}")
        st.caption("*(A lower ratio means you have higher priority to be picked for the next shift)*")
        
        # Show upcoming personal away dates
        away_dates = current_schedule.get("away_dates", [])
        if away_dates:
            st.divider()
            st.subheader("Your Upcoming Absences")
            for away in away_dates:
                if away['start'] == away['end']:
                    st.write(f"🏖️ {away['start']}")
                else:
                    st.write(f"🏖️ {away['start']} to {away['end']}")

# --- SPLIT INTO TABS ---
tab1, tab2 = st.tabs(["📝 My Availability", "📅 Lab Dashboard"])

with tab1:
    st.markdown(f"### Update Profile: **{current_user}**")
    updated_schedule = {"AM": [], "PM": []}

    # Data Migration Safety Net
    if len(current_schedule.get("AM", [])) == 4:
        current_schedule["AM"].insert(0, True)
        current_schedule["PM"].insert(0, True)

    st.markdown("#### Typical Weekly Availability")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Morning (8h15 - 13h)")
        for i, day in enumerate(DAYS):
            is_free = st.checkbox(f"{day} AM", value=current_schedule["AM"][i])
            updated_schedule["AM"].append(is_free)
    with col2:
        st.subheader("Afternoon (13h - 18h)")
        for i, day in enumerate(DAYS):
            is_free = st.checkbox(f"{day} PM", value=current_schedule["PM"][i])
            updated_schedule["PM"].append(is_free)
            
    # Away Dates
    st.markdown("---")
    st.markdown("#### Specific Away Dates (Conferences, Holidays, etc.)")
    existing_away_dates = current_schedule.get("away_dates", [])
    dates_to_keep = []
    if existing_away_dates:
        for i, away_period in enumerate(existing_away_dates):
            label = f"{away_period['start']} to {away_period['end']} ({away_period['reason']})" if away_period['start'] != away_period['end'] else f"{away_period['start']} ({away_period['reason']})"
            if st.checkbox(label, value=True, key=f"keep_{i}"):
                dates_to_keep.append(away_period)
    updated_schedule["away_dates"] = dates_to_keep
    
    new_date_range = st.date_input("Add new away period:", value=[], key="new_dates")
    new_reason = st.selectbox("Reason:", ["Conference", "Holiday", "Course/Teaching", "Other"])

    # --- ADMIN ZONE (Now includes TCV Settings) ---
    st.markdown("---")
    with st.expander("🛠️ Admin Zone"):
        admin_pass = st.text_input("Admin Password:", type="password")
        
        if admin_pass == "ddjninja":
            st.success("Admin access granted.")
            updated_schedule["active"] = st.checkbox("🟢 Active in rotation?", value=current_schedule.get("active", True))
            updated_schedule["historical_shifts"] = st.number_input("Total Shifts:", value=current_schedule.get("historical_shifts", 0), step=1)
            updated_schedule["active_months"] = st.number_input("Total Months:", value=current_schedule.get("active_months", 1), step=1)
            
            st.divider()
            st.markdown("#### 🔧 TCV Operational Control")
            st.write("Current TCV Maintenance/Off Dates:")
            
            tcv_off = config.get("TCV_OFF_RANGES", [])
            new_tcv_off = []
            for i, period in enumerate(tcv_off):
                if st.checkbox(f"🔴 TCV OFF: {period['start']} to {period['end']}", value=True, key=f"tcv_{i}"):
                    new_tcv_off.append(period)
            
            new_tcv_dates = st.date_input("Add TCV Maintenance Dates:", value=[], key="new_tcv")
            if st.button("➕ Add TCV Dates to Database"):
                if len(new_tcv_dates) == 2:
                    new_tcv_off.append({"start": str(new_tcv_dates[0]), "end": str(new_tcv_dates[1])})
                elif len(new_tcv_dates) == 1:
                    new_tcv_off.append({"start": str(new_tcv_dates[0]), "end": str(new_tcv_dates[0])})
                db["__CONFIG__"]["TCV_OFF_RANGES"] = new_tcv_off
                save_data(db)
                st.success("TCV Dates Updated!")
                st.rerun()

            db["__CONFIG__"]["TCV_OFF_RANGES"] = new_tcv_off # Save state
            
            st.divider()
            if st.checkbox(f"Delete {current_user}"):
                if st.button("🗑️ Permanently Delete"):
                    del db[current_user]
                    save_data(db) 
                    st.rerun()
        else:
            updated_schedule["active"] = current_schedule.get("active", True)
            updated_schedule["historical_shifts"] = current_schedule.get("historical_shifts", 0)
            updated_schedule["active_months"] = current_schedule.get("active_months", 1) 

    # Save Button
    if st.button("💾 Save My Availability"):
        if new_date_range: 
            start_date = str(new_date_range[0])
            end_date = str(new_date_range[1] if len(new_date_range) > 1 else new_date_range[0])
            updated_schedule["away_dates"].append({"start": start_date, "end": end_date, "reason": new_reason})   
            
        db[current_user] = updated_schedule
        save_data(db) 
        st.success("Successfully updated!")
        st.rerun()

# --- CALENDAR DASHBOARD TAB ---
with tab2:
    st.header("📅 Lab Dashboard")
    st.info("When the DDJ schedule is officially published, it will appear here.")
    
    # Show upcoming TCV Maintenance
    tcv_dates = config.get("TCV_OFF_RANGES", [])
    if tcv_dates:
        st.error("### 🔧 Upcoming TCV Maintenance Windows")
        for period in tcv_dates:
            st.write(f"**{period['start']}** to **{period['end']}** (No DDJ shifts assigned)")
    
    # Space reserved for the published schedule table
    published = config.get("PUBLISHED_SCHEDULE", [])
    if published:
        st.subheader("Current Published Schedule")
        # Creates a beautiful visual grid automatically!
        st.dataframe(published, use_container_width=True, hide_index=True)