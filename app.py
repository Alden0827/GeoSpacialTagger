import streamlit as st
import pymongo
from pymongo import MongoClient
import pandas as pd
from streamlit_folium import st_folium
import folium
from streamlit_js_eval import streamlit_js_eval
from streamlit_option_menu import option_menu

# --- Database Connection ---
def get_db_connection():
    connection_string = "mongodb+srv://aldenroxy:N53wxkFIvbAJjZjc@cluster0.l7fdbmf.mongodb.net/geodb"
    client = MongoClient(connection_string)
    return client

def get_db():
    client = get_db_connection()
    db = client.geodb
    return db

# --- Main App ---
def main():
    st.title("Geo-Tagging App")

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if 'selected_tab' not in st.session_state:
        st.session_state['selected_tab'] = "Location List"

    if not st.session_state['logged_in']:
        login_page()
    else:
        app_page()

# --- Login Page ---
def login_page():
    st.header("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login", key="login_btn"):
        if username == "user" and password == "pass":
            st.session_state['logged_in'] = True
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password")

# --- App Page with Sidebar Menu ---
def app_page():
    from streamlit_option_menu import option_menu
    import io, simplekml

    # --- Initialize session state ---
    if "selected_tab" not in st.session_state:
        st.session_state["selected_tab"] = "Location List"

    tab_options = ["Location List", "Map View"]
    tab_icons = ["list-ul", "map"]

    # --- Sidebar menu ---
    with st.sidebar:
        selected = option_menu(
            menu_title="Navigation",
            options=tab_options,
            icons=tab_icons,
            menu_icon="cast",
            default_index=tab_options.index(st.session_state["selected_tab"]),
            orientation="vertical",
            key="sidebar_menu"
        )

        st.markdown("---")

        # --- Download KML button ---
        db = get_db()
        locations = list(db.locations.find())

        if locations:
            kml = simplekml.Kml()
            for loc in locations:
                name = loc.get("name", "Unknown")
                hhid = loc.get("hhid", "N/A")
                lat = loc.get("latitude")
                lng = loc.get("longitude")
                if lat is not None and lng is not None:
                    kml.newpoint(name=f"{name} ({hhid})", coords=[(lng, lat)])

            # ✅ Convert KML string to bytes for download
            kml_bytes = io.BytesIO(kml.kml().encode("utf-8"))

            st.download_button(
                label="📥 Download KML",
                data=kml_bytes,
                file_name="locations.kml",
                mime="application/vnd.google-earth.kml+xml"
            )
        else:
            st.info("No locations available for export.")

    # --- Sync both ways ---
    if selected != st.session_state["selected_tab"]:
        st.session_state["selected_tab"] = selected

    current_tab = st.session_state["selected_tab"]

    # --- Load the correct page ---
    if current_tab == "Location List":
        location_list_page()
    elif current_tab == "Map View":
        map_view_page()

def location_list_page():
    st.header("Location List")

    try:
        db = get_db()
        locations_collection = db.locations

        locations_list = list(locations_collection.find())
        if not locations_list:
            st.info("No locations tagged yet.")
            return

        # Keep coordinates internally but hide from UI
        df = pd.DataFrame(locations_list)[['name', 'hhid', 'latitude', 'longitude']]

        st.write("### All Locations")
        search_term = st.text_input("Search by name or HHID", key="search_loc")

        if search_term:
            search_term = search_term.lower()
            df = df[
                df['name'].str.lower().str.contains(search_term) |
                df['hhid'].str.lower().str.contains(search_term)
            ]

        # Header row
        cols = st.columns([3, 2, 1])
        cols[0].write("Name")
        cols[1].write("HHID")
        cols[2].write("Action")

        # Rows with inline buttons
        for index, row in df.iterrows():
            cols = st.columns([3, 2, 1])
            cols[0].write(row['name'])
            cols[1].write(row['hhid'])
            if cols[2].button("View", key=f"map_{index}"):
                st.session_state['selected_location'] = {
                    "name": row['name'],
                    "latitude": row['latitude'],
                    "longitude": row['longitude']
                }
                st.session_state['selected_tab'] = "Map View"
                st.rerun()

    except Exception as e:
        # Don’t show raw error to client
        st.error("⚠️ Something went wrong while loading locations. Please try again later.")
        # Optional: log to server for debugging
        import traceback
        print("Error in location_list_page:", traceback.format_exc())


