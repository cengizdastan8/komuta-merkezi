# Otomatik Ajans / NEXUS müşteri demosu

Python 3.10+ ve ek paket gerektirmeyen, SQLite ile yerelde çalışan brief → sunucu taraflı teklif → revizyon/sürüm kilidi → tutar eşleşmesi → teslim kontrol listesi akışı.

```powershell
python nexus_ajans_motoru.py serve --open
```

Varsayılan adres `http://127.0.0.1:8765/`; API uçları `/api/health`, `/api/packages`, `/api/projects` ve proje altındaki `revision`, `lock`, `payment`, `checklist` işlemleridir. Veritabanı `data/nexus-demo.sqlite3` içinde oluşturulur; farklı konum için `--db <yol>` kullanın. `python nexus_ajans_motoru.py self-check` paket kataloğu ve fiyat hesabını hızlıca kontrol eder.

Teklif ve ek hizmet fiyatları sunucudaki katalogdan hesaplanır. Yanlış tutar/para birimi kabul edilmez. Sürüm kilidinden sonra revizyon isteği reddedilir. Teslim adımları doğrulanmış demo tutarından sonra açılır. Ödeme düğmesi tahsilat yapmaz; bu demo ödeme sağlayıcısı, gerçek müşteri, bildirim veya harici teslimat kullanmaz. Veriler yalnız yerel SQLite dosyasındadır.
