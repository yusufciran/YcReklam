# -*- coding: utf-8 -*-
"""
Sokaktan Dijitale - Yönetim Paneli Sunucusu (app.py)
======================================================
Flask standart klasör yapısı:
    app.py
    templates/   -> tüm .html sayfalar + admin.html (admin paneli)
    static/       -> css/, js/, images/, uploads/ (yüklenen görseller)
    admin_data/   -> yedekler (_yedekler/) ve site-config.json (web'den erişilemez)

Panel adresi:  http://127.0.0.1:5000/admin
Site adresi:   http://127.0.0.1:5000/

LOCALDE ÇALIŞTIRMA:
    pip install -r requirements.txt
    python app.py
    Panel adresi:  http://127.0.0.1:5000/admin
    Site adresi:   http://127.0.0.1:5000/

HOSTING'DE (CANLI) ÇALIŞTIRMA:
    Bu dosya kendi kendine "canlı ortamdayım" olduğunu, hosting'in verdiği
    PORT ortam değişkeninden anlar; ayrıca kod değişikliği gerekmez.
    Çoğu hosting sağlayıcısı (Render, Railway, PythonAnywhere, kendi
    VPS'iniz vb.) gunicorn gibi bir WSGI sunucusu ister, "python app.py"
    değil. Başlatma komutu genelde şöyle olur:
        gunicorn app:app --bind 0.0.0.0:$PORT
    (gunicorn requirements.txt içine eklendi.)

Varsayılan şifre: "sokaktan2026"
Şifreyi değiştirmek için ortam değişkeni kullanın:
    Windows (PowerShell):  $env:ADMIN_SIFRE="yeniSifreniz"
    Mac/Linux:              export ADMIN_SIFRE="yeniSifreniz"

Hosting'de mutlaka ayarlamanız önerilen ortam değişkenleri:
    ADMIN_SIFRE     -> admin paneli şifresi (ayarlamazsanız varsayılan kalır!)
    GIZLI_ANAHTAR   -> oturum (session) imzalama anahtarı; ayarlamazsanız
                       admin_data/.secret_key dosyasına yazılır. Bazı hosting
                       servislerinde disk her deploy'da sıfırlanır; bu da
                       her deploy sonrası oturumların düşmesine yol açar.
                       Sabit, rastgele uzun bir metin atayarak bunu önleyin.
"""

import os
import re
import io
import json
import glob
import time
import shutil
import secrets
import datetime
import uuid
import sqlite3
import hashlib
from functools import wraps
from collections import defaultdict

from flask import Flask, request, jsonify, session, send_from_directory, render_template, abort, Response, redirect
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from bs4 import BeautifulSoup, NavigableString, Comment
from PIL import Image

# ----------------------------------------------------------------------
# TEMEL AYARLAR
# ----------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Düzenlenebilir HTML sayfaları artık templates/ içinde tutulur.
# Görsel/CSS/JS statik dosyalar static/ altında, Flask'in varsayılan
# "/static/<path>" rotasıyla otomatik olarak sunulur.
UPLOADS_DIR = os.path.join(STATIC_DIR, "uploads")

# Portfolyo'da "canlı demo" olarak gösterilecek, müşteriye ait tam site
# projelerinin konduğu kök klasör. Her alt klasör bağımsız bir demo sitesidir
# ve içinde kendi index.html'i (ve varsa kendi css/js/görselleri) bulunur.
# Örn:  demo-siteler/kafe-sitesi/index.html  ->  /demo-siteler/kafe-sitesi/
DEMO_SITES_DIR = os.path.join(BASE_DIR, "demo-siteler")

# Yedekler ve site ayarları (site-config.json) web üzerinden ERİŞİLEMEYEN
# ayrı bir klasörde tutulur (templates/static dışında -> dışarıdan indirilemez).
ADMIN_DATA_DIR = os.path.join(BASE_DIR, "admin_data")
BACKUP_DIR = os.path.join(ADMIN_DATA_DIR, "_yedekler")
CONFIG_PATH = os.path.join(ADMIN_DATA_DIR, "site-config.json")

# Telefon, adres, e-posta, sosyal medya gibi TÜM sayfalarda tekrar eden statik
# bilgiler artık ayrı bir "settings.json" dosyasında, tek bir merkezden
# yönetilir. Bu dosya da (site-config.json gibi) admin_data/ altında,
# web üzerinden ERİŞİLEMEYEN bir konumda tutulur.
SETTINGS_PATH = os.path.join(ADMIN_DATA_DIR, "settings.json")

# Trafik/ziyaretçi analiz verileri (kaç kez girildi, hangi sayfada ne kadar
# durundu, kaç farklı kişi, hangi ziyaretler Meta/Facebook-Instagram reklamından
# geldi vb.) admin_data/ altında, web'den ERİŞİLEMEYEN bir SQLite dosyasında
# tutulur.
ANALYTICS_DB_PATH = os.path.join(ADMIN_DATA_DIR, "analytics.db")

# Bir ziyaretin "Meta reklamı" sayılması için bakılan utm_source değerleri
# (Facebook/Instagram reklam yöneticisinden gelen linkler genelde bunlardan
# birini taşır) - fbclid parametresinin varlığı da tek başına yeterli sayılır.
META_UTM_SOURCES = {"facebook", "instagram", "meta", "fb", "ig", "messenger"}
GOOGLE_UTM_SOURCES = {"google", "googleads", "adwords"}

# Ziyaret süresi (saniye) olarak kabul edilecek makul üst sınır; istemciden
# gelen hatalı/kötü niyetli değerlerin istatistikleri bozmasını engeller.
MAX_TRACK_DURATION_SECONDS = 6 * 60 * 60  # 6 saat

# İletişim formu e-posta adresini tam olarak doğrulamak için kullanılan
# RFC 5322'nin sadeleştirilmiş ama sıkı bir alt kümesi.
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")

CONTACT_SERVICE_LABELS = {
    "web": "Web Tasarım & Yazılım",
    "tabela": "Işıklı/Işıksız Tabela Üretimi",
    "cephe": "Kompozit Cephe Kaplama",
    "kimlik": "Kurumsal Kimlik & Kartvizit Baskı",
    "diger": "Komple Danışmanlık / Diğer",
}

# Varsayılan / ilk kurulum değerleri (mevcut site içeriğiyle birebir aynı,
# böylece settings.json henüz oluşturulmamışken bile site eskisi gibi görünür).
DEFAULT_SETTINGS = {
    "site_domain": "sokaktandijitale.com",  # www. ve https:// OLMADAN, sadece alan adı (ör. siteniz.com)
    "lucide_version": "latest",             # unpkg.com/lucide@<bu deger> - sabit bir sürüm için ör. "0.469.0"
    "phone": "+90 (555) 123 45 67",       # Görünen telefon numarası
    "whatsapp": "905551234567",           # wa.me linki için ülke kodlu, boşluksuz numara
    "email": "hello@sokaktandijitale.com",
    "address_line1": "Osmangazi Cad. Reklam Sk. No: 42",
    "address_line2": "Bursa, Türkiye",
    "city": "Bursa",
    "maps_url": "https://www.google.com/maps/search/?api=1&query=Osmangazi+Cad.+Reklam+Sk.+No:42+Bursa",
    "maps_embed_url": "",                 # Google Haritalar "Yerleştir" (embed) iframe adresi - admin panelinden yapıştırılan <iframe> kodundan otomatik çıkarılır
    "instagram_url": "https://instagram.com/sokaktandijitale",
    "instagram_handle": "sokaktandijitale",
    "facebook_url": "",
    "linkedin_url": "",
    "twitter_url": "",
    "youtube_url": "",
}

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(DEMO_SITES_DIR, exist_ok=True)

ADMIN_PASSWORD = os.environ.get("ADMIN_SIFRE", "sokaktan2026")


