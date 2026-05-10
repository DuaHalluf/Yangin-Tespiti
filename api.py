from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from flask_httpauth import HTTPTokenAuth
from ultralytics import YOLO
import cv2
import numpy as np
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)
auth = HTTPTokenAuth(scheme='Bearer')

# ===== API KEYS =====
API_KEYS = {
    "yangin-api-key-2026": "admin",
    "doktor-demo-key": "demo"
}

@auth.verify_token
def verify_token(token):
    if token in API_KEYS:
        return API_KEYS[token]
    return None

@auth.error_handler
def auth_error(status):
    return jsonify({
        "error": "Geçersiz veya eksik API anahtarı",
        "mesaj": "Lütfen geçerli bir Bearer token ile tekrar deneyin"
    }), 401

# ===== VERİ DOĞRULAMA =====
IZIN_VERILEN_UZANTILAR = {"jpg", "jpeg", "png"}
MAKS_DOSYA_BOYUTU = 10 * 1024 * 1024  # 10 MB

def dosya_uzantisi_kontrol(dosya_adi):
    return '.' in dosya_adi and \
           dosya_adi.rsplit('.', 1)[1].lower() in IZIN_VERILEN_UZANTILAR

def dosya_boyutu_kontrol(dosya):
    dosya.seek(0, 2)
    boyut = dosya.tell()
    dosya.seek(0)
    return boyut <= MAKS_DOSYA_BOYUTU

def goruntu_gecerli_mi(file_bytes):
    img = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    return img is not None

# ===== SWAGGER =====
SWAGGER_URL = '/docs'
API_URL = '/swagger.json'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Yangın Tespiti API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

@app.route('/swagger.json')
def swagger_json():
    return jsonify({
        "openapi": "3.0.0",
        "info": {
            "title": "🔥 Yangın ve Duman Tespiti API",
            "description": "YOLOv8 tabanlı gerçek zamanlı yangın tespiti REST API — Sakarya Üniversitesi Bitirme Projesi",
            "version": "1.0.0"
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer"
                }
            }
        },
        "security": [{"BearerAuth": []}],
        "paths": {
            "/detect": {
                "post": {
                    "summary": "Görüntüde yangın/duman tespiti yap",
                    "description": "Yüklenen görüntüyü YOLOv8 modeli ile analiz eder. Sadece jpg, jpeg, png formatları kabul edilir. Maksimum dosya boyutu 10MB.",
                    "security": [{"BearerAuth": []}],
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "image": {
                                            "type": "string",
                                            "format": "binary",
                                            "description": "Analiz edilecek görüntü (jpg, jpeg, png — maks 10MB)"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "Tespit sonuçları başarıyla döndürüldü"},
                        "400": {"description": "Geçersiz dosya formatı veya boyutu"},
                        "401": {"description": "Geçersiz API anahtarı"}
                    }
                }
            },
            "/history": {
                "get": {
                    "summary": "Tespit kayıtlarını getir (filtreleme destekli)",
                    "description": "Veritabanındaki tespit kayıtlarını getirir. sinif, kaynak ve tarih parametreleriyle filtrelenebilir.",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "sinif",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "enum": ["fire", "smoke"]},
                            "description": "Tespit türüne göre filtrele (fire veya smoke)"
                        },
                        {
                            "name": "kaynak",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "enum": ["fotograf", "video", "kamera", "api"]},
                            "description": "Kaynağa göre filtrele"
                        },
                        {
                            "name": "tarih",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "example": "2026-05-10"},
                            "description": "Tarihe göre filtrele (YYYY-MM-DD formatında)"
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 20},
                            "description": "Maksimum kayıt sayısı (varsayılan: 20)"
                        }
                    ],
                    "responses": {
                        "200": {"description": "Kayıtlar başarıyla döndürüldü"},
                        "401": {"description": "Geçersiz API anahtarı"}
                    }
                }
            },
            "/stats": {
                "get": {
                    "summary": "İstatistikleri getir (kaynağa göre filtrelenebilir)",
                    "description": "Genel tespit istatistiklerini döndürür. kaynak parametresiyle filtrelenebilir.",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "kaynak",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "enum": ["fotograf", "video", "kamera", "api"]},
                            "description": "Kaynağa göre istatistik filtrele"
                        }
                    ],
                    "responses": {
                        "200": {"description": "İstatistikler başarıyla döndürüldü"},
                        "401": {"description": "Geçersiz API anahtarı"}
                    }
                }
            },
            "/delete/{id}": {
                "delete": {
                    "summary": "Belirli bir kaydı sil (Sadece Admin)",
                    "security": [{"BearerAuth": []}],
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                            "description": "Silinecek kaydın ID'si"
                        }
                    ],
                    "responses": {
                        "200": {"description": "Kayıt başarıyla silindi"},
                        "401": {"description": "Geçersiz API anahtarı"},
                        "403": {"description": "Admin yetkisi gereklidir"},
                        "404": {"description": "Kayıt bulunamadı"}
                    }
                }
            },
            "/delete/all": {
                "delete": {
                    "summary": "Tüm kayıtları sil (Sadece Admin)",
                    "security": [{"BearerAuth": []}],
                    "responses": {
                        "200": {"description": "Tüm kayıtlar silindi"},
                        "401": {"description": "Geçersiz API anahtarı"},
                        "403": {"description": "Admin yetkisi gereklidir"}
                    }
                }
            }
        }
    })

