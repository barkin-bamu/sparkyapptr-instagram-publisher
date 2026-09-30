# Instagram Otomasyonu: Kurulum Rehberi

Her sabah **06:45'te** (TR saati) tweet agent'ının yazdığı günlük taslaktan bir carousel üretilir ve
Instagram'a otomatik paylaşılır. Görsel üretim ve paylaşım ücretsizdir; tweetleri carousel
metnine uyarlayan OpenAI API çağrısı, seçilen modele göre kullanım ücreti doğurur.

```
Tweet agent'ı  ──►  HABER_TWEETLERI_YYYY-MM-DD.md
                                   │
Instagram agent'ı (06:45) ──►  content/YYYY-MM-DD.json ──► render.py ──► görseller
                                   │
                            publish.py ──►  görseller repoya yüklenir (public URL)
                                        ──►  Instagram Graph API ile carousel paylaşılır
```

| Parça | Araç | Ücret |
|---|---|---|
| Görsel üretimi | HTML şablon + Playwright (headless Chromium) | Ücretsiz |
| Fontlar | Plus Jakarta Sans + Instrument Serif (OFL lisanslı, repoda) | Ücretsiz |
| Görsel barındırma | Public GitHub reposu (ya da Cloudinary ücretsiz plan) | Ücretsiz |
| Paylaşım | Instagram Graph API (resmi) | Ücretsiz |
| Zamanlama | GitHub Actions (public repoda sınırsız dakika) | Ücretsiz |

---

## 1. Instagram hesabını hazırla (5 dk)

1. Instagram hesabını aç → **Ayarlar → Hesap türü ve araçlar → Profesyonel hesaba geç**
   → **İşletme** ya da **İçerik üreticisi** seç. (API yalnızca profesyonel hesaplarla çalışır.)
2. Profil fotoğrafı olarak `brand/logo-ikon.png` dosyasını kullanabilirsin.

## 2. Meta geliştirici uygulaması ve token (15 dk)

> Meta panelindeki menü adları zaman zaman değişiyor. Takılırsan ekran görüntüsü at, birlikte bakalım.

1. <https://developers.facebook.com> → **My Apps → Create App**.
2. Kullanım amacı olarak **Instagram** / "Manage messaging & content on Instagram" seçeneğini seç.
3. Uygulamada **Instagram → API setup with Instagram login** bölümüne gir.
4. **Generate access tokens → Add account** ile kendi Instagram hesabına giriş yap.
   İzinlerde en az `instagram_business_basic` ve `instagram_business_content_publish` açık olmalı.
5. Ekranda iki değer göreceksin:
   - **Instagram hesap ID'si** (sayı) → `IG_USER_ID`
   - **Access token** (60 gün geçerli) → `IG_ACCESS_TOKEN`

Kendi hesabına paylaşım için "App Review" başvurusu gerekmez; uygulama geliştirme modunda kalabilir.

> Hesabın bir Facebook Sayfasına bağlıysa ve o akışı kullanmak istiyorsan: `GRAPH_HOST=graph.facebook.com`
> ortam değişkenini ekle ve Sayfa akışının token'ını kullan. Kodun geri kalanı aynı çalışır.

## 3. GitHub reposu (10 dk)

1. GitHub'da **public** bir repo aç (örn. `gunun-ozeti-instagram`) ve bu klasördeki her şeyi yükle.
   *Public olması iki nedenle gerekli: Instagram'ın görselleri raw.githubusercontent.com'dan çekebilmesi
   ve Actions dakikalarının ücretsiz olması.* Token'lar Secrets'ta saklandığı için güvende kalır.
2. **Settings → Secrets and variables → Actions → New repository secret**:
   - `IG_USER_ID`
   - `IG_ACCESS_TOKEN`
3. **Settings → Actions → General → Workflow permissions → Read and write permissions** seçeneğini aç.

## 4. Tweet agent'ını bağla

Instagram agent'ı tweet yazmaz; tweet agent'ının **tamamlanmış günlük taslağını** okur ve yalnızca
orada bulunan, kaynaklı bilgileri carousel biçimine kısaltır. Varsayılan olarak kaynak repoda şu dosyayı
arar: `HABER_TWEETLERI_YYYY-MM-DD.md`.

1. Kaynak repo farklıysa hedef repoda **Settings → Secrets and variables → Actions → Variables** bölümüne
   `TWEET_SOURCE_REPOSITORY` olarak `sahip/repo` değerini yaz.
2. Kaynak repo özelse, sadece okuma izni olan bir erişim anahtarını `TWEET_SOURCE_TOKEN` secret'ı olarak ekle.
3. `OPENAI_API_KEY` secret'ını ekle. Agent, Structured Outputs ile şemaya uygun JSON üretir; fakat kaynak
   doğruluğu için tweet agent'ının mevcut editoryal onay süreci korunur.
4. Agent çıktılarını yerelde görmek için:

```bash
OPENAI_API_KEY=... python tweet_to_instagram.py /yol/HABER_TWEETLERI_YYYY-MM-DD.md --date YYYY-MM-DD
python run_daily.py content/YYYY-MM-DD.json --dry-run
```

Tekrar çalıştırılan bir iş aynı tarihte ikinci paylaşım yapmaz: yayın başlamadan GitHub'da `state/YYYY-MM-DD.json`
kaydı oluşturulur. Hata alan veya yarım kalan kayıt, inceleme olmadan otomatik yeniden denenmez.

## 5. Test et

1. **Actions → Instagram günlük carousel → Run workflow → "Sadece üret, paylaşma" işaretli** çalıştır.
2. Bitince **Artifacts → carousel** dosyasını indirip görsellere bak.
3. Her şey yolundaysa işareti kaldırıp bir kez daha çalıştır. İlk gönderi profilinde görünür.

Kendi bilgisayarında denemek için:
```bash
pip install -r requirements.txt
python -m playwright install chromium
python render.py content/2026-09-30.json          # out/2026-09-30/ içine görseller
python run_daily.py content/2026-09-30.json --dry-run
```

## 6. Bakım

- **Token her 60 günde bir yenilenmeli.** Ayda bir `python refresh_token.py` çalıştır ve çıkan
  yeni token'ı `IG_ACCESS_TOKEN` secret'ına yapıştır. (Takvimine hatırlatıcı koy. İstersen bunu da otomatikleştiririz.)
- Hesap adını, renkleri ve kategori isimlerini `config.json` dosyasından değiştirebilirsin.
- Metin uzun gelirse şablon yazıyı otomatik küçültür; %70'in altına düşerse log'da uyarı görürsün.

## Özelleştirme

| Ne | Nerede |
|---|---|
| Hesap adı (@...) | `config.json` → `handle` |
| Kategori renkleri / isimleri | `config.json` → `categories` |
| Son slayt metni | `config.json` → `cta_line` |
| Hashtag'ler | `config.json` → `hashtags` |
| Tasarım (font, boşluk, düzen) | `templates/slide.html.j2` |
| Paylaşım saati | `.github/workflows/instagram.yml` → `cron` (UTC!) |

## Dikkat

- Haber sitelerinin fotoğraflarını **ekleme**; tasarım bu yüzden tipografi ve ikon üzerine kurulu.
- Günde 1 carousel yeterli. Aynı gün birden fazla otomatik paylaşım erişimi düşürebilir.
- Siyaset içeriğini tarafsız tut; bu, şikâyet ve kısıtlama riskini ciddi şekilde azaltır.
