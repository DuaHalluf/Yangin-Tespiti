[README .md](https://github.com/user-attachments/files/33348981/README.md)
# 🔥 FireWatch

YOLOv8n tabanlı, gerçek zamanlı **yangın ve duman tespit sistemi**. Fotoğraf, video ve canlı kamera görüntüsünü analiz eder; güven skoru %70 ve üzerindeki tespitlerde **Telegram** üzerinden anlık bildirim gönderir.

> Sakarya Üniversitesi, Bilgisayar Mühendisliği — BSM 498 Bitirme Çalışması (2025–2026)


##  Özellikler

- **Üç analiz modu:** Fotoğraf, video ve canlı kamera
- **Çift sınıf tespiti:** `fire` ve `smoke`; sınırlayıcı kutu ve güven skoru ile görselleştirme
- **Anlık bildirim:** Güven skoru ≥ %70 olan tespitlerde Telegram uyarısı
- **Kamera ID ve konum bilgisi:** Tespitler hangi kamera ve konumdan geldiğiyle ilişkilendirilir
- **Tespit geçmişi ve istatistikler:** SQLite'ta saklama, filtreleme ve CSV dışa aktarma
- **Kullanıcı yönetimi:** Kayıt/giriş sistemi, SHA-256 ile hashlenmiş parolalar
- **REST API:** FastAPI ile modüler backend, otomatik Swagger dokümantasyonu

##  Teknolojiler

**Model:** YOLOv8n (Ultralytics), PyTorch, OpenCV
**Backend:** FastAPI, SQLAlchemy, SQLite
**Frontend:** Streamlit
**Bildirim:** Telegram Bot API
**Eğitim:** Kaggle, Tesla T4 GPU

##  Sonuçlar

- **Veri seti:** 21.527 görüntü (14.122 eğitim / 3.099 doğrulama / 4.306 test)
- **Başarım:** mAP50 **%76,8** — 50 epoch, Tesla T4 üzerinde yaklaşık 4 saat 51 dakika
- **Model seçimi:** YOLOv8n ve YOLO11n aynı koşullarda eğitilip karşılaştırıldı. YOLOv8n, duman tespitinde 114 fazla True Positive (1.527 – 1.413) ve daha yüksek güven skorlarıyla öne çıktı.
- **Gerçek testler:** Video analizinde 1560. karede 76, canlı kamerada 3420. karede 43 tespit; Telegram bildirimleri %76–%81 güven skoruyla iletildi.

##  Kurulum ve Çalıştırma

```bash
git clone [https://github.com/DuaHalluf/Yangin-Tespiti.git](https://github.com/DuaHalluf/Yangin-Tespiti.git)
cd Yangin-Tespiti
pip install -r requirements.txt
```

**Backend (FastAPI):**
```bash
cd backend
uvicorn main:app --reload
```

**Frontend (Streamlit)** — yeni bir terminalde:
```bash
cd frontend
streamlit run app.py
```

Arayüz `http://localhost:8501` adresinde açılır. API dokümantasyonu: `http://localhost:8000/docs`


##  Geliştiriciler

**Loubana Almlhem** — loubana.almlhem@ogr.sakarya.edu.tr
**Dua Halluf Edib** — dua.edib@ogr.sakarya.edu.tr

Danışman: Prof. Dr. Cemil ÖZ