def map_view_page():
    st.header("Map View")

    # --- Button to get user location ---
    if st.button("📍 Get My Location", key="get_my_location"):
        location = streamlit_js_eval(
            js_expressions="""
                new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(
                        (position) => { 
                            resolve({latitude: position.coords.latitude, longitude: position.coords.longitude}); 
                        },
                        (error) => { resolve(null); }
                    );
                });
            """,
            key="get_location"
        )
        if location:
            st.session_state['user_location'] = location
            st.success("✅ Location retrieved!")
            st.rerun()
        else:
            st.warning("⚠️ Unable to retrieve your location. Please allow location access in your browser.")

    # --- Determine map center priority ---
    if "temp_location" in st.session_state:
        center_lat = st.session_state["temp_location"]["lat"]
        center_lng = st.session_state["temp_location"]["lng"]
        zoom = 18
    elif 'selected_location' in st.session_state:
        center_lat = st.session_state['selected_location']['latitude']
        center_lng = st.session_state['selected_location']['longitude']
        zoom = 17
    elif 'user_location' in st.session_state:
        center_lat = st.session_state['user_location']['latitude']
        center_lng = st.session_state['user_location']['longitude']
        zoom = 15
    else:
        center_lat, center_lng, zoom = 6.488797302979707, 124.85166444167126, 24  # koronadal city

    # --- Create map ---
    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom)

    # --- Add permanent markers ---
    if 'selected_location' in st.session_state:
        loc = st.session_state['selected_location']
        folium.Marker(
            [loc['latitude'], loc['longitude']], 
            popup=loc['name'], 
            icon=folium.Icon(color="red")
        ).add_to(m)

    if 'user_location' in st.session_state:
        user = st.session_state['user_location']
        folium.Marker(
            [user['latitude'], user['longitude']], 
            popup="📍 Your Location", 
            icon=folium.Icon(color="blue")
        ).add_to(m)

    # --- Add temporary marker if exists ---
    if "temp_location" in st.session_state:
        tmp = st.session_state["temp_location"]
        folium.Marker(
            [tmp["lat"], tmp["lng"]],
            popup="📍 Selected (not yet saved)",
            icon=folium.Icon(color="green", icon="info-sign")
        ).add_to(m)

    # --- Render map ---
    map_data = st_folium(m, width=700, height=500)

    # --- Capture clicks and store temp marker ---
    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lng = map_data["last_clicked"]["lng"]
        st.session_state["temp_location"] = {"lat": lat, "lng": lng}
        st.rerun()  # force reload to center map & show marker

    # --- Show form if temp marker exists ---
    if "temp_location" in st.session_state:
        tmp = st.session_state["temp_location"]
        st.info(f"📍 Selected Location: {tmp['lat']:.5f}, {tmp['lng']:.5f}")
        with st.form("location_form"):
            name = st.text_input("Name", key="tag_name")
            hhid = st.text_input("HHID", key="tag_hhid")
            submit_button = st.form_submit_button("Tag Location")
            if submit_button:
                if not name or not hhid:
                    st.error("Please fill in both Name and HHID.")
                else:
                    db = get_db()
                    db.locations.insert_one(
                        {"name": name, "hhid": hhid, "latitude": tmp["lat"], "longitude": tmp["lng"]}
                    )
                    st.success("✅ Location tagged successfully!")
                    del st.session_state["temp_location"]
                    st.rerun()

if __name__ == "__main__":
    main()
