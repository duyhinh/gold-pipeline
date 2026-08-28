import os
import logging
import requests
import xml.etree.ElementTree as ET
from openai import OpenAI
from tvDatafeed import TvDatafeed, Interval

# ==========================================
# 🚨 ĐIỀN CÁC BIẾN VÀO ĐÂY (PHẦN DUY NHẤT CẦN SỬA)
# ==========================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")  # Đọc từ Secrets
TRADINGVIEW_USERNAME = os.environ.get("TRADINGVIEW_USERNAME")
TRADINGVIEW_PASSWORD = os.environ.get("TRADINGVIEW_PASSWORD")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # Đọc từ Secrets
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")      # Đọc từ Secrets

# ==========================================
# CẤU HÌNH LOGGING
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = OpenAI(base_url="https://api.deepseek.com", api_key=DEEPSEEK_API_KEY)
tv = TvDatafeed(TRADINGVIEW_USERNAME, TRADINGVIEW_PASSWORD)

# ==========================================
# DỮ LIỆU THỊ TRƯỜNG (Tự động)
# ==========================================
def fetch_market_data():
    try:
        df_xau = tv.get_hist(symbol='XAUUSD', exchange='OANDA', interval=Interval.in_15_minute, n_bars=5)
        price = f"Giá XAUUSD: {df_xau['close'].iloc[-1]:.2f}" if df_xau is not None and not df_xau.empty else "Không có dữ liệu XAUUSD"
        df_dxy = tv.get_hist(symbol='DXY', exchange='TVC', interval=Interval.in_15_minute, n_bars=5)
        dxy = f"DXY: {df_dxy['close'].iloc[-1]:.2f}" if df_dxy is not None and not df_dxy.empty else "Không có dữ liệu DXY"
        df_us = tv.get_hist(symbol='US10Y', exchange='TVC', interval=Interval.in_15_minute, n_bars=5)
        us10y = f"US10Y: {df_us['close'].iloc[-1]:.2f}%" if df_us is not None and not df_us.empty else "Không có dữ liệu US10Y"
        return f"{price}\n{dxy}\n{us10y}"
    except Exception as e:
        logger.error(f"Lỗi lấy dữ liệu: {e}")
        return "Không thể lấy dữ liệu"

def fetch_news():
    try:
        rss_url = "https://news.google.com/rss/search?q=gold+market+XAUUSD+fed"
        response = requests.get(rss_url)
        root = ET.fromstring(response.content)
        items = root.findall('.//item')[:5]
        return "\n".join(f"- {i.find('title').text}" for i in items if i.find('title') is not None)
    except Exception as e:
        logger.error(f"Lỗi lấy tin tức: {e}")
        return "Không thể lấy tin tức"

# ==========================================
# CÁC AGENT
# ==========================================
def run_pipeline():
    market_data = fetch_market_data()
    news_data = fetch_news()
    logger.info(f"Dữ liệu: {market_data}")

    prompts = [
        {"system": "Bạn là chuyên gia vĩ mô. Phân tích tin tức và dữ liệu, không bịa giá.",
         "user": f"Tin tức:\n{news_data}\nDữ liệu:\n{market_data}"},
        {"system": "Bạn là chuyên gia kỹ thuật XAUUSD. Phân tích cấu trúc M15/H4.",
         "user": f"Phân tích kỹ thuật dựa trên:\n{market_data}"},
        {"system": "Bạn là chuyên gia quản trị rủi ro. Tính Entry, SL, TP tỷ lệ 1:3.",
         "user": "Tính toán Entry, SL, TP cho số dư 20,000 USD, rủi ro 1%."},
        {"system": "Bạn là chuyên gia tổng hợp. Viết báo cáo Telegram sắc bén, kèm disclaimer.",
         "user": "Tổng hợp báo cáo từ dữ liệu: "}
    ]

    # Chain the agents
    results = []
    for i, prompt in enumerate(prompts):
        logger.info(f"Agent {i+1} đang chạy...")
        model = "deepseek-v4-pro" if i == 3 else "deepseek-v4-flash"
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": prompt["system"]},
                      {"role": "user", "content": prompt["user"] + (results[-1] if results else "")}]
        )
        results.append(res.choices[0].message.content)
        logger.info(f"Agent {i+1} hoàn thành.")

    return results[-1]

# ==========================================
# GỬI TELEGRAM
# ==========================================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logger.info("Đã gửi Telegram!")
        else:
            logger.error(f"Lỗi gửi Telegram: {response.text}")
    except Exception as e:
        logger.error(f"Lỗi: {e}")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    report = run_pipeline()
    print("="*60)
    print(report)
    send_telegram(report)