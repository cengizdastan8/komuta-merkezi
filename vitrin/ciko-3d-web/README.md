# Çiko 3D Web Vitrini

Yerel web vitrini; Python 3 kurulu Windows bilgisayarda `start-ciko.bat` tek komutla `http://127.0.0.1:8764/` açar. Alternatif olarak bu klasörde `python -m http.server 8764` çalıştırıp adresi tarayıcıda açın.

## Modlar

1. Sinematik sahne: tarayıcının WebGL API'siyle koddan çizilen, harici görsel kullanmayan dönen ekmek biçimi.
2. Ticari katalog: ürün miktarı, ek malzeme, sepet toplamı ve sipariş özeti.
3. Mobil hafif mod: dar ekrana uygun ızgara ve kapatılmış hareket.

`prefers-reduced-motion: reduce` CSS hareketini azaltır, JavaScript'in sürekli WebGL animasyon döngüsünü de durdurur. WebGL olmayan cihazlarda katalog ve sepet kullanılabilir.

## İşletme verisi ve sınır

Ürünler, fiyatlar, ek malzemeler ve işletme alanları `ciko-config.json` içindedir. Örnek adlar/fiyatlar değiştirilecek yer tutucudur. Fotoğraf, müşteri yorumu veya gerçek sipariş iddiası yoktur. Sipariş özeti ve demo durum bilgisi yalnız tarayıcının `localStorage` alanında tutulur; harici işletmeye gönderilmez.
