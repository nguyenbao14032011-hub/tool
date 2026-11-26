import hashlib
import json
import math
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from google import genai
from google.genai import types

BOT_TOKEN = os.getenv("BOT_TOKEN", "9160345617:AAHgGOmh015rSFy2WMTyGYnlBzecKpkovZ4")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

ADMIN_USERNAME = "lionVnIos".lstrip("@").lower()
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().lstrip("-").isdigit()
}
ADMIN_CONTACT = "@lionVnIos"

DATA_FILE = os.getenv("SUB_DATA_FILE", "subscriptions.json")

PACKAGES = {
    1: "50k",
    2: "100k",
    6: "200k",
}
SECONDS_PER_MONTH = 30 * 24 * 3600

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


# --- HTTP SERVER CHO RENDER WEB SERVICE ---
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"OK - Bot is running")

    def log_message(self, format, *args):
        return


def start_web_server() -> None:
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"[WEB] Listening on port {port}", flush=True)
    server.serve_forever()


# --- QUẢN LÝ GÓI & ADMIN ---
def is_admin(message) -> bool:
    user = getattr(message, "from_user", None)
    if not user:
        return False
    if user.id in ADMIN_IDS:
        return True
    if user.username and user.username.lower() == ADMIN_USERNAME:
        ADMIN_IDS.add(user.id)
        return True
    return False


def load_subscriptions() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_subscriptions(data: dict) -> None:
    tmp_path = f"{DATA_FILE}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, DATA_FILE)


def get_active_subscription(user_id: int) -> tuple[bool, float]:
    subs = load_subscriptions()
    record = subs.get(str(user_id))
    if not record:
        return False, 0.0
    exp = float(record.get("expires_at", 0.0))
    now = time.time()
    return (exp > now), exp


def grant_subscription(target_user_id: int, months: int) -> float:
    subs = load_subscriptions()
    key = str(target_user_id)
    now = time.time()
    current_exp = float(subs.get(key, {}).get("expires_at", 0.0))
    base_time = current_exp if current_exp > now else now
    new_exp = base_time + months * SECONDS_PER_MONTH
    subs[key] = {
        "user_id": target_user_id,
        "expires_at": new_exp,
        "updated_at": now,
    }
    save_subscriptions(subs)
    return new_exp


def format_remaining(expires_at: float) -> str:
    rem = max(0, int(expires_at - time.time()))
    days = rem // 86400
    hours = (rem % 86400) // 3600
    if days > 0:
        return f"{days} ngày {hours} giờ"
    return f"{hours} giờ"


def deny_access(message) -> None:
    uid = message.from_user.id
    msg = (
        f"⛔ <b>Không thể kích hoạt tool</b>\n"
        f"🆔 ID Telegram: <code>{uid}</code>\n"
        f"📦 Gói: 1 tháng (50k) · 2 tháng (100k) · 6 tháng (200k)\n"
        f"📩 Liên hệ admin {ADMIN_CONTACT} & gửi ID <code>{uid}</code> để nạp gói."
    )
    bot.reply_to(message, msg)


# --- THUẬT TOÁN 3.000 TẦNG ---
def to_md5(text: str) -> str:
    s = text.strip().lower()
    return s if re.fullmatch(r"[0-9a-f]{32}", s) else hashlib.md5(s.encode("utf-8")).hexdigest()


