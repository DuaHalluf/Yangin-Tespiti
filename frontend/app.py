import streamlit as st
import cv2
import numpy as np
import tempfile
import os
import requests
import pandas as pd
from datetime import datetime

BACKEND_URL      = "http://127.0.0.1:8000"
TELEGRAM_TOKEN   = "8516296044:AAFdFqOP0KxwptYOocV7o2urYm5SB-QM24Q"
TELEGRAM_CHAT_ID = "7558334990"

st.set_page_config(page_title="FireWatch — Fire Detection System", page_icon="🔥", layout="wide")

for key, val in {"logged_in": False, "username": "", "page": "login"}.items():
    if key not in st.session_state:
        st.session_state[key] = val

st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
div[data-testid="stSidebarNav"] { display: none; }
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }
[data-testid="metric-container"] { background:#1a1a2e; border:1px solid #2d2d44; border-radius:12px; padding:16px; }
.stat-card { background:#1a1a2e; border:1px solid #2d2d44; border-radius:12px; padding:20px; text-align:center; margin-bottom:12px; }
.stat-card .value { font-size:36px; font-weight:700; }
.stat-card .label { color:#888; font-size:13px; }
.badge-green { display:inline-flex; align-items:center; gap:6px; background:#1a3a2a; color:#2ecc71; border:1px solid #27ae60; border-radius:20px; padding:4px 12px; font-size:13px; }
.badge-red { display:inline-flex; align-items:center; gap:6px; background:#3a1a1a; color:#e74c3c; border:1px solid #c0392b; border-radius:20px; padding:4px 12px; font-size:13px; }
.progress-wrap { background:#1a1a2e; border:1px solid #2d2d44; border-radius:12px; padding:16px; margin-bottom:12px; }
.progress-track { background:#2d2d44; border-radius:4px; height:8px; margin-top:8px; }
.progress-fill { height:8px; border-radius:4px; }
.stButton > button { border-radius:8px; font-weight:500; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ───────────────────────────────────────────

def backend_calisiyormu():
    try:
        return requests.get(f"{BACKEND_URL}/", timeout=2).status_code == 200
    except:
        return False

def telegram_gonder(mesaj):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": mesaj},
            timeout=5
        )
    except:
        pass

def alarm_ses():
    st.markdown('<audio autoplay><source src="https://www.soundjay.com/misc/sounds/fire-alarm-1.mp3" type="audio/mpeg"></audio>', unsafe_allow_html=True)

def kutu_ciz(img_bgr, detections):
    res = img_bgr.copy()
    for det in detections:
        x1, y1, x2, y2 = det["box"]
        sinif = det["class"].lower()
        conf  = det["confidence"]
        renk  = (0, 0, 255) if sinif == "fire" else (0, 200, 255)
        cv2.rectangle(res, (x1, y1), (x2, y2), renk, 2)
        cv2.putText(res, f"{sinif} {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, renk, 2)
    return res

def backend_kaydet(detections_list, camera_id="Kamera-1", location="Bilinmiyor"):  # ← YENİ
    if not detections_list:
        return
    try:
        requests.post(
            f"{BACKEND_URL}/save",
            json={
                "detections": detections_list,
                "camera_id":  camera_id,   # ← YENİ
                "location":   location     # ← YENİ
            },
            timeout=3
        )
    except:
        pass

# ── Login ─────────────────────────────────────────────

def login_sayfasi():
    st.markdown("""
    <div style='text-align:center; padding:60px 0 20px 0;'>
        <i class="fa-solid fa-fire-flame-curved" style='font-size:56px; color:#e74c3c;'></i>
        <h1 style='color:#e74c3c; margin:12px 0 4px 0; font-size:32px;'>Fire Detection System</h1>
        <p style='color:#888; margin:0;'>YOLOv8 &middot; FastAPI &middot; SQLite</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        tab1, tab2 = st.tabs(["  Sign In", "  Register"])

        with tab1:
            st.markdown("<p style='color:#aaa;'><i class='fa-solid fa-right-to-bracket'></i> Sign in to your account</p>", unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="your_username", key="l_user")
            password = st.text_input("Password", type="password", placeholder="••••••••", key="l_pass")
            if st.button("Sign In", use_container_width=True, type="primary", key="btn_login"):
                if username and password:
                    try:
                        res = requests.post(f"{BACKEND_URL}/login", json={"username": username, "password": password}, timeout=5)
                        if res.status_code == 200:
                            st.session_state.logged_in = True
                            st.session_state.username  = username
                            st.session_state.page      = "detection"
                            st.rerun()
                        else:
                            st.error(res.json().get("detail", "Login failed."))
                    except:
                        st.error("Cannot connect to server.")
                else:
                    st.warning("Please fill in all fields.")

        with tab2:
            st.markdown("<p style='color:#aaa;'><i class='fa-solid fa-user-plus'></i> Create a new account</p>", unsafe_allow_html=True)
            r_user  = st.text_input("Username", placeholder="your_username", key="r_user")
            r_pass  = st.text_input("Password", type="password", placeholder="••••••••", key="r_pass")
            r_pass2 = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="r_pass2")
            if st.button("Register", use_container_width=True, type="primary", key="btn_reg"):
                if r_user and r_pass and r_pass2:
                    if r_pass != r_pass2:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            res = requests.post(f"{BACKEND_URL}/register", json={"username": r_user, "password": r_pass}, timeout=5)
                            if res.status_code == 200:
                                st.success("Account created! You can now sign in.")
                            else:
                                st.error(res.json().get("detail", "Error occurred."))
                        except:
                            st.error("Cannot connect to server.")
                else:
                    st.warning("Please fill in all fields.")

# ── Sidebar ───────────────────────────────────────────

def sidebar_menu():
    with st.sidebar:
        st.markdown(f"""
        <div style='text-align:center; padding:20px 0 16px 0;'>
            <i class="fa-solid fa-fire-flame-curved" style='font-size:40px; color:#e74c3c;'></i>
            <h3 style='margin:8px 0 2px 0; color:#e74c3c;'>FireWatch</h3>
            <div style='color:#888; font-size:13px;'><i class='fa-solid fa-circle-user'></i> {st.session_state.username}</div>
        </div>
        """, unsafe_allow_html=True)
        st.divider()

        for key, icon, label in [
            ("detection",  "fa-camera",           "Detection"),
            ("history",    "fa-clock-rotate-left", "History"),
            ("statistics", "fa-chart-bar",         "Statistics"),
        ]:
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if st.session_state.page == key else "secondary"):
                st.session_state.page = key
                st.rerun()

        st.divider()

        if backend_calisiyormu():
            st.markdown("<div class='badge-green'><i class='fa-solid fa-circle' style='font-size:8px;'></i> System Online</div>", unsafe_allow_html=True)
            try:
                s = requests.get(f"{BACKEND_URL}/stats", timeout=3).json()
                st.markdown(f"""
                <div style='display:flex; gap:8px; margin-top:12px;'>
                    <div class='stat-card' style='flex:1; padding:12px;'>
                        <i class='fa-solid fa-fire' style='color:#e74c3c; font-size:20px;'></i>
                        <div class='value' style='font-size:22px; color:#e74c3c;'>{s.get("total_fire",0)}</div>
                        <div class='label'>Fire</div>
                    </div>
                    <div class='stat-card' style='flex:1; padding:12px;'>
                        <i class='fa-solid fa-wind' style='color:#f39c12; font-size:20px;'></i>
                        <div class='value' style='font-size:22px; color:#f39c12;'>{s.get("total_smoke",0)}</div>
                        <div class='label'>Smoke</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            except:
                pass
        else:
            st.markdown("<div class='badge-red'><i class='fa-solid fa-circle' style='font-size:8px;'></i> System Offline</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Refresh", use_container_width=True):
                st.rerun()
        with c2:
            if st.button("Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.username  = ""
                st.session_state.page      = "login"
                st.rerun()

# ── Page 1: Detection ─────────────────────────────────

def tespit_sayfasi():
    st.markdown("""
    <h2><i class='fa-solid fa-camera' style='color:#e74c3c;'></i> Fire & Smoke Detection</h2>
    <p style='color:#888;'>Analyze photos, videos or live camera feed.</p>
    <hr style='border-color:#2d2d44;'>
    """, unsafe_allow_html=True)

    # ── Kamera Bilgileri ── ← YENİ BLOK
    col_cam1, col_cam2, col_cam3 = st.columns([1, 1, 2])
    with col_cam1:
        camera_id = st.text_input("📷 Kamera ID", value="Kamera-1", placeholder="Örn: Kamera-1")
    with col_cam2:
        location = st.text_input("📍 Konum", value="Bilinmiyor", placeholder="Örn: Orman-A")
    with col_cam3:
        telegram_aktif = st.toggle("Telegram Alerts", value=False)

    mod = st.radio("Mode:", ["Photo", "Video", "Live Camera"], horizontal=True)
    st.markdown("<hr style='border-color:#2d2d44;'>", unsafe_allow_html=True)

    # PHOTO
    if mod == "Photo":
        uploaded = st.file_uploader("Upload a photo", type=["jpg","jpeg","png"], label_visibility="collapsed")
        if uploaded:
            file_bytes = np.asarray(bytearray(uploaded.read()), dtype=np.uint8)
            img_bgr    = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<p style='color:#888; font-size:13px;'><i class='fa-solid fa-image'></i> Input Image</p>", unsafe_allow_html=True)
                st.image(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB), use_container_width=True)
            with st.spinner("Analyzing..."):
                uploaded.seek(0)
                try:
                    api_data = requests.post(
                        f"{BACKEND_URL}/detect",
                        files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                        params={                        # ← YENİ
                            "camera_id": camera_id,    # ← YENİ
                            "location":  location      # ← YENİ
                        },
                        timeout=30
                    ).json()
                except Exception as e:
                    st.error(f"Server error: {e}")
                    st.stop()

            detections = api_data.get("detections", [])
            yangin_var = any(d["class"] == "fire"  for d in detections)
            duman_var  = any(d["class"] == "smoke" for d in detections)

            with col2:
                st.markdown("<p style='color:#888; font-size:13px;'><i class='fa-solid fa-magnifying-glass'></i> Detection Result</p>", unsafe_allow_html=True)
                st.image(cv2.cvtColor(kutu_ciz(img_bgr, detections), cv2.COLOR_BGR2RGB), use_container_width=True)

            st.markdown("<hr style='border-color:#2d2d44;'>", unsafe_allow_html=True)
            m1, m2, m3 = st.columns(3)
            m1.metric("Total",  api_data.get("total", 0))
            m2.metric("Fire",   sum(1 for d in detections if d["class"] == "fire"))
            m3.metric("Smoke",  sum(1 for d in detections if d["class"] == "smoke"))

            high_conf_fire  = [d for d in detections if d["class"] == "fire"  and d["confidence"] >= 0.70]
            high_conf_smoke = [d for d in detections if d["class"] == "smoke" and d["confidence"] >= 0.70]

            if yangin_var:
                alarm_ses()
                st.error("FIRE DETECTED!")
                if telegram_aktif and high_conf_fire:
                    best = max(high_conf_fire, key=lambda x: x["confidence"])
                    telegram_gonder(
                        "🔥 YANGIN TESPİT EDİLDİ!\n"
                        "Güven skoru: %" + str(round(best["confidence"] * 100)) + "\n"
                        "Konum: " + location + "\n"       # ← YENİ
                        "Kamera: " + camera_id + "\n"     # ← YENİ
                        "Zaman: " + str(best["timestamp"])
                    )

            if duman_var:
                st.warning("SMOKE DETECTED!")
                if telegram_aktif and high_conf_smoke:
                    best = max(high_conf_smoke, key=lambda x: x["confidence"])
                    telegram_gonder(
                        "💨 DUMAN TESPİT EDİLDİ!\n"
                        "Güven skoru: %" + str(round(best["confidence"] * 100)) + "\n"
                        "Konum: " + location + "\n"       # ← YENİ
                        "Kamera: " + camera_id + "\n"     # ← YENİ
                        "Zaman: " + str(best["timestamp"])
                    )

            if not yangin_var and not duman_var:
                st.success("No threats detected.")

            with st.expander("API Response (JSON)"):
                st.json(api_data)

    # VIDEO
    elif mod == "Video":
        video_file = st.file_uploader("Upload a video", type=["mp4","avi","mov"])
        if video_file:
            from ultralytics import YOLO
           BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
           MODEL_PATH = os.path.join(BASE_DIR, "Trained-Models", "yolo8_best.pt")
            @st.cache_resource
            def load_model_vid():
                return YOLO(MODEL_PATH)

            yolo  = load_model_vid()
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            tfile.write(video_file.read())
            tfile.close()

            cap         = cv2.VideoCapture(tfile.name)
            stframe     = st.empty()
            CMAP        = {0: "smoke", 1: "fire"}
            buffer      = []
            frame_count = 0

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                results   = yolo(frame)[0]
                res_frame = frame.copy()
                frame_count += 1
                for box in results.boxes:
                    cls             = int(box.cls[0])
                    conf            = float(box.conf[0])
                    sinif           = CMAP.get(cls, results.names[cls]).lower()
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    renk            = (0, 0, 255) if sinif == "fire" else (0, 200, 255)
                    cv2.rectangle(res_frame, (x1, y1), (x2, y2), renk, 2)
                    cv2.putText(res_frame, f"{sinif} {conf:.2f}", (x1, y1-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, renk, 2)
                    buffer.append({"class_name": sinif, "confidence": round(conf, 2)})
                if buffer:
                    backend_kaydet(buffer, camera_id, location)  # ← YENİ
                    buffer = []
                stframe.image(cv2.cvtColor(res_frame, cv2.COLOR_BGR2RGB), use_container_width=True)

            cap.release()
            os.unlink(tfile.name)
            st.success("Video analysis complete. Results saved to database.")

    # LIVE CAMERA
    elif mod == "Live Camera":
        col1, col2 = st.columns([1, 3])
        with col1:
            kayit_araligi = st.number_input("Save every N frames", min_value=1, max_value=30, value=10)
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            st.info(f"Detections will be saved every {kayit_araligi} frames.")

        if st.button("Start Camera", type="primary"):
            from ultralytics import YOLO
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            MODEL_PATH = os.path.join(BASE_DIR, "Trained-Models", "yolo8_best.pt")

            @st.cache_resource
            def load_model_cam():
                return YOLO(MODEL_PATH)

            yolo        = load_model_cam()
            cap         = cv2.VideoCapture(0)
            stframe     = st.empty()
            status_box  = st.empty()
            CMAP        = {0: "smoke", 1: "fire"}
            buffer      = []
            frame_count = 0

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                results   = yolo(frame)[0]
                res_frame = frame.copy()
                frame_count += 1
                for box in results.boxes:
                    cls             = int(box.cls[0])
                    conf            = float(box.conf[0])
                    sinif           = CMAP.get(cls, results.names[cls]).lower()
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    renk            = (0, 0, 255) if sinif == "fire" else (0, 200, 255)
                    cv2.rectangle(res_frame, (x1, y1), (x2, y2), renk, 2)
                    cv2.putText(res_frame, f"{sinif} {conf:.2f}", (x1, y1-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, renk, 2)
                    buffer.append({"class_name": sinif, "confidence": round(conf, 2)})
                if frame_count % kayit_araligi == 0 and buffer:
                    backend_kaydet(buffer, camera_id, location)  # ← YENİ
                    status_box.success(f"Frame {frame_count}: {len(buffer)} detections saved.")
                    buffer = []
                stframe.image(cv2.cvtColor(res_frame, cv2.COLOR_BGR2RGB), use_container_width=True)

            cap.release()

# ── Page 2: History ───────────────────────────────────

def gecmis_sayfasi():
    st.markdown("""
    <h2><i class='fa-solid fa-clock-rotate-left' style='color:#e74c3c;'></i> Detection History</h2>
    <p style='color:#888;'>All detection records saved in the database.</p>
    <hr style='border-color:#2d2d44;'>
    """, unsafe_allow_html=True)

    col1, col2, col3, _ = st.columns([1, 1, 1, 2])
    with col1:
        limit  = st.selectbox("Records", [20, 50, 100, 200])
    with col2:
        filtre = st.selectbox("Class", ["All", "fire", "smoke"])
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    try:
        history = requests.get(f"{BACKEND_URL}/history?limit={limit}", timeout=5).json()
        if filtre != "All":
            history = [h for h in history if h["class"] == filtre]
        if history:
            df = pd.DataFrame(history)
            df.columns = ["ID", "Class", "Confidence", "Timestamp", "Camera", "Location"]  # ← YENİ
            df["Class"]      = df["Class"].apply(lambda x: "Fire" if x == "fire" else "Smoke")
            df["Confidence"] = df["Confidence"].apply(lambda x: f"{x:.0%}")
            st.markdown(f"<p style='color:#888; font-size:13px;'><i class='fa-solid fa-list'></i> {len(df)} records found</p>", unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True, hide_index=True, height=480)
            csv = pd.DataFrame(history).to_csv(index=False).encode("utf-8")
            st.download_button("Export CSV", data=csv,
                               file_name=f"firewatch_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                               mime="text/csv")
        else:
            st.info("No records found.")
    except Exception as e:
        st.error(f"Error: {e}")

# ── Page 3: Statistics ────────────────────────────────

def istatistik_sayfasi():
    st.markdown("""
    <h2><i class='fa-solid fa-chart-bar' style='color:#e74c3c;'></i> Statistics</h2>
    <p style='color:#888;'>System-wide detection analytics and performance metrics.</p>
    <hr style='border-color:#2d2d44;'>
    """, unsafe_allow_html=True)

    try:
        stats   = requests.get(f"{BACKEND_URL}/stats",             timeout=5).json()
        history = requests.get(f"{BACKEND_URL}/history?limit=500", timeout=5).json()

        fire_total  = stats.get("total_fire", 0)
        smoke_total = stats.get("total_smoke", 0)
        total       = stats.get("total_detections", 0)

        st.markdown(f"""
        <div style='display:flex; gap:16px; margin-bottom:24px;'>
            <div class='stat-card' style='flex:1;'>
                <div><i class='fa-solid fa-fire' style='color:#e74c3c; font-size:28px;'></i></div>
                <div class='value' style='color:#e74c3c;'>{fire_total}</div>
                <div class='label'>Total Fire</div>
            </div>
            <div class='stat-card' style='flex:1;'>
                <div><i class='fa-solid fa-wind' style='color:#f39c12; font-size:28px;'></i></div>
                <div class='value' style='color:#f39c12;'>{smoke_total}</div>
                <div class='label'>Total Smoke</div>
            </div>
            <div class='stat-card' style='flex:1;'>
                <div><i class='fa-solid fa-database' style='color:#3498db; font-size:28px;'></i></div>
                <div class='value' style='color:#3498db;'>{total}</div>
                <div class='label'>Total Detections</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if history and total > 0:
            df = pd.DataFrame(history)
            df.columns = ["ID", "class", "confidence", "timestamp", "camera", "location"]  # ← YENİ

            fire_avg  = df[df["class"]=="fire"]["confidence"].mean()  if fire_total  > 0 else 0
            smoke_avg = df[df["class"]=="smoke"]["confidence"].mean() if smoke_total > 0 else 0
            total_avg = df["confidence"].mean()
            fire_pct  = fire_total  / total * 100
            smoke_pct = smoke_total / total * 100

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("<h4 style='color:#ccc;'><i class='fa-solid fa-chart-pie'></i> Distribution</h4>", unsafe_allow_html=True)
                for label, icon, color, count, pct in [
                    ("Fire",  "fa-fire", "#e74c3c", fire_total,  fire_pct),
                    ("Smoke", "fa-wind", "#f39c12", smoke_total, smoke_pct),
                ]:
                    st.markdown(f"""
                    <div class='progress-wrap'>
                        <div style='display:flex; justify-content:space-between;'>
                            <span style='color:#aaa; font-size:13px;'><i class='fa-solid {icon}' style='color:{color};'></i> {label}</span>
                            <span style='color:{color}; font-weight:600;'>{count} ({pct:.1f}%)</span>
                        </div>
                        <div class='progress-track'><div class='progress-fill' style='width:{pct:.0f}%; background:{color};'></div></div>
                    </div>
                    """, unsafe_allow_html=True)

            with col2:
                st.markdown("<h4 style='color:#ccc;'><i class='fa-solid fa-bullseye'></i> Average Confidence</h4>", unsafe_allow_html=True)
                for label, icon, color, avg in [
                    ("Fire avg. confidence",    "fa-fire",       "#e74c3c", fire_avg),
                    ("Smoke avg. confidence",   "fa-wind",       "#f39c12", smoke_avg),
                    ("Overall avg. confidence", "fa-chart-line", "#2ecc71", total_avg),
                ]:
                    st.markdown(f"""
                    <div class='progress-wrap'>
                        <div style='display:flex; justify-content:space-between;'>
                            <span style='color:#aaa; font-size:13px;'><i class='fa-solid {icon}' style='color:{color};'></i> {label}</span>
                            <span style='color:{color}; font-weight:600;'>{avg:.1%}</span>
                        </div>
                        <div class='progress-track'><div class='progress-fill' style='width:{avg*100:.0f}%; background:{color};'></div></div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<hr style='border-color:#2d2d44;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='color:#ccc;'><i class='fa-solid fa-clock-rotate-left'></i> Last 10 Detections</h4>", unsafe_allow_html=True)
            son10 = df.head(10)[["ID","class","confidence","timestamp","camera","location"]].copy()  # ← YENİ
            son10["class"]      = son10["class"].apply(lambda x: "Fire" if x=="fire" else "Smoke")
            son10["confidence"] = son10["confidence"].apply(lambda x: f"{x:.0%}")
            son10.columns       = ["ID", "Class", "Confidence", "Timestamp", "Camera", "Location"]  # ← YENİ
            st.dataframe(son10, use_container_width=True, hide_index=True)
        else:
            st.info("No records yet.")

    except Exception as e:
        st.error(f"Error: {e}")

    if st.button("Refresh"):
        st.rerun()

# ── Router ────────────────────────────────────────────

if not st.session_state.logged_in:
    login_sayfasi()
else:
    sidebar_menu()
    page = st.session_state.page
    if   page == "detection":  tespit_sayfasi()
    elif page == "history":    gecmis_sayfasi()
    elif page == "statistics": istatistik_sayfasi()
