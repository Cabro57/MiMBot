# config.py

class Config:
    # --- Otomatik Parite Çekme ---
    # Boş bırakıldığında bot tüm Binance Futures USDT paritelerini çeker
    SYMBOLS = [] 

    # --- Telegram Bilgileri ---
    BOT_TOKEN = '8143998160:AAHbCy0zE6IrwsFlJ4LwTo6ulsPUkRPyDAw'
    CHAT_ID = '-1002547240908'

    # --- Zaman Ayarları ---
    # Bot artık bu dakikanın katlarında (00, 15, 30, 45) otomatik tarama yapar
    SCAN_INTERVAL_MINUTES = 15 
    
    # Açık işlemleri (TP/SL) kontrol etme sıklığı (Saniye)
    TRADE_CONTROL_SECONDS = 30 
    
    # --- Risk ve Strateji Ayarları ---
    RR_RATIO = 1.4             # 1:1.4 Risk/Ödül oranı
    MAX_STOP_PERCENT = 0.02    # %2 Maksimum Stop Loss sınırı
    STOP_OFFSET = 0.0005       # Teknik stop esneme payı
    
    # --- Teknik Filtre Ayarları ---
    # Trend yönünü belirleyen ana ortalama (v2 ile eklendi)
    EMA_TREND_PERIOD = 200     
    BREAKOUT_TIMEFRAME = '1m'  # Onay mumları periyodu
    ENABLE_CONSOLE_LOG = True  # CMD ekranında logları göster
