import streamlit as st
import pymongo
from pymongo import MongoClient
import pandas as pd
from streamlit_folium import st_folium
import folium
from streamlit_js_eval import streamlit_js_eval

# --- Database Connection ---
def get_db_connection():
    """Returns a connection to the MongoDB database."""
    connection_string = "mongodb+srv://aldenroxy:N53wxkFIvbAJjZjc@cluster0.l7fdbmf.mongodb.net/geodb"
    client = MongoClient(connection_string)
    return client

def get_db():
    """Returns the 'geodb' database."""
    client = get_db_connection()
    db = client.geodb
    return db

def main():
    st.title("Geo-Tagging App")

    # Session state to keep track of login status
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        login_page()
    else:
        app_page()

def login_page():
    st.header("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        # Hardcoded credentials for now
        if username == "user" and password == "pass":
            st.session_state['logged_in'] = True
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password")

def app_page():
    st.sidebar.title("Navigation")
    menu = ["Location List", "Map View"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Location List":
        location_list_page()
    elif choice == "Map View":
        map_view_page()

def location_list_page():
    st.header("Location List")
    db = get_db()
    locations_collection = db.locations

    # Fetch data from MongoDB
    locations_cursor = locations_collection.find()
    locations_list = list(locations_cursor)

    if not locations_list:
        st.write("No locations tagged yet.")
        return

    # Convert to DataFrame
    df = pd.DataFrame(locations_list)
    # Reorder columns to be more intuitive
    df = df[['name', 'hhid', 'latitude', 'longitude']]

    st.write("### All Locations")

    # Search functionality
    search_term = st.text_input("Search by name or HHID")
    if search_term:
        # Case-insensitive search
        search_term = search_term.lower()
        # Search in name and hhid columns
        df_search = df[
            df['name'].str.lower().str.contains(search_term) |
            df['hhid'].str.lower().str.contains(search_term)
        ]
        st.dataframe(df_search)
    else:
        st.dataframe(df)

def map_view_page():
    st.header("Map View")

    # --- Get Current Location ---
    st.write("### View Your Current Location")
    if st.button("Get My Location"):
        # Get location from browser
        location = streamlit_js_eval(js_expressions='''
            new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        resolve({
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude
                        });
                    },
                    (error) => {
                        reject(error);
                    }
                );
            });
        ''', key='get_location')

        if location:
            st.session_state['user_location'] = location

    # --- Map Display ---
    if 'user_location' in st.session_state:
        user_lat = st.session_state['user_location']['latitude']
        user_lng = st.session_state['user_location']['longitude']
        m = folium.Map(location=[user_lat, user_lng], zoom_start=15)
        folium.Marker([user_lat, user_lng], popup="Your Location").add_to(m)
    else:
        # Default location (New York)
        m = folium.Map(location=[40.7128, -74.0060], zoom_start=12)

    # Get last click
    map_data = st_folium(m, width=700, height=500)

    # --- Location Tagging ---
    st.write("### Tag a Location")
    st.write("Click on the map to select a location.")

    if map_data and map_data["last_clicked"]:
        lat = map_data["last_clicked"]["lat"]
        lng = map_data["last_clicked"]["lng"]

        st.write(f"Selected Location: Latitude={lat}, Longitude={lng}")

        with st.form("location_form"):
            name = st.text_input("Name")
            hhid = st.text_input("HHID")
            submit_button = st.form_submit_button("Tag Location")

            if submit_button:
                if not name or not hhid:
                    st.error("Please fill in both Name and HHID.")
                else:
                    # Save to database
                    db = get_db()
                    locations_collection = db.locations
                    location_data = {
                        "name": name,
                        "hhid": hhid,
                        "latitude": lat,
                        "longitude": lng
                    }
                    locations_collection.insert_one(location_data)
                    st.success("Location tagged successfully!")

if __name__ == "__main__":
    main()
