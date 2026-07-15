# Demo Siteler Klasörü

Bu klasör, portfolyoda "canlı demo" olarak gösterilecek tamamlanmış web sitesi
projelerini barındırır. Her müşteri/demo sitesi kendi alt klasöründe durur.

## Nasıl kullanılır?

1. Bu klasörün (`demo-siteler/`) içine yeni bir klasör oluşturun.
   Klasör adı, sitenin adresinde görünecek kısımdır (örn: `kafe-sitesi`).
2. O klasörün içine sitenin dosyalarını koyun. En az bir `index.html` dosyası
   olmalı. CSS, JS ve görsel dosyalarını da aynı klasörün içinde (isterseniz
   alt klasörlerde, örn. `css/`, `js/`, `img/`) tutabilirsiniz — hepsi otomatik
   olarak sunulur.
3. Site şu adreste yayında olur:

   ```
   https://siteniz.com/demo-siteler/kafe-sitesi/
   ```

4. Admin panelinde **Portfolyo Yönetimi → Web** sekmesinden "Yeni Proje Ekle"
   veya mevcut bir kartı düzenleyerek "Demo Klasörü" seçeneğini kullanın ve
   klasör adını (örn. `kafe-sitesi`) yazın/seçin. Panel otomatik olarak
   `/demo-siteler/kafe-sitesi/` adresine bağlar.
   - İsterseniz bunun yerine "Harici Link" seçeneğiyle dışarıdaki (başka bir
     alan adındaki) bir siteye de bağlantı verebilirsiniz.
   - Proje başlığı (kartta görünen isim) klasör adından tamamen bağımsızdır;
     istediğiniz herhangi bir başlığı girebilirsiniz.

## Örnek

`demo-siteler/ornek-kafe-sitesi/` klasörü, sistemin nasıl çalıştığını gösteren
basit bir örnektir. Gerçek projelerinizi eklemeye başladığınızda bu örnek
klasörü silebilirsiniz.
