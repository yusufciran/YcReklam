/* =====================================================
   SOKAKTAN DİJİTALE — Ana JavaScript Dosyası
   Çok sayfalı (multi-page) site için ortak site işlevleri
   ===================================================== */

// İkonları Yükle
lucide.createIcons();

/* -----------------------------------------------------
   1. SAYFA HARİTASI (PAGE MAP)
   SPA yerine gerçek çoklu sayfa yapısı kullanıldığı için
   navigateSPA() artık ilgili .html dosyasına yönlendirir.
------------------------------------------------------ */
const SD_PAGES = {
    home: '/',
    about: '/hakkimizda-bursa',
    services: '/web-tasarim-tabela',
    portfolio: '/portfolyo-ornekleri',
    pricing: '/web-tasarim-fiyatlari',
    contact: '/bursa-iletisim'
};

function navigateSPA(pageId, anchor) {
    const url = SD_PAGES[pageId] || '/';
    window.location.href = anchor ? `${url}#${anchor}` : url;
}

// Aynı sayfa içindeki bölümlere yumuşak kaydırma (ör. portfolyo alt kategorileri)
function smoothJumpTo(e, id) {
    if (e) e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (history.pushState) {
            history.pushState(null, null, `#${id}`);
        }
    }
    return false;
}

// Sayfa yüklendiğinde URL'de hash varsa ilgili bölüme kaydır (ör. portfolyo.html#portfolio-web)
function handleInitialHashScroll() {
    const hash = window.location.hash.substring(1);
    if (!hash) return;
    const targetEl = document.getElementById(hash);
    if (targetEl) {
        setTimeout(() => {
            targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 150);
    }
}
window.addEventListener('load', handleInitialHashScroll);

/* -----------------------------------------------------
   1.5 Masaüstü Açılır Menüler (Dokunmatik ekranlar için tıklama desteği)
------------------------------------------------------ */
document.querySelectorAll('.dropdown-wrapper > button').forEach(btn => {
    btn.addEventListener('click', (e) => {
        const wrapper = btn.parentElement;
        const wasOpen = wrapper.classList.contains('dropdown-open');
        document.querySelectorAll('.dropdown-wrapper').forEach(w => w.classList.remove('dropdown-open'));
        if (!wasOpen) {
            wrapper.classList.add('dropdown-open');
            e.stopPropagation();
        }
    });
});
document.addEventListener('click', () => {
    document.querySelectorAll('.dropdown-wrapper').forEach(w => w.classList.remove('dropdown-open'));
});

/* -----------------------------------------------------
   2. Mobil Menü Toggle İşlevi
------------------------------------------------------ */
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const mobileCloseBtn = document.getElementById('mobile-close-btn');
const mobileMenu = document.getElementById('mobile-menu');

function toggleMobileMenu() {
    if (!mobileMenu) return;
    if (mobileMenu.classList.contains('hidden')) {
        mobileMenu.classList.remove('hidden');
        mobileMenu.classList.add('flex');
        setTimeout(() => mobileMenu.classList.remove('opacity-0'), 10);
        document.body.style.overflow = 'hidden';
    } else {
        mobileMenu.classList.add('opacity-0');
        setTimeout(() => {
            mobileMenu.classList.add('hidden');
            mobileMenu.classList.remove('flex');
            document.body.style.overflow = '';
        }, 300);
    }
}

if (mobileMenuBtn) mobileMenuBtn.addEventListener('click', toggleMobileMenu);
if (mobileCloseBtn) mobileCloseBtn.addEventListener('click', toggleMobileMenu);

// Mobil Menü Akordeon (Alt Menü) Kontrolü
function toggleMobileSubmenu(key) {
    const submenu = document.getElementById(`submenu-${key}`);
    const chevron = document.getElementById(`chevron-${key}`);
    if (!submenu) return;

    const isOpen = submenu.classList.contains('open');

    document.querySelectorAll('.mobile-submenu.open').forEach(el => {
        if (el !== submenu) el.classList.remove('open');
    });
    document.querySelectorAll('[id^="chevron-"]').forEach(el => {
        if (el !== chevron) el.classList.remove('rotate-180');
    });

    submenu.classList.toggle('open', !isOpen);
    if (chevron) chevron.classList.toggle('rotate-180', !isOpen);
}

/* -----------------------------------------------------
   3. Header Scroll Efekti (Şeffaf / Blur geçişi)
------------------------------------------------------ */
const headerContainer = document.getElementById('nav-container');
if (headerContainer) {
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            headerContainer.classList.remove('glass-nav');
            headerContainer.classList.add('bg-brand-sand/95', 'backdrop-blur-xl', 'shadow-md', 'py-2');
            headerContainer.classList.remove('py-4');
        } else {
            headerContainer.classList.add('glass-nav');
            headerContainer.classList.remove('bg-brand-sand/95', 'backdrop-blur-xl', 'shadow-md', 'py-2');
            headerContainer.classList.add('py-4');
        }
    });
}

