import json
import math
import networkx as nx
import streamlit as st
from streamlit_geolocation import streamlit_geolocation
import folium
from streamlit_folium import st_folium

# --- SAYFA YAPILANDIRMASI ---
st.set_page_config(
    page_title="Istanbul Rail Transit Assistant",
    page_icon="🚇",
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- OTURUM HAFIZASI ---
if "lang" not in st.session_state:
    st.session_state.lang = "tr"
if "theme" not in st.session_state:
    st.session_state.theme = "Light"
if "favorites" not in st.session_state:
    st.session_state.favorites = {}
if "maintenance_lines" not in st.session_state:
    st.session_state.maintenance_lines = []

# --- PWA VE MOBİL UYGULAMA META ETİKETLERİ ---
pwa_header = """
    <link rel="manifest" href="manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="MetroX">
    <link rel="apple-touch-icon" href="https://img.icons8.com/color/192/subway.png">
"""
st.markdown(pwa_header, unsafe_allow_html=True)

# --- DİNAMİK TEMA VE CSS STİLLERİ ---
is_dark = st.session_state.theme == "Dark"
bg_color = "#0e1117" if is_dark else "#ffffff"
text_color = "#fafafa" if is_dark else "#31333f"

css_style = """
    <style>
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none !important; }
    [data-testid="stToolbar"] { visibility: hidden !important; height: 0px !important; display: none !important; }
    header { visibility: hidden !important; height: 0px !important; }
    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 750px;
        background-color: """ + bg_color + """;
        color: """ + text_color + """;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3.2em;
        background-color: #ff4b4b;
        color: white;
        font-weight: bold;
        font-size: 1rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #e03e3e;
        color: white;
    }
    div.stSuccess, div.stInfo, div.stWarning {
        border-radius: 8px;
    }
    </style>
"""
st.markdown(css_style, unsafe_allow_html=True)

# --- DİL SÖZLÜĞÜ (TRANSLATIONS) ---
LANG = {
    "tr": {
        "title": "🚇 İstanbul Raylı Sistem Asistanı",
        "subtitle": "GPS konumu, canlı süre hesaplama, alternatif rota simülasyonu ve dahası.",
        "loc_header": "📍 1. Konum Tespiti",
        "loc_success": "GPS Konumunuz Başarıyla Alındı! ✅",
        "loc_info": "Konum almak için yukarıdaki butona tıklayın (Varsayılan: Bağcılar).",
        "nearest_station": "🔍 **En Yakın İstasyon:**",
        "target_header": "🎯 2. Hedef İstasyon ve Rota",
        "select_target": "Gitmek İstediğiniz İstasyonu Yazın veya Seçin:",
        "calc_button": "Rotayı Hesapla ve Göster",
        "already_there": "Zaten seçtiğiniz istasyondasınız!",
        "no_station": "Seçilen istasyonlar graf ağında bulunamadı!",
        "route_summary": "🚇 En Hızlı Rota Özeti:",
        "step": "Adım:",
        "board_line": "hattına binin",
        "map_header": "🗺️ Rota Haritası",
        "no_path": "Seçtiğiniz bu iki istasyon arasında, bakımda olan hatlar nedeniyle doğrudan bir bağlantı bulunamadı!",
        "error": "Beklenmeyen bir hata oluştu:",
        "est_time": "Tahmini Süre",
        "transfers": "Aktarma Sayısı",
        "minutes": "dk",
        "transfer_count": "aktarma",
        "fav_header": "⭐ Favoriler",
        "add_fav": "Favorilere Ekle",
        "fav_name_input": "Favori Adı (Örn: Ev, İş):",
        "saved_favs": "Hızlı Seçim:",
        "sim_header": "🚨 Hat Bakım / Kesinti Simülasyonu",
        "sim_desc": "Bakımda/kapalı olan hatları buradan seçebilirsiniz:"
    },
    "en": {
        "title": "🚇 Istanbul Rail Transit Assistant",
        "subtitle": "GPS location, live duration calculation, alternative route simulation and more.",
        "loc_header": "📍 1. Location Detection",
        "loc_success": "GPS Location Successfully Acquired! ✅",
        "loc_info": "Click the button above to get your location (Default: Bağcılar).",
        "nearest_station": "🔍 **Nearest Station:**",
        "target_header": "🎯 2. Destination Station & Route",
        "select_target": "Type or Select Destination Station:",
        "calc_button": "Calculate Route & Show Map",
        "already_there": "You are already at the selected station!",
        "no_station": "Selected stations could not be found in the transit graph!",
        "route_summary": "🚇 Fastest Route Summary:",
        "step": "Step:",
        "board_line": "board the line",
        "map_header": "🗺️ Route Map",
        "no_path": "No direct connection found due to lines under maintenance!",
        "error": "An unexpected error occurred:",
        "est_time": "Estimated Time",
        "transfers": "Transfers",
        "minutes": "mins",
        "transfer_count": "transfers",
        "fav_header": "⭐ Favorites",
        "add_fav": "Add to Favorites",
        "fav_name_input": "Favorite Name (e.g., Home, Work):",
        "saved_favs": "Quick Select:",
        "sim_header": "🚨 Line Maintenance Simulation",
        "sim_desc": "Select lines under maintenance here:"
    }
}

t = LANG[st.session_state.lang]

# --- VERİLERİ YÜKLEME VE GRAF ---
@st.cache_data
def load_stations():
    with open("stations.json", "r", encoding="utf-8") as f:
        return json.load(f)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def build_transit_graph(maintenance_list):
    stations = load_stations()
    G = nx.Graph()
    for station in stations:
        station_line = station["line"]
        is_under_maintenance = any(m_line in station_line for m_line in maintenance_list)
        
        if not is_under_maintenance:
            G.add_node(station["id"], name=station["name"], line=station["line"], lat=station["lat"], lon=station["lon"])
            for neighbor in station.get("neighbors", []):
                neighbor_station = next((s for s in stations if s["id"] == neighbor), None)
                if neighbor_station:
                    n_line = neighbor_station["line"]
                    if not any(m_line in n_line for m_line in maintenance_list):
                        G.add_edge(station["id"], neighbor)
    return G

stations = load_stations()
all_lines = sorted(list(set([s["line"] for s in stations])))

# --- ÜST KISIM (BAŞLIK VE KÜÇÜK YAN YANA BUTONLAR) ---
col_title, col_theme, col_tr, col_en = st.columns([5, 1, 1, 1])

with col_title:
    st.markdown(f"## {t['title']}")

with col_theme:
    if st.button("🌙" if is_dark else "☀️", use_container_width=True):
        st.session_state.theme = "Light" if is_dark else "Dark"
        st.rerun()

with col_tr:
    if st.button("TR", use_container_width=True):
        st.session_state.lang = "tr"
        st.rerun()

with col_en:
    if st.button("EN", use_container_width=True):
        st.session_state.lang = "en"
        st.rerun()

st.write(t["subtitle"])

# --- HAT BAKIM / KESİNTİ SİMÜLASYONU (ANA EKRANDA RAHAT ERİŞİM İÇİN EXPANDER) ---
with st.expander(t["sim_header"], expanded=False):
    st.write(t["sim_desc"])
    selected_maintenance = st.multiselect("Hatlar / Lines", options=all_lines, default=st.session_state.maintenance_lines, label_visibility="collapsed")
    st.session_state.maintenance_lines = selected_maintenance

st.markdown("---")

station_options = {s["name"]: s["id"] for s in stations}
station_names_list = list(station_options.keys())

# --- BÖLÜM 1: KONUM TESPİTİ ---
st.markdown(f"### {t['loc_header']}")
location = streamlit_geolocation()

user_lat, user_lon = None, None

if location.get("latitude") and location.get("longitude"):
    user_lat = location["latitude"]
    user_lon = location["longitude"]
    st.success(t["loc_success"])
else:
    st.info(t["loc_info"])
    user_lat, user_lon = 41.0350, 28.8500

# En Yakın İstasyonu Bulma
min_dist = float('inf')
nearest_station = None
for s in stations:
    dist = haversine(user_lat, user_lon, s["lat"], s["lon"])
    if dist < min_dist:
        min_dist = dist
        nearest_station = s

if nearest_station:
    st.info(f"{t['nearest_station']} `{nearest_station['name']}` (~{round(min_dist*1000)} meters / metre)")

st.markdown("---")

# --- BÖLÜM 2: FAVORİLER VE HEDEF ARAMA ---
st.markdown(f"### {t['target_header']}")

if st.session_state.favorites:
    st.markdown(f"**{t['saved_favs']}**")
    fav_cols = st.columns(len(st.session_state.favorites))
    selected_fav_target = None
    for idx, (fav_name, fav_id) in enumerate(st.session_state.favorites.items()):
        with fav_cols[idx]:
            if st.button(f"⭐ {fav_name}"):
                for name, s_id in station_options.items():
                    if s_id == fav_id:
                        selected_fav_target = name

default_index = 0
if 'selected_fav_target' in locals() and selected_fav_target in station_names_list:
    default_index = station_names_list.index(selected_fav_target)

target_name = st.selectbox(
    t["select_target"],
    options=station_names_list,
    index=default_index
)
target_id = station_options[target_name]

col_fav1, col_fav2 = st.columns([2, 1])
with col_fav1:
    fav_custom_name = st.text_input("Label", value=target_name, label_visibility="collapsed", placeholder=t["fav_name_input"])
with col_fav2:
    if st.button(t["add_fav"]):
        if fav_custom_name:
            st.session_state.favorites[fav_custom_name] = target_id
            st.success("⭐ " + ("Kaydedildi!" if st.session_state.lang=="tr" else "Saved!"))

st.write("")
if st.button(t["calc_button"]):
    if nearest_station["id"] == target_id:
        st.warning(t["already_there"])
    else:
        G = build_transit_graph(st.session_state.maintenance_lines)
        
        if not G.has_node(nearest_station["id"]) or not G.has_node(target_id):
            st.error(t["no_station"])
        else:
            try:
                path = nx.shortest_path(G, source=nearest_station["id"], target=target_id)
                
                # --- DOĞRULANMIŞ ROTA ADIMLARI VE AKTARMA SAYACI ---
                steps = []
                if path and len(path) > 1:
                    def get_common_line(n1_data, n2_data):
                        lines1 = [l.strip() for l in n1_data['line'].split('/')]
                        lines2 = [l.strip() for l in n2_data['line'].split('/')]
                        common = [l for l in lines1 if l in lines2]
                        return common[0] if common else lines2[0]

                    current_from = G.nodes[path[0]]['name']
                    active_line = get_common_line(G.nodes[path[0]], G.nodes[path[1]])
                    segment_start = current_from
                    
                    for i in range(1, len(path)):
                        n_curr = G.nodes[path[i]]
                        n_prev = G.nodes[path[i-1]]
                        curr_lines = [l.strip() for l in n_curr['line'].split('/')]
                        
                        if active_line not in curr_lines:
                            steps.append({
                                "from": segment_start,
                                "to": n_prev['name'],
                                "line": active_line
                            })
                            segment_start = n_prev['name']
                            active_line = curr_lines[0]
                        
                        if i == len(path) - 1:
                            steps.append({
                                "from": segment_start,
                                "to": n_curr['name'],
                                "line": active_line
                            })

                total_transfers = max(0, len(steps) - 1)
                total_stations = len(path) - 1
                
                # Gerçekçi Metro Süre Formülü: (Durak Başına 2 Dk) + (Aktarma Başına 4 Dk)
                estimated_minutes = (total_stations * 2) + (total_transfers * 4)

                st.markdown("---")
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.metric(label=t["est_time"], value=f"{estimated_minutes} {t['minutes']}")
                with col_m2:
                    st.metric(label=t["transfers"], value=f"{total_transfers} {t['transfer_count']}")

                st.markdown(f"### {t['route_summary']}")
                for idx, step in enumerate(steps, 1):
                    if st.session_state.lang == "tr":
                        st.markdown(f"**{idx}. {t['step']}** `{step['line']}` {t['board_line']} (**{step['from']}** ➔ **{step['to']}**)")
                    else:
                        st.markdown(f"**{idx}. Step:** Board `{step['line']}` line (**{step['from']}** ➔ **{step['to']}**)")
                
                st.markdown(f"### {t['map_header']}")
                m = folium.Map(location=[nearest_station['lat'], nearest_station['lon']], zoom_start=12)
                
                route_coords = []
                for node_id in path:
                    n_data = G.nodes[node_id]
                    route_coords.append([n_data['lat'], n_data['lon']])
                    
                    folium.Marker(
                        [n_data['lat'], n_data['lon']],
                        popup=f"{n_data['name']} ({n_data['line']})",
                        tooltip=n_data['name'],
                        icon=folium.Icon(color="red" if node_id == nearest_station['id'] or node_id == target_id else "blue", icon="info-sign")
                    ).add_to(m)

                folium.PolyLine(route_coords, color="red", weight=5, opacity=0.8).add_to(m)
                st_folium(m, width=700, height=450, returned_objects=[])
                    
            except nx.NetworkXNoPath:
                st.error(t["no_path"])
            except Exception as e:
                st.error(f"{t['error']} {e}")   
