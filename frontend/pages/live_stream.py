"""
Live Market Stream Page - Real-time data from WebSocket -> Redis
"""
import os
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
import json

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Live Market Stream",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Live Market Stream Data")
st.markdown("Real-time market data from Polymarket WebSocket → Redis")

# ==================== Sidebar Controls ====================

with st.sidebar:
    st.header("Stream Controls")
    
    # Asset ID input
    asset_id = st.text_input(
        "Asset ID to subscribe to:",
        value="59500043981638253528854819796350757181716737470693576068597643626706510223839",
        help="Enter the asset ID you want to monitor",
    )
    
    # Refresh interval
    refresh_interval = st.slider(
        "Auto-refresh interval (seconds)",
        min_value=1,
        max_value=30,
        value=5,
    )
    
    # Number of messages to display
    message_count = st.slider(
        "Number of recent messages",
        min_value=10,
        max_value=200,
        value=50,
    )
    
    st.divider()
    
    # Health check
    if st.button("Check Redis Connection"):
        try:
            response = requests.get(f"{API_URL}/market-stream/health")
            data = response.json()
            if response.status_code == 200 and data.get("status") == "ok":
                st.success("✓ Redis stream service is healthy")
            else:
                st.error(f"✗ {data.get('message', 'Unknown error')}")
        except Exception as e:
            st.error(f"✗ Connection failed: {e}")

    # Apply subscription button
    if st.button("Apply subscription"):
        try:
            resp = requests.post(f"{API_URL}/market-stream/control", json={"asset_ids": [asset_id]})
            if resp.status_code == 200 and resp.json().get("status") == "ok":
                st.success("Subscription request sent")
            else:
                st.error(f"Failed to publish control: {resp.text}")
        except Exception as e:
            st.error(f"Error sending control: {e}")

# ==================== Main Content ====================

# Fetch stream info
try:
    response = requests.get(f"{API_URL}/market-stream/info")
    if response.status_code == 200:
        info = response.json()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Stream Length", info.get("length", "N/A"))
        with col2:
            st.metric("First Entry", info.get("first_entry_id", "N/A")[:20] + "...")
        with col3:
            st.metric("Last Entry", info.get("last_entry_id", "N/A")[:20] + "...")
except Exception as e:
    st.error(f"Failed to fetch stream info: {e}")

st.divider()

# ==================== Live Messages Display ====================

st.subheader(f"Recent Messages (last {message_count})")

# Placeholder for auto-refresh
message_placeholder = st.empty()
timestamp_placeholder = st.empty()

# Auto-refresh logic
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

# Fetch messages
try:
    response = requests.get(
        f"{API_URL}/market-stream/recent",
        params={"count": message_count}
    )
    
    if response.status_code == 200:
        messages = response.json()
        
        with timestamp_placeholder.container():
            st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        
        if not messages:
            st.info("No messages in stream yet. Waiting for WebSocket data...")
        else:
            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["Table View", "JSON View", "Details"])
            
            with tab1:
                # Convert to DataFrame for better visualization
                df_data = []
                for msg in messages:
                    data = msg.get("data", {})
                    df_data.append({
                        "Timestamp": msg.get("timestamp", ""),
                        "Type": data.get("type", "unknown"),
                        "Asset IDs Count": len(data.get("assets_ids", [])),
                        "Message ID": msg.get("id", "")[:15] + "...",
                    })
                
                if df_data:
                    df = pd.DataFrame(df_data)
                    st.dataframe(df, use_container_width=True)
            
            with tab2:
                # JSON viewer
                selected_msg_idx = st.slider(
                    "Select message to view",
                    0,
                    len(messages) - 1,
                    0,
                )
                
                if messages:
                    selected_msg = messages[selected_msg_idx]
                    st.json({
                        "id": selected_msg.get("id"),
                        "timestamp": selected_msg.get("timestamp"),
                        "data": selected_msg.get("data"),
                    })
            
            with tab3:
                # Detailed analysis
                st.markdown("### Message Statistics")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Messages", len(messages))
                
                with col2:
                    # Count by type
                    types = {}
                    for msg in messages:
                        msg_type = msg.get("data", {}).get("type", "unknown")
                        types[msg_type] = types.get(msg_type, 0) + 1
                    st.metric("Message Types", len(types))
                
                with col3:
                    # Latest timestamp
                    if messages:
                        latest_time = messages[0].get("timestamp", "N/A")
                        st.metric("Latest Update", latest_time[-8:])  # Show time part
                
                st.markdown("### Message Types Distribution")
                if messages:
                    type_counts = {}
                    for msg in messages:
                        msg_type = msg.get("data", {}).get("type", "unknown")
                        type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
                    
                    type_df = pd.DataFrame([
                        {"Type": k, "Count": v}
                        for k, v in type_counts.items()
                    ])
                    
                    st.bar_chart(type_df.set_index("Type"))

except requests.exceptions.ConnectionError:
    st.error(f"Cannot connect to API at {API_URL}")
except Exception as e:
    st.error(f"Error fetching messages: {e}")

# ==================== Auto-refresh ====================

st.divider()
st.markdown("### Auto-Refresh")
st.info(f"Page will auto-refresh every {refresh_interval} seconds")

# Use streamlit's rerun with a delay
import time as time_module
time_module.sleep(refresh_interval)
st.rerun()