def run_3000_layer_pipeline(raw_text: str, md5_hex: str) -> dict:
    src_bytes = raw_text.encode("utf-8")
    hex_vals = [int(ch, 16) for ch in md5_hex]

    ascii_sum = sum(src_bytes)
    bigram_score = sum(
        ((hex_vals[i] * 16 + hex_vals[i + 1]) / 255.0) * (1.0 + (i % 4) * 0.05)
        for i in range(31)
    ) / 31.0
    freq_map = {c: md5_hex.count(c) for c in set(md5_hex)}
    char_entropy = -sum((cnt / 32.0) * math.log2(cnt / 32.0) for cnt in freq_map.values())
    char_vec = [(v - 7.5) / 7.5 for v in hex_vals]
    c1 = sum(
        char_vec[step % 32] * math.cos((step / 450.0) * math.pi + (ascii_sum % 17) * 0.1)
        for step in range(450)
    ) / 450.0
    p_char = 0.5 + 0.5 * math.tanh(c1 * 3.5 + (bigram_score - 0.5) * 1.4)

    mean_v = sum(hex_vals) / 32.0
    var_v = sum((v - mean_v) ** 2 for v in hex_vals) / 32.0
    std_v = math.sqrt(var_v)
    norm_params = [((v - mean_v) / (std_v + 1e-6)) for v in hex_vals]
    noise_filter = 1.0 / (1.0 + max(0.0, char_entropy - 3.5))
    c2 = sum(
        norm_params[step % 32] * (0.7 + 0.3 * math.sin((step / 450.0) * 2 * math.pi))
        for step in range(450)
    ) / 450.0
    p_param = 0.5 + 0.5 * math.tanh(c2 * 2.2 * noise_filter + (mean_v - 7.5) * 0.12)

    poly_terms = [
        0.6 * norm_params[i]
        + 0.3 * (norm_params[i] ** 2) * (1 if norm_params[i] >= 0 else -1)
        + 0.25 * (norm_params[i] * norm_params[(i + 1) % 32])
        for i in range(32)
    ]
    c3 = sum(
        poly_terms[step % 32] * ((step + 1) / 450.0)
        for step in range(450)
    ) / 225.0
    p_alg = 0.5 + 0.5 * math.tanh(c3 * 1.8)

    mat = [poly_terms[r * 8 : (r + 1) * 8] for r in range(4)]
    row_energies = [
        sum(mat[r][k] * mat[r][(k + r) % 8] for k in range(8)) / 8.0
        for r in range(4)
    ]
    c4 = sum(
        row_energies[step % 4] * math.cos((step / 500.0) * math.pi * 1.5)
        for step in range(500)
    ) / 500.0
    p_mat = 0.5 + 0.5 * math.tanh(c4 * 3.0 + sum(row_energies) * 0.35)

    axes = [
        sum(poly_terms[i] * math.cos(i * 0.4) for i in range(32)) / 16.0,
        sum(poly_terms[i] * math.sin(i * 0.7) for i in range(32)) / 16.0,
        sum(poly_terms[i] * ((i % 3) - 1) for i in range(32)) / 24.0,
    ]
    mda_proj = axes[0] * 0.5 + axes[1] * 0.3 + axes[2] * 0.2
    c5 = sum(
        mda_proj * math.sin((step / 450.0) * math.pi + axes[step % 3])
        for step in range(450)
    ) / 450.0
    p_mda = 0.5 + 0.5 * math.tanh(c5 * 4.0 + mda_proj * 1.5)

    prior = p_char * 0.14 + p_param * 0.18 + p_alg * 0.20 + p_mat * 0.24 + p_mda * 0.24
    markov_shift = (hex_vals[-1] - 7.5) / 30.0
    c6 = sum(
        (prior - 0.5) * (0.85 + 0.15 * math.cos((step / 350.0) * math.pi))
        for step in range(350)
    ) / 350.0
    p_prob = max(0.05, min(0.95, 0.5 + c6 * 2.2 + markov_shift))

    layer_signals = [p_char, p_param, p_alg, p_mat, p_mda, p_prob]
    weights = [0.10, 0.14, 0.16, 0.20, 0.18, 0.22]
    attn_scores = [math.exp((s - 0.5) * 2.5) * w for s, w in zip(layer_signals, weights)]
    attn_sum = sum(attn_scores)
    attn_out = sum(s * (a / attn_sum) for s, a in zip(layer_signals, attn_scores))

    residual = 0.0
    for step in range(350):
        idx = step % 6
        residual += (layer_signals[idx] - attn_out) * math.sin((step / 350.0) * math.pi)
    final_p_tai = max(0.01, min(0.99, attn_out + (residual / 350.0) * 0.25))

    tai_pct = round(final_p_tai * 100.0, 1)
    xiu_pct = round(100.0 - tai_pct, 1)
    margin = abs(tai_pct - xiu_pct)

    pick = "TÀI" if tai_pct >= xiu_pct else "XỈU"
    icon = "🔥" if pick == "TÀI" else "❄️"
    conf = "Cao" if margin >= 14 else ("Vừa" if margin >= 6 else "Thấp")

    filled = int(round(tai_pct / 10.0))
    bar = "🟥" * filled + "🟦" * (10 - filled)

    return {
        "md5": md5_hex,
        "tai": tai_pct,
        "xiu": xiu_pct,
        "pick": pick,
        "icon": icon,
        "conf": conf,
        "bar": bar,
        "layers_summary": (
            f"C1:{p_char*100:.0f}% C2:{p_param*100:.0f}% C3:{p_alg*100:.0f}% "
            f"C4:{p_mat*100:.0f}% C5:{p_mda*100:.0f}% C6:{p_prob*100:.0f}%"
        ),
    }


def ai_core_refine(stats: dict) -> None:
    if not ai_client:
        return
    try:
        ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                f"Hash {stats['md5'][:12]} qua 3000 tầng ({stats['layers_summary']}) "
                f"cho Tài {stats['tai']}% / Xỉu {stats['xiu']}%, quyết định {stats['pick']}."
            ),
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=40),
        )
    except Exception:
        pass