# ===== MODEL =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'weights', 'best.pt')
model = YOLO(MODEL_PATH)

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

# ===== POST /detect =====
@app.route('/detect', methods=['POST'])
@auth.login_required
def detect():
    if 'image' not in request.files:
        return jsonify({
            "error": "Dosya bulunamadı",
            "mesaj": "Lütfen 'image' anahtarıyla bir dosya gönderin"
        }), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({
            "error": "Dosya adı boş",
            "mesaj": "Lütfen geçerli bir dosya seçin"
        }), 400

    if not dosya_uzantisi_kontrol(file.filename):
        return jsonify({
            "error": "Geçersiz dosya formatı",
            "mesaj": f"Sadece şu formatlar kabul edilir: {', '.join(IZIN_VERILEN_UZANTILAR)}",
            "gonderilen_format": file.filename.rsplit('.', 1)[-1] if '.' in file.filename else "bilinmiyor"
        }), 400

    if not dosya_boyutu_kontrol(file):
        return jsonify({
            "error": "Dosya boyutu çok büyük",
            "mesaj": "Maksimum dosya boyutu 10MB'dir"
        }), 400

    file_bytes = file.read()
    if not goruntu_gecerli_mi(file_bytes):
        return jsonify({
            "error": "Geçersiz görüntü",
            "mesaj": "Dosya açılamadı veya bozuk bir görüntü dosyası"
        }), 400

    img = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    results = model.predict(source=img, conf=0.45, iou=0.40, verbose=False)
    boxes = results[0].boxes
    names = results[0].names

    tespitler = []
    for box in boxes:
        cls = int(box.cls)
        conf = float(box.conf)
        sinif = names[cls]
        tespitler.append({
            "sinif": sinif,
            "guven": round(conf * 100, 2)
        })

    if tespitler:
        siniflar = ", ".join(sorted(set([t["sinif"] for t in tespitler])))
        max_guven = max([t["guven"] for t in tespitler])
        _, buf = cv2.imencode('.jpg', img)
        db_kaydet(siniflar, max_guven, "api", buf.tobytes())

    return jsonify({
        "tespit_sayisi": len(tespitler),
        "tespitler": tespitler,
        "zaman": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kullanici": auth.current_user(),
        "dosya_adi": file.filename
    })