/* -----------------------------------------------------
   4. Özel Bildirim Sistemi
------------------------------------------------------ */
const notification = document.getElementById('notification');
const notificationText = document.getElementById('notification-text');

function showNotification(message) {
    if (!notification || !notificationText) return;
    notificationText.innerText = message;
    notification.classList.remove('translate-y-24', 'opacity-0');

    setTimeout(() => {
        notification.classList.add('translate-y-24', 'opacity-0');
    }, 4000);
}

// İletişim Formu Submit Yakalama
const contactForm = document.getElementById('main-contact-form');
if (contactForm) {
    // E-postanın "tam teyit" edilmesi için kullanılan sıkı doğrulama deseni
    // (sunucu tarafındaki EMAIL_RE ile aynı mantık).
    const EMAIL_PATTERN = /^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$/;

    function isValidEmail(value) {
        const v = (value || '').trim();
        if (!v || v.length > 254 || v.includes('..')) return false;
        return EMAIL_PATTERN.test(v);
    }

    const emailInput = document.getElementById('cf-eposta');
    const emailError = document.getElementById('cf-eposta-error');
    const submitBtn = document.getElementById('cf-submit-btn');
    const submitText = document.getElementById('cf-submit-text');

    function setEmailInvalid(invalid) {
        if (!emailInput) return;
        emailInput.classList.toggle('border-brand-rust', invalid);
        if (emailError) emailError.classList.toggle('hidden', !invalid);
    }

    if (emailInput) {
        emailInput.addEventListener('blur', () => {
            if (emailInput.value.trim()) setEmailInvalid(!isValidEmail(emailInput.value));
        });
        emailInput.addEventListener('input', () => setEmailInvalid(false));
    }

    contactForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const payload = {
            ad_soyad: (document.getElementById('cf-ad-soyad') || {}).value || '',
            telefon: (document.getElementById('cf-telefon') || {}).value || '',
            e_posta: (emailInput || {}).value || '',
            hizmet: (document.getElementById('cf-hizmet') || {}).value || '',
            mesaj: (document.getElementById('cf-mesaj') || {}).value || '',
            sayfa: window.location.pathname
        };

        if (!isValidEmail(payload.e_posta)) {
            setEmailInvalid(true);
            emailInput.focus();
            showNotification("Lütfen geçerli bir e-posta adresi girin.");
            return;
        }
        setEmailInvalid(false);

        if (!contactForm.reportValidity()) return;

        const originalText = submitText ? submitText.textContent : '';
        if (submitBtn) submitBtn.disabled = true;
        if (submitText) submitText.textContent = 'Gönderiliyor...';

        try {
            const res = await fetch('/api/contact-message', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json().catch(() => ({}));

            if (!res.ok || !data.ok) {
                const firstFieldError = data.fields && Object.values(data.fields)[0];
                showNotification(firstFieldError || data.error || "Mesaj gönderilemedi, lütfen tekrar deneyin.");
                if (data.fields && data.fields.e_posta) setEmailInvalid(true);
                return;
            }

            showNotification("Talebiniz başarıyla alındı! En kısa sürede dönüş yapacağız.");
            contactForm.reset();
            setEmailInvalid(false);
        } catch (err) {
            showNotification("Bağlantı hatası, lütfen tekrar deneyin.");
        } finally {
            if (submitBtn) submitBtn.disabled = false;
            if (submitText) submitText.textContent = originalText;
        }
    });
}

