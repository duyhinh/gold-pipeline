import os
import logging
import requests
import xml.etree.ElementTree as ET
from openai import OpenAI

# ==========================================
# CẤU HÌNH LOGGING
# ==========================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==========================================
# KẾT NỐI API
# ==========================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

client = OpenAI(
    base_url="https://api.deepseek.com",
    api_key=DEEPSEEK_API_KEY
)

# ==========================================
# DỮ LIỆU DỰ PHÒNG (Chỉ dùng khi không thể kết nối TradingView)
# ==========================================
DEFAULT_PRICE = "4.580"
DEFAULT_NEWS = (
    "Thị trường đang chờ đợi bài phát biểu của Chủ tịch Fed. "
    "Căng thẳng địa chính trị tại Trung Đông vẫn tiếp diễn, hỗ trợ nhu cầu vàng. "
    "Chỉ số DXY đang giao dịch quanh mức 99, lợi suất trái phiếu Mỹ 10 năm neo cao."
)

# ==========================================
# HÀM LẤY DỮ LIỆU THỊ TRƯỜNG (Tự động, có fallback)
# ==========================================
def fetch_market_data():
    try:
        # Import thư viện tvDatafeed (đã được cài trong GitHub Actions)
        from tvDatafeed import TvDatafeed, Interval

        # Đọc username/password từ Secrets
        username = os.environ.get("TRADINGVIEW_USERNAME")
        password = os.environ.get("TRADINGVIEW_PASSWORD")

        # Nếu có tài khoản, kết nối và lấy dữ liệu
        if username and password:
            tv = TvDatafeed(username, password)

            # Lấy giá vàng (XAUUSD)
            df_xau = tv.get_hist(symbol='XAUUSD', exchange='OANDA', interval=Interval.in_15_minute, n_bars=5)
            if df_xau is not None and not df_xau.empty:
                price = df_xau['close'].iloc[-1]
            else:
                price = DEFAULT_PRICE

            # Lấy DXY (nếu có dữ liệu)
            dxy_value = DEFAULT_PRICE  # tạm thời, bạn có thể thay bằng lệnh tương tự cho DXY
            try:
                df_dxy = tv.get_hist(symbol='DXY', exchange='TVC', interval=Interval.in_15_minute, n_bars=5)
                if df_dxy is not None and not df_dxy.empty:
                    dxy_value = f"{df_dxy['close'].iloc[-1]:.2f}"
            except:
                pass

            # Lấy US10Y (nếu có dữ liệu)
            us10y_value = "N/A"
            try:
                df_us = tv.get_hist(symbol='US10Y', exchange='TVC', interval=Interval.in_15_minute, n_bars=5)
                if df_us is not None and not df_us.empty:
                    us10y_value = f"{df_us['close'].iloc[-1]:.2f}%"
            except:
                pass

            return f"Giá XAUUSD: {float(price):.2f} USD | DXY: {dxy_value} | US10Y: {us10y_value}"

        # Nếu không có tài khoản, dùng mặc định
        return f"Giá XAUUSD: {DEFAULT_PRICE} USD"

    except Exception as e:
        logger.warning(f"Không thể lấy dữ liệu TradingView: {e}. Dùng dữ liệu mặc định.")
        return f"Giá XAUUSD: {DEFAULT_PRICE} USD"