# ===== GET /history (با فلترة) =====
@app.route('/history', methods=['GET'])
@auth.login_required
def history():
    try:
        # قراءة الفلاتر من الـ URL
        sinif  = request.args.get('sinif')   # fire أو smoke
        kaynak = request.args.get('kaynak')  # fotograf, video, kamera, api
        tarih  = request.args.get('tarih')   # 2026-05-10
        limit  = request.args.get('limit', 20)

        try:
            limit = int(limit)
            if limit <= 0 or limit > 1000:
                limit = 20
        except:
            limit = 20

        # بناء الـ query بشكل ديناميكي
        query = "SELECT id, sinif, guven, tarih, kaynak FROM tespitler WHERE 1=1"
        params = []

        if sinif:
            query += " AND sinif LIKE %s"
            params.append(f"%{sinif}%")

        if kaynak:
            query += " AND kaynak = %s"
            params.append(kaynak)

        if tarih:
            query += " AND DATE(tarih) = %s"
            params.append(tarih)

        query += " ORDER BY tarih DESC LIMIT %s"
        params.append(limit)

        conn = db_baglan()
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        conn.close()

        data = []
        for row in rows:
            data.append({
                "id":     row[0],
                "sinif":  row[1],
                "guven":  row[2],
                "tarih":  str(row[3]),
                "kaynak": row[4]
            })

        # إرجاع النتيجة مع معلومات الفلترة
        return jsonify({
            "kayitlar": data,
            "toplam": len(data),
            "filtreler": {
                "sinif":  sinif  or "tümü",
                "kaynak": kaynak or "tümü",
                "tarih":  tarih  or "tümü",
                "limit":  limit
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== GET /stats (با فلترة بالمصدر) =====
@app.route('/stats', methods=['GET'])
@auth.login_required
def stats():
    try:
        kaynak = request.args.get('kaynak')

        conn = db_baglan()
        cur = conn.cursor()

        if kaynak:
            cur.execute("SELECT COUNT(*) FROM tespitler WHERE kaynak = %s", (kaynak,))
            toplam = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM tespitler WHERE sinif LIKE %s AND kaynak = %s", ('%fire%', kaynak))
            yangin = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM tespitler WHERE sinif LIKE %s AND kaynak = %s", ('%smoke%', kaynak))
            duman = cur.fetchone()[0]
        else:
            cur.execute("SELECT COUNT(*) FROM tespitler")
            toplam = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM tespitler WHERE sinif LIKE %s", ('%fire%',))
            yangin = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM tespitler WHERE sinif LIKE %s", ('%smoke%',))
            duman = cur.fetchone()[0]

        cur.close()
        conn.close()

        return jsonify({
            "toplam_tespit": toplam,
            "yangin": yangin,
            "duman": duman,
            "filtre_kaynak": kaynak or "tümü"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ===== DELETE /delete/all =====
@app.route('/delete/all', methods=['DELETE'])
@auth.login_required
def delete_all():
    if auth.current_user() != "admin":
        return jsonify({
            "error": "Yetkisiz erişim",
            "mesaj": "Bu işlem için admin yetkisi gereklidir"
        }), 403

    try:
        conn = db_baglan()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tespitler")
        sayi = cur.fetchone()[0]
        cur.execute("DELETE FROM tespitler")
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "mesaj": "Tüm kayıtlar silindi",
            "silinen_kayit_sayisi": sayi
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ===== DELETE /delete/<id> =====
@app.route('/delete/<int:id>', methods=['DELETE'])
@auth.login_required
def delete_by_id(id):
    if auth.current_user() != "admin":
        return jsonify({
            "error": "Yetkisiz erişim",
            "mesaj": "Bu işlem için admin yetkisi gereklidir"
        }), 403

    try:
        conn = db_baglan()
        cur = conn.cursor()
        cur.execute("SELECT id FROM tespitler WHERE id = %s", (id,))
        kayit = cur.fetchone()

        if not kayit:
            return jsonify({"error": f"ID {id} bulunamadı"}), 404

        cur.execute("DELETE FROM tespitler WHERE id = %s", (id,))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"mesaj": f"ID {id} başarıyla silindi"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("🔑 API Anahtarları:")
    print("   Admin : yangin-api-key-2026")
    print("   Demo  : doktor-demo-key")
    print("=" * 50)
    print("🔒 Yetkiler:")
    print("   Admin : detect, history, stats, delete")
    print("   Demo  : detect, history, stats (silme yok)")
    print("=" * 50)
    print("✅ Filtreleme:")
    print("   /history?sinif=fire")
    print("   /history?kaynak=kamera")
    print("   /history?tarih=2026-05-10")
    print("   /history?limit=50")
    print("   /stats?kaynak=api")
    print("=" * 50)
    app.run(debug=True, port=5050)