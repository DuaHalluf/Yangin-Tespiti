import streamlit as st
import cv2
import numpy as np
import tempfile
import os
import requests
from datetime import datetime
from ultralytics import YOLO
import psycopg2
import pandas as pd
import altair as alt

def db_baglan():
    return psycopg2.connect(
        dbname="yangin_db",
        user="duahallufedib",
        password="",
        host="localhost",
        port="5432"
    )

def db_kaydet(sinif, guven, kaynak, goruntu=None):
    try:
        conn = db_baglan()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tespitler (sinif, guven, kaynak, goruntu) VALUES (%s, %s, %s, %s)",
            (sinif, guven, kaynak, goruntu)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        pass

def kullanici_dogrula(email, sifre):
    try:
        conn = db_baglan()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, ad, email, rol FROM kullanicilar WHERE email = %s AND sifre = %s",
            (email, sifre)
        )
        kullanici = cur.fetchone()
        cur.close()
        conn.close()
        return kullanici
    except Exception as e:
        return None

def kullanici_kaydet(ad, email, sifre):
    try:
        conn = db_baglan()
        cur = conn.cursor()
        # تحقق إذا الإيميل موجود مسبقاً
        cur.execute("SELECT id FROM kullanicilar WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return "exists"
        cur.execute(
            "INSERT INTO kullanicilar (ad, email, sifre, rol) VALUES (%s, %s, %s, %s)",
            (ad, email, sifre, "kullanici")
        )
        conn.commit()
        cur.close()
        conn.close()
        return "ok"
    except Exception as e:
        return f"error: {e}"

# ===== AYARLAR =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'weights', 'best.pt')

TELEGRAM_TOKEN = "8516296044:AAF5k9Yc2nvAiJEhw5e6OObCHH5hjnz9v6A"
TELEGRAM_CHAT_ID = "7558334990"

# ===== SAYFA AYARI =====
st.set_page_config(
    page_title="Yangın ve Duman Tespiti",
    page_icon="🔥",
    layout="wide"
)

# ===== MODEL =====
@st.cache_resource
def load_model():
    return YOLO(MODEL_PATH)

model = load_model()

# ===== Session State =====
if "conf_threshold" not in st.session_state:
    st.session_state.conf_threshold = 0.45
if "iou_threshold" not in st.session_state:
    st.session_state.iou_threshold = 0.40
if "sis_filtre" not in st.session_state:
    st.session_state.sis_filtre = True
if "kullanici" not in st.session_state:
    st.session_state.kullanici = None
if "sayfa" not in st.session_state:
    st.session_state.sayfa = "giris"

# ===== SİS FİLTRESİ =====
def gercek_yangin_mi(img_bgr, box):
    x1, y1, x2, y2 = map(int, box.xyxy[0])
    roi = img_bgr[y1:y2, x1:x2]
    if roi.size == 0:
        return False
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lower1 = np.array([0, 50, 50])
    upper1 = np.array([35, 255, 255])
    lower2 = np.array([160, 50, 50])
    upper2 = np.array([180, 255, 255])
    mask1 = cv2.inRange(hsv, lower1, upper1)
    mask2 = cv2.inRange(hsv, lower2, upper2)
    mask = cv2.bitwise_or(mask1, mask2)
    fire_ratio = np.sum(mask > 0) / mask.size
    return fire_ratio > 0.10

def gercek_duman_mi(img_bgr, box):
    x1, y1, x2, y2 = map(int, box.xyxy[0])
    roi = img_bgr[y1:y2, x1:x2]
    if roi.size == 0:
        return False
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    ortalama_parlaklik = np.mean(gray)
    standart_sapma = np.std(gray)
    if ortalama_parlaklik > 220 and standart_sapma < 15:
        return False
    return True

# ===== TELEGRAM =====
def telegram_gonder(mesaj):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mesaj,
            "parse_mode": "HTML"
        }, timeout=5)
    except Exception:
        pass

# ===== ALARM SESİ =====
def alarm_ses():
    st.markdown("""
        <audio autoplay>
            <source src="https://www.soundjay.com/misc/sounds/fire-alarm-1.mp3" type="audio/mpeg">
        </audio>
    """, unsafe_allow_html=True)