def fetch_news():
    try:
        rss_url = "https://news.google.com/rss/search?q=gold+market+XAUUSD+fed"
        response = requests.get(rss_url, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = root.findall('.//item')[:5]
        if items:
            news_list = []
            for item in items:
                title = item.find('title')
                if title is not None:
                    news_list.append(f"- {title.text}")
            return "\n".join(news_list) if news_list else DEFAULT_NEWS
        return DEFAULT_NEWS
    except Exception as e:
        logger.warning(f"Không thể lấy tin tức RSS: {e}. Dùng tin dự phòng.")
        return DEFAULT_NEWS

# ==========================================
# PROMPT CHI TIẾT CHO TỪNG AGENT
# ==========================================
AGENT_PROMPTS = {
    "data_fetcher": {
        "system": (
            "Bạn là Market Data & Quant Agent kiêm chuyên gia phân tích địa chính trị và vĩ mô toàn cầu của studio vàng XAUUSD (khung M15, MTF H4).\n"
            "HÃY PHÂN TÍCH SẮC BÉN DỰA TRÊN DỮ LIỆU ĐƯỢC CUNG CẤP:\n"
            "1. Diễn giải các tin tức nóng hổi (chiến tranh, xung đột địa chính trị, phát biểu Fed) trong 24h qua có tác động mạnh mẽ đến tài sản trú ẩn an toàn (Vàng/XAUUSD).\n"
            "2. Tổng hợp các chỉ số vĩ mô (DXY, US10Y, GLD) từ dữ liệu thời gian thực được cung cấp.\n"
            "3. Đánh giá tác động của các yếu tố này lên tín hiệu thuật toán hiện tại.\n"
            "YÊU CẦU VĂN PHONG: Sắc bén, cập nhật thời sự nóng hổi, giật gân cuốn hút người đọc nhưng vẫn giữ chuẩn mực quản trị rủi ro chặt chẽ.\n"
            "TUYỆT ĐỐI KHÔNG BỊA GIÁ hoặc tự ý thêm dữ liệu mới. CHỈ phân tích dữ liệu được cung cấp.\n"
            "KHÔNG hứa lợi nhuận. Ghi rõ nguồn/giờ nếu có. Ngôn ngữ: tiếng Việt."
        ),
        "user": "Dữ liệu thị trường hiện tại:\n{market_data}\n\nTin tức mới nhất trong 24h qua:\n{news_data}\n\nHãy phân tích tình hình vĩ mô và địa chính trị ảnh hưởng đến vàng, và đối chiếu với tín hiệu thị trường."
    },
    "tech_analyst": {
        "system": (
            "Bạn là Senior Technical Analyst chuyên về Vàng (XAUUSD). "
            "Dựa trên dữ liệu giá được cung cấp và bối cảnh vĩ mô, hãy xác định: "
            "1) Xu hướng chính (H4) 2) Vùng hỗ trợ/kháng cự quan trọng (chính xác đến 5 USD) 3) Tín hiệu giao dịch ngắn hạn (M15). "
            "Trả về dạng bullet point ngắn gọn, sắc bén."
        ),
        "user": "Dữ liệu thị trường:\n{market_data}\n\nBối cảnh vĩ mô:\n{context_data}\n\nHãy phân tích kỹ thuật XAUUSD."
    },
    "risk_manager": {
        "system": (
            "Bạn là Chief Risk Manager. Dựa trên phân tích kỹ thuật, hãy đề xuất một kế hoạch giao dịch cụ thể: "
            "Entry, Stop Loss, Take Profit (tỷ lệ R:R 1:3), khối lượng lot (với vốn 20.000 USD, rủi ro 1%). "
            "Trả về dạng JSON: entry, stop_loss, take_profit, risk_level, lot_size."
        ),
        "user": "Phân tích kỹ thuật:\n{tech_analysis}\n\nHãy tính toán kế hoạch giao dịch."
    },
    "orchestrator": {
        "system": (
            "Bạn là Lead Quant Agent, chịu trách nhiệm tổng hợp báo cáo cuối cùng. "
            "Báo cáo PHẢI có đầy đủ 4 phần: "
            "1. Tóm tắt thị trường (dựa trên dữ liệu vĩ mô) "
            "2. Phân tích kỹ thuật "
            "3. Chiến lược giao dịch (Entry/SL/TP/Lot) "
            "4. Cảnh báo rủi ro. "
            "Dùng Markdown, kèm disclaimer. KHÔNG sửa số liệu của Agent 3. "
            "Nếu dữ liệu vĩ mô trống, ghi rõ 'Không có dữ liệu vĩ mô cập nhật'."
        ),
        "user": (
            "Viết báo cáo Telegram từ:\n"
            "**Dữ liệu vĩ mô (Agent 1):** {context_data}\n"
            "**Phân tích kỹ thuật (Agent 2):** {tech_analysis}\n"
            "**Kế hoạch giao dịch (Agent 3):** {risk_plan}"
        )
    }
}

# ==========================================
# HÀM GỬI TELEGRAM
# ==========================================
def send_telegram_report(message: str):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Thiếu cấu hình Telegram. Bỏ qua bước gửi tin nhắn.")
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Đã gửi báo cáo qua Telegram thành công!")
        else:
            logger.error(f"Lỗi gửi Telegram: {response.text}")
    except Exception as e:
        logger.error(f"Lỗi khi gửi Telegram: {e}")

# ==========================================
# HÀM CHẠY PIPELINE CHÍNH
# ==========================================
def run_pipeline():
    logger.info("Bắt đầu pipeline...")
    market_data = fetch_market_data()
    news_data = fetch_news()
    logger.info(f"Dữ liệu thị trường: {market_data}")

    # Agent 1: Vĩ mô
    logger.info("Agent 1 (Vĩ mô) đang chạy...")
    res_1 = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": AGENT_PROMPTS["data_fetcher"]["system"]},
            {"role": "user", "content": AGENT_PROMPTS["data_fetcher"]["user"].format(
                market_data=market_data, news_data=news_data
            )}
        ]
    )
    context_data = res_1.choices[0].message.content
    logger.info("Agent 1 hoàn thành.")

    # Agent 2: Kỹ thuật
    logger.info("Agent 2 (Kỹ thuật) đang chạy...")
    res_2 = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": AGENT_PROMPTS["tech_analyst"]["system"]},
            {"role": "user", "content": AGENT_PROMPTS["tech_analyst"]["user"].format(
                market_data=market_data, context_data=context_data
            )}
        ]
    )
    tech_analysis = res_2.choices[0].message.content
    logger.info("Agent 2 hoàn thành.")

    # Agent 3: Rủi ro
    logger.info("Agent 3 (Rủi ro) đang chạy...")
    res_3 = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": AGENT_PROMPTS["risk_manager"]["system"]},
            {"role": "user", "content": AGENT_PROMPTS["risk_manager"]["user"].format(
                tech_analysis=tech_analysis
            )}
        ]
    )
    risk_plan = res_3.choices[0].message.content
    logger.info("Agent 3 hoàn thành.")

    # Agent 4: Tổng hợp
    logger.info("Agent 4 (Tổng hợp) đang tạo báo cáo...")
    res_4 = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": AGENT_PROMPTS["orchestrator"]["system"]},
            {"role": "user", "content": AGENT_PROMPTS["orchestrator"]["user"].format(
                context_data=context_data, tech_analysis=tech_analysis, risk_plan=risk_plan
            )}
        ]
    )
    final_report = res_4.choices[0].message.content
    logger.info("Pipeline hoàn thành.")

    return final_report

# ==========================================
# CHẠY CHÍNH
# ==========================================
if __name__ == "__main__":
    try:
        report = run_pipeline()
        print("\n" + "=" * 60)
        print("BÁO CÁO CUỐI CÙNG:")
        print("=" * 60)
        print(report)
        send_telegram_report(report)
    except Exception as e:
        logger.error(f"Pipeline thất bại: {e}")
