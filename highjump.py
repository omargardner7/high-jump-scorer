import streamlit as st
import pandas as pd
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="School High Jump Scorer", layout="wide")

# --- STATE MANAGEMENT ---
if 'data' not in st.session_state:
    st.session_state.data = []  # List of dictionaries for all athletes

# --- FUNCTIONS ---

def parse_heights(height_str):
    """Converts string '1.20, 1.25' to list [1.20, 1.25]"""
    try:
        # Split by comma, strip whitespace, convert to float
        return [float(h.strip()) for h in str(height_str).split(',') if h.strip()]
    except:
        return []

def calculate_score(competitor):
    """
    Calculates metrics:
    1. Max Height Cleared (Float)
    2. Failures at Max Height (Int)
    3. Total Failures up to Max Height (Int)
    """
    results = competitor.get('results', {})
    best_height = 0.0
    failures_at_best = 0
    
    # 1. Determine Best Height & Failures at that height
    for height_label, result in results.items():
        if not result: continue
        try:
            height_val = float(height_label)
        except ValueError:
            continue
            
        fails_in_jump = result.upper().count('X')
        cleared = 'O' in result.upper()
        
        if cleared:
            if height_val > best_height:
                best_height = height_val
                failures_at_best = fails_in_jump

    # 2. Calculate Total Failures (only up to best height)
    total_failures = 0
    for height_label, result in results.items():
        try:
            h_val = float(height_label)
        except ValueError:
            continue
            
        # Standard rule: Count failures of heights equal to or less than best cleared
        if h_val <= best_height:
             total_failures += result.upper().count('X')

    return best_height, failures_at_best, total_failures

# --- SIDEBAR: SETUP & UPLOAD ---
with st.sidebar:
    st.header("1. Upload Start List")
    uploaded_file = st.file_uploader("Upload CSV (Heights, Category, House, Name)", type=['csv'])
    
    if uploaded_file is not None:
        if st.button("Load/Reset Data from CSV"):
            try:
                df_upload = pd.read_csv(uploaded_file)
                # Normalize headers just in case
                df_upload.columns = [c.strip() for c in df_upload.columns]
                
                # Check required columns
                required = ['Heights', 'Category', 'House', 'Name']
                missing = [c for c in required if c not in df_upload.columns]
                
                if missing:
                    st.error(f"CSV missing columns: {missing}")
                else:
                    # Convert to session state format
                    st.session_state.data = []
                    for _, row in df_upload.iterrows():
                        st.session_state.data.append({
                            "Category": str(row['Category']),
                            "House": str(row['House']),
                            "Name": str(row['Name']),
                            "Heights_Str": str(row['Heights']), 
                            "results": {} 
                        })
                    st.success("Data Loaded Successfully!")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

    st.divider()
    st.header("2. Manual Entry")
    with st.expander("Add Late Entry Athlete"):
        m_cat = st.text_input("Category", "Open")
        m_house = st.text_input("House", "Red")
        m_name = st.text_input("Name")
        m_heights = st.text_input("Heights (comma separated)", "1.20, 1.25, 1.30")
        
        if st.button("Add Athlete"):
            st.session_state.data.append({
                "Category": m_cat,
                "House": m_house,
                "Name": m_name,
                "Heights_Str": m_heights,
                "results": {}
            })
            st.success("Added!")
            st.rerun()

# --- MAIN PAGE ---
st.title("🏆 High Jump Manager")

if not st.session_state.data:
    st.info("👈 Please upload your CSV file in the sidebar to begin.")
    st.markdown("""
    **CSV Format Example:**
    | Heights | Category | House | Name |
    | :--- | :--- | :--- | :--- |
    | 1.20,1.25,1.30 | Senior Boys | Blue | John Doe |
    """)
