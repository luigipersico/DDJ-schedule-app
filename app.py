import streamlit as st
import json
import datetime
import requests
import urllib.parse
import pandas as pd

DAYS = ["Monday (just in case)", "Tuesday", "Wednesday", "Thursday", "Friday"]

BIN_ID = st.secrets["BIN_ID"]
API_KEY = st.secrets["API_KEY"]
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{BIN_ID}"

def get_initials(name):
    if name == "⚠️ UNFILLED - NO ONE FREE": return "---"
    custom_initials = {
        "Martino Bonisolli": "MBO",        
        "Garance Durr-Legoupil-Nicoud": "GDL",
        "Sergio García Herreros": "SGS",
        "Guillaume Van Parys": "GVS",
        "Michele Bottino": "MBT",   
    }
    if name in custom_initials: return custom_initials[name]
    parts = name.split()
    if len(parts) >= 3: return (parts[0][0] + parts[1][0] + parts[2][0]).upper()
    elif len(parts) == 2: return (parts[0][0] + parts[1][0] + parts[-1][-1]).upper()
    return name[:3].upper()

def load_data():
    headers = {"X-Master-Key": API_KEY}
    try:
        response = requests.get(JSONBIN_URL, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json().get("record", {})
            if "__CONFIG__" not in data:
                data["__CONFIG__"] = {"TCV_OFF_RANGES": [], "PUBLISHED_SCHEDULE": [], "HISTORY": {}}
            if "__TOURS__" not in data:
                data["__TOURS__"] = []
            if "__GUEST_GUIDES__" not in data:
                data["__GUEST_GUIDES__"] = {}
            return data
    except requests.exceptions.RequestException:
        st.error("🚨 **CRITICAL DATABASE ERROR** 🚨\n\nThe central database is currently offline. Please try again later.")
        st.stop()
    return {}

def save_data(data):
    headers = {"Content-Type": "application/json", "X-Master-Key": API_KEY}
    try:
        requests.put(JSONBIN_URL, json=data, headers=headers, timeout=5)
    except requests.exceptions.RequestException:
        st.error("🚨 ERROR: The database is offline. Your changes were NOT saved!")

db = load_data()
config = db.get("__CONFIG__", {})
tours_db = db.get("__TOURS__", [])
guest_db = db.get("__GUEST_GUIDES__", {})

# --- SILENT AUTO-COUNTER FOR PAST TOURS ---
today = datetime.date.today()
needs_save = False
for tour in tours_db:
    try:
        tour_date = datetime.date.fromisoformat(tour["date"])
        if tour_date < today and not tour.get("counted", False):
            # Credit DDJs
            for guide in tour.get("approved_guides", []):
                if guide in db:
                    db[guide]["historical_tours"] = db[guide].get("historical_tours", 0) + 1
                    if db[guide]["historical_tours"] % 2 == 0:
                        db[guide]["historical_shifts"] = db[guide].get("historical_shifts", 0) + 1
            # Credit Non-DDJ Guests
            for guest in tour.get("guest_guides", []):
                db["__GUEST_GUIDES__"][guest] = db["__GUEST_GUIDES__"].get(guest, 0) + 1
                
            tour["counted"] = True
            needs_save = True
    except ValueError:
        pass
if needs_save: save_data(db)

st.set_page_config(page_title="DDJ Schedule", page_icon="🇨🇭", layout="centered")

current_month = datetime.datetime.now().month
monthly_emojis = {1: "❄️", 2: "🏔️", 3: "🌱", 4: "🥚", 5: "🌷", 6: "☀️", 7: "🐄", 8: "🇨🇭", 9: "🍇", 10: "🍂", 11: "🫕", 12: "🎄"}
st.markdown(
    f"""<style>.stApp {{ background-image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><text x='50%' y='50%' font-size='40' text-anchor='middle' dominant-baseline='middle' opacity='0.08'>{monthly_emojis.get(current_month, "📅")}</text></svg>"); }}</style>""",
    unsafe_allow_html=True
)

st.title("SPC DDJ Portal 3.0")

phd_names = [name for name in db.keys() if name not in ["__CONFIG__", "__TOURS__", "__GUEST_GUIDES__"]]
phd_names.sort()
phd_names.insert(0, "--- Select your name ---")
phd_names.insert(1, "I am a NEW PhD (Add me)") 

def format_dropdown(name):
    if name in ["--- Select your name ---", "I am a NEW PhD (Add me)"]: return name
    return f"{name} ({get_initials(name)})"

selected_name = st.selectbox("Who are you?", phd_names, format_func=format_dropdown)

if selected_name == "I am a NEW PhD (Add me)":
    current_user = st.text_input("Enter your Full Name (and press Enter):")
    current_schedule = {"AM": [True]*5, "PM": [True]*5, "historical_tours": 0}
    if not current_user: st.stop()
elif selected_name != "--- Select your name ---":
    current_user = selected_name
    current_schedule = db[current_user]
else:
    current_user = None
    st.stop()

# --- THE SIDEBAR ---
if current_user and current_user != "I am a NEW PhD (Add me)":
    with st.sidebar:
        st.header(f"📊 {current_user.split()[0]} ({get_initials(current_user)})'s Profile")
        st.divider()
        
        shifts = current_schedule.get("historical_shifts", 0)
        months = current_schedule.get("active_months", 1)
        ratio = shifts / months if months > 0 else 0
        
        st.metric("Completed Shifts", shifts)
        st.metric("Fairness Ratio", f"{ratio:.2f}")
        
        st.divider()
        st.markdown("#### 🎤 Guided Tours")
        completed_tours = current_schedule.get("historical_tours", 0)
        st.metric("Completed Tours", completed_tours)
        
        progress_val = 50 if completed_tours % 2 != 0 else 0
        st.progress(progress_val, text=f"{progress_val}% to next DDJ shift credit")
        
        st.divider()
        is_active = current_schedule.get("active", True)
        if is_active: st.success("🟢 Active in rotation")
        else: st.error("🔴 Inactive (Excluded from shifts)")
            
        away_dates = current_schedule.get("away_dates", [])
        st.markdown("#### ✈️ Upcoming Absences")
        if away_dates:
            for away in away_dates:
                reason = away.get("reason", "Away")
                if away['start'] == away['end']: st.write(f"• **{away['start']}** ({reason})")
                else: st.write(f"• **{away['start']}** to **{away['end']}** ({reason})")
        else:
            st.caption("*(No away dates scheduled)*")
            
        published = config.get("PUBLISHED_SCHEDULE", [])
        if published:
            st.divider()
            st.markdown("### 📅 Upcoming Month")
            user_initials = get_initials(current_user)
            
            html = "<table style='width:100%; font-size:13px; text-align:center; border-collapse: collapse;'>"
            html += "<tr style='background-color:#444; color:white;'><th>Date</th><th>AM</th><th>PM</th></tr>"
            
            for day in published:
                bg_color = "border-bottom: 1px solid #ddd;"
                day_type = day.get("Type", "NORMAL") 
                
                if day_type == "TCV_OFF": bg_color = "background-color: #ffcccc; color: #990000; border-bottom: 1px solid #ddd;"
                elif day_type == "HOLIDAY": bg_color = "background-color: #cce5ff; color: #004085; border-bottom: 1px solid #ddd;"
                
                am_style = "background-color: #ffd700; color: black; font-weight: bold; font-size: 15px;" if user_initials != "" and user_initials == day["AM"] else ""
                pm_style = "background-color: #ffd700; color: black; font-weight: bold; font-size: 15px;" if user_initials != "" and user_initials == day["PM"] else ""
                
                html += f"<tr style='{bg_color}'><td style='padding:5px;'>{day['Date']}</td><td style='{am_style}'>{day['AM']}</td><td style='{pm_style}'>{day['PM']}</td></tr>"
            
            html += "</table>"
            st.markdown(html, unsafe_allow_html=True)

main_tab1, main_tab2, main_tab3 = st.tabs(["📝 My Availability", "📅 DDJ History", "🎤 Guided Tours"])

# ==========================================
# TAB 1: AVAILABILITY
# ==========================================
with main_tab1:
    st.markdown(f"### Update Profile: **{current_user}**")
    updated_schedule = {"AM": [], "PM": []}

    if len(current_schedule.get("AM", [])) == 4:
        current_schedule["AM"].insert(0, True)
        current_schedule["PM"].insert(0, True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Morning (8h15 - 13h)")
        for i, day in enumerate(DAYS): updated_schedule["AM"].append(st.checkbox(f"{day} AM", value=current_schedule["AM"][i]))
    with col2:
        st.subheader("Afternoon (13h - 18h)")
        for i, day in enumerate(DAYS): updated_schedule["PM"].append(st.checkbox(f"{day} PM", value=current_schedule["PM"][i]))
            
    st.markdown("---")
    st.markdown("#### Specific Away Dates")
    existing_away_dates = current_schedule.get("away_dates", [])
    dates_to_keep = []
    
    if existing_away_dates:
        st.write("Uncheck a box to delete that away period:")
        for i, away_period in enumerate(existing_away_dates):
            is_past = False
            try:
                if datetime.date.fromisoformat(away_period['end']) < today: is_past = True
            except: pass 
                
            if not is_past:
                reason = away_period.get('reason', 'Away')
                label = f"🗓️ {away_period['start']} ({reason})" if away_period['start'] == away_period['end'] else f"🗓️ {away_period['start']} to {away_period['end']} ({reason})"
                if st.checkbox(label, value=True, key=f"keep_{i}_{away_period['start']}"): dates_to_keep.append(away_period)
    else: st.caption("*(No upcoming away dates scheduled)*")
        
    updated_schedule["away_dates"] = dates_to_keep
    new_date_range = st.date_input("Select dates:", value=[], key="new_dates")
    new_reason = st.selectbox("Reason:", ["Conference", "Holiday", "Course/Teaching", "Other"], key="new_reason")

    st.markdown("---")
    with st.expander("🛠️ Admin Dojo"):
        admin_pass = st.text_input("Admin Password:", type="password")
        if admin_pass == st.secrets.get("ADMIN_PASSWORD", ""):
            st.success("Admin access granted.")
            updated_schedule["active"] = st.checkbox("🟢 Active in rotation?", value=current_schedule.get("active", True))
            updated_schedule["historical_shifts"] = st.number_input("Total Shifts:", value=current_schedule.get("historical_shifts", 0), step=1)
            updated_schedule["active_months"] = st.number_input("Total Months:", value=current_schedule.get("active_months", 1), step=1)
            updated_schedule["historical_tours"] = st.number_input("Total Tours Completed:", value=current_schedule.get("historical_tours", 0), step=1)
            
            st.divider()
            st.markdown("#### 🔧 TCV Operational Control")
            tcv_off = config.get("TCV_OFF_RANGES", [])
            new_tcv_off = []
            for i, period in enumerate(tcv_off):
                if st.checkbox(f"🔴 TCV OFF: {period['start']} to {period['end']}", value=True, key=f"tcv_{i}"): new_tcv_off.append(period)
            
            new_tcv_dates = st.date_input("Add TCV Maintenance Dates:", value=[], key="new_tcv")
            if st.button("➕ Add TCV Dates"):
                if len(new_tcv_dates) == 2: new_tcv_off.append({"start": str(new_tcv_dates[0]), "end": str(new_tcv_dates[1])})
                elif len(new_tcv_dates) == 1: new_tcv_off.append({"start": str(new_tcv_dates[0]), "end": str(new_tcv_dates[0])})
                db["__CONFIG__"]["TCV_OFF_RANGES"] = new_tcv_off
                save_data(db)
                st.success("TCV Dates Updated!")
                st.rerun()

            db["__CONFIG__"]["TCV_OFF_RANGES"] = new_tcv_off 
            
            st.divider()
            if st.checkbox(f"Delete {current_user}") and st.button("🗑️ Permanently Delete"):
                del db[current_user]
                save_data(db) 
                st.rerun()
        else:
            updated_schedule["active"] = current_schedule.get("active", True)
            updated_schedule["historical_shifts"] = current_schedule.get("historical_shifts", 0)
            updated_schedule["active_months"] = current_schedule.get("active_months", 1) 
            updated_schedule["historical_tours"] = current_schedule.get("historical_tours", 0)

    st.markdown("""<style>div.stButton > button[kind="primary"] { position: fixed; bottom: 40px; right: 40px; width: 260px; background-color: #28a745; color: white; font-size: 18px !important; height: 3em; border-radius: 8px; border: 2px solid #1e7e34; font-weight: bold; z-index: 99999; box-shadow: 0px 4px 12px rgba(0,0,0,0.3); } div.stButton > button[kind="primary"]:hover { background-color: #218838; border-color: #1e7e34; }</style>""", unsafe_allow_html=True)

    if st.button("💾 SAVE MY AVAILABILITY", type="primary"):
        available_slots = sum(updated_schedule["AM"][1:]) + sum(updated_schedule["PM"][1:])
        if available_slots < 2:
            st.error("Please select at least two slots between Tuesday and Friday.")
        else:
            if new_date_range: 
                start_date = str(new_date_range[0])
                end_date = str(new_date_range[1] if len(new_date_range) > 1 else new_date_range[0])
                updated_schedule["away_dates"].append({"start": start_date, "end": end_date, "reason": new_reason})   
            db[current_user] = updated_schedule
            save_data(db) 
            st.success("Successfully updated!")
            st.rerun()

# ==========================================
# TAB 2: HISTORY
# ==========================================
with main_tab2:
    st.header("📅 DDJ Historical Dashboard")
    history_book = config.get("HISTORY", {})
    if history_book:
        months = list(history_book.keys())
        months.reverse() 
        selected_month = st.selectbox("View Schedule for:", months)
        st.dataframe(history_book[selected_month], use_container_width=True, hide_index=True)
    else: st.write("No historical data available yet.")

# ==========================================
# TAB 3: GUIDED TOURS 
# ==========================================
with main_tab3:
    st.header("🎤 Guided Tours")
    
    # --- VISIT COORDINATOR PORTAL ---
    with st.expander("🔐 Visit Coordinator Access"):
        coord_pass = st.text_input("Coordinator Password:", type="password")
        if coord_pass == st.secrets.get("COORD_PASSWORD", ""):
            st.success("Access granted.")
            
            coord_tab1, coord_tab2, coord_tab3 = st.tabs(["📝 Add Visit", "🛠️ Manage Guides", "✉️ Call for Guides"])
            
            with coord_tab1:
                with st.form("new_visit_form"):
                    st.write("Schedule a New Visit")
                    c1, c2 = st.columns(2)
                    with c1:
                        visit_date = st.date_input("Date")
                        visit_time = st.time_input("Time (Heure)")
                        duration = st.text_input("Duration", value="00:45")
                        group_name = st.text_input("Group Name")
                        contact_info = st.text_input("Contact Email")
                    with c2:
                        locations = st.multiselect("Locations", ["TCV", "Helios", "Bio Plasmas"])
                        language = st.selectbox("Language", ["English", "French", "German", "Italian", "Spanish", "Chinese"])
                        num_people = st.number_input("Number of People", min_value=1, value=4)
                        guides_needed = st.number_input("Guides Required", min_value=1, value=1)
                        spc_resp = st.text_input("Resp SPC")

                    if st.form_submit_button("➕ Add Visit"):
                        new_tour = {
                            "date": str(visit_date), "time": str(visit_time), "duration": duration,
                            "group": group_name, "contact": contact_info, "locations": locations,
                            "language": language, "people": num_people, "resp_spc": spc_resp,
                            "guides_needed": guides_needed, "assigned_guides": [], "approved_guides": [], "guest_guides": [], "counted": False
                        }
                        if "__TOURS__" not in db: db["__TOURS__"] = []
                        db["__TOURS__"].append(new_tour)
                        save_data(db)
                        st.success(f"Added visit for {group_name}!")
                        st.rerun()

            with coord_tab2:
                for i, tour in enumerate(tours_db):
                    if not tour.get("counted", False):
                        st.markdown(f"**{tour['date']}** - {tour['group']} (Requires {tour['guides_needed']})")
                        
                        # Pending DDJs
                        for guide in tour.get("assigned_guides", []):
                            pc1, pc2, pc3 = st.columns([3, 1, 1])
                            pc1.write(f"⏳ {guide} (Pending)")
                            if pc2.button("✅ Approve", key=f"app_{i}_{guide}"):
                                tour["assigned_guides"].remove(guide)
                                if "approved_guides" not in tour: tour["approved_guides"] = []
                                tour["approved_guides"].append(guide)
                                save_data(db)
                                st.rerun()
                            if pc3.button("❌ Reject", key=f"rej_{i}_{guide}"):
                                tour["assigned_guides"].remove(guide)
                                save_data(db)
                                st.rerun()
                                
                        # Approved DDJs
                        for guide in tour.get("approved_guides", []):
                            cc1, cc2 = st.columns([4, 1])
                            cc1.write(f"✅ **{guide}** *(DDJ)*")
                            if cc2.button("Revoke", key=f"revoke_{i}_{guide}"):
                                tour["approved_guides"].remove(guide)
                                save_data(db)
                                st.rerun()
                                
                        # Non-DDJ / Guest Guides
                        for guest in tour.get("guest_guides", []):
                            gc1, gc2 = st.columns([4, 1])
                            gc1.write(f"🧑‍🏫 **{guest}** *(Guest)*")
                            if gc2.button("Remove", key=f"rem_guest_{i}_{guest}"):
                                tour["guest_guides"].remove(guest)
                                save_data(db)
                                st.rerun()
                                
                        # Add Guest Form
                        with st.form(f"add_guest_form_{i}"):
                            new_guest = st.text_input("Assign a Guest/Postdoc (Manual Entry)")
                            if st.form_submit_button("Add Guest"):
                                if new_guest:
                                    if "guest_guides" not in tour: tour["guest_guides"] = []
                                    tour["guest_guides"].append(new_guest)
                                    save_data(db)
                                    st.rerun()
                        st.divider()
                
            with coord_tab3:
                st.write("Generate an automatic email draft for empty tours in the next 7 days.")
                next_week = today + datetime.timedelta(days=7)
                empty_tours = []
                for t in tours_db:
                    try:
                        t_date = datetime.date.fromisoformat(t["date"])
                        if today <= t_date <= next_week:
                            total_guides = len(t.get("assigned_guides", [])) + len(t.get("approved_guides", [])) + len(t.get("guest_guides", []))
                            if total_guides < t.get("guides_needed", 1): empty_tours.append(t)
                    except: pass
                
                if st.button("Generate Email Draft"):
                    if not empty_tours: st.success("All tours for the next 7 days are fully booked!")
                    else:
                        subject = urllib.parse.quote("Urgent: Tour Guides Needed for Upcoming Visits")
                        body = "Hello everyone,\n\nWe are looking for guides for the following upcoming tours:\n\n"
                        for t in empty_tours:
                            missing = t.get("guides_needed", 1) - (len(t.get("assigned_guides", [])) + len(t.get("approved_guides", [])) + len(t.get("guest_guides", [])))
                            body += f"- {t['date']} at {t['time']}: {t['group']} ({missing} guides missing, Language: {t['language']})\n"
                        body += "\nPlease book via the DDJ Portal.\n\nBest,\nVisit Coordinator"
                        
                        mailto_link = f"mailto:crpp-ddj@groupes.epfl.ch?subject={subject}&body={urllib.parse.quote(body)}"
                        st.markdown(f'<a href="{mailto_link}" target="_blank"><button style="background-color:#0066cc;color:white;border-radius:5px;padding:10px;border:none;cursor:pointer;">📧 Open Email Draft in Outlook/Mail</button></a>', unsafe_allow_html=True)
                        
    # --- SUB-TABS FOR TOURS ---
    tour_tab1, tour_tab2 = st.tabs(["📅 Upcoming Visits", "📈 Tour Statistics"])
    
    with tour_tab1:
        future_tours = [t for t in tours_db if not t.get("counted", False)]
        if not future_tours: st.write("No upcoming tours scheduled.")
        
        for i, tour in enumerate(future_tours):
            with st.container(border=True):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"#### {tour['date']} at {tour['time']}")
                    st.write(f"**Group:** {tour['group']} ({tour['people']} people)")
                    st.write(f"**Duration:** {tour.get('duration', 'N/A')} | **Contact:** {tour.get('contact', 'N/A')}")
                    st.write(f"**Locations:** {', '.join(tour.get('locations', []))} | **Language:** {tour.get('language', 'Unknown')}")
                    st.caption(f"SPC Resp: {tour.get('resp_spc', '')}")
                
                with col2:
                    assigned = tour.get('assigned_guides', [])
                    approved = tour.get('approved_guides', [])
                    guests = tour.get('guest_guides', [])
                    needed = tour.get('guides_needed', 1)
                    total_booked = len(assigned) + len(approved) + len(guests)
                    
                    st.write(f"**Guides:** {total_booked} / {needed}")
                    
                    for guide in approved: st.write(f"✅ **{guide}**")
                    for guide in guests: st.write(f"🧑‍🏫 **{guide}** *(Guest)*")
                    for guide in assigned: st.write(f"⏳ {guide} *(Pending)*")
                            
                    if current_user in approved:
                        st.success("You are locked in. Contact coordinator to cancel.")
                    elif current_user in assigned:
                        if st.button("❌ Cancel Request", key=f"cancel_{i}"):
                            tour['assigned_guides'].remove(current_user)
                            save_data(db)
                            st.rerun()
                    elif total_booked < needed and current_user not in guests:
                        if st.button("✋ Volunteer as Guide", key=f"book_{i}"):
                            tour['assigned_guides'].append(current_user)
                            save_data(db)
                            st.rerun()
                    else:
                        st.success("Tour is fully booked!")

    with tour_tab2:
        st.subheader("Yearly Analysis")
        # Extract all available years from the database
        years_available = sorted(list(set([t["date"][:4] for t in tours_db if "date" in t])), reverse=True)
        
        if not years_available:
            st.write("No statistics available yet.")
        else:
            selected_year = st.selectbox("Select Year", years_available)
            
            # Filter tours by selected year AND ensure they actually occurred (counted = True)
            year_tours = [t for t in tours_db if t["date"].startswith(selected_year) and t.get("counted", False)]
            st.metric(f"Total Completed Tours in {selected_year}", len(year_tours))
            
            # --- LANGUAGE CHART ---
            st.markdown("##### Language Distribution")
            langs = [t.get("language", "Unknown") for t in year_tours]
            if langs:
                lang_counts = {l: langs.count(l) for l in set(langs)}
                st.bar_chart(pd.DataFrame.from_dict(lang_counts, orient='index', columns=['Tours']))
            
            # --- LEADERBOARD & PROJECTIONS ---
            st.markdown("##### Guide Leaderboard & Projections")
            
            guide_counts = {}
            for t in year_tours:
                for g in t.get("approved_guides", []): guide_counts[g] = guide_counts.get(g, 0) + 1
                for g in t.get("guest_guides", []): guide_counts[g] = guide_counts.get(g, 0) + 1
                
            if guide_counts:
                # Determine how many months have passed for the projection calculation
                current_year_str = str(today.year)
                months_passed = today.month if selected_year == current_year_str else 12
                
                table_data = []
                for guide, count in sorted(guide_counts.items(), key=lambda x: x[1], reverse=True):
                    is_guest = "Yes" if guide in guest_db else "No"
                    projection = round((count / months_passed) * 12, 1) if months_passed > 0 else count
                    table_data.append({
                        "Guide Name": guide,
                        "Tours Completed": count,
                        "Projected / Year": projection,
                        "Guest (Non-DDJ)": is_guest
                    })
                
                st.dataframe(table_data, use_container_width=True, hide_index=True)
                
                top_guide = table_data[0]["Guide Name"]
                top_count = table_data[0]["Tours Completed"]
                st.success(f"🏆 **Top Guide of {selected_year}:** {top_guide} ({top_count} tours)")
            else:
                st.write(f"No tours have been completed yet in {selected_year}.")