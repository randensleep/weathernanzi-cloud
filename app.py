from flask import Flask, jsonify, request
import threading, time, requests
from datetime import datetime

app = Flask(__name__)
weather_data = {}

# =========================
# Google Apps Script URL
# =========================
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbwtoRDe-xMFq27HAs-7lndZmEeyqeJhhYrE5wVx4laBIcjrYYXKnSGgC0eEh6RqfHRe/exec"

# =========================6
# Telegram 設定
# =========================
TELEGRAM_BOT_TOKEN = "8572660643:AAF6H46EqtgNaR-XXzGlJcRTIg2hyAD0xMs"
TELEGRAM_CHAT_ID   = "-5009690228"

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text
        }
        requests.post(url, json=payload, timeout=5)
        print("📤 Telegram 已送出：", text)
    except Exception as e:
        print("❌ Telegram 推播失敗：", e)

# =========================
# Demo 門檻
# =========================
TEMP_LOW_THRESHOLD = 18
RAIN_THRESHOLD     = 60

# =========================
# 狀態 / 暫存
# =========================
weather_alert_sent = False
latest_weight = {}              # 只存「狀態」
last_weight_push_ts = 0

# =========================
# 天氣更新（Demo）
# =========================
def update_weather():
    global weather_data, weather_alert_sent

    url = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-D0047-065?Authorization=CWA-00898630-8462-4B79-84D6-07DFC022CB32&downloadType=WEB&format=JSON"

    while True:
        try:
            data = requests.get(url, timeout=5).json()
            locations = data["cwaopendata"]["Dataset"]["Locations"]["Location"]

            for loc in locations:
                if loc["LocationName"] == "楠梓區":
                    elements = {e["ElementName"]: e["Time"] for e in loc["WeatherElement"]}

                    weather = elements["天氣現象"][0]["ElementValue"]["Weather"]
                    temps = [int(t["ElementValue"]["Temperature"]) for t in elements["溫度"]]
                    min_temp = min(temps)
                    max_temp = max(temps)

                    rain_str = elements["3小時降雨機率"][0]["ElementValue"]["ProbabilityOfPrecipitation"]
                    rain_prob = int(rain_str) if rain_str.isdigit() else 0

                    weather_data = {
                        "city": "Kaohsiung - Nanzih",
                        "weather": weather,
                        "min_temp": min_temp,
                        "max_temp": max_temp,
                        "rain_prob": rain_prob
                    }

                    print("✅ 天氣更新：", weather_data)

                    # ===== Demo：只推播一次 =====
                    if not weather_alert_sent:
                        msgs = []
                        if min_temp <= TEMP_LOW_THRESHOLD:
                            msgs.append("注意保暖")
                        if rain_prob >= RAIN_THRESHOLD:
                            msgs.append("攜帶雨具")

                        send_telegram(
                            f"楠梓區天氣\n"
                            f"天氣：{weather}\n"
                            f"最低溫：{min_temp}°C\n"
                            f"降雨機率：{rain_prob}%\n"
                            f"{'提醒：' + '、'.join(msgs) if msgs else '無需特別提醒'}"
                        )

                        weather_alert_sent = True
                    break

        except Exception as e:
            print("❌ 天氣更新錯誤：", e)

        time.sleep(60)

# =========================
# 重量推播（只傳狀態）
# =========================
def scheduler_loop():
    global last_weight_push_ts

    while True:
        now = time.time()

        if now - last_weight_push_ts >= 120:   # Demo：5 分鐘
            last_weight_push_ts = now

            try:
                if not latest_weight:
                    send_telegram("重量狀態回報：尚未收到資料")
                else:
                    for student, info in latest_weight.items():
                        send_telegram(
                            f"{student} 同學\n"
                            f"書包重量狀態：{info['status']}"
                        )
                latest_weight.clear()

            except Exception as e:
                print("❌ 重量推播錯誤：", e)

        time.sleep(5)

# =========================
# API：提供天氣
# =========================
@app.route("/weather")
def get_weather():
    return jsonify(weather_data)

# =========================
# API：接收重量（只用 status）
# =========================
@app.route("/weight")
def weight_status():
    student = request.args.get("student", "陳大壯")
    status  = request.args.get("status", "")   # 只用這個
    value  = request.args.get("value", "0")
    # value 仍可傳，但不使用

    print(f"📥 重量接收：{student} | 狀態={status}({value} kg)")

    latest_weight[student] = {
        "status": status,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        gs_url = GOOGLE_SCRIPT_URL + f"?action=weight&status={status}&value={value}"
        r = requests.get(gs_url, timeout=5)
        print("📤 GAS 回傳：", r.text)
    except Exception as e:
        print("❌ Google Sheet 傳送失敗：", e)

    return "OK"

# =========================
# 主程式
# =========================
if __name__ == "__main__":
    threading.Thread(target=update_weather, daemon=True).start()
    threading.Thread(target=scheduler_loop, daemon=True).start()

    print("Flask Demo 伺服器啟動")
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)