def get_or_create_secret_key():
    """Sabit bir GIZLI_ANAHTAR döndürür.

    Öncelik sırası:
      1) GIZLI_ANAHTAR ortam değişkeni (üretimde önerilen yöntem)
      2) admin_data/.secret_key dosyasında daha önce üretilmiş anahtar
      3) Hiçbiri yoksa yeni bir anahtar üretilir ve dosyaya yazılır,
         böylece sunucu yeniden başladığında oturumlar geçersiz olmaz.
    """
    env_key = os.environ.get("GIZLI_ANAHTAR")
    if env_key:
        return env_key

    key_file = os.path.join(ADMIN_DATA_DIR, ".secret_key")
    if os.path.isfile(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                saved_key = f.read().strip()
            if saved_key:
                return saved_key
        except Exception:
            pass

    new_key = secrets.token_hex(32)
    try:
        os.makedirs(ADMIN_DATA_DIR, exist_ok=True)
        with open(key_file, "w", encoding="utf-8") as f:
            f.write(new_key)
        try:
            os.chmod(key_file, 0o600)
        except Exception:
            pass
    except Exception:
        pass
    return new_key


# ----------------------------------------------------------------------
# ORTAM ALGILAMA (localde "python app.py" ile / hosting'de gunicorn ile)
# ----------------------------------------------------------------------
# Barındırma (hosting) servislerinin neredeyse tamamı (Render, Railway,
# Heroku, Fly.io vb.) sunucuya PORT ortam değişkenini otomatik olarak
# geçer; localde bu değişken bulunmaz. Bu yüzden PORT'un varlığı, ekstra
# bir ayar yapmaya gerek kalmadan "canlı ortamda mıyız?" sorusuna güvenilir
# bir cevap verir. İsterseniz FLASK_ENV=production ortam değişkenini elle
# ayarlayarak da (ör. kendi VPS/sunucunuzda) aynı davranışı tetikleyebilirsiniz.
IS_PRODUCTION = os.environ.get("FLASK_ENV", "").lower() == "production" or "PORT" in os.environ

app = Flask(__name__)
app.secret_key = get_or_create_secret_key()

# Ters proxy (Render/Railway/Heroku/nginx vb.) arkasında çalışırken gelen
# X-Forwarded-* başlıklarını dikkate alır; böylece Flask isteğin gerçekte
# HTTPS üzerinden geldiğini doğru anlar (aksi halde "güvenli" çerezler
# hosting'de hiç gönderilmez ve admin girişi sürekli düşer).
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config["SESSION_COOKIE_HTTPONLY"] = True
# Localde (http://127.0.0.1) test edebilmek için False, hosting'de (HTTPS
# arkasında) otomatik olarak True olur; elle bir şey değiştirmeniz gerekmez.
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"    # CSRF riskini azaltır
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB yükleme sınırı

# ----------------------------------------------------------------------
# GİRİŞ İÇİN BASİT IP BAZLI RATE-LIMIT AYARLARI
# ----------------------------------------------------------------------
LOGIN_MAX_ATTEMPTS = 5      # Bu kadar başarısız denemeden sonra
LOGIN_BLOCK_SECONDS = 60    # ... bu kadar saniye boyunca IP engellenir
_login_attempts = defaultdict(list)  # ip -> [başarısız deneme zaman damgaları]

# ----------------------------------------------------------------------
# GÖRSEL SIKIŞTIRMA (Pillow) AYARLARI
# ----------------------------------------------------------------------
MAX_IMAGE_WIDTH = 1920   # Bu genişlikten büyük görseller oranlı küçültülür
WEBP_QUALITY = 82        # WebP sıkıştırma kalitesi (0-100)
# Pillow ile yeniden kodlanmayacak, olduğu gibi kaydedilecek uzantılar
# (SVG vektörel bir formattır; GIF olası animasyonu bozmamak için korunur)
SKIP_OPTIMIZATION_EXT = {"svg", "gif"}
try:
    app.json.ensure_ascii = False  # Flask 2.3+ (Türkçe karakterler JSON'da bozulmasın)
except AttributeError:
    app.config["JSON_AS_ASCII"] = False  # Eski Flask sürümleri için

# Sayfa dosya adı -> panelde görünecek isim
PAGE_LABELS = {
    "index.html": "Ana Sayfa",
    "hakkimizda.html": "Hakkımızda",
    "hizmetler.html": "Hizmetler",
    "portfolyo.html": "Portfolyo",
    "iletisim.html": "İletişim",
    "fiyatlandirma.html": "Fiyatlandırma",
    "kullanim-sartlari.html": "Kullanım Şartları",
    "kvkk-gizlilik.html": "KVKK & Gizlilik",
    "cerez-politikasi.html": "Çerez Politikası",
}

# Ziyaretçiye gösterilen SEO dostu, ".html" uzantısız kısa adresler.
# Şablon dosyaları (yönetim paneli / yedekleme / find-replace sistemiyle
# uyumlu kalması için) aynı isimde durur; sadece dışa açılan URL değişir.
# Örn: gerçek dosya "hizmetler.html", ziyaretçi adresi ise "/hizmetler".
CLEAN_SLUGS = {
    "hakkimizda-bursa": "hakkimizda.html",
    "web-tasarim-tabela": "hizmetler.html",
    "portfolyo-ornekleri": "portfolyo.html",
    "bursa-iletisim": "iletisim.html",
    "web-tasarim-fiyatlari": "fiyatlandirma.html",
    "kullanim-sartlari": "kullanim-sartlari.html",
    "kvkk-gizlilik": "kvkk-gizlilik.html",
    "cerez-politikasi": "cerez-politikasi.html",
}

# Önceki adres denemelerinden (tek kelimelik ve gereğinden uzun 4 kelimelik
# sürümler) gelen ziyaretçiler/bağlantılar kırılmasın diye, hepsi güncel
# kısa adrese 301 ile yönlendirilir.
OLD_SHORT_SLUGS = {
    # İlk sürüm: tek kelimelik, uzantısız adresler
    "hakkimizda": "hakkimizda-bursa",
    "hizmetler": "web-tasarim-tabela",
    "portfolyo": "portfolyo-ornekleri",
    "iletisim": "bursa-iletisim",
    "fiyatlandirma": "web-tasarim-fiyatlari",
    # İkinci sürüm: gereğinden uzun, 4 kelimelik adresler
    "hakkimizda-bursa-reklam-ajansi": "hakkimizda-bursa",
    "web-tasarim-bursa-tabela-hizmetleri": "web-tasarim-tabela",
    "web-tasarim-tabela-portfolyo": "portfolyo-ornekleri",
    "bursa-reklam-ajansi-iletisim": "bursa-iletisim",
    "web-tasarim-tabela-fiyatlari": "web-tasarim-fiyatlari",
}

# Metin taraması sırasında İÇİNE GİRİLMEYECEK etiketler
SKIP_TAGS = {"script", "style", "noscript", "template", "head", "title", "meta", "link", "svg", "path"}

# Sitede HER SAYFADA aynı şekilde tekrar eden, ama panelde gerçek/benzersiz bir
# "sayfa içeriği" olmayan gizli bileşenler (bildirim kutusu, medya pop-up'ı vb.).
# Bunlar panelde her sayfa için ayrı ayrı ve işe yaramaz kartlar olarak
# görünüyordu; artık taramaya hiç dahil edilmiyorlar.
BLOCKED_CONTAINER_IDS = {"notification", "media-modal"}

ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp", "gif", "svg"}
ALLOWED_FAVICON_EXT = {"png", "ico", "svg"}

# Portfolyo kategorileri ve "Yeni Proje Ekle" ile eklenen kartın HTML şablonu.
# portfolyo.html içindeki mevcut kartlarla BİREBİR aynı yapı/CSS sınıfları kullanılır,
# böylece yeni eklenen proje site tasarımıyla tam uyumlu görünür.
PORT_ITEM_TEMPLATES = {
    "web": """<div class="port-item group rounded-3xl overflow-hidden cursor-pointer" data-cat="web" onclick="openPortfolioWebsite('')">
<div class="aspect-[4/3] relative overflow-hidden img-loader">
<img alt="Yeni Proje" class="w-full h-full object-cover group-hover:scale-110 group-hover:opacity-40 transition-all duration-700" decoding="async" loading="lazy" onerror="this.parentElement.classList.add('img-ready')" onload="this.classList.add('img-loaded'); this.parentElement.classList.add('img-ready')" src="https://placehold.co/600x450/2C2C2C/FFF?text=Yeni+Proje"/>
<div class="port-zoom-badge absolute inset-0 flex items-center justify-center pointer-events-none">
<div class="w-14 h-14 rounded-full bg-white/95 backdrop-blur-md flex items-center justify-center shadow-2xl">
<i class="w-6 h-6 text-brand-charcoal" data-lucide="external-link"></i>
</div>
</div>
<div class="absolute inset-0 flex flex-col justify-end p-6 translate-y-4 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all duration-500">
<span class="text-brand-rust text-[10px] font-bold uppercase tracking-widest mb-2 bg-white/10 w-max px-2 py-1 rounded backdrop-blur-md flex items-center gap-1"><i class="w-3 h-3" data-lucide="external-link"></i> Web Sitesi</span>
<h4 class="text-white text-base font-bold leading-snug">Yeni Proje</h4>
</div>
</div>
</div>""",
    "kartvizit": """<div class="port-item group rounded-3xl overflow-hidden cursor-pointer" data-cat="kartvizit" onclick="openMediaModal('', 'Yeni Proje', 'Kartvizit')">
<div class="aspect-[4/3] relative overflow-hidden img-loader">
<img alt="Yeni Proje" class="w-full h-full object-cover group-hover:scale-110 group-hover:opacity-50 transition-all duration-700" decoding="async" loading="lazy" onerror="this.parentElement.classList.add('img-ready')" onload="this.classList.add('img-loaded'); this.parentElement.classList.add('img-ready')" src="https://placehold.co/900x650/EFEAE2/1C1C1C?text=Yeni+Proje"/>
<div class="port-zoom-badge absolute inset-0 flex items-center justify-center pointer-events-none">
<div class="w-14 h-14 rounded-full bg-white/95 backdrop-blur-md flex items-center justify-center shadow-2xl">
<i class="w-6 h-6 text-brand-charcoal" data-lucide="expand"></i>
</div>
</div>
<div class="absolute inset-0 flex flex-col justify-end p-6 translate-y-4 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all duration-500">
<span class="text-white text-[10px] font-bold uppercase tracking-widest mb-2 bg-black/50 w-max px-2 py-1 rounded backdrop-blur-md flex items-center gap-1"><i class="w-3 h-3" data-lucide="zoom-in"></i> Kartvizit</span>
<h4 class="text-white text-base font-bold leading-snug">Yeni Proje</h4>
</div>
</div>
</div>""",
    "tabela": """<div class="port-item group rounded-3xl overflow-hidden cursor-pointer" data-cat="tabela" data-subcat="all" onclick="openMediaModal('', 'Yeni Proje', 'Tabela')">
<div class="aspect-[4/3] relative overflow-hidden img-loader">
<img alt="Yeni Proje" class="w-full h-full object-cover group-hover:scale-110 group-hover:opacity-50 transition-all duration-700" decoding="async" loading="lazy" onerror="this.parentElement.classList.add('img-ready')" onload="this.classList.add('img-loaded'); this.parentElement.classList.add('img-ready')" src="https://placehold.co/900x650/2C1C1C/FFF?text=Yeni+Proje"/>
<div class="port-zoom-badge absolute inset-0 flex items-center justify-center pointer-events-none">
<div class="w-14 h-14 rounded-full bg-white/95 backdrop-blur-md flex items-center justify-center shadow-2xl">
<i class="w-6 h-6 text-brand-charcoal" data-lucide="expand"></i>
</div>
</div>
<div class="absolute inset-0 flex flex-col justify-end p-6 translate-y-4 opacity-0 group-hover:translate-y-0 group-hover:opacity-100 transition-all duration-500">
<span class="text-yellow-500 text-[10px] font-bold uppercase tracking-widest mb-2 bg-black/50 w-max px-2 py-1 rounded backdrop-blur-md flex items-center gap-1"><i class="w-3 h-3" data-lucide="zoom-in"></i> Tabela</span>
<h4 class="text-white text-base font-bold leading-snug">Yeni Proje</h4>
</div>
</div>
</div>""",
}


# ----------------------------------------------------------------------
# YARDIMCI FONKSİYONLAR
# ----------------------------------------------------------------------

def list_site_pages():
    """templates/ klasöründeki düzenlenebilir .html sayfalarını listeler (admin.html hariç)."""
    files = sorted(glob.glob(os.path.join(TEMPLATES_DIR, "*.html")))
    pages = []
    for f in files:
        name = os.path.basename(f)
        if name == "admin.html":
            continue
        label = PAGE_LABELS.get(name, name.replace(".html", "").replace("-", " ").title())
        pages.append({"file": name, "label": label})
    return pages


def safe_page(page_name):
    """Path traversal saldırılarını engelleyip dosyanın gerçek yolunu döndürür."""
    if not page_name:
        abort(400, "Sayfa belirtilmedi")
    name = os.path.basename(page_name)
    if not name.endswith(".html") or name == "admin.html":
        abort(400, "Geçersiz dosya türü")
    full = os.path.normpath(os.path.join(TEMPLATES_DIR, name))
    if not full.startswith(TEMPLATES_DIR) or not os.path.isfile(full):
        abort(404, "Sayfa bulunamadı")
    return full


def list_brand_pages():
    """Logo/favicon güncellemesinde düzenlenecek TÜM şablonları döndürür.
    list_site_pages()'ten farklı olarak admin.html'i de kapsar; çünkü marka
    (logo/favicon) yönetim panelinde de tutarlı görünmelidir."""
    pages = list_site_pages()
    pages.append({"file": "admin.html", "label": "Yönetim Paneli"})
    return pages


def safe_brand_page(page_name):
    """safe_page ile aynı güvenlik kontrollerini uygular, ancak logo/favicon
    güncelleme akışları için admin.html dosyasına da izin verir."""
    if not page_name:
        abort(400, "Sayfa belirtilmedi")
    name = os.path.basename(page_name)
    if not name.endswith(".html"):
        abort(400, "Geçersiz dosya türü")
    full = os.path.normpath(os.path.join(TEMPLATES_DIR, name))
    if not full.startswith(TEMPLATES_DIR) or not os.path.isfile(full):
        abort(404, "Sayfa bulunamadı")
    return full


def list_demo_sites():
    """demo-siteler/ klasörü altındaki, içinde index.html bulunan alt klasörleri listeler."""
    sites = []
    if os.path.isdir(DEMO_SITES_DIR):
        for name in sorted(os.listdir(DEMO_SITES_DIR), key=lambda s: s.lower()):
            if name.startswith(".") or name.startswith("_"):
                continue
            full = os.path.join(DEMO_SITES_DIR, name)
            if not os.path.isdir(full):
                continue
            has_index = os.path.isfile(os.path.join(full, "index.html"))
            sites.append({"folder": name, "has_index": has_index, "url": f"/demo-siteler/{name}/"})
    return sites


def _is_within_dir(base_dir, target_path):
    """target_path'in base_dir'in gerçekten içinde olup olmadığını doğrular
    (path traversal / '..' saldırılarını engellemek için)."""
    base = os.path.abspath(base_dir)
    target = os.path.abspath(target_path)
    return target == base or target.startswith(base + os.sep)


def get_analytics_db():
    """Her istek için ayrı bir SQLite bağlantısı açar (basit ve düşük trafikli
    bir kurumsal site için yeterlidir)."""
    conn = sqlite3.connect(ANALYTICS_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_analytics_db():
    """analytics.db henüz yoksa tabloyu oluşturur."""
    conn = get_analytics_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ziyaretler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                page TEXT NOT NULL,
                referrer TEXT,
                utm_source TEXT,
                utm_medium TEXT,
                utm_campaign TEXT,
                fbclid TEXT,
                gclid TEXT,
                is_meta_ad INTEGER NOT NULL DEFAULT 0,
                ip_hash TEXT,
                user_agent TEXT,
                duration_seconds INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ziyaret_tarih ON ziyaretler(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ziyaret_visitor ON ziyaretler(visitor_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS mesajlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_soyad TEXT NOT NULL,
                telefon TEXT NOT NULL,
                e_posta TEXT NOT NULL,
                hizmet TEXT,
                mesaj TEXT NOT NULL,
                sayfa TEXT,
                ip_hash TEXT,
                user_agent TEXT,
                okundu INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mesaj_tarih ON mesajlar(created_at)")
        conn.commit()
    finally:
        conn.close()


def hash_ip(ip):
    """IP adresini geri döndürülemeyecek şekilde (gizli anahtarla tuzlanmış)
    özetler; ham IP hiçbir zaman diske yazılmaz."""
    try:
        return hashlib.sha256((app.secret_key + "|" + (ip or "")).encode("utf-8")).hexdigest()[:16]
    except Exception:
        return ""


def classify_source(row):
    """Bir ziyaret satırını trafik kaynağı kategorisine ayırır."""
    utm_source = (row["utm_source"] or "").strip().lower()
    utm_medium = (row["utm_medium"] or "").strip().lower()
    referrer = (row["referrer"] or "").strip().lower()
    has_fbclid = bool(row["fbclid"])
    has_gclid = bool(row["gclid"])

    if row["is_meta_ad"] or has_fbclid or utm_source in META_UTM_SOURCES:
        return "meta_reklam"
    if has_gclid or utm_source in GOOGLE_UTM_SOURCES or (utm_medium in ("cpc", "ppc", "paid")):
        return "google_ads"
    if utm_source:
        return "diger_kampanya"
    if not referrer:
        return "dogrudan"
    if any(s in referrer for s in ("google.", "bing.", "yandex.", "duckduckgo.")):
        return "organik_arama"
    if any(s in referrer for s in ("facebook.", "instagram.", "l.facebook.")):
        return "sosyal_medya_organik"
    return "diger_yonlendirme"


SOURCE_LABELS = {
    "meta_reklam": "Meta Reklamları (Facebook/Instagram)",
    "google_ads": "Google Ads",
    "diger_kampanya": "Diğer Kampanya (UTM)",
    "dogrudan": "Doğrudan Giriş",
    "organik_arama": "Organik Arama",
    "sosyal_medya_organik": "Sosyal Medya (Organik)",
    "diger_yonlendirme": "Diğer Yönlendirme",
}


init_analytics_db()


def backup_file(full_path):
    """Kaydetmeden önce dosyanın yedeğini alır."""
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name = os.path.basename(full_path)
        shutil.copy2(full_path, os.path.join(BACKUP_DIR, f"{name}.{ts}.bak"))
    except Exception:
        pass  # Yedekleme başarısız olsa da kaydetme işlemi engellenmesin


def is_blocked(el, root):
    """Bir elemanın script/style/svg/title gibi 'dokunulmaz' bir atanın,
    ya da BLOCKED_CONTAINER_IDS içindeki paylaşılan/gizli bir bileşenin
    (bildirim kutusu, medya pop-up'ı vb.) içinde olup olmadığını kontrol eder."""
    p = el
    while p is not None and p is not root:
        if getattr(p, "name", None) in SKIP_TAGS:
            return True
        if getattr(p, "get", None) and p.get("id") in BLOCKED_CONTAINER_IDS:
            return True
        p = p.parent
    return False


def nearest_context(el):
    """Panelde göstermek için elemanın hangi bölümde olduğunu tahmin eder."""
    labels = {"header": "Üst Menü (Header)", "footer": "Alt Bilgi (Footer)", "nav": "Navigasyon Menüsü"}
    p = el.parent
    depth = 0
    while p is not None and depth < 15:
        if p.name in labels:
            return labels[p.name]
        if p.name == "section":
            sid = p.get("id")
            return f"Bölüm: {sid}" if sid else "Sayfa İçeriği"
        p = p.parent
        depth += 1
    return "Sayfa İçeriği"


def ensure_ids_and_extract(soup):
    """
    Sayfadaki tüm düzenlenebilir metin/resim/placeholder öğelerine kalıcı
    'data-eid' kimliği atar (varsa dokunmaz) ve panel için listeler.
    """
    body = soup.body or soup

    existing_ids = [el.get("data-eid") for el in soup.find_all(attrs={"data-eid": True})]
    max_n = 0
    for v in existing_ids:
        try:
            max_n = max(max_n, int(str(v).split("-")[-1]))
        except (ValueError, IndexError):
            pass
    counter = [max_n]

    def next_id():
        counter[0] += 1
        return f"e-{counter[0]}"

    # 1) Serbest metinleri <span data-eid="..."> ile sarmala (option hariç)
    targets = []
    for ns in list(body.descendants):
        if not isinstance(ns, NavigableString) or isinstance(ns, Comment):
            continue
        if not ns.strip():
            continue
        parent = ns.parent
        if parent is None or parent.name in SKIP_TAGS or parent.name == "option":
            continue
        if is_blocked(parent, body):
            continue
        # Logo metin bloğu (data-role=logo-text) panelde ayrı yönetildiği için
        # serbest metin listesine dahil edilmez.
        p = parent
        skip_logo = False
        depth = 0
        while p is not None and p is not body and depth < 8:
            # "logo-text": logo & favicon panelinde ayrı yönetilir.
            # "settings-field": Genel Ayarlar panelinden ({{ settings.xxx }})
            # otomatik gelen telefon/adres/e-posta/sosyal medya metinleridir;
            # bunlar sayfa bazlı "İçerik" listesinde tekrar tekrar ve anlamsız
            # (ham Jinja kodu olarak) görünmesin diye taramaya dahil edilmez.
            if p.get("data-role") in ("logo-text", "settings-field"):
                skip_logo = True
                break
            p = p.parent
            depth += 1
        if skip_logo:
            continue
        targets.append(ns)

    for ns in targets:
        parent = ns.parent
        if parent.name == "span" and parent.get("data-eid") and len(parent.contents) == 1:
            continue  # zaten sarılmış, id sabit kalsın
        new_span = soup.new_tag("span")
        new_span["data-eid"] = next_id()
        value = str(ns)
        ns.replace_with(new_span)
        new_span.append(NavigableString(value))

    # 2) <option> etiketleri (dropdown seçenekleri) doğrudan işaretlenir
    for opt in body.find_all("option"):
        if is_blocked(opt, body):
            continue
        if not opt.get("data-eid"):
            opt["data-eid"] = next_id()

    # 3) Görseller (logo görseli hariç - Logo & Favicon sekmesinde yönetilir)
    for img in body.find_all("img"):
        if is_blocked(img, body):
            continue
        if img.get("data-role") == "logo-img":
            continue
        if not img.get("data-eid"):
            img["data-eid"] = next_id()

    # 4) Form alanlarındaki placeholder metinleri
    for el in body.find_all(["input", "textarea"]):
        if is_blocked(el, body):
            continue
        if el.get("placeholder") and not el.get("data-eid"):
            el["data-eid"] = next_id()

    # --- Panel için verileri topla ---
    items = []
    for span in body.find_all("span", attrs={"data-eid": True}):
        if is_blocked(span, body):
            continue
        txt = span.get_text()
        if txt.strip():
            items.append({"id": span["data-eid"], "kind": "text", "value": txt, "context": nearest_context(span)})
    for opt in body.find_all("option", attrs={"data-eid": True}):
        if is_blocked(opt, body):
            continue
        items.append({"id": opt["data-eid"], "kind": "option", "value": opt.get_text(), "context": "Seçenek (Dropdown)"})

    images = []
    for img in body.find_all("img", attrs={"data-eid": True}):
        if is_blocked(img, body):
            continue
        img_data = {
            "id": img["data-eid"], "kind": "image",
            "src": img.get("src", ""), "alt": img.get("alt", ""),
            "context": nearest_context(img),
        }
        # Portfolyo ek bilgileri: data-cat, onclick linki, h4 başlığı
        port_item = img.parent
        depth = 0
        while port_item and depth < 8:
            cat_val = port_item.get("data-cat")
            if cat_val:
                img_data["cat"] = cat_val
            sub_val = port_item.get("data-subcat", "")
            if sub_val:
                img_data["sub"] = sub_val
            onclick = port_item.get("onclick", "")
            if onclick:
                import re as _re
                # openPortfolioWebsite('URL') veya openMediaModal('URL', ...)
                m = _re.search(r"openPortfolioWebsite\(['\"]([^'\"]+)['\"]", onclick)
                if m:
                    img_data["link"] = m.group(1)
                else:
                    m2 = _re.search(r"openMediaModal\(['\"]([^'\"]+)['\"]", onclick)
                    if m2:
                        img_data["link"] = m2.group(1)
            h4 = port_item.find("h4")
            if h4:
                img_data["ptitle"] = h4.get_text()
            if cat_val or onclick:
                break
            port_item = port_item.parent
            depth += 1
        images.append(img_data)

    placeholders = []
    for el in body.find_all(["input", "textarea"], attrs={"data-eid": True}):
        if is_blocked(el, body):
            continue
        placeholders.append({
            "id": el["data-eid"], "kind": "placeholder",
            "value": el.get("placeholder", ""), "context": nearest_context(el),
        })

    return items, images, placeholders


def get_meta(soup):
    title = soup.title.string.strip() if (soup.title and soup.title.string) else ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag["content"].strip() if (desc_tag and desc_tag.get("content")) else ""
    return {"title": title, "description": description}


def literal_replace(text, find, replace, case_sensitive):
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(find), flags)
    new_text, n = pattern.subn(lambda m: replace, text)
    return new_text, n


def count_occurrences(text, find, case_sensitive):
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(find), flags)
    return len(pattern.findall(text))


def make_snippet(text, find, case_sensitive, radius=28):
    flags = 0 if case_sensitive else re.IGNORECASE
    m = re.search(re.escape(find), text, flags)
    if not m:
        return text[:80]
    start = max(0, m.start() - radius)
    end = min(len(text), m.end() + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def get_port_section(soup, cat):
    """Verilen kategoriye ait portfolyo bölümünü (örn. #portfolio-web) döndürür."""
    return soup.find(id=f"portfolio-{cat}")


def get_port_grid(soup, cat):
    """Verilen kategoriye ait proje kartlarının bulunduğu grid <div> öğesini döndürür."""
    section = get_port_section(soup, cat)
    if section is None:
        return None
    return section.find("div", class_=lambda c: c and "grid" in c.split())


def update_port_count(soup, cat):
    """
    Kategori başlığının altındaki 'N Proje · ...' metnindeki sayıyı,
    o kategoride gerçekte kaç kart olduğuyla senkronize eder.
    (Proje eklenip/silindiğinde site tarafında sayı yanlış görünmesin diye.)
    """
    section = get_port_section(soup, cat)
    grid = get_port_grid(soup, cat)
    if section is None or grid is None:
        return
    count = len(grid.find_all("div", attrs={"class": lambda c: c and "port-item" in c.split()}, recursive=False))
    p_tag = section.find("p")
    if p_tag is None:
        return
    for ns in p_tag.find_all(string=True):
        if re.match(r"^\s*\d+", ns):
            new_str = re.sub(r"^(\s*)\d+", lambda m: f"{m.group(1)}{count}", ns, count=1)
            ns.replace_with(NavigableString(new_str))
            return


def load_config():
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"logo_url": None, "favicon_url": None}


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------
# GENEL AYARLAR (Telefon / Adres / E-posta / Sosyal Medya) - settings.json
# ----------------------------------------------------------------------

def clean_domain(value):
    """Admin panelinden gelen alan adını normalize eder: başındaki
    http(s)://, www. ve sondaki / karakterlerini temizler, küçük harfe
    çevirir. 'https://www.Siteniz.com/' -> 'siteniz.com'"""
    v = (value or "").strip().lower()
    v = re.sub(r"^https?://", "", v)
    v = v.lstrip("/")
    v = re.sub(r"^www\.", "", v)
    v = v.split("/")[0].strip()
    return v or DEFAULT_SETTINGS["site_domain"]


def clean_lucide_version(value):
    """unpkg.com/lucide@<sürüm> için güvenli bir değer üretir. Sadece
    'latest' veya rakam/nokta/tire içeren sürüm numaralarına (ör. 0.469.0)
    izin verilir; aksi halde varsayılana döner."""
    v = (value or "").strip()
    if v == "latest" or re.match(r"^[0-9]+(\.[0-9]+){0,2}(-[a-zA-Z0-9.]+)?$", v):
        return v
    return DEFAULT_SETTINGS["lucide_version"]


def load_settings():
    """settings.json'u okur; dosya yoksa veya bir alan eksikse
    DEFAULT_SETTINGS ile tamamlar. Ayrıca tel: linki için telefonun
    sadece rakam+artı içeren halini (phone_tel), site adresi için de
    tam URL'yi (site_url) otomatik türetir."""
    data = dict(DEFAULT_SETTINGS)
    if os.path.isfile(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                data.update(saved)
        except Exception:
            pass
    digits = re.sub(r"[^\d+]", "", data.get("phone", ""))
    data["phone_tel"] = digits or DEFAULT_SETTINGS["phone"]
    data["site_domain"] = clean_domain(data.get("site_domain"))
    data["lucide_version"] = clean_lucide_version(data.get("lucide_version"))
    # Tüm şablonlarda kullanılan tam site adresi (sonunda / OLMADAN):
    # {{ settings.site_url }}/  ->  https://www.siteniz.com/
    data["site_url"] = f"https://www.{data['site_domain']}"
    return data


def extract_maps_embed_src(raw_value):
    """Admin panelinden "Google Haritalar Embed Kodu" alanına yapıştırılan
    değeri güvenli bir <iframe src="..."> adresine indirger.

    Kabul edilen girdiler:
      - Google Haritalar'ın "Haritayı Yerleştir" ekranından kopyalanan
        tam <iframe ...></iframe> HTML kodu (src'si otomatik çıkarılır)
      - Doğrudan yapıştırılmış bir google.com/maps/embed... adresi

    Güvenlik: gelen değer olduğu gibi (ham HTML olarak) hiçbir zaman
    kaydedilmez/render edilmez; yalnızca google.com/maps embed
    adresiyle eşleşen "src" değeri kabul edilir. Aksi halde boş
    döndürülür (bozuk/şüpheli kod sessizce reddedilir).
    """
    raw_value = (raw_value or "").strip()
    if not raw_value:
        return ""

    src = raw_value
    match = re.search(r'src=["\']([^"\']+)["\']', raw_value, re.IGNORECASE)
    if match:
        src = match.group(1)

    src = src.strip()
    if not re.match(r'^https://www\.google\.com/maps/embed', src, re.IGNORECASE):
        return ""
    return src


def save_settings(new_values):
    """Gelen alanları mevcut settings.json ile birleştirip kaydeder.
    Sadece DEFAULT_SETTINGS içinde tanımlı anahtarlar kabul edilir."""
    current = dict(DEFAULT_SETTINGS)
    if os.path.isfile(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                current.update(saved)
        except Exception:
            pass
    for key in DEFAULT_SETTINGS.keys():
        if key in new_values:
            current[key] = str(new_values[key] or "").strip()
    if "maps_embed_url" in new_values:
        current["maps_embed_url"] = extract_maps_embed_src(new_values["maps_embed_url"])
    if "site_domain" in new_values:
        current["site_domain"] = clean_domain(new_values["site_domain"])
    if "lucide_version" in new_values:
        current["lucide_version"] = clean_lucide_version(new_values["lucide_version"])
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current


@app.context_processor
def inject_settings():
    """Tüm şablonlara (site sayfaları + admin.html) global 'settings'
    değişkenini otomatik olarak enjekte eder: {{ settings.phone }} vb."""
    return {"settings": load_settings()}


def unique_filename(original_name, prefix=""):
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    safe = secure_filename(original_name.rsplit(".", 1)[0]) or "dosya"
    token = uuid.uuid4().hex[:8]
    fname = f"{prefix}{safe}-{token}.{ext}" if ext else f"{prefix}{safe}-{token}"
    return fname, ext


def optimize_and_save_image(file_storage, dest_dir, prefix=""):
    """Yüklenen görseli sunucu tarafında Pillow ile optimize edip kaydeder.

    - Genişliği MAX_IMAGE_WIDTH'ten büyükse oranlı şekilde küçültür.
    - Raster görselleri (png/jpg/jpeg/webp vb.) WebP formatına dönüştürüp
      WEBP_QUALITY ile sıkıştırır.
    - SVG (vektörel) ve GIF (olası animasyon) dosyalarını olduğu gibi,
      yalnızca benzersiz bir isimle kaydeder.
    - Pillow görseli açamazsa (bozuk dosya vb.) orijinal dosyayı olduğu
      gibi kaydederek isteği kesintiye uğratmaz.

    Dönüş: kaydedilen dosyanın adı (fname)
    """
    original_name = file_storage.filename
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    safe = secure_filename(original_name.rsplit(".", 1)[0]) or "dosya"
    token = uuid.uuid4().hex[:8]

    if ext in SKIP_OPTIMIZATION_EXT:
        fname = f"{prefix}{safe}-{token}.{ext}"
        file_storage.save(os.path.join(dest_dir, fname))
        return fname

    try:
        img = Image.open(file_storage.stream)
        img.load()
    except Exception:
        # Pillow açamadıysa (örn. desteklenmeyen/bozuk içerik) orijinal
        # dosyayı olduğu gibi kaydet, kullanıcının yüklemesi başarısız olmasın.
        fname = f"{prefix}{safe}-{token}.{ext}" if ext else f"{prefix}{safe}-{token}"
        try:
            file_storage.stream.seek(0)
        except Exception:
            pass
        file_storage.save(os.path.join(dest_dir, fname))
        return fname

    # WebP ile uyumlu renk moduna çevir (şeffaflığı koru)
    if img.mode == "P":
        img = img.convert("RGBA")
    elif img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    if img.width > MAX_IMAGE_WIDTH:
        oran = MAX_IMAGE_WIDTH / float(img.width)
        yeni_boyut = (MAX_IMAGE_WIDTH, max(1, int(img.height * oran)))
        img = img.resize(yeni_boyut, Image.LANCZOS)

    fname = f"{prefix}{safe}-{token}.webp"
    img.save(os.path.join(dest_dir, fname), "WEBP", quality=WEBP_QUALITY, method=6)
    return fname


def get_client_ip():
    """İstemci IP adresini tespit eder (varsa ters proxy başlığını dikkate alır)."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "bilinmiyor"


def is_login_blocked(ip):
    """Son LOGIN_BLOCK_SECONDS içinde LOGIN_MAX_ATTEMPTS'ten fazla başarısız
    deneme yapılmışsa True döner."""
    now = time.time()
    attempts = [t for t in _login_attempts[ip] if now - t < LOGIN_BLOCK_SECONDS]
    _login_attempts[ip] = attempts
    return len(attempts) >= LOGIN_MAX_ATTEMPTS


def register_failed_login(ip):
    _login_attempts[ip].append(time.time())


def clear_login_attempts(ip):
    _login_attempts.pop(ip, None)


# ----------------------------------------------------------------------
# GİRİŞ / OTURUM KORUMASI
# ----------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("auth"):
            return jsonify(ok=False, error="Oturum açılmamış"), 401
        return f(*args, **kwargs)
    return wrapper


@app.route("/api/login", methods=["POST"])
def api_login():
    ip = get_client_ip()
    if is_login_blocked(ip):
        return jsonify(ok=False, error="Çok fazla başarısız deneme yapıldı. Lütfen 60 saniye sonra tekrar deneyin."), 429

    data = request.get_json(force=True, silent=True) or {}
    password = data.get("password", "")
    if password and password == ADMIN_PASSWORD:
        clear_login_attempts(ip)
        session.clear()
        session["auth"] = True
        session.permanent = True
        return jsonify(ok=True)

    register_failed_login(ip)
    return jsonify(ok=False, error="Şifre hatalı"), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify(ok=True)


@app.route("/api/check-auth", methods=["GET"])
def api_check_auth():
    return jsonify(authenticated=bool(session.get("auth")))


@app.route("/api/analytics/reset", methods=["POST"])
@login_required
def api_analytics_reset():
    """Trafik analiz verilerini (tüm ziyaret kayıtlarını) tamamen siler.
    Geri alınamaz; ön yüzde ayrıca bir onay penceresiyle korunur."""
    conn = get_analytics_db()
    try:
        conn.execute("DELETE FROM ziyaretler")
        try:
            conn.execute("DELETE FROM sqlite_sequence WHERE name = 'ziyaretler'")
        except Exception:
            pass  # sqlite_sequence tablosu henüz oluşmamış olabilir - sorun değil
        conn.commit()
    except Exception:
        return jsonify(ok=False, error="Sıfırlanamadı"), 500
    finally:
        conn.close()
    return jsonify(ok=True)


# ----------------------------------------------------------------------
# API - TRAFİK ANALİZİ (ziyaret takibi + admin panel raporu)
# ----------------------------------------------------------------------
# NOT: /api/track ve /api/track-duration bilerek login_required DEĞİLDİR;
# bunlar sitedeki her ziyaretçinin tarayıcısından (static/js/analytics.js
# tarafından) otomatik olarak çağrılır. Admin şifresi gerektirmezler.

@app.route("/api/track", methods=["POST"])
def api_track():
    """Bir sayfa görüntülemesini kaydeder. static/js/analytics.js tarafından
    her sayfa yüklendiğinde bir kez çağrılır."""
    data = request.get_json(force=True, silent=True) or {}

    def s(key, maxlen=180):
        v = data.get(key)
        if v is None:
            return None
        v = str(v).strip()
        return v[:maxlen] if v else None

    visitor_id = s("visitor_id", 64)
    session_id = s("session_id", 64)
    page = s("page", 120) or "/"
    if not visitor_id or not session_id:
        return jsonify(ok=False, error="Eksik parametre"), 400

    referrer = s("referrer", 300)
    utm_source = s("utm_source", 80)
    utm_medium = s("utm_medium", 80)
    utm_campaign = s("utm_campaign", 120)
    fbclid = s("fbclid", 200)
    gclid = s("gclid", 200)
    is_meta_ad = 1 if (fbclid or (utm_source or "").lower() in META_UTM_SOURCES) else 0
    ip_hash = hash_ip(get_client_ip())
    user_agent = (request.headers.get("User-Agent") or "")[:250]
    now = datetime.datetime.utcnow().isoformat()

    conn = get_analytics_db()
    try:
        cur = conn.execute("""
            INSERT INTO ziyaretler
                (visitor_id, session_id, page, referrer, utm_source, utm_medium,
                 utm_campaign, fbclid, gclid, is_meta_ad, ip_hash, user_agent,
                 duration_seconds, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0,?)
        """, (visitor_id, session_id, page, referrer, utm_source, utm_medium,
              utm_campaign, fbclid, gclid, is_meta_ad, ip_hash, user_agent, now))
        conn.commit()
        new_id = cur.lastrowid
    except Exception:
        return jsonify(ok=False, error="Kaydedilemedi"), 500
    finally:
        conn.close()

    return jsonify(ok=True, id=new_id)


@app.route("/api/track-duration", methods=["POST"])
def api_track_duration():
    """Bir sayfada geçirilen süreyi (saniye) günceller. Sayfa kapatılırken/
    gizlenirken navigator.sendBeacon ile çağrılır, bu yüzden auth gerektirmez
    ve sadece kendi kaydına ait süreyi günceller."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        visit_id = int(data.get("id"))
        seconds = int(float(data.get("seconds", 0)))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Geçersiz veri"), 400

    seconds = max(0, min(seconds, MAX_TRACK_DURATION_SECONDS))

    conn = get_analytics_db()
    try:
        conn.execute(
            "UPDATE ziyaretler SET duration_seconds = MAX(duration_seconds, ?) WHERE id = ?",
            (seconds, visit_id),
        )
        conn.commit()
    except Exception:
        return jsonify(ok=False, error="Güncellenemedi"), 500
    finally:
        conn.close()

    return jsonify(ok=True)


@app.route("/api/contact-message", methods=["POST"])
def api_contact_message():
    """İletişim sayfasındaki formdan gelen mesajı analytics.db > mesajlar
    tablosuna kaydeder. Herkese açık bir uç noktadır (ziyaretçi girer),
    ama tüm alanlar sunucu tarafında sıkı biçimde doğrulanır."""
    data = request.get_json(force=True, silent=True) or {}

    def s(key, maxlen=2000):
        v = data.get(key)
        if v is None:
            return ""
        return str(v).strip()[:maxlen]

    ad_soyad = s("ad_soyad", 150)
    telefon = s("telefon", 40)
    e_posta = s("e_posta", 200)
    hizmet = s("hizmet", 40)
    mesaj = s("mesaj", 4000)
    sayfa = s("sayfa", 120)

    errors = {}
    if not ad_soyad or len(ad_soyad) < 2:
        errors["ad_soyad"] = "Ad soyad gerekli"
    if not telefon or len(re.sub(r"\D", "", telefon)) < 10:
        errors["telefon"] = "Geçerli bir telefon numarası girin"
    # E-posta zorunlu ve tam olarak doğrulanır (RFC 5322 alt kümesi + uzunluk sınırları).
    if not e_posta:
        errors["e_posta"] = "E-posta adresi gerekli"
    elif len(e_posta) > 254 or not EMAIL_RE.match(e_posta):
        errors["e_posta"] = "Geçerli bir e-posta adresi girin"
    else:
        local_part, _, domain_part = e_posta.rpartition("@")
        if len(local_part) > 64 or ".." in e_posta or domain_part.startswith("-") or domain_part.endswith("-"):
            errors["e_posta"] = "Geçerli bir e-posta adresi girin"
    if hizmet and hizmet not in CONTACT_SERVICE_LABELS:
        errors["hizmet"] = "Geçersiz hizmet kategorisi"
    if not mesaj or len(mesaj) < 5:
        errors["mesaj"] = "Mesajınızı biraz daha detaylandırın"

    if errors:
        return jsonify(ok=False, error="Formu eksiksiz ve doğru doldurun", fields=errors), 400

    e_posta = e_posta.lower()
    ip_hash = hash_ip(get_client_ip())
    user_agent = (request.headers.get("User-Agent") or "")[:250]
    now = datetime.datetime.utcnow().isoformat()

    conn = get_analytics_db()
    try:
        cur = conn.execute("""
            INSERT INTO mesajlar
                (ad_soyad, telefon, e_posta, hizmet, mesaj, sayfa, ip_hash, user_agent, okundu, created_at)
            VALUES (?,?,?,?,?,?,?,?,0,?)
        """, (ad_soyad, telefon, e_posta, hizmet, mesaj, sayfa, ip_hash, user_agent, now))
        conn.commit()
        new_id = cur.lastrowid
    except Exception:
        return jsonify(ok=False, error="Mesajınız kaydedilemedi, lütfen tekrar deneyin"), 500
    finally:
        conn.close()

    return jsonify(ok=True, id=new_id)


@app.route("/api/messages", methods=["GET"])
@login_required
def api_list_messages():
    """Admin panelindeki 'Mesajlar' bölümü için kayıtlı iletişim formu
    mesajlarını en yeniden en eskiye sıralı döner."""
    conn = get_analytics_db()
    try:
        rows = conn.execute(
            "SELECT id, ad_soyad, telefon, e_posta, hizmet, mesaj, sayfa, okundu, created_at "
            "FROM mesajlar ORDER BY created_at DESC LIMIT 500"
        ).fetchall()
        unread = conn.execute("SELECT COUNT(*) AS c FROM mesajlar WHERE okundu = 0").fetchone()["c"]
    finally:
        conn.close()

    messages = []
    for r in rows:
        messages.append({
            "id": r["id"],
            "ad_soyad": r["ad_soyad"],
            "telefon": r["telefon"],
            "e_posta": r["e_posta"],
            "hizmet": r["hizmet"],
            "hizmet_label": CONTACT_SERVICE_LABELS.get(r["hizmet"], r["hizmet"] or ""),
            "mesaj": r["mesaj"],
            "sayfa": r["sayfa"],
            "okundu": bool(r["okundu"]),
            "created_at": r["created_at"],
        })

    return jsonify(ok=True, messages=messages, unread_count=unread)


@app.route("/api/messages/mark-read", methods=["POST"])
@login_required
def api_mark_message_read():
    data = request.get_json(force=True, silent=True) or {}
    msg_id = data.get("id")
    if not msg_id:
        return jsonify(ok=False, error="Kimlik (id) eksik"), 400

    conn = get_analytics_db()
    try:
        conn.execute("UPDATE mesajlar SET okundu = 1 WHERE id = ?", (msg_id,))
        conn.commit()
    except Exception:
        return jsonify(ok=False, error="Güncellenemedi"), 500
    finally:
        conn.close()

    return jsonify(ok=True)


@app.route("/api/messages/delete", methods=["POST"])
@login_required
def api_delete_message():
    data = request.get_json(force=True, silent=True) or {}
    msg_id = data.get("id")
    if not msg_id:
        return jsonify(ok=False, error="Kimlik (id) eksik"), 400

    conn = get_analytics_db()
    try:
        conn.execute("DELETE FROM mesajlar WHERE id = ?", (msg_id,))
        conn.commit()
    except Exception:
        return jsonify(ok=False, error="Silinemedi"), 500
    finally:
        conn.close()

    return jsonify(ok=True)


@app.route("/api/analytics", methods=["GET"])
@login_required
def api_analytics():
    """Admin paneli için trafik analiz raporu döndürür.
    ?days=7|30|90|0  (0 = tüm zamanlar)"""
    try:
        days = int(request.args.get("days", 30))
    except ValueError:
        days = 30

    conn = get_analytics_db()
    try:
        if days and days > 0:
            cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
            rows = conn.execute(
                "SELECT * FROM ziyaretler WHERE created_at >= ? ORDER BY created_at ASC", (cutoff,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM ziyaretler ORDER BY created_at ASC").fetchall()
    finally:
        conn.close()

    # Tarayıcıdan gelen "page" değeri window.location.pathname (örn. "/hakkimizda.html")
    # olduğu için hem "hakkimizda.html" hem de "/hakkimizda.html" biçimlerini eşleştir.
    page_labels = {}
    for p in list_site_pages():
        page_labels[p["file"]] = p["label"]
        page_labels["/" + p["file"]] = p["label"]
    page_labels["/"] = "Ana Sayfa"

    total_visits = len(rows)
    unique_visitors = len({r["visitor_id"] for r in rows})
    total_duration = sum(r["duration_seconds"] for r in rows)
    avg_duration = round(total_duration / total_visits, 1) if total_visits else 0

    meta_rows = [r for r in rows if classify_source(r) == "meta_reklam"]
    meta_visits = len(meta_rows)
    meta_unique_visitors = len({r["visitor_id"] for r in meta_rows})
    meta_avg_duration = round(sum(r["duration_seconds"] for r in meta_rows) / meta_visits, 1) if meta_visits else 0

    # Sayfa bazlı kırılım
    by_page = defaultdict(lambda: {"views": 0, "visitors": set(), "duration": 0})
    for r in rows:
        p = by_page[r["page"]]
        p["views"] += 1
        p["visitors"].add(r["visitor_id"])
        p["duration"] += r["duration_seconds"]
    by_page_list = []
    for page, d in by_page.items():
        by_page_list.append({
            "page": page,
            "label": page_labels.get(page, page),
            "views": d["views"],
            "unique_visitors": len(d["visitors"]),
            "avg_duration_seconds": round(d["duration"] / d["views"], 1) if d["views"] else 0,
        })
    by_page_list.sort(key=lambda x: x["views"], reverse=True)

    # Kaynak bazlı kırılım (Meta reklamı / Google Ads / organik / doğrudan vb.)
    by_source = defaultdict(lambda: {"visits": 0, "visitors": set(), "duration": 0})
    for r in rows:
        cat = classify_source(r)
        d = by_source[cat]
        d["visits"] += 1
        d["visitors"].add(r["visitor_id"])
        d["duration"] += r["duration_seconds"]
    by_source_list = []
    for cat, d in by_source.items():
        by_source_list.append({
            "source": cat,
            "label": SOURCE_LABELS.get(cat, cat),
            "visits": d["visits"],
            "unique_visitors": len(d["visitors"]),
            "avg_duration_seconds": round(d["duration"] / d["visits"], 1) if d["visits"] else 0,
            "pct": round(100 * d["visits"] / total_visits, 1) if total_visits else 0,
        })
    by_source_list.sort(key=lambda x: x["visits"], reverse=True)

    # Meta reklamlarında en çok trafik getiren kampanyalar (utm_campaign)
    by_campaign = defaultdict(lambda: {"visits": 0, "visitors": set(), "duration": 0})
    for r in meta_rows:
        camp = r["utm_campaign"] or "(kampanya etiketi yok)"
        d = by_campaign[camp]
        d["visits"] += 1
        d["visitors"].add(r["visitor_id"])
        d["duration"] += r["duration_seconds"]
    meta_campaigns = []
    for camp, d in by_campaign.items():
        meta_campaigns.append({
            "campaign": camp,
            "visits": d["visits"],
            "unique_visitors": len(d["visitors"]),
            "avg_duration_seconds": round(d["duration"] / d["visits"], 1) if d["visits"] else 0,
        })
    meta_campaigns.sort(key=lambda x: x["visits"], reverse=True)

    # Güne göre ziyaret sayısı (grafik için)
    by_day = defaultdict(lambda: {"visits": 0, "meta_visits": 0})
    for r in rows:
        day = r["created_at"][:10]
        by_day[day]["visits"] += 1
        if classify_source(r) == "meta_reklam":
            by_day[day]["meta_visits"] += 1
    daily = [{"date": d, "visits": v["visits"], "meta_visits": v["meta_visits"]} for d, v in sorted(by_day.items())]

    return jsonify(
        ok=True,
        range_days=days,
        summary={
            "total_visits": total_visits,
            "unique_visitors": unique_visitors,
            "avg_duration_seconds": avg_duration,
            "meta_visits": meta_visits,
            "meta_unique_visitors": meta_unique_visitors,
            "meta_avg_duration_seconds": meta_avg_duration,
            "meta_pct": round(100 * meta_visits / total_visits, 1) if total_visits else 0,
        },
        by_page=by_page_list,
        by_source=by_source_list,
        meta_campaigns=meta_campaigns,
        daily=daily,
    )


# ----------------------------------------------------------------------
# API - SAYFALAR & İÇERİK
# ----------------------------------------------------------------------

@app.route("/api/pages", methods=["GET"])
@login_required
def api_pages():
    return jsonify(pages=list_site_pages())


@app.route("/api/content/<page>", methods=["GET"])
@login_required
def api_content(page):
    full = safe_page(page)
    with open(full, "r", encoding="utf-8") as f:
        original = f.read()

    soup = BeautifulSoup(original, "html.parser")
    items, images, placeholders = ensure_ids_and_extract(soup)
    meta = get_meta(soup)

    new_html = str(soup)
    if new_html != original:
        # İlk açılışta kalıcı data-eid'ler dosyaya yazılır (bir kereye mahsus)
        backup_file(full)
        with open(full, "w", encoding="utf-8") as f:
            f.write(new_html)

    return jsonify(ok=True, meta=meta, items=items, images=images, placeholders=placeholders)


@app.route("/api/save-item", methods=["POST"])
@login_required
def api_save_item():
    data = request.get_json(force=True, silent=True) or {}
    page = data.get("page")
    item_id = data.get("id")
    value = data.get("value", "")
    alt = data.get("alt", None)

    if not item_id:
        return jsonify(ok=False, error="Kimlik (id) eksik"), 400

    full = safe_page(page)
    with open(full, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")

    el = soup.find(attrs={"data-eid": item_id})
    if el is None:
        return jsonify(ok=False, error="Öğe bulunamadı, sayfayı yeniden yükleyin"), 404

    backup_file(full)

    if el.name == "img":
        is_delete = data.get("_delete", False)
        cat = data.get("cat")
        link = data.get("link")
        ptitle = data.get("ptitle")
        sub = data.get("sub")  # tabela alt türü

        if is_delete:
            # Silme: src ve alt boşalt, h4 boşalt, onclick temizle
            el["src"] = ""
            el["alt"] = ""
        else:
            el["src"] = value
            if alt is not None:
                el["alt"] = alt

        # port-item container'ını bul (data-cat olan parent)
        port_item_el = el.parent
        depth = 0
        port_container = None
        while port_item_el and depth < 8:
            if port_item_el.get("data-cat") is not None:
                port_container = port_item_el
                break
            if port_item_el.get("onclick"):
                port_container = port_item_el
                break
            port_item_el = port_item_el.parent
            depth += 1

        if port_container is not None:
            if cat is not None:
                port_container["data-cat"] = cat

            if is_delete:
                port_container["onclick"] = ""
            else:
                effective_cat = cat if cat is not None else port_container.get("data-cat")
                if effective_cat == "web":
                    # Web kategorisinde "link" harici bir web sitesi adresidir.
                    if link is not None and link.strip():
                        port_container["onclick"] = f"openPortfolioWebsite('{link}')"
                    elif link is not None:
                        port_container["onclick"] = ""
                else:
                    # Kartvizit/Tabela kategorisinde pop-up'ta gösterilecek görsel HER ZAMAN
                    # yüklenen görselin kendisidir (value). Önceden ayrı bir "Bağlantı URL"
                    # alanına bağımlıydı; o alan boş kaldığında onclick tamamen siliniyor ve
                    # pop-up hiç açılmıyordu. Artık görsel varsa pop-up her zaman çalışır.
                    popup_img = (value or el.get("src") or "").strip()
                    if popup_img:
                        cat_label = {"kartvizit": "Kartvizit", "tabela": "Tabela"}.get(effective_cat or "", "Proje")
                        title_val = (ptitle if ptitle is not None else (port_container.find("h4").get_text() if port_container.find("h4") else "")).replace("'", "\\'")
                        popup_img_esc = popup_img.replace("'", "\\'")
                        port_container["onclick"] = f"openMediaModal('{popup_img_esc}', '{title_val}', '{cat_label}')"
                    else:
                        port_container["onclick"] = ""

            # tabela alt-tür data-subcat attribute (site tarafındaki filterTabelaSub
            # fonksiyonu bu attribute'u okuyor; "data-sub" YANLIŞTI, kategori filtresi
            # bu yüzden çalışmıyordu)
            if sub is not None:
                port_container["data-subcat"] = sub

            # h4 güncelle
            if ptitle is not None:
                h4 = port_container.find("h4")
                if h4:
                    h4.clear()
                    h4.append(NavigableString("" if is_delete else ptitle))

    elif el.name in ("input", "textarea"):
        el["placeholder"] = value
    else:  # span veya option -> düz metin
        el.clear()
        el.append(NavigableString(value))

    with open(full, "w", encoding="utf-8") as f:
        f.write(str(soup))

    return jsonify(ok=True)


@app.route("/api/save-meta", methods=["POST"])
@login_required
def api_save_meta():
    data = request.get_json(force=True, silent=True) or {}
    page = data.get("page")
    title = data.get("title", "")
    description = data.get("description", "")

    full = safe_page(page)
    with open(full, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")

    backup_file(full)

    if soup.title:
        soup.title.string = title
    elif soup.head:
        new_title = soup.new_tag("title")
        new_title.string = title
        soup.head.append(new_title)

    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag:
        desc_tag["content"] = description
    elif soup.head:
        new_meta = soup.new_tag("meta")
        new_meta["name"] = "description"
        new_meta["content"] = description
        soup.head.append(new_meta)

    with open(full, "w", encoding="utf-8") as f:
        f.write(str(soup))

    return jsonify(ok=True)


# ----------------------------------------------------------------------
# API - GÖRSEL YÜKLEME (bilgisayardan PNG/JPG vb. dosya yükleme)
# ----------------------------------------------------------------------

@app.route("/api/upload-image", methods=["POST"])
@login_required
def api_upload_image():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(ok=False, error="Dosya seçilmedi"), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        return jsonify(ok=False, error="Desteklenmeyen dosya türü. İzin verilenler: " + ", ".join(sorted(ALLOWED_IMAGE_EXT))), 400

    fname = optimize_and_save_image(file, UPLOADS_DIR)

    url = f"/static/uploads/{fname}"
    return jsonify(ok=True, url=url)


# ----------------------------------------------------------------------
# API - DEMO SİTELER (kök dizindeki demo-siteler/ klasöründeki hazır siteler)
# ----------------------------------------------------------------------

@app.route("/api/demo-sites", methods=["GET"])
@login_required
def api_list_demo_sites():
    """Admin panelindeki 'Demo Klasörü' seçicisi için demo-siteler/ altındaki
    klasörleri döndürür (panelde otomatik tamamlama / seçim listesi olarak kullanılır)."""
    return jsonify(ok=True, sites=list_demo_sites())


# ----------------------------------------------------------------------
# API - PORTFOLYO YÖNETİMİ (yeni proje ekleme / tamamen silme)
# ----------------------------------------------------------------------

@app.route("/api/add-portfolio-item", methods=["POST"])
@login_required
def api_add_portfolio_item():
    data = request.get_json(force=True, silent=True) or {}
    cat = data.get("cat", "web")
    if cat not in PORT_ITEM_TEMPLATES:
        return jsonify(ok=False, error="Geçersiz kategori"), 400

    full = safe_page("portfolyo.html")
    with open(full, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")
    ensure_ids_and_extract(soup)  # mevcut kimliklerin tutarlı olduğundan emin ol

    grid = get_port_grid(soup, cat)
    if grid is None:
        return jsonify(ok=False, error="Kategori bölümü bulunamadı"), 404

    fragment = BeautifulSoup(PORT_ITEM_TEMPLATES[cat], "html.parser")
    new_item = fragment.find("div", class_="port-item")
    new_item.extract()
    grid.append(new_item)

    update_port_count(soup, cat)

    # Yeni eklenen görsele/karta kalıcı data-eid ata
    items, images, placeholders = ensure_ids_and_extract(soup)

    backup_file(full)
    with open(full, "w", encoding="utf-8") as f:
        f.write(str(soup))

    # Az önce eklenen kartı (aynı kategoride en son sırada olan) bul ve döndür
    new_img = None
    for im in reversed(images):
        if im.get("cat") == cat:
            new_img = im
            break

    return jsonify(ok=True, item=new_img)


@app.route("/api/delete-portfolio-item", methods=["POST"])
@login_required
def api_delete_portfolio_item():
    data = request.get_json(force=True, silent=True) or {}
    item_id = data.get("id")
    if not item_id:
        return jsonify(ok=False, error="Kimlik (id) eksik"), 400

    full = safe_page("portfolyo.html")
    with open(full, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")

    img = soup.find("img", attrs={"data-eid": item_id})
    if img is None:
        return jsonify(ok=False, error="Öğe bulunamadı, sayfayı yeniden yükleyin"), 404

    # img'i kapsayan .port-item kart konteynerini bul
    container = img.parent
    depth = 0
    while container is not None and depth < 8:
        classes = container.get("class") or []
        if "port-item" in classes:
            break
        container = container.parent
        depth += 1

    if container is None or "port-item" not in (container.get("class") or []):
        return jsonify(ok=False, error="Proje kartı bulunamadı"), 404

    cat = container.get("data-cat")

    backup_file(full)
    container.decompose()  # kartı DOM'dan tamamen kaldır (yarım/kırık kart bırakmaz)

    if cat:
        update_port_count(soup, cat)

    with open(full, "w", encoding="utf-8") as f:
        f.write(str(soup))

    return jsonify(ok=True)


# ----------------------------------------------------------------------
# API - YEDEKLER (her kayıtta otomatik alınan yedekleri listeleme / geri yükleme)
# ----------------------------------------------------------------------

@app.route("/api/backups/<page>", methods=["GET"])
@login_required
def api_list_backups(page):
    """Bir sayfaya ait otomatik yedekleri en yeniden en eskiye sıralı döndürür."""
    full = safe_page(page)  # sayfanın gerçekten var olduğunu doğrular
    name = os.path.basename(full)
    pattern = os.path.join(BACKUP_DIR, f"{name}.*.bak")
    backups = []
    for path in glob.glob(pattern):
        fname = os.path.basename(path)
        # Beklenen biçim: sayfa.html.YYYYMMDD_HHMMSS.bak
        m = re.match(re.escape(name) + r"\.(\d{8}_\d{6})\.bak$", fname)
        if not m:
            continue
        ts_raw = m.group(1)
        try:
            dt = datetime.datetime.strptime(ts_raw, "%Y%m%d_%H%M%S")
            label = dt.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            label = ts_raw
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        backups.append({"filename": fname, "label": label, "ts": ts_raw, "size": size})
    backups.sort(key=lambda b: b["ts"], reverse=True)
    return jsonify(ok=True, page=name, backups=backups)


@app.route("/api/restore-backup", methods=["POST"])
@login_required
def api_restore_backup():
    """Seçilen yedeği geri yükler. Geri yüklemeden önce mevcut hâlin de yedeğini alır
    (böylece geri yükleme kendisi de geri alınabilir)."""
    data = request.get_json(force=True, silent=True) or {}
    page = data.get("page")
    filename = data.get("filename")
    if not filename:
        return jsonify(ok=False, error="Yedek dosyası belirtilmedi"), 400

    full = safe_page(page)
    name = os.path.basename(full)

    safe_backup_name = os.path.basename(filename)
    if not re.match(re.escape(name) + r"\.\d{8}_\d{6}\.bak$", safe_backup_name):
        return jsonify(ok=False, error="Geçersiz yedek dosyası"), 400

    backup_path = os.path.join(BACKUP_DIR, safe_backup_name)
    if not os.path.isfile(backup_path):
        return jsonify(ok=False, error="Yedek bulunamadı"), 404

    backup_file(full)  # geri yüklemeden önce mevcut durumu da yedekle (geri alınabilsin)
    shutil.copy2(backup_path, full)

    return jsonify(ok=True)


# ----------------------------------------------------------------------
# API - LOGO & FAVICON (tüm sayfalarda tek seferde günceller)
# ----------------------------------------------------------------------

@app.route("/api/site-settings", methods=["GET"])
@login_required
def api_site_settings():
    return jsonify(ok=True, settings=load_config())


# ----------------------------------------------------------------------
# API - GENEL AYARLAR (Telefon / Adres / E-posta / Sosyal Medya)
# ----------------------------------------------------------------------

@app.route("/api/settings", methods=["GET"])
@login_required
def api_get_settings():
    return jsonify(ok=True, settings=load_settings())


@app.route("/api/save-settings", methods=["POST"])
@login_required
def api_save_settings():
    data = request.get_json(force=True, silent=True) or {}
    updated = save_settings(data)
    return jsonify(ok=True, settings=updated)


@app.route("/api/upload-logo", methods=["POST"])
@login_required
def api_upload_logo():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(ok=False, error="Dosya seçilmedi"), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        return jsonify(ok=False, error="Desteklenmeyen dosya türü. İzin verilenler: " + ", ".join(sorted(ALLOWED_IMAGE_EXT))), 400

    fname = optimize_and_save_image(file, UPLOADS_DIR, prefix="logo-")
    url = f"/static/uploads/{fname}"

    updated_pages = []
    for page_info in list_brand_pages():
        full = safe_brand_page(page_info["file"])
        with open(full, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")

        # Bir sayfada logo hem üst menüde (header) hem de alt bilgide (footer)
        # gösterildiği için TÜM logo-img / logo-text çiftleri güncellenir.
        # (admin.html dahil - yönetim paneli de aynı logoyu kullanır.)
        logo_imgs = soup.find_all("img", attrs={"data-role": "logo-img"})
        logo_texts = soup.find_all(attrs={"data-role": "logo-text"})
        if not logo_imgs:
            continue

        backup_file(full)
        for logo_img in logo_imgs:
            logo_img["src"] = url
            classes = [c for c in logo_img.get("class", []) if c != "hidden"]
            logo_img["class"] = classes
        for logo_text in logo_texts:
            cls = logo_text.get("class", [])
            if "hidden" not in cls:
                cls.append("hidden")
            logo_text["class"] = cls

        with open(full, "w", encoding="utf-8") as f:
            f.write(str(soup))
        updated_pages.append(page_info["file"])

    cfg = load_config()
    cfg["logo_url"] = url
    save_config(cfg)

    return jsonify(ok=True, url=url, updated_pages=updated_pages)


@app.route("/api/reset-logo", methods=["POST"])
@login_required
def api_reset_logo():
    updated_pages = []
    for page_info in list_brand_pages():
        full = safe_brand_page(page_info["file"])
        with open(full, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")

        logo_imgs = soup.find_all("img", attrs={"data-role": "logo-img"})
        logo_texts = soup.find_all(attrs={"data-role": "logo-text"})
        if not logo_imgs:
            continue

        backup_file(full)
        for logo_img in logo_imgs:
            logo_img["src"] = ""
            cls = logo_img.get("class", [])
            if "hidden" not in cls:
                cls.append("hidden")
            logo_img["class"] = cls
        for logo_text in logo_texts:
            logo_text["class"] = [c for c in logo_text.get("class", []) if c != "hidden"]

        with open(full, "w", encoding="utf-8") as f:
            f.write(str(soup))
        updated_pages.append(page_info["file"])

    cfg = load_config()
    cfg["logo_url"] = None
    save_config(cfg)

    return jsonify(ok=True, updated_pages=updated_pages)


@app.route("/api/upload-favicon", methods=["POST"])
@login_required
def api_upload_favicon():
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify(ok=False, error="Dosya seçilmedi"), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_FAVICON_EXT:
        return jsonify(ok=False, error="Desteklenmeyen dosya türü. İzin verilenler: " + ", ".join(sorted(ALLOWED_FAVICON_EXT))), 400

    fname, _ = unique_filename(file.filename, prefix="favicon-")
    dest = os.path.join(UPLOADS_DIR, fname)
    file.save(dest)
    url = f"/static/uploads/{fname}"

    mime = {"png": "image/png", "ico": "image/x-icon", "svg": "image/svg+xml"}.get(ext, "image/png")

    updated_pages = []
    for page_info in list_brand_pages():
        full = safe_brand_page(page_info["file"])
        with open(full, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")

        icon_link = soup.find("link", attrs={"rel": "icon"})
        if icon_link is None and soup.head:
            icon_link = soup.new_tag("link")
            icon_link["rel"] = "icon"
            soup.head.append(icon_link)
        if icon_link is None:
            continue

        backup_file(full)
        icon_link["href"] = url
        icon_link["type"] = mime

        with open(full, "w", encoding="utf-8") as f:
            f.write(str(soup))
        updated_pages.append(page_info["file"])

    cfg = load_config()
    cfg["favicon_url"] = url
    save_config(cfg)

    return jsonify(ok=True, url=url, updated_pages=updated_pages)


# ----------------------------------------------------------------------
# API - BUL & DEĞİŞTİR (önce arama/önizleme, sonra sadece seçilenleri değiştirme)
# ----------------------------------------------------------------------

@app.route("/api/find-replace-search", methods=["POST"])
@login_required
def api_find_replace_search():
    data = request.get_json(force=True, silent=True) or {}
    find = data.get("find", "")
    case_sensitive = bool(data.get("case_sensitive", False))
    pages = data.get("pages") or []

    if not find:
        return jsonify(ok=False, error="Aranacak metin boş olamaz"), 400

    all_pages = [p["file"] for p in list_site_pages()]
    target_pages = all_pages if (not pages or "all" in pages) else [p for p in pages if p in all_pages]

    matches = []
    for page in target_pages:
        full = safe_page(page)
        with open(full, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        ensure_ids_and_extract(soup)  # id'lerin tutarlı olduğundan emin ol

        for span in soup.find_all("span", attrs={"data-eid": True}):
            txt = span.get_text()
            n = count_occurrences(txt, find, case_sensitive)
            if n:
                matches.append({
                    "page": page, "id": span["data-eid"], "kind": "text",
                    "count": n, "context": nearest_context(span),
                    "snippet": make_snippet(txt, find, case_sensitive),
                })
        for opt in soup.find_all("option", attrs={"data-eid": True}):
            txt = opt.get_text()
            n = count_occurrences(txt, find, case_sensitive)
            if n:
                matches.append({
                    "page": page, "id": opt["data-eid"], "kind": "option",
                    "count": n, "context": "Seçenek (Dropdown)",
                    "snippet": make_snippet(txt, find, case_sensitive),
                })
        for el in soup.find_all(["input", "textarea"], attrs={"data-eid": True}):
            ph = el.get("placeholder", "")
            n = count_occurrences(ph, find, case_sensitive)
            if n:
                matches.append({
                    "page": page, "id": el["data-eid"], "kind": "placeholder",
                    "count": n, "context": nearest_context(el),
                    "snippet": make_snippet(ph, find, case_sensitive),
                })

    return jsonify(ok=True, matches=matches, total=sum(m["count"] for m in matches))


@app.route("/api/find-replace-apply", methods=["POST"])
@login_required
def api_find_replace_apply():
    data = request.get_json(force=True, silent=True) or {}
    find = data.get("find", "")
    replace = data.get("replace", "")
    case_sensitive = bool(data.get("case_sensitive", False))
    selections = data.get("selections") or []  # [{page, id}, ...]

    if not find:
        return jsonify(ok=False, error="Aranacak metin boş olamaz"), 400
    if not selections:
        return jsonify(ok=False, error="Değiştirilecek hiçbir öğe seçilmedi"), 400

    by_page = {}
    for sel in selections:
        by_page.setdefault(sel.get("page"), set()).add(sel.get("id"))

    results = []
    for page, ids in by_page.items():
        try:
            full = safe_page(page)
        except Exception:
            continue
        with open(full, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        ensure_ids_and_extract(soup)

        changed = 0
        for eid in ids:
            el = soup.find(attrs={"data-eid": eid})
            if el is None:
                continue
            if el.name in ("span", "option"):
                txt = el.get_text()
                new_txt, n = literal_replace(txt, find, replace, case_sensitive)
                if n:
                    el.clear()
                    el.append(NavigableString(new_txt))
                    changed += n
            elif el.name in ("input", "textarea"):
                ph = el.get("placeholder", "")
                new_txt, n = literal_replace(ph, find, replace, case_sensitive)
                if n:
                    el["placeholder"] = new_txt
                    changed += n

        if changed:
            backup_file(full)
            with open(full, "w", encoding="utf-8") as f:
                f.write(str(soup))

        results.append({"page": page, "degisiklik_sayisi": changed})

    return jsonify(ok=True, results=results)


# Eski toplu (önizlemesiz) bul&değiştir uç noktası geriye dönük uyumluluk için korunur.
@app.route("/api/find-replace", methods=["POST"])
@login_required
def api_find_replace():
    data = request.get_json(force=True, silent=True) or {}
    find = data.get("find", "")
    replace = data.get("replace", "")
    case_sensitive = bool(data.get("case_sensitive", False))
    pages = data.get("pages") or []

    if not find:
        return jsonify(ok=False, error="Aranacak metin boş olamaz"), 400

    all_pages = [p["file"] for p in list_site_pages()]
    target_pages = all_pages if (not pages or "all" in pages) else [p for p in pages if p in all_pages]

    results = []
    for page in target_pages:
        full = safe_page(page)
        with open(full, "r", encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        ensure_ids_and_extract(soup)

        changed = 0
        for span in soup.find_all("span", attrs={"data-eid": True}):
            txt = span.get_text()
            new_txt, n = literal_replace(txt, find, replace, case_sensitive)
            if n:
                span.clear()
                span.append(NavigableString(new_txt))
                changed += n
        for opt in soup.find_all("option", attrs={"data-eid": True}):
            txt = opt.get_text()
            new_txt, n = literal_replace(txt, find, replace, case_sensitive)
            if n:
                opt.clear()
                opt.append(NavigableString(new_txt))
                changed += n
        for el in soup.find_all(["input", "textarea"], attrs={"data-eid": True}):
            ph = el.get("placeholder", "")
            new_txt, n = literal_replace(ph, find, replace, case_sensitive)
            if n:
                el["placeholder"] = new_txt
                changed += n

        if changed:
            backup_file(full)
            with open(full, "w", encoding="utf-8") as f:
                f.write(str(soup))

        results.append({"page": page, "degisiklik_sayisi": changed})

    return jsonify(ok=True, results=results)


# ----------------------------------------------------------------------
# SAYFA SUNUMU (Site + Admin Paneli)
# ----------------------------------------------------------------------
# CSS/JS/görseller artık Flask'in varsayılan "/static/<path>" rotasıyla
# static/ klasöründen otomatik sunulur (ayrı bir route gerekmez).
# HTML sayfaları templates/ içinden render_template ile sunulur; böylece
# sayfa içindeki {{ url_for('static', filename='...') }} ifadeleri
# Flask/Jinja tarafından gerçek statik dosya adreslerine dönüştürülür.

@app.route("/admin")
@app.route("/admin/")
def admin_panel():
    return render_template("admin.html")


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/robots.txt")
def robots_txt():
    # templates/robots.txt içinde {{ settings.site_url }} kullanır, böylece
    # admin panelinden değiştirilen alan adı buraya da otomatik yansır.
    return Response(render_template("robots.txt"), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    # templates/sitemap.xml içinde {{ settings.site_url }} kullanır, böylece
    # admin panelinden değiştirilen alan adı buraya da otomatik yansır.
    return Response(render_template("sitemap.xml"), mimetype="application/xml")


@app.route("/demo-siteler/<folder>/", defaults={"subpath": ""})
@app.route("/demo-siteler/<folder>/<path:subpath>")
def serve_demo_site(folder, subpath):
    """Portfolyodaki 'canlı demo' web siteleri için kök dizindeki demo-siteler/
    klasöründen statik dosya sunar. Örn: /demo-siteler/kafe-sitesi/ -> o klasörün
    içindeki index.html; /demo-siteler/kafe-sitesi/css/stil.css -> o klasördeki dosya.
    Path traversal ('..' vb.) girişimlerine karşı klasör isimleri ve alt yol
    her istekte demo-siteler/ kökünün gerçekten içinde olacak şekilde doğrulanır."""
    if not folder or folder in (".", "..") or "/" in folder or "\\" in folder:
        abort(404)

    folder_dir = os.path.join(DEMO_SITES_DIR, folder)
    if not _is_within_dir(DEMO_SITES_DIR, folder_dir) or not os.path.isdir(folder_dir):
        abort(404)

    rel = subpath or "index.html"
    target = os.path.normpath(os.path.join(folder_dir, rel))
    if not _is_within_dir(folder_dir, target):
        abort(404)

    if os.path.isdir(target):
        target = os.path.join(target, "index.html")

    if not os.path.isfile(target):
        abort(404)

    rel_to_folder = os.path.relpath(target, folder_dir)
    return send_from_directory(folder_dir, rel_to_folder)


@app.route("/<path:filename>")
def site_pages(filename):
    """SEO dostu, çok kelimeli adresleri (ör. /web-tasarim-tabela)
    ilgili şablona render eder. Eski '.html' uzantılı adresler ve bir önceki
    tek kelimelik kısa adresler (ör. /hizmetler.html, /hizmetler) arama motoru
    sıralamasını ve gelen bağlantıları (backlink) korumak için yeni adrese
    301 (kalıcı) yönlendirilir. Bunların dışındaki her şey (admin.html,
    .py dosyaları, rastgele/çok parçalı yollar) reddedilir."""
    name = os.path.basename(filename)
    if filename != name:
        abort(404)

    if name.endswith(".html"):
        stem = name[: -len(".html")]
        if stem == "index":
            return redirect("/", code=301)
        if stem in CLEAN_SLUGS:
            return redirect(f"/{stem}", code=301)
        if stem in OLD_SHORT_SLUGS:
            return redirect(f"/{OLD_SHORT_SLUGS[stem]}", code=301)
        abort(404)

    if name in OLD_SHORT_SLUGS:
        return redirect(f"/{OLD_SHORT_SLUGS[name]}", code=301)

    template_name = CLEAN_SLUGS.get(name)
    if not template_name:
        abort(404)
    return render_template(template_name)


# ----------------------------------------------------------------------
# NOT: Bu blok sadece "python app.py" ile DOĞRUDAN çalıştırıldığında (yani
# localde) devreye girer. Gerçek hosting'de bunun yerine gunicorn gibi bir
# WSGI sunucusu app.py'yi bir modül olarak import eder (ör.
# "gunicorn app:app") ve bu blok hiç çalışmaz; bu yüzden production'da
# host/port/debug ayarları için ayrıca bir işlem yapmanıza gerek yoktur.
if __name__ == "__main__":
    # Hosting sağlayıcısı (varsa) hangi port'u dinlememizi istediğini PORT
    # ortam değişkeniyle bildirir; localde bu değişken olmadığından 5000
    # kullanılır.
    port = int(os.environ.get("PORT", 5000))
    # "0.0.0.0" hem localde (http://127.0.0.1:PORT üzerinden) hem de
    # hosting'de (dışarıdan gelen bağlantılara açık) sorunsuz çalışır.
    host = "0.0.0.0"

    print("=" * 60)
    print(" Sokaktan Dijitale - Yönetim Paneli")
    if IS_PRODUCTION:
        print(" Ortam : PRODUCTION (canlı)")
    else:
        print(" Ortam : DEVELOPMENT (yerel)")
        print(f" Panel : http://127.0.0.1:{port}/admin")
        print(f" Site  : http://127.0.0.1:{port}/")
        print(f" Şifre : {ADMIN_PASSWORD}  (ADMIN_SIFRE ortam değişkeniyle değiştirin)")
    print("=" * 60)

    # debug=True sadece localde aktif olur; canlı ortamda güvenlik açığı
    # oluşturmaması (Werkzeug hata ayıklayıcısı üzerinden kod çalıştırma
    # riski) için otomatik olarak kapanır.
    app.run(host=host, port=port, debug=not IS_PRODUCTION)