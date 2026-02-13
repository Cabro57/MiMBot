# config.py

class Config:
    # --- Otomatik Parite Çekme ---
    # Boş bırakıldığında bot tüm Binance Futures USDT paritelerini çeker
    SYMBOLS = [] 

    # --- Telegram Bilgileri ---
    BOT_TOKEN = '8143998160:AAHbCy0zE6IrwsFlJ4LwTo6ulsPUkRPyDAw'
    CHAT_ID = '-1002547240908'

    # --- Zaman Ayarları ---
    SCAN_INTERVAL_MINUTES = 15 # 15 dakikada bir tüm piyasayı tara
    TRADE_CONTROL_SECONDS = 30 # 30 saniyede bir TP/SL kontrolü yap
    
    # --- Risk ve Strateji Ayarları ---
    RR_RATIO = 1.4             # 1:1.4 Risk/Ödül oranı
    MAX_STOP_PERCENT = 0.02    # %2 Maksimum Stop Loss sınırı
    STOP_OFFSET = 0.0005       # Teknik stop esneme payı
    
    # --- Teknik Ayarlar ---
    BREAKOUT_TIMEFRAME = '1m'  # Onay mumları 1 dakikalık olsun
    ENABLE_CONSOLE_LOG = True  # CMD ekranında logları göster
