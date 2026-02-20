import streamlit as st
import json
import datetime
import requests

# Define our working days
DAYS = ["Tuesday", "Wednesday", "Thursday", "Friday"]

# --- CLOUD DATABASE SETUP ---
# Streamlit pulls these safely from the Secrets tab!
BIN_ID = st.secrets["BIN_ID"]
API_KEY = st.secrets["API_KEY"]
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}"

def load_data():
    headers = {"X-Master-Key": API_KEY}
    response = requests.get(JSONBIN_URL, headers=headers)
    if response.status_code == 200:
        return response.json().get("record", {})
    return {}

def save_data(data):
    headers = {
        "Content-Type": "application/json",
        "X-Master-Key": API_KEY
    }
    requests.put(JSONBIN_URL, json=data, headers=headers)

# --- Load the database ---
db = load_data()

# ... (Keep the rest of your web page and theme code exactly the same) ...

# --- Build the Web Page ---
st.title("SPC DDJ Monthly Availability Form")
st.write("Please update your typical weekly availability. Uncheck the box if you are busy.")

# --- NEW: DYNAMIC MONTHLY THEME (SWISS EDITION) ---
import datetime

# 1. Get the current month
current_month = datetime.datetime.now().month

# 2. Define a fun, seasonal emoji for each month
monthly_emojis = {
    1: "❄️", 2: "🏔️", 3: "🌱", 4: "🥚", 5: "🌷", 6: "☀️",
    7: "🐄", 8: "🇨🇭", 9: "🍇", 10: "🍂", 11: "🫕", 12: "🎄"
}
current_emoji = monthly_emojis.get(current_month, "📅")

# 3. Inject the emoji as a faint background pattern
st.markdown(
    f"""
    <style>
    .stApp {{
        background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><text x='50%' y='50%' font-size='40' text-anchor='middle' dominant-baseline='middle' opacity='0.08'>{current_emoji}</text></svg>");
    }}
    </style>
    """,
    unsafe_allow_html=True
)
# ----------------------------------

# 1. Ask who is filling out the form
phd_names = list(db.keys())
phd_names.sort()

# NEW: Build the list with "Add me" right at the top!
phd_names.insert(0, "--- Select your name ---")
phd_names.insert(1, "I am a NEW PhD (Add me)") 

selected_name = st.selectbox("Who are you?", phd_names)

# 2. Handle the "New PhD" case
if selected_name == "I am a NEW PhD (Add me)":
    current_user = st.text_input("Enter your Full Name (and press Enter):", key="new_user_input")
    current_schedule = {"AM": [True, True, True, True], "PM": [True, True, True, True]}
    
    if current_user == "":
        st.info("☝️ Please type your name in the box above and press **Enter** to reveal the schedule.")
        st.stop() # Pauses the app until they type something

# 3. Handle existing PhDs
elif selected_name != "--- Select your name ---":
    current_user = selected_name
    current_schedule = db[current_user]

else:
    current_user = None
    st.stop() # Pauses the app on the blank dropdown screen

# 4. Display the Checkboxes (The actual form)
if current_user:
    st.markdown("---")
    st.markdown(f"### Update Profile: **{current_user}**")
    
    updated_schedule = {"AM": [], "PM": []}
    
# Active Toggle and History Preservation
    is_active = st.checkbox("🟢 Active in DDJ rotation this semester?", value=current_schedule.get("active", True))
    updated_schedule["active"] = is_active
    
    # --- SECURE ADMIN ZONE ---
    st.markdown("---")
    with st.expander("🛠️ Admin: Manual Shift Override"):
        st.info("Admin only: Adjust shift counts if TCV breaks down or shifts are cancelled.")
        
        # 1. The Password Field
        admin_pass = st.text_input("Admin Password:", type="password", key="admin_pw")
        
        # 2. Check the password (you can change "plasma2026" to anything you want!)
        if admin_pass == "plasma2026":
            st.success("Admin access granted.")
            
            # Now the admin can see and safely edit the absolute numbers
            updated_schedule["historical_shifts"] = st.number_input(
                "Total Completed Shifts:", 
                value=current_schedule.get("historical_shifts", 0), 
                step=1
            )
            
            updated_schedule["active_months"] = st.number_input(
                "Total Active Months:", 
                value=current_schedule.get("active_months", 1), 
                step=1
            )
        else:
            # 3. IF NO PASSWORD: We silently pass their exact current numbers through so they stay safe!
            if admin_pass != "":
                st.error("Incorrect password.")
                
            updated_schedule["historical_shifts"] = current_schedule.get("historical_shifts", 0)
            updated_schedule["active_months"] = current_schedule.get("active_months", 1) 
    # -------------------------
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
            
    # --- Specific Away Dates Section ---
    st.markdown("---")
    st.markdown("#### Specific Away Dates (Conferences, Holidays, etc.)")
    
    existing_away_dates = current_schedule.get("away_dates", [])
    dates_to_keep = []
    
    if existing_away_dates:
        st.write("**Currently saved away dates (uncheck a box to delete it):**")
        for i, away_period in enumerate(existing_away_dates):
            if away_period['start'] == away_period['end']:
                date_label = f"{away_period['start']} ({away_period['reason']})"
            else:
                date_label = f"{away_period['start']} to {away_period['end']} ({away_period['reason']})"
            
            keep = st.checkbox(date_label, value=True, key=f"keep_date_{i}")
            if keep:
                dates_to_keep.append(away_period)
    
    updated_schedule["away_dates"] = dates_to_keep
    
    st.write("**Add a new away period:**")
    st.write("*(Click a single date for a 1-day absence, or click two dates for a range)*")
    
    new_date_range = st.date_input("Select Date(s):", value=[], key="new_dates")
    new_reason = st.selectbox("Reason:", ["Conference", "Holiday", "Course/Teaching", "Other"], key="new_reason")

    # 5. Save Button
    if st.button("💾 Save My Availability"):
        if new_date_range: 
            if len(new_date_range) == 1:
                start_date = str(new_date_range[0])
                end_date = str(new_date_range[0]) 
            else:
                start_date = str(new_date_range[0])
                end_date = str(new_date_range[1])
                
            new_entry = {
                "start": start_date,
                "end": end_date,
                "reason": new_reason
            }
            updated_schedule["away_dates"].append(new_entry)   
        db[current_user] = updated_schedule
        save_data(db) # <-- NEW: Saves to the cloud!
        
        st.success(f"Availability for {current_user} has been successfully updated!")
        st.rerun()

    # --- NEW: THE DANGER ZONE (Delete Profile) ---
    st.markdown("---")
    with st.expander("🚨 Danger Zone: Delete Profile"):
        st.warning("⚠️ **Warning:** This will permanently erase your profile, typical week, and all shift history. Only do this if you have graduated or left the SPC.")
        
        # They must check this box to reveal the delete button
        confirm_delete = st.checkbox(f"I confirm I want to permanently delete {current_user}.")
        
        if confirm_delete:
            if st.button("🗑️ Permanently Delete Profile"):
                del db[current_user]
                save_data(db) # <-- NEW: Saves to the cloud!
                
                st.success("Profile deleted. Reloading page...")
                st.rerun()