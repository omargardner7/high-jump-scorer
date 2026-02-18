import streamlit as st
import pandas as pd
import os
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="High Jump Scorer", layout="wide")

# 1. LOCAL BACKUP (Saves full app state so you can refresh page/restart app)
LOCAL_BACKUP_FILE = "highjump_state_backup.csv"

# 2. GOOGLE DRIVE SYNC (Saves clean results for the Live Scoreboard)
# We use r"" to ensure Windows backslashes are read correctly
DRIVE_FOLDER = r"G:\My Drive\Sports Day results"

# --- HELPER FUNCTIONS ---

def calculate_score(competitor):
    """Calculates Best Height, Failures at Best, and Total Failures."""
    results = competitor.get('results', {})
    best_height = 0.0
    failures_at_best = 0
    
    # 1. Find Best Height
    for height_label, result in results.items():
        if not result: continue
        try: 
            height_val = float(height_label)
            # Check for clearance (O)
            if 'O' in result.upper():
                if height_val > best_height:
                    best_height = height_val
                    # Count failures at this specific new best height
                    failures_at_best = result.upper().count('X')
        except ValueError: 
            continue
            
    # 2. Calculate Total Failures (up to and including best height)
    total_failures = 0
    for height_label, result in results.items():
        try: 
            h_val = float(height_label)
            # Only count failures for heights that were attempted
            if result: 
                total_failures += result.upper().count('X')
        except ValueError: 
            continue
            
    return best_height, failures_at_best, total_failures

def save_local_state():
    """Saves the full app state (every X and O) to a local CSV."""
    if st.session_state.data:
        export_data = []
        for d in st.session_state.data:
            row = d.copy()
            # Convert the results dictionary to a string so it fits in one CSV cell
            row['results'] = json.dumps(d['results']) 
            export_data.append(row)
        
        df = pd.DataFrame(export_data)
        df.to_csv(LOCAL_BACKUP_FILE, index=False)

def save_to_drive(category_name):
    """
    Saves a clean Leaderboard CSV to Google Drive for the Live Scoreboard.
    Filename format: 'Highjump_Senior Boys.csv'
    """
    # Safety Check: Does the folder exist?
    target_folder = DRIVE_FOLDER
    if not os.path.exists(target_folder):
        # Fallback: specific warning but don't crash
        # st.toast(f"⚠️ Drive folder not found! Saving locally only.", icon="Vc")
        return 

    # Filter data for just this category
    cat_data = [d for d in st.session_state.data if d['Category'] == category_name]
    
    if not cat_data:
        return

    # Build the clean leaderboard
    leaderboard = []
    for athlete in cat_data:
        best, fails, total = calculate_score(athlete)
        leaderboard.append({
            "Rank": 0, # Placeholder, Sheet logic handles sorting visually if needed
            "Name": athlete['Name'],
            "House": athlete['House'],
            "Best": best,
            "Fails@Best": fails,
            "TotalFails": total
        })

    df = pd.DataFrame(leaderboard)
    
    if not df.empty:
        # Sort: Highest Best -> Lowest Fails@Best -> Lowest TotalFails
        df = df.sort_values(by=["Best", "Fails@Best", "TotalFails"], ascending=[False, True, True])
        
        # Add Rank
        df.reset_index(drop=True, inplace=True)
        df.index += 1
        df["Rank"] = df.index

        # Reorder columns for the Sheet
        df = df[["Rank", "Name", "House", "Best", "Fails@Best", "TotalFails"]]
        
        # Construct Filename
        filename = f"Highjump_{category_name}.csv"
        full_path = os.path.join(target_folder, filename)
        
        try:
            df.to_csv(full_path, index=False)
            # success toast removed to avoid spamming the user
        except Exception as e:
            st.error(f"Could not save to Drive: {e}")

def load_local_state():
    """Restores the app state from the local backup file on startup."""
    if os.path.exists(LOCAL_BACKUP_FILE):
        try:
            df = pd.read_csv(LOCAL_BACKUP_FILE)
            data = []
            for _, row in df.iterrows():
                item = row.to_dict()
                # Parse the 'results' string back into a dictionary
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
    """Parses '1.20, 1.25' into a list of floats."""
    try: 
        return [float(h.strip()) for h in str(height_str).split(',') if h.strip()]
    except: 
        return []

# --- APP STARTUP ---

