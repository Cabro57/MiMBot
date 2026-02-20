# 💰 MoneyIsMoney — Crypto Scanner & Paper Trading Bot

Binance Futures halka açık WebSocket stream'lerini kullanan, **sinyal üreten** ve **sanal (paper) pozisyon takibi** yapan modüler bir trading botudur. Gerçek işlem açmaz, API anahtarı gerektirmez.

---

## ✨ Özellikler

| Özellik | Açıklama |
|---|---|
| 🔌 **WebSocket Veri Akışı** | Kline + Mark Price stream (REST polling yok) |
| 📊 **EMA + Hacim Stratejisi** | NumPy ile vektörize hesaplama |
| 🎯 **Sanal TP / SL / Timeout** | Mark Price üzerinden pozisyon takibi |
| 📲 **Telegram Bildirimleri** | Sinyal ve kapanış bildirimleri |
| 🗄️ **SQLite Veritabanı** | Async SQLAlchemy ile sinyal ve trade kayıtları |
| 📝 **Yapısal Loglama** | structlog ile JSON formatında log |
| ⚙️ **Dinamik Konfigürasyon** | `.env` dosyasından tüm parametreler |

---

## 📂 Proje Yapısı

```
├── main.py                  # Ana giriş noktası ve orkestratör
├── core/
│   ├── config.py            # TradingConfig dataclass (.env okuyucu)
│   ├── database.py          # Async SQLAlchemy engine & session
│   └── logger.py            # structlog yapılandırması
├── data/
│   ├── memory_store.py      # CandleBuffer + fiyat cache (deque + NumPy)
│   └── websocket_client.py  # Binance public WS istemcisi
├── strategies/
│   ├── base_strategy.py     # Soyut strateji arayüzü
│   └── ema_volume_strategy.py  # EMA + Hacim kırılım stratejisi
├── execution/
│   ├── signal_dispatcher.py # Telegram + DB sinyal dağıtıcı
│   └── position_watcher.py  # Sanal TP/SL/Timeout takipçisi
├── models/
│   └── db_models.py         # SQLAlchemy ORM modelleri
├── requirements.txt
├── .env.example             # Ortam değişkenleri şablonu
└── .gitignore
```

---

## 🚀 Kurulum

### 1. Depoyu Klonla

```bash
git clone https://github.com/mmertseref-crypto/moneyismoney.git
cd moneyismoney
```

### 2. Sanal Ortam Oluştur

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. Bağımlılıkları Kur

```bash
pip install -r requirements.txt
```

### 4. Ortam Değişkenlerini Ayarla

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/Mac
```

`.env` dosyasını düzenleyerek **Telegram Bot Token** ve **Chat ID** değerlerini girin:

```env
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=-100123456789
```

### 5. Botu Başlat

```bash
python main.py
```

---

## ⚙️ Konfigürasyon

Tüm parametreler `.env` dosyasından okunur. Varsayılan değerler `core/config.py` içinde tanımlanmıştır.

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Zorunlu. Telegram bot token |
| `TELEGRAM_CHAT_ID` | — | Zorunlu. Telegram chat/group ID |
| `EMA_FAST` | `5` | Hızlı EMA periyodu |
| `EMA_SLOW` | `20` | Yavaş EMA periyodu |
| `TP_PERCENT` | `1.5` | Take profit yüzdesi |
| `SL_PERCENT` | `0.75` | Stop loss yüzdesi |
| `VOLUME_SPIKE_MIN` | `2.0` | Minimum hacim spike oranı |
| `VOLUME_SPIKE_MAX` | `10.0` | Maximum hacim spike oranı |
| `SCAN_INTERVAL_SEC` | `90` | Tarama döngüsü süresi (saniye) |
| `TOP_VOLUME_LIMIT` | `100` | Taranacak en yüksek hacimli sembol sayısı |
| `POSITION_TIMEOUT_MIN` | `60` | Sanal pozisyon timeout süresi (dakika) |

---

## 📊 Strateji Mantığı

**EMA + Hacim Kırılım Stratejisi:**

- **LONG Sinyal:** `close > range_high` VE `EMA_fast > EMA_slow` VE hacim spike filtrede
- **SHORT Sinyal:** `close < range_low` VE `EMA_fast < EMA_slow` VE hacim spike filtrede

Sinyal oluştuğunda:
1. Telegram'a bildirim gönderilir
2. Veritabanına kaydedilir
3. Sanal pozisyon açılır ve TP/SL/Timeout takibi başlar

---

## 🛡️ Güvenlik

- ❌ Binance API anahtarı **gerekmez** — tüm veriler halka açık stream'lerden
- ❌ Gerçek işlem **açılmaz** — sadece sinyal üretimi ve sanal takip
- ✅ `.env` dosyası `.gitignore`'da — tokenlar repoya yüklenmez

---

## 📜 Lisans

MIT License
