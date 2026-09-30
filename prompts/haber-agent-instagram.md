# Tweet agent'ı için Instagram sıralama notu

Instagram agent'ı, tweet agent'ının tamamlanmış `HABER_TWEETLERI_YYYY-MM-DD.md` taslağını veri olarak
okur. Bu nedenle tweet agent'ı her haberin sonunda kaynak adını, URL'sini ve doğrulama notunu korumalıdır.
Taslakta iki farklı, kaynaklı haber bulunmayan bir kategori Instagram carousel'ine alınmaz. Tweet agent'ı
Instagram için ayrıca JSON üretmez ve carousel agent'ı yeni haber, sayı, tarih veya yorum eklemez.
