# Sokaktan Dijitale — Çok Sayfalı Web Sitesi

Bu proje, tek sayfa (SPA) yapıdaki orijinal siteden dönüştürülerek **çok sayfalı, SEO uyumlu**
ve dosya bazında düzenli bir yapıya kavuşturulmuştur.

## 📁 Klasör Yapısı

```
├── index.html            → Ana Sayfa
├── hakkimizda.html        → Kurumsal
├── hizmetler.html         → Hizmetlerimiz
├── portfolyo.html         → Portfolyo
├── fiyatlandirma.html     → Paketler & Fiyatlar
├── iletisim.html          → İletişim
├── css/
│   └── style.css          → Tüm özel stiller (Tailwind dışı)
├── js/
│   ├── tailwind-config.js → Tailwind tema (renkler, animasyonlar)
│   └── main.js            → Menü, modal, filtre, bildirim vb. tüm etkileşimler
├── images/                → Kendi görsellerinizi buraya ekleyin
├── robots.txt
└── sitemap.xml
```

## 🔍 Yapılan SEO İyileştirmeleri

- Her sayfa **kendi URL'sine, `<title>` ve `<meta description>`** etiketine sahip (tek bir SPA
  yerine gerçek, aranabilir/crawl edilebilir 6 ayrı sayfa).
- Her sayfada **tek bir `<h1>`** başlığı (arama motorları için doğru başlık hiyerarşisi).
- `rel="canonical"`, Open Graph ve Twitter Card etiketleri eklendi.
- Ana sayfa ve İletişim sayfasına **Schema.org (JSON-LD) yapılandırılmış veri** eklendi
  (işletme adı, adres, telefon, sosyal medya).
- `robots.txt` ve `sitemap.xml` dosyaları eklendi.
- Ana menü ve alt bilgi (footer) linkleri artık gerçek `<a href="...">` bağlantıları — arama
  motorları tüm sayfaları kolayca keşfedebilir.
- Görsellerde `loading="lazy"` ve açıklayıcı `alt` metinleri korundu.

## 🛠️ Yönetim Paneli (Admin)

Site içeriğini, görselleri, logo/favicon'u ve arama motoru bilgilerini kod bilmeden
düzenlemek için `app.py` ile çalışan bir yönetim paneli dahildir.

### Kurulum
```bash
pip install -r requirements.txt
```

### Çalıştırma
```bash
python app.py
```
- Panel: **http://127.0.0.1:5000/admin**
- Site:  **http://127.0.0.1:5000/**
- Varsayılan şifre: `sokaktan2026`
  (değiştirmek için `ADMIN_SIFRE` ortam değişkenini kullanın)

### Panel Bölümleri
Panel artık kategorilere ayrılmıştır, tek bir uzun sayfa değildir:

- **Sayfalar** (sol menü) → her sayfa için ayrı çalışma alanı, 3 sekme:
  - **İçerik**: tüm metinler ve form placeholder'ları, arama kutusuyla filtrelenebilir.
  - **Görseller**: her görsel için ayrı kart; **bilgisayarınızdan PNG/JPG/WEBP
    dosyası doğrudan sürükleyip bırakarak veya seçerek** yükleyebilirsiniz,
    isterseniz URL de yapıştırabilirsiniz.
  - **SEO**: sayfa başlığı ve meta açıklaması.
- **Logo & Favicon** (Genel Ayarlar) → kendi PNG logonuzu ve favicon'unuzu
  yükleyin; yüklediğiniz anda **tüm sayfalarda otomatik olarak güncellenir**.
  "Varsayılan yazılı logoya dön" ile istediğiniz zaman eski duruma dönebilirsiniz.
- **Bul & Değiştir** (Genel Ayarlar) → önce **Ara** butonuyla metnin geçtiği
  tüm yerleri sayfa/bölüm bilgisiyle listeler, ardından **yalnızca seçtiğiniz**
  sonuçlarda değişikliği uygularsınız (tümünü aynı anda değiştirmek zorunda değilsiniz).

Her kaydetmeden önce dosyanın otomatik yedeği `admin/_yedekler/` klasörüne alınır.

## ⚙️ Nasıl Çalışır?

- Site tamamen **statiktir**, herhangi bir sunucu/derleme adımına ihtiyaç duymaz.
- `app.py` sadece yönetim paneli için gereklidir; siteyi başka bir statik barındırma
  hizmetine (örn. Netlify, herhangi bir hosting) yüklerken `app.py` ve `admin/`
  klasörünü dahil etmeyebilirsiniz — ama içerik güncellemeye devam etmek istiyorsanız
  ikisini de saklayın.
  `index.html` dosyasını çift tıklayarak veya herhangi bir statik hosting'e (Netlify, Vercel,
  cPanel, GitHub Pages vb.) yükleyerek yayınlayabilirsiniz.
- Tailwind CSS ve Lucide İkonlar hâlâ CDN üzerinden yüklenmektedir (internet bağlantısı gerekir).
- Sayfa içi bazı kartlar/görseller JavaScript (`main.js` içindeki `navigateSPA()`) ile ilgili
  sayfaya yönlendirme yapar; ana menü/alt menü linkleri ise doğrudan HTML bağlantısıdır.

## ✏️ Yayına Almadan Önce Güncellemeniz Gerekenler

1. **Alan adı**: `js`/`html` dosyalarındaki `https://www.sokaktandijitale.com/` adresini kendi
   gerçek alan adınızla değiştirin (canonical, Open Graph, sitemap.xml, robots.txt içinde geçiyor).
2. **Görseller**: Şu an `placehold.co` üzerinden gelen geçici görseller var. Gerçek görsellerinizi
   `images/` klasörüne ekleyip `<img src="...">` adreslerini güncelleyin.
3. **İletişim bilgileri**: Telefon, WhatsApp, e-posta ve adres bilgileri `iletisim.html`,
   `templates` (header/footer) ve JSON-LD içinde örnek olarak girilmiştir, gerçek bilgilerinizle
   değiştirin.
4. **Google Search Console**: Yayına aldıktan sonra `sitemap.xml` dosyasını Google Search
   Console'a ekleyerek indekslenmeyi hızlandırabilirsiniz.
