# config.py

class Config:
    SYMBOLS = []               # Boş kalsın, otomatik çeker
    
    # --- Zaman Ayarları ---
    SCAN_INTERVAL_MINUTES = 15 # Her tarama sonrası 10 dk mola
    TRADE_CONTROL_SECONDS = 30 # Açık işlemleri 30 saniyede bir kontrol et
    
    # --- Risk ve Strateji Ayarları ---
    RR_RATIO = 1.4             # İstediğin 1.4 Risk/Ödül oranı
    MAX_STOP_PERCENT = 0.02    # %2 Maksimum Stop Loss kuralı
    STOP_OFFSET = 0.0005       # Teknik stop için küçük esneme payı
    
    BREAKOUT_TIMEFRAME = '1m'
    ENABLE_CONSOLE_LOG = True