/* -----------------------------------------------------
   5. Tabela Alt Kategori Filtreleme
------------------------------------------------------ */
function filterTabelaSub(subcat) {
    const subButtons = document.querySelectorAll('.tabela-sub-btn');
    subButtons.forEach(btn => {
        btn.classList.remove('bg-brand-rust', 'text-white');
        btn.classList.add('bg-white', 'text-brand-charcoal', 'border', 'border-brand-charcoal/10');
        if (btn.getAttribute('onclick') === `filterTabelaSub('${subcat}')`) {
            btn.classList.remove('bg-white', 'text-brand-charcoal', 'border', 'border-brand-charcoal/10');
            btn.classList.add('bg-brand-rust', 'text-white');
        }
    });

    const items = document.querySelectorAll('#tabela-grid .port-item');
    const toShow = [];
    const toHide = [];
    items.forEach(item => {
        const matches = subcat === 'all' || item.getAttribute('data-subcat') === subcat;
        const isVisible = item.style.display !== 'none';
        if (matches) {
            toShow.push(item);
        } else if (isVisible) {
            toHide.push(item);
        }
    });

    // 1) Artık uyuşmayan kartları önce yumuşakça soldurup kaybet
    toHide.forEach(item => {
        item.classList.add('port-item-leaving');
    });

    const afterLeave = () => {
        toHide.forEach(item => {
            item.style.display = 'none';
            item.classList.remove('port-item-leaving');
        });

        // 2) Eşleşen kartları göster ve sırayla (staggered) belirsin
        toShow.forEach((item, i) => {
            item.style.display = 'block';
            item.classList.add('port-item-entering');
            item.classList.remove('port-item-entered');
            // Reflow ile animasyonun yeniden tetiklenmesini garanti et
            void item.offsetWidth;
            setTimeout(() => {
                item.classList.remove('port-item-entering');
                item.classList.add('port-item-entered');
            }, 40 + i * 60);
        });
    };

    if (toHide.length > 0) {
        setTimeout(afterLeave, 220);
    } else {
        afterLeave();
    }
}

// Web sitesi projelerini yeni sekmede aç
function openPortfolioWebsite(url) {
    window.open(url, '_blank', 'noopener');
}

/* -----------------------------------------------------
   Kartvizit & Tabela Görselleri İçin Pop-up Galeri
------------------------------------------------------ */
const mediaModal = document.getElementById('media-modal');
const mediaModalImg = document.getElementById('media-modal-img');
const mediaModalTitle = document.getElementById('media-modal-title');
const mediaModalTag = document.getElementById('media-modal-tag');

function openMediaModal(imgUrl, title, tag) {
    if (!mediaModal) return;
    mediaModalImg.classList.remove('img-loaded');
    mediaModalImg.src = imgUrl;
    mediaModalImg.alt = title;
    mediaModalTitle.innerText = title;
    mediaModalTag.innerText = tag;
    mediaModal.classList.add('modal-open');
    document.body.style.overflow = 'hidden';
}

function closeMediaModal() {
    if (!mediaModal) return;
    mediaModal.classList.remove('modal-open');
    document.body.style.overflow = '';
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && mediaModal && mediaModal.classList.contains('modal-open')) {
        closeMediaModal();
    }
});

/* -----------------------------------------------------
   6. Kaydırınca Beliren Elemanlar (Reveal on Scroll)
------------------------------------------------------ */
const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('reveal-active');
            revealObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.12, rootMargin: '0px 0px -60px 0px' });

function initRevealElements(scope) {
    scope.querySelectorAll('.group, article, details').forEach(el => {
        if (el.classList.contains('reveal-pending')) return;
        if (el.closest('header') || el.closest('#mobile-menu') || el.classList.contains('fixed')) return;
        // Yatay kaydırmalı (.mobile-scroll) carousel kartları hariç tutulur:
        // bu kartlar telefon genişliğinde overflow-x ile kısmen görünür/gizli
        // olduğundan, kullanıcı carousel'i parmakla kaydırdığında IntersectionObserver
        // tetiklenip fade/translateY animasyonunu ortasında başlatıyor; bu da kartların
        // birbirinin üstüne bindiği, köşelerin "hayalet" gibi görünmesine yol açan
        // görsel hataya sebep oluyordu.
        if (el.closest('.mobile-scroll')) return;
        el.classList.add('reveal-pending');
        revealObserver.observe(el);
    });
}
initRevealElements(document);