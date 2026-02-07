import streamlit as st
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="High Jump Scorer", layout="wide")

# --- STATE MANAGEMENT ---
if 'competitors' not in st.session_state:
    st.session_state.competitors = [] # List of dicts
if 'heights' not in st.session_state:
    st.session_state.heights = [1.20, 1.23, 1.26, 1.29, 1.32, 1.35] # Default heights

# --- FUNCTIONS ---

def calculate_score(competitor):
    """
    Calculates metrics based on the image rules:
    1. Max Height Cleared
    2. Attempts at Max Height (Tie breaker 1)
    3. Total Failures up to Max Height (Tie breaker 2)
    """
    results = competitor['results']
    best_height = 0.0
    failures_at_best = 0
    total_failures = 0
    
    # Calculate Total Failures and Best Height
    temp_total_fails = 0
    
    for height_label, result in results.items():
        if not result: continue
        
        height_val = float(height_label)
        
        # Count failures in this specific jump string (e.g., "XXO" is 2 fails)
        fails_in_jump = result.upper().count('X')
        
        # Check clearance
        cleared = 'O' in result.upper()
        
        if cleared:
            if height_val > best_height:
                best_height = height_val
                failures_at_best = fails_in_jump # Failures at this specific height
            
            # If cleared, these failures count toward total
            temp_total_fails += fails_in_jump
        else:
            # If not cleared (XXX), these failures usually do NOT count 
            # towards the tie-break for previous heights in standard rules,
            # but usually counting stops at the last cleared height.
            pass

    # Recalculate total failures strictly UP TO the best height cleared
    # (Re-loop to ensure we don't count failures at 1.30 if they only cleared 1.25)
    final_total_failures = 0
    for height_label, result in results.items():
        h_val = float(height_label)
        if h_val <= best_height:
             final_total_failures += result.upper().count('X')

    return best_height, failures_at_best, final_total_failures

# --- SIDEBAR: SETUP ---
with st.sidebar:
    st.header("Event Setup")
    new_name = st.text_input("Add Competitor Name")
    if st.button("Add Athlete"):
        if new_name:
            st.session_state.competitors.append({
                "name": new_name,
                "results": {str(h): "" for h in st.session_state.heights}
            })
            st.rerun()
            
    st.divider()
    
    new_height = st.number_input("Add New Height (m)", value=1.30, step=0.01)
    if st.button("Add Height"):
        if new_height not in st.session_state.heights:
            st.session_state.heights.append(new_height)
            st.session_state.heights.sort()
            # Update existing competitors with new height key
            for comp in st.session_state.competitors:
                comp['results'][str(new_height)] = ""
            st.rerun()

# --- MAIN PAGE ---
st.title("🏆 High Jump Scoring App")
st.markdown("Rules: _Rank by Height > Failures at Max Height > Total Failures_")

if not st.session_state.competitors:
    st.info("Add competitors in the sidebar to start.")
else:
    # --- INPUT SECTION ---
    st.subheader("Recording")
    
    # Create a grid for entry
    for comp in st.session_state.competitors:
        with st.expander(f"Jumper: {comp['name']}", expanded=True):
            cols = st.columns(len(st.session_state.heights))
            for i, h in enumerate(st.session_state.heights):
                h_str = str(h)
                with cols[i]:
                    # Input for results (O, XO, XXO, XXX)
                    val = st.text_input(
                        f"{h}m", 
                        value=comp['results'].get(h_str, ""), 
                        key=f"{comp['name']}_{h}",
                        placeholder="-",
                        max_chars=3
                    )
                    comp['results'][h_str] = val.upper()

    # --- LEADERBOARD & LOGIC ---
    st.divider()
    st.subheader("Leaderboard")

    leaderboard_data = []
    for comp in st.session_state.competitors:
        best, fails_at_best, total_fails = calculate_score(comp)
        row = {
            "Name": comp['name'],
            "Best Height": best,
            "Failures at Best": fails_at_best,
            "Total Failures": total_fails,
            "Raw Results": comp['results'] # kept for CSV export logic if needed
        }
        # Flatten results for display
        for h, res in comp['results'].items():
            row[f"{h}m"] = res
        leaderboard_data.append(row)

    df = pd.DataFrame(leaderboard_data)

    # SORTING LOGIC (The Core Requirement)
    # 1. Best Height (Descending)
    # 2. Failures at Best (Ascending)
    # 3. Total Failures (Ascending)
    if not df.empty:
        df = df.sort_values(
            by=["Best Height", "Failures at Best", "Total Failures"], 
            ascending=[False, True, True]
        )
        
        # Add Rank Column
        df.reset_index(drop=True, inplace=True)
        df.index += 1
        df.index.name = "Rank"

        # Show the table (Hiding raw dict column)
        display_cols = ["Name", "Best Height", "Failures at Best", "Total Failures"] + [f"{h}m" for h in st.session_state.heights]
        st.dataframe(df[display_cols], use_container_width=True)

        # --- EXPORT ---
        csv = df.to_csv().encode('utf-8')
        st.download_button(
            label="Download Results as CSV",
            data=csv,
            file_name='high_jump_results.csv',
            mime='text/csv',
        )