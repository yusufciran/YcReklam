/*
 * Sokaktan Dijitale - Trafik Analiz Scripti
 * ==========================================
 * Bu dosya sitenin her sayfasına eklenir ve şunları admin panelindeki
 * "Trafik Analizi" bölümüne göndermek için sunucuya bildirir:
 *   - Hangi sayfanın kaç kez görüntülendiği
 *   - Sayfada kaç saniye kalındığı
 *   - Kaç farklı (tekil) ziyaretçi geldiği
 *   - Ziyaretin nereden geldiği (özellikle Meta/Facebook-Instagram reklamı mı)
 *
 * Kişisel veri toplanmaz: sadece tarayıcıda üretilen anonim bir kimlik
 * (visitor_id) kullanılır, isim/e-posta/IP gibi bilgiler saklanmaz.
 */
(function () {
  "use strict";

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      var r = (Math.random() * 16) | 0, v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  // Kalıcı ziyaretçi kimliği (tarayıcı/cihaz bazlı, "kaç farklı kişi girdi" sayımı için)
  function getVisitorId() {
    try {
      var id = localStorage.getItem("sd_visitor_id");
      if (!id) {
        id = uuid();
        localStorage.setItem("sd_visitor_id", id);
      }
      return id;
    } catch (e) {
      return "no-storage-" + uuid();
    }
  }

  // Oturum kimliği (tarayıcı sekmesi/oturumu bazlı)
  function getSessionId() {
    try {
      var id = sessionStorage.getItem("sd_session_id");
      if (!id) {
        id = uuid();
        sessionStorage.setItem("sd_session_id", id);
      }
      return id;
    } catch (e) {
      return "no-storage-" + uuid();
    }
  }

  function getParam(params, name) {
    var v = params.get(name);
    return v ? v.trim().slice(0, 200) : null;
  }

  // Reklam kaynağı (utm_*, fbclid, gclid) SADECE ziyaretçinin sitedeki ilk
  // sayfasının URL'sinde bulunur; aynı sekmede başka bir sayfaya geçildiğinde
  // bu parametreler URL'de artık yoktur. Bu yüzden bilgiyi oturum boyunca
  // (sessionStorage - session_id ile aynı ömürde) saklayıp, sonraki her
  // /api/track çağrısında da kullanıyoruz. Böylece "Meta reklamından geldi"
  // etiketi sadece giriş sayfasında değil, o oturumdaki TÜM sayfa
  // görüntülemelerinde doğru şekilde uygulanır.
  function getAttribution(params) {
    var fromUrl = {
      utm_source: getParam(params, "utm_source"),
      utm_medium: getParam(params, "utm_medium"),
      utm_campaign: getParam(params, "utm_campaign"),
      fbclid: getParam(params, "fbclid"),
      gclid: getParam(params, "gclid"),
    };
    var hasUrlAttribution =
      fromUrl.utm_source || fromUrl.utm_medium || fromUrl.utm_campaign ||
      fromUrl.fbclid || fromUrl.gclid;

    if (hasUrlAttribution) {
      try { sessionStorage.setItem("sd_attribution", JSON.stringify(fromUrl)); } catch (e) { /* yoksay */ }
      return fromUrl;
    }

    try {
      var raw = sessionStorage.getItem("sd_attribution");
      if (raw) return JSON.parse(raw);
    } catch (e) { /* yoksay */ }

    return fromUrl; // hiçbir yerde yok - hepsi null
  }

  function sendBeaconJson(url, payload) {
    var body = JSON.stringify(payload);
    try {
      if (navigator.sendBeacon) {
        var blob = new Blob([body], { type: "application/json" });
        navigator.sendBeacon(url, blob);
        return;
      }
    } catch (e) { /* devam et, fetch dene */ }
    try {
      fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: body, keepalive: true });
    } catch (e) { /* sessizce yok say - analiz asla site işlevini bozmamalı */ }
  }

  function init() {
    var params = new URLSearchParams(window.location.search);
    var visitorId = getVisitorId();
    var sessionId = getSessionId();

    var attribution = getAttribution(params);

    var payload = {
      visitor_id: visitorId,
      session_id: sessionId,
      page: window.location.pathname || "/",
      referrer: document.referrer || null,
      utm_source: attribution.utm_source,
      utm_medium: attribution.utm_medium,
      utm_campaign: attribution.utm_campaign,
      fbclid: attribution.fbclid,
      gclid: attribution.gclid,
    };

    var visitId = null;
    var startTime = Date.now();
    var lastSentSeconds = 0;

    fetch("/api/track", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data && data.id) visitId = data.id; })
      .catch(function () { /* takip başarısız olsa da kullanıcı deneyimi etkilenmez */ });

    function sendDuration() {
      if (!visitId) return;
      var seconds = Math.round((Date.now() - startTime) / 1000);
      if (seconds <= lastSentSeconds) return;
      lastSentSeconds = seconds;
      sendBeaconJson("/api/track-duration", { id: visitId, seconds: seconds });
    }

    // Sekme arka plana alındığında / kapatıldığında son süreyi gönder
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") sendDuration();
    });
    window.addEventListener("pagehide", sendDuration);

    // Uzun süre açık kalan sekmeler için periyodik güncelleme (20 sn'de bir)
    setInterval(sendDuration, 20000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
