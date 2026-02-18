import streamlit as st
import pandas as pd
import io
import os
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="High Jump Scorer", layout="wide")
BACKUP_FILE = "highjump_backup.csv"

# --- FUNCTIONS ---
def save_backup():
    """Saves session state data to CSV. Results dict is JSON stringified."""
    if st.session_state.data:
        # We must convert the 'results' dictionary to a string to save in CSV
        # We create a copy to not mess up the session state
        export_data = []
        for d in st.session_state.data:
            row = d.copy()
            row['results'] = json.dumps(d['results']) # Convert dict to string
            export_data.append(row)
        
        df = pd.DataFrame(export_data)
        df.to_csv(BACKUP_FILE, index=False)

def load_backup():
    """Loads backup CSV and parses the results JSON back to dict."""
    if os.path.exists(BACKUP_FILE):
        try:
            df = pd.read_csv(BACKUP_FILE)
            data = []
            for _, row in df.iterrows():
                item = row.to_dict()
                # Convert results string back to dict
                if isinstance(item['results'], str):
                    try:
                        item['results'] = json.loads(item['results'])
                    except:
                        item['results'] = {}
                else:
                    item['results'] = {}
                data.append(item)
            return data
        except Exception:
            return []
    return []

def parse_heights(height_str):
    try: return [float(h.strip()) for h in str(height_str).split(',') if h.strip()]
    except: return []

def calculate_score(competitor):
    results = competitor.get('results', {})
    best_height = 0.0
    failures_at_best = 0
    for height_label, result in results.items():
        if not result: continue
        try: height_val = float(height_label)
        except ValueError: continue
        cleared = 'O' in result.upper()
        if cleared and height_val > best_height:
            best_height = height_val
            failures_at_best = result.upper().count('X')
            
    total_failures = 0
    for height_label, result in results.items():
        try: h_val = float(height_label)
        except ValueError: continue
        if h_val <= best_height:
             total_failures += result.upper().count('X')
    return best_height, failures_at_best, total_failures

# --- STATE ---
if 'data' not in st.session_state:
    backup = load_backup()
    if backup:
        st.session_state.data = backup
        st.toast("Restored from backup!", icon="💾")
    else:
        st.session_state.data = []

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Upload Start List")
    uploaded_file = st.file_uploader("Upload CSV", type=['csv'])
    if uploaded_file and st.button("Load (Overwrites Backup)"):
        df = pd.read_csv(uploaded_file)
        df.columns = [c.strip() for c in df.columns]
        st.session_state.data = []
        for _, row in df.iterrows():
            st.session_state.data.append({
                "Category": str(row['Category']), "House": str(row['House']),
                "Name": str(row['Name']), "Heights_Str": str(row['Heights']),
                "results": {}
            })
        save_backup()
        st.success("Loaded!")
        st.rerun()
    
    st.divider()
    if st.button("🗑️ Clear All Data"):
        if os.path.exists(BACKUP_FILE): os.remove(BACKUP_FILE)
        st.session_state.data = []
        st.rerun()

# --- MAIN ---
st.title("High Jump Manager")

if not st.session_state.data:
    st.info("Upload CSV to start. Data autosaves locally.")
else:
    categories = sorted(list(set(d['Category'] for d in st.session_state.data)))
    col_cat, col_add = st.columns([2, 1])
    with col_cat:
        selected_cat = st.selectbox("Category", categories)
    
    with col_add:
        with st.form("add_height"):
            new_h = st.number_input("Add Height", 0.5, 3.0, 1.40)
            if st.form_submit_button("Add"):
                for d in st.session_state.data:
                    if d['Category'] == selected_cat:
                        if new_h not in parse_heights(d['Heights_Str']):
                            d['Heights_Str'] += f", {new_h}"
                save_backup()
                st.rerun()

    # Filter & Sort Heights
    cat_data = [d for d in st.session_state.data if d['Category'] == selected_cat]
    all_heights = set()
    for d in cat_data: all_heights.update(parse_heights(d['Heights_Str']))
    sorted_heights = sorted(list(all_heights))

    st.subheader(f"Scoring: {selected_cat}")
    for idx, athlete in enumerate(st.session_state.data):
        if athlete['Category'] != selected_cat: continue
        
        with st.expander(f"🏅 {athlete['Name']} ({athlete['House']})", expanded=True):
            c1, c2 = st.columns([1, 4])
            with c1:
                new_name = st.text_input("Name", athlete['Name'], key=f"n_{idx}")
                if new_name != athlete['Name']:
                    athlete['Name'] = new_name
                    save_backup()
            with c2:
                cols = st.columns(len(sorted_heights))
                for i, h in enumerate(sorted_heights):
                    h_str = str(h)
                    val = st.text_input(f"{h}", athlete['results'].get(h_str, ""), key=f"r_{idx}_{h_str}", placeholder="-")
                    if val.upper() != athlete['results'].get(h_str, ""):
                        athlete['results'][h_str] = val.upper()
                        save_backup() # Save on every result entry

    # --- LEADERBOARD ---
    st.divider()
    leaderboard = []
    for athlete in cat_data:
        best, fails, total = calculate_score(athlete)
        row = {"Name": athlete['Name'], "House": athlete['House'], "Best": best, "Fails@Best": fails, "TotalFails": total}
        for h in sorted_heights: row[str(h)] = athlete['results'].get(str(h), "")
        leaderboard.append(row)
    
    df = pd.DataFrame(leaderboard)
    if not df.empty:
        df = df.sort_values(by=["Best", "Fails@Best", "TotalFails"], ascending=[False, True, True])
        df.reset_index(drop=True, inplace=True)
        df.index += 1
        st.dataframe(df[["Name", "House", "Best", "Fails@Best", "TotalFails"]], use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(f"Download {selected_cat}", csv, f"Highjump_{selected_cat}.csv", "text/csv")