# ===== LOGIN / KAYIT SAYFASI =====
if st.session_state.kullanici is None:
    st.markdown("""
        <div style='text-align:center; padding:40px 0 10px;'>
            <h1 style='color:#E74C3C; font-size:2.5em;'>🔥 Yangın ve Duman Tespiti</h1>
            <p style='color:gray;'>YOLOv8 Derin Öğrenme Modeli — Sakarya Üniversitesi</p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("---")

        # أزرار التبديل بين لوغن وتسجيل
        col_a, col_b = st.columns(2)
        if col_a.button("🔐 Giriş Yap", use_container_width=True):
            st.session_state.sayfa = "giris"
            st.rerun()
        if col_b.button("📝 Kayıt Ol", use_container_width=True):
            st.session_state.sayfa = "kayit"
            st.rerun()

        st.markdown("---")

        # ===== صفحة اللوغن =====
        if st.session_state.sayfa == "giris":
            st.markdown("### 🔐 Giriş Yap")

            email = st.text_input("📧 E-posta:", placeholder="email@example.com")
            sifre = st.text_input("🔑 Şifre:", type="password", placeholder="Şifrenizi girin")

            if st.button("Giriş Yap", type="primary", use_container_width=True):
                if not email or not sifre:
                    st.error("❌ Lütfen tüm alanları doldurun!")
                else:
                    kullanici = kullanici_dogrula(email, sifre)
                    if kullanici:
                        st.session_state.kullanici = {
                            "id": kullanici[0],
                            "ad": kullanici[1],
                            "email": kullanici[2],
                            "rol": kullanici[3]
                        }
                        st.session_state.sayfa = "giris"
                        st.rerun()
                    else:
                        st.error("❌ E-posta veya şifre hatalı!")

            st.markdown("---")
            st.markdown("""
                <p style='text-align:center; font-size:12px; color:gray;'>
                Hesabınız yok mu? Yukarıdan <b>Kayıt Ol</b> butonuna tıklayın.
                </p>
            """, unsafe_allow_html=True)

        # ===== صفحة التسجيل =====
        elif st.session_state.sayfa == "kayit":
            st.markdown("### 📝 Yeni Hesap Oluştur")

            yeni_ad = st.text_input("👤 Ad Soyad:", placeholder="Adınızı girin")
            yeni_email = st.text_input("📧 E-posta:", placeholder="email@example.com")
            yeni_sifre = st.text_input("🔑 Şifre:", type="password", placeholder="Şifre belirleyin")
            yeni_sifre2 = st.text_input("🔑 Şifre Tekrar:", type="password", placeholder="Şifreyi tekrar girin")

            if st.button("✅ Kayıt Ol", type="primary", use_container_width=True):
                if not yeni_ad or not yeni_email or not yeni_sifre or not yeni_sifre2:
                    st.error("❌ Lütfen tüm alanları doldurun!")
                elif yeni_sifre != yeni_sifre2:
                    st.error("❌ Şifreler eşleşmiyor!")
                elif len(yeni_sifre) < 3:
                    st.error("❌ Şifre en az 3 karakter olmalıdır!")
                else:
                    sonuc = kullanici_kaydet(yeni_ad, yeni_email, yeni_sifre)
                    if sonuc == "ok":
                        st.success("✅ Hesap oluşturuldu! Şimdi giriş yapabilirsiniz.")
                        st.session_state.sayfa = "giris"
                        st.rerun()
                    elif sonuc == "exists":
                        st.error("❌ Bu e-posta adresi zaten kayıtlı!")
                    else:
                        st.error(f"❌ Hata oluştu: {sonuc}")

            st.markdown("---")
            st.markdown("""
                <p style='text-align:center; font-size:12px; color:gray;'>
                Zaten hesabınız var mı? Yukarıdan <b>Giriş Yap</b> butonuna tıklayın.
                </p>
            """, unsafe_allow_html=True)

    st.markdown("""
        <p style='text-align:center; color:gray; font-size:12px; margin-top:2rem;'>
        Loubana ALMLHEM & Dua HALLUF EDİB · Danışman: Prof. Dr. Cemil ÖZ
        </p>
    """, unsafe_allow_html=True)

# ===== ANA SAYFA =====
else:
    kullanici = st.session_state.kullanici
    rol = kullanici["rol"]
    ad = kullanici["ad"]

    # Header
    if rol == "admin":
        st.markdown(f"""
            <h1 style='text-align:center; color:#E74C3C;'>
                🔥 Yangın ve Duman Tespiti
            </h1>
            <p style='text-align:center; background:#fff3cd; padding:8px; border-radius:8px; color:#856404;'>
                🔐 Admin olarak giriş yapıldı — <b>{ad}</b>
            </p>
            <hr>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
            <h1 style='text-align:center; color:#E74C3C;'>
                🔥 Yangın ve Duman Tespiti
            </h1>
            <p style='text-align:center; background:#d4edda; padding:8px; border-radius:8px; color:#155724;'>
                👤 Hoş geldiniz, <b>{ad}</b>
            </p>
            <hr>
        """, unsafe_allow_html=True)

    # ===== SIDEBAR =====
    st.sidebar.header("⚙️ Ayarlar")

    if rol == "admin":
        st.sidebar.success(f"🔐 Admin: {ad}")
    else:
        st.sidebar.info(f"👤 {ad}")

    conf_threshold = st.sidebar.slider("Güven Eşiği", 0.10, 1.0, st.session_state.conf_threshold, 0.05)
    iou_threshold = st.sidebar.slider("IoU Eşiği", 0.10, 1.0, st.session_state.iou_threshold, 0.05)
    sis_filtre = st.sidebar.checkbox("🌫️ Sis Filtresi Aktif", value=st.session_state.sis_filtre)
    telegram_aktif = st.sidebar.checkbox("📱 Telegram Bildirimi", value=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Hazırlayanlar:**")
    st.sidebar.markdown("Loubana ALMLHEM")
    st.sidebar.markdown("Dua HALLUF EDİB")
    st.sidebar.markdown("**Danışman:** Prof. Dr. Cemil ÖZ")

    if st.sidebar.button("🚪 Çıkış Yap"):
        st.session_state.kullanici = None
        st.session_state.sayfa = "giris"
        st.rerun()

    if "log" not in st.session_state:
        st.session_state.log = []

    if st.session_state.log:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📋 Son Tespitler")
        for kayit in st.session_state.log[-5:][::-1]:
            emoji = "🔥" if kayit["sinif"] == "fire" else "💨"
            st.sidebar.write(f"{emoji} {kayit['zaman']} — %{kayit['guven']:.1f}")

    # ===== TABS =====
    if rol == "admin":
        tab1, tab2, tab3 = st.tabs(["🔍 Tespit", "📊 İstatistikler", "🔐 Admin Panel"])
    else:
        tab1, tab2 = st.tabs(["🔍 Tespit", "📊 İstatistikler"])
        tab3 = None

    # ===== TAB 1: TESPİT =====
    with tab1:
        mod = st.selectbox("Tespit Modu:", ["📷 Fotoğraf", "🎥 Video", "📡 Canlı Kamera"])
        st.markdown("---")

        if mod == "📷 Fotoğraf":
            uploaded = st.file_uploader("Fotoğraf yükleyin", type=["jpg","jpeg","png"])

            if uploaded is not None:
                dosya_adi = uploaded.name
                if st.session_state.get("son_fotograf") != dosya_adi:
                    st.session_state["son_fotograf"] = dosya_adi
                    st.session_state["kayit_yapildi"] = False

            if uploaded:
                col1, col2 = st.columns(2)
                file_bytes = np.asarray(bytearray(uploaded.read()), dtype=np.uint8)
                img_bgr = cv2.imdecode(file_bytes, 1)
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

                with col1:
                    st.image(img_rgb, caption="📌 Yüklenen Fotoğraf", use_container_width=True)

                with st.spinner("🔍 Analiz ediliyor..."):
                    results = model.predict(
                        source=img_bgr,
                        conf=conf_threshold,
                        iou=iou_threshold,
                        verbose=False
                    )

                res_img = img_bgr.copy()
                boxes = results[0].boxes
                names = results[0].names

                yangin_var = False
                duman_var = False
                gosterilen_tespitler = []

                for box in boxes:
                    cls = int(box.cls)
                    conf_val = float(box.conf)
                    sinif = names[cls]

                    if sis_filtre:
                        if sinif == "fire" and not gercek_yangin_mi(img_bgr, box):
                            continue
                        if sinif == "smoke" and not gercek_duman_mi(img_bgr, box):
                            continue

                    gosterilen_tespitler.append((sinif, conf_val))

                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    renk = (0, 0, 255) if sinif == "fire" else (0, 255, 0)
                    cv2.rectangle(res_img, (x1, y1), (x2, y2), renk, 2)
                    cv2.putText(res_img, f"{sinif} {conf_val:.2f}",
                               (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, renk, 2)

                    if sinif == "fire":
                        yangin_var = True
                    elif sinif == "smoke":
                        duman_var = True

                if gosterilen_tespitler and not st.session_state.get("kayit_yapildi", False):
                    _, buf = cv2.imencode('.jpg', res_img)
                    img_bytes = buf.tobytes()
                    siniflar = ", ".join(sorted(set([s for s, c in gosterilen_tespitler])))
                    max_guven = max([c for s, c in gosterilen_tespitler]) * 100
                    db_kaydet(siniflar, max_guven, "fotograf", img_bytes)
                    st.session_state["kayit_yapildi"] = True

                res_rgb = cv2.cvtColor(res_img, cv2.COLOR_BGR2RGB)

                with col2:
                    st.image(res_rgb, caption="✅ Tespit Sonucu", use_container_width=True)

                st.markdown("### 📊 Tespit Sonuçları")

                if yangin_var:
                    alarm_ses()
                    st.error("🔥 YANGIN TESPİT EDİLDİ!")
                    zaman = datetime.now().strftime("%H:%M:%S")
                    if telegram_aktif:
                        telegram_gonder(f"🔥 YANGIN UYARISI!\nSaat: {zaman}")
                    for s, c in gosterilen_tespitler:
                        if s == "fire":
                            st.session_state.log.append({"sinif": s, "guven": c*100, "zaman": zaman})

                if duman_var:
                    st.warning("💨 DUMAN TESPİT EDİLDİ!")
                    zaman = datetime.now().strftime("%H:%M:%S")
                    for s, c in gosterilen_tespitler:
                        if s == "smoke":
                            st.session_state.log.append({"sinif": s, "guven": c*100, "zaman": zaman})

                if not yangin_var and not duman_var:
                    if sis_filtre and len(boxes) > 0:
                        st.info("🌫️ Sis filtresi devrede — yanlış tespit engellendi.")
                    else:
                        st.success("✅ Yangın veya duman tespit edilmedi.")

        elif mod == "🎥 Video":
            video_file = st.file_uploader("Video yükleyin", type=["mp4","avi","mov"])
            if video_file:
                tfile = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                tfile.write(video_file.read())
                tfile.close()

                cap = cv2.VideoCapture(tfile.name)
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                st.info(f"📹 {frame_count} kare | {fps:.1f} FPS")

                stframe = st.empty()
                progress = st.progress(0)
                alert_box = st.empty()
                stop_btn = st.button("⏹ Durdur")

                frame_num = 0
                while cap.isOpened() and not stop_btn:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame_num += 1
                    if frame_num % 3 != 0:
                        continue

                    results = model.predict(
                        source=frame,
                        conf=conf_threshold,
                        iou=iou_threshold,
                        verbose=False
                    )

                    res_frame = frame.copy()
                    for box in results[0].boxes:
                        cls = int(box.cls)
                        conf_val = float(box.conf)
                        sinif = results[0].names[cls]

                        if sis_filtre:
                            if sinif == "fire" and not gercek_yangin_mi(frame, box):
                                continue
                            if sinif == "smoke" and not gercek_duman_mi(frame, box):
                                continue

                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        renk = (0, 0, 255) if sinif == "fire" else (0, 255, 0)
                        cv2.rectangle(res_frame, (x1, y1), (x2, y2), renk, 2)
                        cv2.putText(res_frame, f"{sinif} {conf_val:.2f}",
                                   (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, renk, 2)

                        if sinif == "fire" and conf_val > 0.75:
                            alert_box.error(f"🔥 YANGIN! Güven: %{conf_val*100:.1f}")
                            if telegram_aktif:
                                telegram_gonder(f"🔥 Video'da YANGIN tespit edildi!\nGüven: %{conf_val*100:.1f}")
                            _, buf = cv2.imencode('.jpg', res_frame)
                            db_kaydet(sinif, conf_val*100, "video", buf.tobytes())

                    stframe.image(
                        cv2.cvtColor(res_frame, cv2.COLOR_BGR2RGB),
                        caption=f"Kare: {frame_num}",
                        use_container_width=True
                    )
                    progress.progress(min(frame_num / max(frame_count, 1), 1.0))

                cap.release()
                os.unlink(tfile.name)
                st.success("✅ Video analizi tamamlandı!")

        elif mod == "📡 Canlı Kamera":
            st.info("📡 Bilgisayar kamerası kullanılacak.")
            col1, col2 = st.columns(2)
            start = col1.button("▶️ Başlat", type="primary")
            stop_flag = col2.button("⏹ Durdur")

            if start:
                cap = cv2.VideoCapture(0)
                if not cap.isOpened():
                    st.error("❌ Kamera açılamadı!")
                else:
                    stframe = st.empty()
                    alert_box = st.empty()

                    while True:
                        ret, frame = cap.read()
                        if not ret or stop_flag:
                            break

                        results = model.predict(
                            source=frame,
                            conf=conf_threshold,
                            iou=iou_threshold,
                            verbose=False
                        )

                        res_frame = frame.copy()
                        for box in results[0].boxes:
                            cls = int(box.cls)
                            conf_val = float(box.conf)
                            sinif = results[0].names[cls]

                            if sis_filtre:
                                if sinif == "fire" and not gercek_yangin_mi(frame, box):
                                    continue
                                if sinif == "smoke" and not gercek_duman_mi(frame, box):
                                    continue

                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            renk = (0, 0, 255) if sinif == "fire" else (0, 255, 0)
                            cv2.rectangle(res_frame, (x1, y1), (x2, y2), renk, 2)
                            cv2.putText(res_frame, f"{sinif} {conf_val:.2f}",
                                       (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, renk, 2)

                            if sinif == "fire" and conf_val > 0.50:
                                alert_box.error(f"🚨 YANGIN! Güven: %{conf_val*100:.1f}")
                                if telegram_aktif:
                                    telegram_gonder("🚨 Canlı kamerada YANGIN tespit edildi!")
                                _, buf = cv2.imencode('.jpg', res_frame)
                                db_kaydet(sinif, conf_val*100, "kamera", buf.tobytes())

                        stframe.image(
                            cv2.cvtColor(res_frame, cv2.COLOR_BGR2RGB),
                            caption="📡 Canlı",
                            use_container_width=True
                        )

                    cap.release()
                    st.success("Kamera kapatıldı.")

    # ===== TAB 2: İSTATİSTİKLER =====
    with tab2:
        st.markdown("### 📊 Tespit İstatistikleri")

        try:
            conn = db_baglan()
            cur = conn.cursor()
            cur.execute("SELECT id, sinif, guven, tarih, kaynak FROM tespitler ORDER BY tarih DESC")
            rows = cur.fetchall()

            if rows:
                df = pd.DataFrame(rows, columns=["ID", "Tespitler", "Maks Güven", "Tarih", "Kaynak"])

                toplam = len(df)
                yangin_say = df[df["Tespitler"].str.contains("fire", na=False)].shape[0]
                duman_say = df[df["Tespitler"].str.contains("smoke", na=False)].shape[0]

                col1, col2, col3 = st.columns(3)
                col1.metric("🔢 Toplam Analiz", toplam)
                col2.metric("🔥 Yangın İçeren", yangin_say)
                col3.metric("💨 Duman İçeren", duman_say)

                st.markdown("---")

                st.markdown("### 🔎 Filtrele")
                filtre_col1, filtre_col2 = st.columns(2)
                sinif_filtre = filtre_col1.selectbox("Tespit Türü:", ["Tümü", "fire", "smoke"])
                kaynak_filtre = filtre_col2.selectbox("Kaynak:", ["Tümü", "fotograf", "video", "kamera", "api"])

                df_filtre = df.copy()
                if sinif_filtre != "Tümü":
                    df_filtre = df_filtre[df_filtre["Tespitler"].str.contains(sinif_filtre, na=False)]
                if kaynak_filtre != "Tümü":
                    df_filtre = df_filtre[df_filtre["Kaynak"] == kaynak_filtre]

                st.markdown("---")

                chart_data = pd.DataFrame({
                    "Tür": ["🔥 Yangın", "💨 Duman"],
                    "Sayı": [yangin_say, duman_say]
                })
                chart = alt.Chart(chart_data).mark_bar().encode(
                    x="Tür",
                    y="Sayı",
                    color=alt.Color("Tür", scale=alt.Scale(range=["#aec7e8", "#1f77b4"]))
                )
                st.altair_chart(chart, use_container_width=True)

                st.markdown("### 📋 Tespit Geçmişi")
                tablo_col, goruntu_col = st.columns([1, 1])

                with tablo_col:
                    st.dataframe(df_filtre, use_container_width=True, hide_index=True)

                id_listesi = df_filtre["ID"].tolist()

                with goruntu_col:
                    st.markdown("#### 🖼️ Tespit Görüntüsü")
                    if id_listesi:
                        secilen_id = st.selectbox("🔍 ID seçin:", id_listesi, key="goruntu_sec")
                        cur2 = conn.cursor()
                        cur2.execute(
                            "SELECT sinif, guven, tarih, goruntu FROM tespitler WHERE id = %s",
                            (int(secilen_id),)
                        )
                        row = cur2.fetchone()
                        if row and row[3]:
                            sinif, guven, tarih, goruntu_bytes = row
                            nparr = np.frombuffer(bytes(goruntu_bytes), np.uint8)
                            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            st.image(img_rgb, caption=f"🔍 {sinif} — %{guven:.1f} — {tarih}", use_container_width=True)
                        else:
                            st.info("Bu kayıt için görüntü bulunamadı.")
                        cur2.close()
                    else:
                        st.info("👈 Soldan filtre uygulayın.")

            else:
                st.info("Henüz tespit kaydı yok.")

            cur.close()
            conn.close()
        except Exception as e:
            st.error(f"Veritabanı hatası: {e}")

    # ===== TAB 3: ADMIN PANEL =====
    if rol == "admin" and tab3 is not None:
        with tab3:
            st.markdown("### 🔐 Admin Panel")
            st.success(f"✅ Admin olarak giriş yapıldı: {ad}")
            st.markdown("---")

            # إعدادات النموذج
            st.markdown("### ⚙️ Model Ayarları")
            yeni_conf = st.slider("Güven Eşiği:", 0.10, 1.0, st.session_state.conf_threshold, 0.05, key="admin_conf")
            yeni_iou = st.slider("IoU Eşiği:", 0.10, 1.0, st.session_state.iou_threshold, 0.05, key="admin_iou")
            yeni_sis = st.checkbox("🌫️ Sis Filtresi Aktif", value=st.session_state.sis_filtre, key="admin_sis")

            if st.button("💾 Ayarları Kaydet", type="primary"):
                st.session_state.conf_threshold = yeni_conf
                st.session_state.iou_threshold = yeni_iou
                st.session_state.sis_filtre = yeni_sis
                st.success("✅ Ayarlar kaydedildi!")

            st.markdown("---")

            # إدارة المستخدمين
            st.markdown("### 👥 Kullanıcı Yönetimi")
            try:
                conn2 = db_baglan()
                cur2 = conn2.cursor()
                cur2.execute("SELECT id, ad, email, rol FROM kullanicilar ORDER BY id")
                kullanicilar = cur2.fetchall()
                df_kul = pd.DataFrame(kullanicilar, columns=["ID", "Ad", "E-posta", "Rol"])
                st.dataframe(df_kul, use_container_width=True, hide_index=True)
                cur2.close()
                conn2.close()
            except Exception as e:
                st.error(f"Hata: {e}")

            st.markdown("---")

            # عرض كل البيانات
            st.markdown("### 📋 Tüm Kayıtlar")
            try:
                conn = db_baglan()
                cur = conn.cursor()
                cur.execute("SELECT id, sinif, guven, tarih, kaynak FROM tespitler ORDER BY tarih DESC")
                rows = cur.fetchall()

                if rows:
                    df_admin = pd.DataFrame(rows, columns=["ID", "Tespitler", "Maks Güven", "Tarih", "Kaynak"])
                    st.dataframe(df_admin, use_container_width=True, hide_index=True)
                    st.info(f"Toplam {len(df_admin)} kayıt")
                else:
                    st.info("Henüz kayıt yok.")

                st.markdown("---")

                # حذف بالـ ID
                st.markdown("### 🗑️ ID'ye Göre Sil")
                if rows:
                    id_listesi = [row[0] for row in rows]
                    sil_col1, sil_col2 = st.columns([2, 1])
                    with sil_col1:
                        silinecek_id = st.selectbox("Silinecek ID:", id_listesi, key="admin_sil_id")
                    with sil_col2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🗑️ Sil", type="primary", key="admin_sil_btn"):
                            cur2 = conn.cursor()
                            cur2.execute("DELETE FROM tespitler WHERE id = %s", (int(silinecek_id),))
                            conn.commit()
                            cur2.close()
                            st.success(f"✅ ID {silinecek_id} silindi!")
                            st.rerun()

                st.markdown("---")

                # حذف الكل
                st.markdown("### 🗑️ Tüm Kayıtları Sil")
                st.error("⚠️ Bu işlem geri alınamaz!")
                if st.button("🗑️ Tüm Kayıtları Sil", type="primary"):
                    cur3 = conn.cursor()
                    cur3.execute("DELETE FROM tespitler")
                    conn.commit()
                    cur3.close()
                    st.success("✅ Tüm kayıtlar silindi!")
                    st.rerun()

                cur.close()
                conn.close()

            except Exception as e:
                st.error(f"Hata: {e}")