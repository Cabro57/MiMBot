# config.py

class Config:
    # --- Otomatik Parite Çekme ---
    # Boş bırakıldığında bot tüm Binance Futures USDT paritelerini otomatik tarar
    SYMBOLS = [] 

    # --- Telegram Bilgileri ---
    BOT_TOKEN = '8143998160:AAHbCy0zE6IrwsFlJ4LwTo6ulsPUkRPyDAw'
    CHAT_ID = '-1002547240908'

    # --- Zaman Ayarları ---
    # Bot artık bu dakikanın katlarında (00, 15, 30, 45) otomatik senkronize olur
    SCAN_INTERVAL_MINUTES = 15 
    
    # Açık işlemleri (TP/SL) kontrol etme sıklığı (Saniye)
    TRADE_CONTROL_SECONDS = 30 
    
    # --- Risk ve Strateji Ayarları ---
    RR_RATIO = 1.4             # 1:1.4 Risk/Ödül oranı
    MAX_STOP_PERCENT = 0.02    # %2 Maksimum Stop Loss sınırı (Zorunlu)
    STOP_OFFSET = 0.0005       # Teknik stop için bırakılan esneme payı
    
    # --- v3.0 Gelişmiş Filtre Ayarları ---
    EMA_TREND_PERIOD = 200     # Trend yönünü belirleyen ana ortalama
    TIME_STOP_HOURS = 4        # 4 saat dolunca stopu girişe çekme kuralı
    
    # --- Teknik Ayarlar ---
    BREAKOUT_TIMEFRAME = '1m'  # Onay mumu periyodu
    ENABLE_CONSOLE_LOG = True  # CMD ekranında canlı akışı göster
