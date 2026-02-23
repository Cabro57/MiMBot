# 🚀 MiMBot — Advanced Crypto Scanner & Paper Trading

MiMBot, Binance Futures halka açık WebSocket stream'lerini kullanarak gerçek zamanlı piyasa taraması yapan, **dinamik strateji yükleme** kabiliyetiyle ve **gerçekçi sanal (paper) pozisyon takibi** sunan modüler bir trading botudur. 

Gerçek işlem açmaz, API anahtarı gerektirmez ve tamamen asenkron (`asyncio`) mimari üzerine kuruludur.

---

## ✨ Öne Çıkan Özellikler

| Özellik | Açıklama |
|---|---|
| 🔌 **WebSocket & REST Hibrit** | WebSocket (Kline + Mark Price) ve REST (Preload) ile sıfır gecikmeli veri. |
| 🧩 **Dinamik Strateji Motoru** | Stratejiler `importlib` ile çalışma anında yüklenir; `main.py`'ye dokunmanıza gerek kalmaz. |
| 📅 **Dinamik Zaman Dilimi** | Stratejinin ihtiyaç duyduğu tüm timeframe'ler (1m, 5m, 1h vb.) otomatik olarak taranır. |
| 🎯 **Gerçekçi Paper Trading** | Giriş fiyatları "Mark Price" üzerinden alınır; TP/SL hesaplamaları milisaniyelik hassasiyettedir. |
| ❄️ **Cold Start Çözümü** | Bot başlar başlamaz geçmiş veriyi çeker ve bekleme süresi olmadan taramaya başlar. |
| 🛡️ **Akıllı Filtreleme** | Cooldown (soğuma süresi) mekanizması ile aynı sembolden sinyal spamlanmasını önler. |
| 📝 **Derin Analiz Logları** | `structlog` ile JSON formatında zenginleştirilmiş loglar; geriye dönük analiz (backtest) dostu. |

---

## 📂 Proje Mimarisi

```
├── main.py                  # Ana orkestratör (Asenkron Döngü)
├── core/
│   ├── config.py            # .env tabanlı dinamik yapılandırma
│   ├── database.py          # SQLite & Async SQLAlchemy yönetimi
│   └── logger.py            # Renkli konsol ve JSON dosya loglama
├── data/
│   ├── memory_store.py      # NumPy tabanlı yüksek performanslı bellek deposu
│   ├── rest_client.py       # Geçmiş veri ve borsa bilgi istemcisi
│   └── websocket_client.py  # Canlı fiyat ve mum akış yöneticisi
├── strategies/
│   ├── loader.py            # Dinamik strateji yükleyici fabrika
│   ├── base_strategy.py     # Soyut strateji taban sınıfı
│   └── ema_volume_strategy.py # Mevcut aktif EMA+Hacim stratejisi
├── execution/
│   ├── signal_dispatcher.py # Telegram bildirimleri ve DB kayıtları
│   └── position_watcher.py  # 1s periyotlu sanal pozisyon takipçisi
├── models/
│   └── db_models.py         # SQLAlchemy ORM tabloları (Signals & Trades)
├── requirements.txt
└── .env                     # Özel ayarlar (Bot Token, RR Oranı vb.)
```

---

## 🚀 Hızlı Başlangıç

### 1. Kurulum

```bash
# Depoyu klonlayın
git clone https://github.com/Cabro57/MiMBot.git
cd MiMBot

# Sanal ortam oluşturun ve aktif edin
python -m venv .venv
# Windows için:
.venv\Scripts\activate

# Bağımlılıkları yükleyin
pip install -r requirements.txt
```

### 2. Yapılandırma

`.env.example` dosyasını `.env` olarak kopyalayın ve bilgilerinizi girin:

```env
TELEGRAM_BOT_TOKEN="BOT_TOKENINIZ"
TELEGRAM_CHAT_ID="CHAT_IDNIZ"
ACTIVE_STRATEGY="ema_volume_strategy.EmaVolumeStrategy"
COOLDOWN_MINUTES=30
SCAN_INTERVAL_SECONDS=300
```

### 3. Çalıştırma

```bash
python main.py
```

---

## ⚙️ Dinamik Konfigürasyon (Settings)

Tüm ayarlar `core/config.py` üzerinden yönetilir. Önemli parametreler:

- `ACTIVE_STRATEGY`: Yüklenecek stratejinin `modül.Sınıf` adresi.
- `RR_RATIO`: Risk/Ödül oranı (Örn: 1.4).
- `MAX_STOP_PERCENT`: Bir işlemin alabileceği maksimum stop mesafesi (%2.5).
- `TOP_VOLUME_LIMIT`: Binance'deki en hacimli ilk N sembolü tarar.

---

## 🔍 Geriye Dönük Analiz (Backtesting)

MiMBot, her sinyal üretildiğinde `trading_bot.log` dosyasına ve veritabanına zenginleştirilmiş veri yazar. JSON loglarında şunları görebilirsiniz:
- `entry`, `sl`, `tp` (Fiyat seviyeleri)
- `spike_ratio` (Hacim gücü)
- `ema_fast` / `ema_slow` (İndikatör değerleri)
- `volume` / `avg_vol` (Anlık ve ortalama hacim)

---

## 🛡️ Güvenlik ve Uyarılar

- **Risk Yok:** Bu bot hiçbir borsa API'sine *Trade/Withdraw* yetkisi ile bağlanmaz. Sadece halka açık veri okur.
- **Eğitim Amaçlıdır:** Üretilen sinyaller finansal tavsiye niteliği taşımaz.
- **Performans:** 150+ sembolü asenkron yapısı sayesinde milisaniyeler içinde tarayabilir.

---

## 📜 Lisans

MIT License - 2026 MiMBot Project.