# Initialize Session State
if 'data' not in st.session_state:
    backup = load_local_state()
    if backup:
        st.session_state.data = backup
        st.toast("Restored data from local backup!", icon="💾")
    else:
        st.session_state.data = []

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Setup")
    uploaded_file = st.file_uploader("Upload Start List (CSV)", type=['csv'])
    
    if uploaded_file:
        if st.button("Load Data (Overwrites current)"):
            try:
                df = pd.read_csv(uploaded_file)
                # Clean headers
                df.columns = [c.strip() for c in df.columns]
                
                # Reset Data
                st.session_state.data = []
                for _, row in df.iterrows():
                    st.session_state.data.append({
                        "Category": str(row['Category']),
                        "House": str(row['House']),
                        "Name": str(row['Name']),
                        "Heights_Str": str(row['Heights']), # e.g. "1.20, 1.25"
                        "results": {}
                    })
                save_local_state()
                st.success("Start list loaded!")
                st.rerun()
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
    
    st.divider()
    if st.button("🗑️ Clear All Data"):
        if os.path.exists(LOCAL_BACKUP_FILE):
            os.remove(LOCAL_BACKUP_FILE)
        st.session_state.data = []
        st.rerun()
        
    st.info(f"Syncing to:\n{DRIVE_FOLDER}")

# --- MAIN INTERFACE ---
st.title("High Jump Manager")

if not st.session_state.data:
    st.info("Upload a start list CSV to begin.")
else:
    # 1. Select Category
    categories = sorted(list(set(d['Category'] for d in st.session_state.data)))
    
    col_cat, col_add = st.columns([2, 1])
    with col_cat:
        selected_cat = st.selectbox("Select Category", categories)
        
    # 2. Add New Height Logic
    with col_add:
        with st.form("add_height_form"):
            new_h = st.number_input("Add New Height", 0.50, 2.50, 1.35, step=0.01)
            if st.form_submit_button("Add Height"):
                # Add this height to everyone in this category
                for d in st.session_state.data:
                    if d['Category'] == selected_cat:
                        current_heights = parse_heights(d['Heights_Str'])
                        if new_h not in current_heights:
                            d['Heights_Str'] += f", {new_h}"
                save_local_state()
                st.rerun()

    # 3. Prepare Data for Display
    # Filter for category
    cat_data = [d for d in st.session_state.data if d['Category'] == selected_cat]
    
    # Get all unique heights for this category and sort them
    all_heights = set()
    for d in cat_data:
        all_heights.update(parse_heights(d['Heights_Str']))
    sorted_heights = sorted(list(all_heights))

    st.divider()

    # 4. Scoring Matrix
    for idx, athlete in enumerate(st.session_state.data):
        # Skip athletes not in selected category
        if athlete['Category'] != selected_cat: 
            continue
        
        # Use an expander for each athlete
        with st.expander(f"🏅 {athlete['Name']} ({athlete['House']})", expanded=True):
            c1, c2 = st.columns([1, 4])
            
            # Left Column: Name Edit
            with c1:
                new_name = st.text_input("Name", athlete['Name'], key=f"name_{idx}")
                if new_name != athlete['Name']:
                    athlete['Name'] = new_name
                    save_local_state()
                    save_to_drive(selected_cat) # Update Drive immediately
            
            # Right Column: Height Inputs
            with c2:
                # Create dynamic columns for heights
                if sorted_heights:
                    h_cols = st.columns(len(sorted_heights))
                    for i, h in enumerate(sorted_heights):
                        h_str = str(h)
                        
                        # Existing result or empty
                        current_val = athlete['results'].get(h_str, "")
                        
                        with h_cols[i]:
                            val = st.text_input(
                                f"{h}m", 
                                value=current_val,
                                key=f"res_{idx}_{h_str}",
                                placeholder="-"
                            )
                            
                            # If value changed, save EVERYTHING
                            if val.upper() != current_val:
                                athlete['results'][h_str] = val.upper()
                                save_local_state()        # Backup to laptop
                                save_to_drive(selected_cat) # Sync to Google Drive
                else:
                    st.caption("No heights added yet.")

    # 5. Leaderboard Section
    st.header(f"Leaderboard: {selected_cat}")
    
    leaderboard = []
    for athlete in cat_data:
        best, fails, total = calculate_score(athlete)
        
        row = {
            "Name": athlete['Name'],
            "House": athlete['House'],
            "Best": best,
            "Fails@Best": fails,
            "TotalFails": total
        }
        # Add individual heights for the display table
        for h in sorted_heights:
            row[str(h)] = athlete['results'].get(str(h), "")
            
        leaderboard.append(row)
    
    df_disp = pd.DataFrame(leaderboard)
    
    if not df_disp.empty:
        # Sort logic
        df_disp = df_disp.sort_values(by=["Best", "Fails@Best", "TotalFails"], ascending=[False, True, True])
        
        # Add Rank
        df_disp.reset_index(drop=True, inplace=True)
        df_disp.index += 1
        
        # Show table
        st.dataframe(
            df_disp.style.highlight_max(axis=0, subset=["Best"], color="#90ee90"), 
            use_container_width=True
        )
        
        # Manual Download Button (Optional, since we auto-sync)
        csv = df_disp.to_csv().encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"Highjump_{selected_cat}.csv",
            mime="text/csv"
        )
