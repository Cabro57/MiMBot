class Config:
    # --- Telegram Bilgileri ---
    # Botun sinyal ve bildirim göndereceği adresler
    BOT_TOKEN = '8143998160:AAHbCy0zE6IrwsFlJ4LwTo6ulsPUkRPyDAw'
    CHAT_ID = '-1002547240908'

    # --- Market Tarama Filtreleri ---
    # Bot, 24 saatlik hacme göre ilk kaç coini tarasın?
    TOP_VOLUME_LIMIT = 100 
    # Market listesi kaç saatte bir güncellensin? (Yenilenen hacim şampiyonları için)
    MARKET_REFRESH_HOURS = 1 

    # --- Zamanlama Ayarları ---
    # Bot kaç dakikada bir tarama yapsın? (Scalping için 1 veya 5 önerilir)
    SCAN_INTERVAL_MINUTES = 5 
    # Açık işlemleri (TP/SL) kontrol etme sıklığı (Saniye)
    TRADE_CONTROL_SECONDS = 10 
    
    # --- Strateji Parametreleri (EMA & Hacim) ---
    EMA_FAST = 9              # Hızlı hareketli ortalama
    EMA_SLOW = 21             # Yavaş hareketli ortalama
    # Hacim Patlaması Çarpanı: Son 1dk hacmi, son 10dk ortalamasının kaç katı olmalı?
    VOLUME_SPIKE_MULTIPLIER = 1     # Alt sınırımız
    MAX_VOLUME_SPIKE_LIMIT = 20      # YENİ: Üst sınırımız (Bunu config'e ekle)
    BREAKOUT_RANGE_PERIOD = 5 

    # --- Risk ve Strateji Ayarları (TP/SL) ---
    RR_RATIO = 1.4            # 1:1.4 Risk/Ödül oranı (Hedef = Risk x 1.4)
    MAX_STOP_PERCENT = 0.025   # %2 Maksimum Stop Loss sınırı (Fiyat çok uçarsa kasayı korur)
    STOP_OFFSET = 0.0005      # Teknik stop seviyesine (r_high/low) eklenen esneme payı
    
    # --- Akıllı Zaman Stopu ---
    # İşlem bu saatten uzun sürerse ve kârda ise otomatik kapatılır.
    TIME_STOP_HOURS = 4        
    
    # --- Sistem ve Log Ayarları ---
    MAX_PARALLEL_TASKS = 15   # Aynı anda analiz edilecek sembol sayısı (Semaphore)
    ENABLE_CONSOLE_LOG = True # Terminalde tarama detaylarını gösterir
