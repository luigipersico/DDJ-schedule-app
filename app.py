import streamlit as st
import json
import datetime
import requests

DAYS = ["Monday (just in case)", "Tuesday", "Wednesday", "Thursday", "Friday"]

BIN_ID = st.secrets["BIN_ID"]
API_KEY = st.secrets["API_KEY"]
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}"

# --- HELPER: GET INITIALS FOR HIGHLIGHTING ---
def get_initials(full_name):
    if not full_name or full_name == "I am a NEW PhD (Add me)":
        return ""
    parts = full_name.split()
    if not parts: return ""
    first_name_letter = parts[0][0]
    first_surname_letter = parts[1][0] if len(parts) > 1 else parts[0][1] if len(parts[0])>1 else ""
    last_surname_letter = full_name[-1]
    return (first_name_letter + first_surname_letter + last_surname_letter).upper()

def load_data():
    headers = {"X-Master-Key": API_KEY}
    response = requests.get(JSONBIN_URL, headers=headers)
    if response.status_code == 200:
        data = response.json().get("record", {})
        if "__CONFIG__" not in data:
            data["__CONFIG__"] = {"TCV_OFF_RANGES": [], "PUBLISHED_SCHEDULE": [], "HISTORY": {}}
        return data
    return {}

def save_data(data):
    headers = {"Content-Type": "application/json", "X-Master-Key": API_KEY}
    requests.put(JSONBIN_URL, json=data, headers=headers)

db = load_data()
config = db.get("__CONFIG__", {"TCV_OFF_RANGES": [], "PUBLISHED_SCHEDULE": [], "HISTORY": {}})

st.set_page_config(page_title="DDJ Schedule", page_icon="🇨🇭", layout="centered")

current_month = datetime.datetime.now().month
monthly_emojis = {1: "❄️", 2: "🏔️", 3: "🌱", 4: "🥚", 5: "🌷", 6: "☀️", 7: "🐄", 8: "🇨🇭", 9: "🍇", 10: "🍂", 11: "🫕", 12: "🎄"}
st.markdown(
    f"""<style>.stApp {{ background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><text x='50%' y='50%' font-size='40' text-anchor='middle' dominant-baseline='middle' opacity='0.08'>{monthly_emojis.get(current_month, "📅")}</text></svg>"); }}</style>""",
    unsafe_allow_html=True
)

st.title("SPC DDJ Portal")

phd_names = [name for name in db.keys() if name != "__CONFIG__"]
phd_names.sort()
phd_names.insert(0, "--- Select your name ---")
phd_names.insert(1, "I am a NEW PhD (Add me)") 

selected_name = st.selectbox("Who are you?", phd_names)

if selected_name == "I am a NEW PhD (Add me)":
    current_user = st.text_input("Enter your Full Name (and press Enter):")
    current_schedule = {"AM": [True, True, True, True, True], "PM": [True, True, True, True, True]}
    if not current_user:
        st.stop()
elif selected_name != "--- Select your name ---":
    current_user = selected_name
    current_schedule = db[current_user]
else:
    current_user = None
    st.stop()

# --- THE SIDEBAR (Stats + New Visual Calendar) ---
if current_user and current_user != "I am a NEW PhD (Add me)":
    with st.sidebar:
        st.header(f"📊 {current_user.split()[0]}'s Profile")
        st.divider()
        
        shifts = current_schedule.get("historical_shifts", 0)
        months = current_schedule.get("active_months", 1)
        ratio = shifts / months if months > 0 else 0

        st.metric("Total Completed Shifts (since 04/2026)", shifts)
        st.metric("Fairness Ratio", f"{ratio:.2f}")
        
        # --- NEW: VISUAL CALENDAR ---
        published = config.get("PUBLISHED_SCHEDULE", [])
        if published:
            st.divider()
            st.markdown("### 📅 Upcoming Month")
            user_initials = get_initials(current_user)
            
            # Build custom HTML grid
            html = "<table style='width:100%; font-size:13px; text-align:center; border-collapse: collapse;'>"
            html += "<tr style='background-color:#444; color:white;'><th>Date</th><th>AM</th><th>PM</th></tr>"
            
            for day in published:
                bg_color = "border-bottom: 1px solid #ddd;"
                
                # --- THE FIX: Use .get() to default to NORMAL if "Type" is missing ---
                day_type = day.get("Type", "NORMAL") 
                
                if day_type == "TCV_OFF": bg_color = "background-color: #ffcccc; color: #990000; border-bottom: 1px solid #ddd;"
                elif day_type == "HOLIDAY": bg_color = "background-color: #cce5ff; color: #004085; border-bottom: 1px solid #ddd;"
                
                # Check if the user is assigned this shift
                am_style = "background-color: #ffd700; color: black; font-weight: bold; font-size: 15px;" if user_initials != "" and user_initials == day["AM"] else ""
                pm_style = "background-color: #ffd700; color: black; font-weight: bold; font-size: 15px;" if user_initials != "" and user_initials == day["PM"] else ""
                
                html += f"<tr style='{bg_color}'><td style='padding:5px;'>{day['Date']}</td><td style='{am_style}'>{day['AM']}</td><td style='{pm_style}'>{day['PM']}</td></tr>"
            
            html += "</table>"
            st.markdown(html, unsafe_allow_html=True)