def render_output(raw: str, s: dict) -> str:
    short_in = raw if len(raw) <= 16 else f"{raw[:7]}...{raw[-5:]}"
    return (
        f"🎯 {s['icon']} <b>{s['pick']}</b> · 🛡️ <i>Tin cậy: {s['conf']}</i>\n"
        f"📥 <code>{short_in}</code>\n"
        f"🔑 <code>{s['md5'][:16]}...</code>\n"
        f"{s['bar']} 🔺<b>{s['tai']}%</b> / 🔻<b>{s['xiu']}%</b>"
    )


@bot.message_handler(commands=["nap"])
def cmd_nap(message):
    try:
        if not is_admin(message):
            bot.reply_to(message, f"🚫 Lệnh này chỉ dành cho admin {ADMIN_CONTACT}.")
            return

        parts = (message.text or "").strip().split()
        if len(parts) != 3:
            bot.reply_to(message, "⚠️ Cú pháp đúng: <code>/nap số_tháng id_người_mua</code>\nVí dụ: <code>/nap 1 123456789</code>")
            return

        try:
            months = int(parts[1])
            target_id = int(parts[2])
        except ValueError:
            bot.reply_to(message, "⚠️ Số tháng và ID người mua phải là số nguyên hợp lệ.")
            return

        if months not in PACKAGES:
            bot.reply_to(message, "📦 Gói hỗ trợ: <b>1</b> tháng (50k), <b>2</b> tháng (100k), <b>6</b> tháng (200k).")
            return

        new_exp = grant_subscription(target_id, months)
        rem_str = format_remaining(new_exp)
        price = PACKAGES[months]

        bot.reply_to(
            message,
            f"✅ Đã nạp gói <b>{months} tháng ({price})</b> cho ID <code>{target_id}</code>\n"
            f"⏳ Thời hạn còn lại: <b>{rem_str}</b>",
        )

        try:
            bot.send_message(
                target_id,
                f"🎉 Tài khoản ID <code>{target_id}</code> đã được kích hoạt gói <b>{months} tháng ({price})</b>!\n"
                f"⏳ Thời hạn sử dụng: <b>{rem_str}</b> — Gửi chuỗi MD5 để bắt đầu.",
            )
        except Exception:
            pass
    except Exception as e:
        print(f"[CMD_NAP ERR] {e}", flush=True)


@bot.message_handler(commands=["start"])
def on_start(m):
    try:
        uid = m.from_user.id
        active, exp = get_active_subscription(uid)
        status_line = (
            f"✅ Đã kích hoạt · Còn <b>{format_remaining(exp)}</b>"
            if active
            else "⛔ Chưa kích hoạt gói"
        )
        welcome = (
            "⚡ <b>MD5 · 3000-LAYER ENGINE</b> 🧠\n"
            f"🆔 ID của bạn: <code>{uid}</code> · {status_line}\n"
            "📦 Gói: 1T (50k) · 2T (100k) · 6T (200k) · LH: " + ADMIN_CONTACT + "\n"
            "🔑 <code>9e107d9d372bb6826bd81d3542a419d6</code>"
        )
        bot.reply_to(m, welcome)
    except Exception as e:
        print(f"[START ERR] {e}", flush=True)


@bot.message_handler(func=lambda m: bool(m.text and m.text.strip()))
def on_input(m):
    try:
        uid = m.from_user.id
        active, _ = get_active_subscription(uid)
        if not active and not is_admin(m):
            deny_access(m)
            return

        raw = m.text.strip()
        try:
            bot.send_chat_action(m.chat.id, "typing")
        except Exception:
            pass
        md5_hex = to_md5(raw)
        stats = run_3000_layer_pipeline(raw, md5_hex)
        ai_core_refine(stats)
        bot.reply_to(m, render_output(raw, stats))
    except Exception as e:
        print(f"[INPUT ERR] {e}", flush=True)


def _extract_retry_after(err: Exception) -> int:
    msg = str(err)
    match = re.search(r"retry after\s+(\d+)|\"retry_after\"\s*:\s*(\d+)", msg, re.IGNORECASE)
    if match:
        val = int(match.group(1) or match.group(2))
        return max(10, val + 5)
    if "429" in msg or "Too Many Requests" in msg:
        return 30
    return 10


def run_bot_polling() -> None:
    time.sleep(5)
    try:
        bot.remove_webhook()
    except Exception:
        pass

    while True:
        try:
            print("[BOT] Polling started...", flush=True)
            bot.polling(
                non_stop=True,
                skip_pending=True,
                timeout=30,
                long_polling_timeout=25,
                interval=2,
            )
        except Exception as err:
            wait_sec = _extract_retry_after(err)
            print(f"[BOT] Polling error ({wait_sec}s): {err}", flush=True)
            time.sleep(wait_sec)


if __name__ == "__main__":
    threading.Thread(target=run_bot_polling, daemon=True).start()
    start_web_server()