else:
    # --- CATEGORY SELECTION ---
    categories = sorted(list(set(d['Category'] for d in st.session_state.data)))
    col_cat, col_add = st.columns([2, 1])
    
    with col_cat:
        selected_cat = st.selectbox("Select Category to Score:", categories)

    # --- ADD HEIGHT FEATURE ---
    with col_add:
        # Mini form to add height to THIS category
        with st.form("add_height_form"):
            new_h_val = st.number_input("Add Extra Height (m)", min_value=0.5, max_value=3.0, step=0.01, value=1.40)
            submitted = st.form_submit_button("Add Height")
            if submitted:
                # Add this height to everyone in the current category
                count = 0
                for athlete in st.session_state.data:
                    if athlete['Category'] == selected_cat:
                        current_list = parse_heights(athlete['Heights_Str'])
                        if new_h_val not in current_list:
                            # Append to string representation
                            athlete['Heights_Str'] += f", {new_h_val}"
                            count += 1
                if count > 0:
                    st.success(f"Added {new_h_val}m to {count} athletes.")
                    st.rerun()

    # Filter data for this category
    category_data = [d for d in st.session_state.data if d['Category'] == selected_cat]

    if not category_data:
        st.warning("No athletes in this category.")
    else:
        # Determine the "Master List" of heights for this category 
        all_heights = set()
        for d in category_data:
            h_list = parse_heights(d['Heights_Str'])
            all_heights.update(h_list)
        
        sorted_heights = sorted(list(all_heights))
        
        # --- SCORING GRID ---
        st.divider()
        st.subheader(f"Scoring: {selected_cat}")
        st.caption("Instructions: Enter 'O' (Clear), 'X' (Fail), '-' (Pass). logic: XO, XXO, etc.")

        # Display Athletes
        for idx, athlete in enumerate(st.session_state.data):
            # Only show athletes in selected category
            if athlete['Category'] != selected_cat:
                continue

            # Visual Row
            with st.expander(f"🏅 {athlete['Name']} ({athlete['House']})", expanded=True):
                c1, c2 = st.columns([1, 4])
                with c1:
                    # Quick Edit Name
                    new_name = st.text_input("Name", athlete['Name'], key=f"name_{idx}")
                    athlete['Name'] = new_name
                
                with c2:
                    # Dynamic columns for heights
                    # If there are too many heights, this might get squished, but Streamlit handles scroll horizontally on mobile usually
                    cols = st.columns(len(sorted_heights))
                    for i, h in enumerate(sorted_heights):
                        h_str = str(h)
                        with cols[i]:
                            val = st.text_input(
                                f"{h}",
                                value=athlete['results'].get(h_str, ""),
                                key=f"res_{idx}_{h_str}",
                                placeholder="-",
                                max_chars=3
                            )
                            athlete['results'][h_str] = val.upper()

        # --- RANKING TABLE ---
        st.divider()
        st.subheader(f"Leaderboard: {selected_cat}")

        leaderboard = []
        for athlete in category_data:
            best, fails_at_best, total_fails = calculate_score(athlete)
            
            row = {
                "Rank": 0,
                "Name": athlete['Name'],
                "House": athlete['House'],
                "Best": best,
                "Fail @ Best": fails_at_best,
                "Total Fails": total_fails,
            }
            # Add raw results for CSV
            for h in sorted_heights:
                 row[str(h)] = athlete['results'].get(str(h), "")
            
            leaderboard.append(row)

        df = pd.DataFrame(leaderboard)
        
        if not df.empty:
            # Sort Logic
            df = df.sort_values(
                by=["Best", "Fail @ Best", "Total Fails"], 
                ascending=[False, True, True]
            )
            
            # Add Rank
            df.reset_index(drop=True, inplace=True)
            df.index += 1
            df['Rank'] = df.index
            
            # Reorder columns for display
            display_cols = ["Rank", "Name", "House", "Best", "Fail @ Best", "Total Fails"]
            st.dataframe(df[display_cols], use_container_width=True)

            # Export
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"💾 Download {selected_cat} Results",
                data=csv,
                file_name=f'{selected_cat}_results.csv',
                mime='text/csv',
            )
