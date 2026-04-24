# LocalFit Planner

Girilen kullanici bilgilerine gore otomatik diyet ve fitness programi olusturan, lokal kullanim icin tasarlanmis Flask tabanli web uygulamasi.

## Ozellikler

- Cok kullanicili kayit ve giris sistemi
- Admin paneli
- Profil / olcu bilgisi kaydetme
- Otomatik kalori, makro ve su hedefi hesaplama
- Otomatik diyet plani uretimi
- Alternatif ogun onerileri
- Fitness programi uretimi
- Supplement oneri alani
- Plan gecmisi
- Haftalik ilerleme takibi
- PDF cikti alma

## Kurulum

```bash
cd diet_fitness_app
python -m venv .venv
```

### Windows
```bash
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### macOS / Linux
```bash
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Ardindan tarayicida su adresi ac:

```bash
http://127.0.0.1:5000
```

## Varsayilan admin hesabi

- E-posta: `admin@localfit.com`
- Sifre: `admin123`

Ilk giristen sonra istersen veritabanindan veya koddan degistirebilirsin.

## Dosya yapisi

- `app.py` -> backend ve is mantigi
- `templates/` -> HTML sayfalari
- `static/` -> CSS ve JS
- `instance/app.db` -> SQLite veritabani (ilk calistirmada olusur)

## Uyari

Bu uygulama tibbi tavsiye yerine gecmez. Genel planlama ve icerik otomasyonu icin hazirlanmistir.