# --- THE TABS ---
tab1, tab2 = st.tabs(["📝 My Availability", "📅 DDJ Historical Dashboard"])

with tab1:
    st.markdown(f"### Update Profile: **{current_user}**")
    updated_schedule = {"AM": [], "PM": []}

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
            
    # --- AUTO-CLEANUP AWAY DATES ---
    st.markdown("---")
    st.markdown("#### Specific Away Dates (Conferences, Holidays, etc.)")
    existing_away_dates = current_schedule.get("away_dates", [])
    dates_to_keep = []
    
    # NEW logic: Drop any dates that happened before today!
    today = datetime.date.today()
    if existing_away_dates:
        for i, away_period in enumerate(existing_away_dates):
            try:
                end_date = datetime.date.fromisoformat(away_period['end'])
                if end_date >= today:
                    label = f"{away_period['start']} to {away_period['end']} ({away_period['reason']})" if away_period['start'] != away_period['end'] else f"{away_period['start']} ({away_period['reason']})"
                    if st.checkbox(label, value=True, key=f"keep_{i}"):
                        dates_to_keep.append(away_period)
            except:
                # If they manually typed a broken date somehow, just keep it to be safe.
                dates_to_keep.append(away_period)
                
    updated_schedule["away_dates"] = dates_to_keep
    
    new_date_range = st.date_input("Add new away period:", value=[], key="new_dates")
    new_reason = st.selectbox("Reason:", ["Conference", "Holiday", "Course/Teaching", "Other"])

    # --- ADMIN ZONE ---
    st.markdown("---")
    with st.expander("🛠️ Admin Dojo"):
        admin_pass = st.text_input("Admin Password:", type="password")
        
        if admin_pass == "ForzaNapoli":
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

            db["__CONFIG__"]["TCV_OFF_RANGES"] = new_tcv_off 
            
            st.divider()
            if st.checkbox(f"Delete {current_user}"):
                if st.button("🗑️ Permanently Delete"):
                    del db[current_user]
                    save_data(db) 
                    st.rerun()
        else:
            if admin_pass != "":
                st.error("🥷 Nice try, Padawan. The Admin Dojo is sealed to outsiders. Seek the true password or return to your shifts.")
            updated_schedule["active"] = current_schedule.get("active", True)
            updated_schedule["historical_shifts"] = current_schedule.get("historical_shifts", 0)
            updated_schedule["active_months"] = current_schedule.get("active_months", 1) 

    if st.button("💾 Save My Availability"):
        if new_date_range: 
            start_date = str(new_date_range[0])
            end_date = str(new_date_range[1] if len(new_date_range) > 1 else new_date_range[0])
            updated_schedule["away_dates"].append({"start": start_date, "end": end_date, "reason": new_reason})   
            
        db[current_user] = updated_schedule
        save_data(db) 
        st.success("Successfully updated!")
        st.rerun()

    st.markdown("---")
    st.markdown("#### Tired of shifts?")
    
    # We use a slightly different button style for emphasis
    if st.button("🚫 I don't want to do DDJ shifts anymore"):
        st.warning("### You wish... 😏")
        st.success("""
        ...But wait, you actually can! 🎉
        
        If you take on a **6-month DDJ Project**, you are officially excused from the standard shift rotation during that time. 
        
        👉 [Click here to find more info on available DDJ Projects!](https://insert-your-epfl-intranet-link-here.ch)
        """)
        st.balloons() # Streamlit will literally drop animated balloons on their screen!

# --- NEW: HISTORY DASHBOARD TAB ---
with tab2:
    st.header("📅 DDJ Historical Dashboard")
    st.info("Select a past month below to view previous schedules.")
    
    history_book = config.get("HISTORY", {})
    if history_book:
        # Sort history so the newest months appear first
        months = list(history_book.keys())
        months.reverse() 
        selected_month = st.selectbox("View Schedule for:", months)
        
        st.dataframe(history_book[selected_month], use_container_width=True, hide_index=True)
    else:
        st.write("No historical data available yet. Next time the admin hits 'Save', the schedule will appear here!")