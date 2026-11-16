import asyncio
import base64
import html
import json
import os
import re
import io
import urllib.error
import urllib.parse
import urllib.request
from threading import Thread
from flask import Flask

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError, TimedOut, NetworkError, RetryAfter
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

app = Flask(__name__)

@app.route('/')
def home():
    return "Middleman Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

flask_thread = Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
ADMIN_USER_ID = 8258524753  # Your Telegram user ID

# Custom Emoji Icon IDs (Yahan apni numeric emoji IDs dalein)
ICON_ACCOUNTS_ID = "5341715473882955310"       # Accounts button emoji ID
ICON_HELP_ID = "5361741454685256344"           # View Help Commands emoji ID
ICON_OFFICIAL_CH_ID = "5282843764451195532"    # Official Channel emoji ID
ICON_NETWORK_ID = "5427168083074628963"        # View Network emoji ID
ICON_BACK_ID = "5877629862306385808"           # Back button emoji ID
JOINED_BUTTON_EMOJI_ID = "5206607081334906820" # "I've Joined" button emoji ID
PREV_BUTTON_EMOJI_ID = "5447389832781264371"   # Prev button emoji ID
NEXT_BUTTON_EMOJI_ID = "5447181973544008180"   # Next button emoji ID

# Standard / Premium Emojis
PREMIUM_EMOJIS = {
    "warn": "5231012545799666522",
    "arrow": "5416117059207572332",
    "success": "5206607081334906820",
    "error": "5210952531676504517",
    "loading": "5386367538735104399",
    "user": "5206607081334906820",
    "time": "5440621591387980068",
    "gear": "5341715473882955310",
    "join_check": "5406745015365943482",
}

DATA_FILE = "user_accounts.json"
WAITING_FOR_SESSION = 1

start_menu_messages = {}

# ----------------- STORAGE HELPERS -----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "all_chats": []}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"users": {}, "all_chats": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def register_chat(chat_id: int):
    data = load_data()
    if chat_id not in data.get("all_chats", []):
        data.setdefault("all_chats", []).append(chat_id)
        save_data(data)

def get_user_accounts(user_id: int):
    data = load_data()
    return data.get("users", {}).get(str(user_id), [])

def add_user_account(user_id: int, username: str, sessionid: str, uid: str):
    data = load_data()
    users = data.setdefault("users", {})
    user_list = users.setdefault(str(user_id), [])
    
    for acc in user_list:
        if acc["uid"] == uid or acc["username"].lower() == username.lower():
            acc["sessionid"] = sessionid
            acc["username"] = username
            save_data(data)
            return
            
    user_list.append({"username": username, "sessionid": sessionid, "uid": uid})
    save_data(data)

def remove_user_account(user_id: int, username: str):
    data = load_data()
    user_list = data.get("users", {}).get(str(user_id), [])
    data["users"][str(user_id)] = [acc for acc in user_list if acc["username"].lower() != username.lower()]
    save_data(data)

def e(key: str, fallback: str) -> str:
    custom_id = str(PREMIUM_EMOJIS.get(key, "") or "").strip()
    if custom_id:
        return f'<tg-emoji emoji-id="{custom_id}">{fallback}</tg-emoji>'
    return fallback

# ----------------- CHANNELS CONFIG -----------------
CHANNELS = [
    {"name": "Join Channel 1", "url": "https://t.me/affux", "chat_id": "@affux"},
    {"name": "Join Channel 2", "url": "https://t.me/chated", "chat_id": "@chated"},
    {"name": "Join Channel 3", "url": "https://t.me/flicktools", "chat_id": "@flicktools"},
    {"name": "Join Channel 4", "url": "https://t.me/forumingly", "chat_id": "@forumingly"},
]

# ----------------- PRIVACY FEATURES SETUP -----------------
PAGE_FEATURES = {
    1: [
        [("Hide Followers", "act_hide_list", "danger"), ("Show Followers", "act_unhide_list", "success")],
        [("Disable DP Zoom", "act_hide_pfp", "danger"), ("Allow DP Zoom", "act_unhide_pfp", "success")],
        [("Hide My Account", "act_hide_acc", "danger"), ("Show My Account", "act_unhide_acc", "success")],
    ],
    2: [
        [("Block Story Share", "act_disable_story_share", "danger"), ("Allow Story Share", "act_enable_story_share", "success")],
        [("Hide Suggestions", "act_hide_suggestions", "danger"), ("Show Suggestions", "act_show_suggestions", "success")],
        [("Disable Contact Sync", "act_disable_contacts", "danger"), ("Enable Contact Sync", "act_enable_contacts", "success")],
    ],
    3: [
        [("Turn On Word Filter", "act_enable_words", "success"), ("Turn Off Word Filter", "act_disable_words", "danger")],
        [("Block DM Media Export", "act_disable_media_export", "danger"), ("Allow DM Media Export", "act_enable_media_export", "success")],
        [("Enable Screenshot Alert", "act_enable_screenshot_alert", "success"), ("Disable Screenshot Alert", "act_disable_screenshot_alert", "danger")],
    ],
    4: [
        [("Enable Quiet Mode", "act_enable_quiet", "success"), ("Disable Quiet Mode", "act_disable_quiet", "danger")],
        [("Hide Chat Presence", "act_hide_chat_presence", "danger"), ("Show Chat Presence", "act_show_chat_presence", "success")],
        [("Enable Spam Filter", "act_enable_spam_filter", "success"), ("Disable Spam Filter", "act_disable_spam_filter", "danger")],
    ],
    5: [
        [("Hide DM Requests", "act_hide_dm_reqs", "danger"), ("Show DM Requests", "act_show_dm_reqs", "success")],
        [("Block Tag Scraping", "act_block_tag_scraping", "danger"), ("Allow Tag Scraping", "act_allow_tag_scraping", "success")],
    ],
}
TOTAL_PAGES = len(PAGE_FEATURES)

# ----------------- INSTAGRAM API HELPERS -----------------
def parse_session(sid: str):
    sid = sid.strip()
    if not sid:
        return None, "Empty session ID."
    if sid.startswith("sessionid="):
        sid = sid[len("sessionid="):]
    if any(ord(c) <= 32 or ord(c) >= 127 or c in ';,"\\' for c in sid):
        return None, "Invalid characters in session ID."

    m = re.fullmatch(r"([1-9][0-9]*)(?::|%3[aA])(.+)", sid)
    if not m:
        return None, "Wrong format (must start with user ID + ':' or '%3A')."

    return {"raw": sid, "uid": m.group(1), "token_len": len(m.group(2))}, None

def fetch_username(sessionid: str, uid: str) -> str:
    try:
        url = "https://www.instagram.com/api/v1/accounts/edit/web_form_data/"
        req = urllib.request.Request(
            url,
            headers={
                "Cookie": f"sessionid={sessionid}; ds_user_id={uid}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "X-IG-App-ID": "936619743392459",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            username = data.get("form_data", {}).get("username")
            if username:
                return username
    except Exception:
        pass

    try:
        url = f"https://i.instagram.com/api/v1/users/{uid}/info/"
        req = urllib.request.Request(
            url,
            headers={
                "Cookie": f"sessionid={sessionid}; ds_user_id={uid}",
                "User-Agent": "Instagram 453.0.0",
                "X-IG-App-ID": "124024574287414",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            username = data.get("user", {}).get("username")
            if username:
                return username
    except Exception:
        pass

    return None

def _sanitize_ig_debug(value):
    """Remove credentials and identifying values before writing API data to Termux."""
    sensitive_keys = {
        "sessionid", "session_id", "authorization", "cookie", "set-cookie",
        "password", "passwd", "access_token", "refresh_token", "token",
        "email", "phone_number", "phone", "username", "full_name",
    }
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in sensitive_keys or any(part in key_text for part in ("token", "cookie", "password", "session")):
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = _sanitize_ig_debug(item)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_ig_debug(item) for item in value]
    if isinstance(value, str):
        # Scrub credentials if Instagram embeds them in a text field.
        value = re.sub(r"(?i)(sessionid|authorization|cookie|access_token|refresh_token)(\s*[:=]\s*)[^,;\s]+", r"\1\2[REDACTED]", value)
        return value[:12000]
    return value


def _print_ig_debug(title, payload):
    try:
        safe_payload = _sanitize_ig_debug(payload)
        print(f"\n========== {title} ==========", flush=True)
        print(json.dumps(safe_payload, indent=2, ensure_ascii=False, default=str)[:16000], flush=True)
        print("========== END DEBUG ==========\n", flush=True)
    except Exception as debug_exc:
        print(f"[IG DEBUG] Could not print sanitized response: {type(debug_exc).__name__}", flush=True)


def execute_ig_mutation(sessionid: str, uid: str, setting_id: str, value: bool, callsite: str = "account_privacy"):
    # Log only non-secret request metadata; never print sessionid, uid, auth or cookies.
    _print_ig_debug("INSTAGRAM MUTATION REQUEST", {
        "setting_id": setting_id,
        "target_value": value,
        "callsite": callsite,
        "endpoint": "https://i.instagram.com/graphql/query",
    })

    tok = base64.b64encode(
        json.dumps(
            {"ds_user_id": uid, "sessionid": sessionid, "should_use_header_over_cookies": True},
            separators=(",", ":"),
        ).encode()
    ).decode()

    form = {
        "method": "post",
        "format": "json",
        "server_timestamps": "true",
        "locale": "user",
        "fb_api_req_friendly_name": "IGSettingsBooleanMutation",
        "client_doc_id": "2669261950526978627082629536",
        "variables": json.dumps({"setting_id": setting_id, "allow_error_codes": True, "callsite": callsite, "value": value}),
    }

    req = urllib.request.Request(
        "https://i.instagram.com/graphql/query",
        data=urllib.parse.urlencode(form).encode(),
        headers={
            "Authorization": f"Bearer IGT:2:{tok}",
            "Cookie": f"sessionid={sessionid}; ds_user_id={uid}",
            "IG-INTENDED-USER-ID": uid,
            "X-IG-App-ID": "124024574287414",
            "X-Auth-Type": "instagram",
            "User-Agent": "Instagram 453.0.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "identity",
            "X-GraphQL-Client-Library": "pando",
            "X-FB-Friendly-Name": "IGSettingsBooleanMutation",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            http_status = getattr(r, "status", None)
            raw_response = r.read(1024 * 1024 + 1)
        try:
            body = json.loads(raw_response.decode("utf-8", errors="replace"))
        except Exception:
            body = {"unparsed_response": raw_response.decode("utf-8", errors="replace")[:12000]}
        _print_ig_debug("INSTAGRAM MUTATION RESPONSE", {
            "http_status": http_status,
            "response": body,
        })
    except urllib.error.HTTPError as exc:
        raw_error = exc.read(1024 * 1024 + 1)
        try:
            error_body = json.loads(raw_error.decode("utf-8", errors="replace"))
        except Exception:
            error_body = {"unparsed_response": raw_error.decode("utf-8", errors="replace")[:12000]}
        _print_ig_debug("INSTAGRAM HTTP ERROR RESPONSE", {
            "http_status": exc.code,
            "reason": str(exc.reason),
            "response": error_body,
        })
        raise RuntimeError(f"Instagram HTTP {exc.code}: {str(exc.reason)}") from None
    except Exception as exc:
        _print_ig_debug("INSTAGRAM REQUEST EXCEPTION", {
            "exception_type": type(exc).__name__,
            "message": str(exc),
        })
        raise

    data = body.get("data") if isinstance(body, dict) else {}
    root = "xdt_api__v1__settings__set_bool"
    res = next((v for k, v in (data or {}).items() if k == root or k.startswith(root + "(")), {})

    ok = (
        isinstance(body, dict)
        and not body.get("errors")
        and not body.get("error")
        and body.get("status") != "fail"
        and isinstance(res, dict)
        and res.get("value") is value
    )
    reason = body.get("message") or body.get("error")
    errors = body.get("errors") if isinstance(body, dict) else None
    if errors:
        # Instagram sometimes returns HTTP 200 with data=null and a generic
        # GraphQL execution error. This is NOT a successful settings change.
        error_messages = [
            str(item.get("message", ""))
            for item in errors
            if isinstance(item, dict)
        ]
        if data is None and any(msg.lower() == "execution error" for msg in error_messages):
            reason = (
                "Instagram rejected this setting mutation (GraphQL execution error). "
                "The current setting identifier/client_doc_id or required mutation "
                "parameters are not verified for this feature. No change was confirmed."
            )
        else:
            reason = json.dumps(errors, ensure_ascii=False)[:1000]
    if not reason and not ok:
        reason = json.dumps(body, ensure_ascii=False)[:1000]
    return ok, reason or ("Instagram did not confirm the requested setting." if not ok else None)

def check_account_status(sessionid: str, uid: str) -> dict:
    """Read the settings exposed by Instagram's web form endpoint.

    UNKNOWN means Instagram did not return that field; it is not treated as OFF.
    """
    status_summary = {
        "Followers List Hidden": "UNKNOWN",
        "DP Zoom Disabled": "UNKNOWN",
        "Search Discovery Off": "UNKNOWN",
        "Quiet Mode": "UNKNOWN",
    }

    url = "https://www.instagram.com/api/v1/accounts/edit/web_form_data/"
    req = urllib.request.Request(
        url,
        headers={
            "Cookie": f"sessionid={sessionid}; ds_user_id={uid}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-IG-App-ID": "936619743392459",
            "X-Requested-With": "XMLHttpRequest",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        fd = data.get("form_data", {}) if isinstance(data, dict) else {}
        if not isinstance(fd, dict):
            raise ValueError("Instagram returned an invalid form_data response.")

        # Use the same field name used by the corresponding mutation mapping.
        if "hide_followers_following_list" in fd:
            status_summary["Followers List Hidden"] = "ON" if fd["hide_followers_following_list"] is True else "OFF"
        if "allow_profile_picture_expansion" in fd:
            status_summary["DP Zoom Disabled"] = "ON" if fd["allow_profile_picture_expansion"] is False else "OFF"
        if "should_show_account_suggestions" in fd:
            status_summary["Search Discovery Off"] = "ON" if fd["should_show_account_suggestions"] is False else "OFF"
        if "quiet_mode_enabled" in fd:
            status_summary["Quiet Mode"] = "ON" if fd["quiet_mode_enabled"] is True else "OFF"
        return status_summary
    except Exception as exc:
        return {"Status Check": f"ERROR: {exc}"}

# ----------------- TELEGRAM MENUS -----------------
async def check_user_joined_all(bot, user_id: int) -> bool:
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except TelegramError:
            return False
    return True

async def send_join_prompt(target_message):
    btn_args = {"text": "I've Joined", "callback_data": "check_joined", "style": "success"}
    joined_emoji_id = str(JOINED_BUTTON_EMOJI_ID or "").strip()
    if joined_emoji_id:
        btn_args["icon_custom_emoji_id"] = joined_emoji_id

    keyboard = [
        [InlineKeyboardButton(CHANNELS[0]["name"], url=CHANNELS[0]["url"]), InlineKeyboardButton(CHANNELS[1]["name"], url=CHANNELS[1]["url"])],
        [InlineKeyboardButton(CHANNELS[2]["name"], url=CHANNELS[2]["url"]), InlineKeyboardButton(CHANNELS[3]["name"], url=CHANNELS[3]["url"])],
        [InlineKeyboardButton(**btn_args)],
    ]
    await target_message.reply_text(f"<b>To use the Bot please Join: {e('join_check', '✅')}</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

def build_start_keyboard():
    def make_button(
        text,
        data=None,
        url=None,
        emoji_id=None,
        emoji="",
        style=None
    ):
        emoji_html = ""

        emoji_id = str(emoji_id or "").strip()

        if emoji_id:
            emoji_html = (
                f'<tg-emoji emoji-id="{html.escape(emoji_id, quote=True)}">'
                f'{emoji}</tg-emoji> '
            )

        label = emoji_html + html.escape(text)
        style_attr = f' style="{style}"' if style else ""

        if url:
            return (
                f'<tg-button type="url" '
                f'url="{html.escape(url, quote=True)}"'
                f'{style_attr}>'
                f'{label}'
                '</tg-button>'
            )

        return (
            f'<tg-button type="callback_data" '
            f'data="{html.escape(str(data), quote=True)}"'
            f'{style_attr}>'
            f'{label}'
            '</tg-button>'
        )

    accounts = make_button(
        "Accounts",
        data="menu_accounts",
        emoji_id=ICON_ACCOUNTS_ID,
        emoji="👤",
        style="success"
    )

    help_menu = make_button(
        "View Menu",
        data="menu_help_page_1",
        emoji_id=ICON_HELP_ID,
        emoji="⚙️"
    )

    official_channel = make_button(
        "Official Channel",
        url="https://t.me/+Al5LghBDbfxhN2Iy",
        emoji_id=ICON_OFFICIAL_CH_ID,
        emoji="📢",
        style="primary"
    )

    network = make_button(
        "View Network",
        url="https://t.me/affux",
        emoji_id=ICON_NETWORK_ID,
        emoji="🌐",
        style="danger"
    )

    return (
        '<tg-button-row>'
        f'{accounts}{help_menu}'
        '</tg-button-row>'
        '<tg-button-row>'
        f'{official_channel}{network}'
        '</tg-button-row>'
    )

def get_start_text():
    return {
        "html": (
            "<p>"
            "<tg-emoji emoji-id='5251203410396458957'>⚠️</tg-emoji> "
            "<b>@NimoggBot</b>"
            "</p>"
            "<p><i>Take control of your Instagram privacy with ease.</i></p>"
            "<blockquote>"
            "Manage visibility, organize followers, and customize your privacy "
            "experience with just a few taps."
            "</blockquote>"
            "<p>"
            "<tg-emoji emoji-id='5416117059207572332'>⚠️</tg-emoji> "
            "Tap a button below to get started."
            "</p>"
        )
    }


async def send_start_menu(bot, chat_id: int):
    register_chat(chat_id)

    # Delete previous start menu if it exists
    old_msg_id = start_menu_messages.get(chat_id)

    if old_msg_id:
        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=old_msg_id
            )
        except Exception:
            pass

    rich_text = get_start_text()["html"] + build_start_keyboard()

    result = await bot._post(
        "sendRichMessage",
        data={
            "chat_id": chat_id,
            "rich_message": {
                "html": rich_text
            }
        }
    )

    start_menu_messages[chat_id] = result["message_id"]

def build_help_keyboard(page: int = 1) -> str:
    keyboard_html = []

    current_page_features = PAGE_FEATURES.get(
        page, PAGE_FEATURES[1]
    )

    allowed_styles = {"primary", "success", "danger", "link"}

    def make_button(label, callback_data, style=None, emoji_id=None, emoji=""):
        label = html.escape(str(label))
        callback_data = html.escape(str(callback_data), quote=True)

        style_attr = (
            f' style="{style}"'
            if style in allowed_styles else ""
        )

        emoji_html = ""
        if emoji_id and str(emoji_id).strip():
            emoji_html = (
                f'<tg-emoji emoji-id="{html.escape(str(emoji_id), quote=True)}">'
                f'{html.escape(emoji)}</tg-emoji> '
            )

        return (
            f'<tg-button type="callback_data"{style_attr} '
            f'data="{callback_data}">'
            f'{emoji_html}{label}'
            f'</tg-button>'
        )

    # Feature buttons
    for row in current_page_features:
        row_buttons = []

        for btn in row:
            label = btn[0]
            callback_data = btn[1]
            style = btn[2] if len(btn) > 2 and btn[2] else None

            row_buttons.append(
                make_button(label, callback_data, style)
            )

        if row_buttons:
            keyboard_html.append(
                '<tg-button-row>'
                + "".join(row_buttons)
                + '</tg-button-row>'
            )

    # Navigation buttons
    nav_buttons = []

    if page > 1:
        nav_buttons.append(
            make_button(
                "Prev",
                f"help_page_{page - 1}",
                "primary",
                PREV_BUTTON_EMOJI_ID,
                "⬅️"
            )
        )

    # Total Pages - Default Style
    nav_buttons.append(
        make_button(
            f"{page}/{TOTAL_PAGES}",
            "noop"
        )
    )

    if page < TOTAL_PAGES:
        nav_buttons.append(
            make_button(
                "Next",
                f"help_page_{page + 1}",
                "primary",
                NEXT_BUTTON_EMOJI_ID,
                "➡️"
            )
        )

    keyboard_html.append(
        '<tg-button-row>'
        + "".join(nav_buttons)
        + '</tg-button-row>'
    )

    # Back to Main Menu - Default Style
    back_button = make_button(
        "Back to Main Menu",
        "back_to_main",
        emoji_id=ICON_BACK_ID,
        emoji="⬅️"
    )

    keyboard_html.append(
        '<tg-button-row>'
        + back_button
        + '</tg-button-row>'
    )

    return "\n".join(keyboard_html)

def get_commands_table_message():
    text = (
        "<b><tg-emoji emoji-id='5341715473882955310'>⚙️</tg-emoji> Bot Commands Directory</b>\n\n"
        "<pre>"
        "+----------+----------------------------+\n"
        "| Command  | What it does               |\n"
        "+----------+----------------------------+\n"
        "| /add     | Link new Instagram account |\n"
        "| /check   | View live privacy status   |\n"
        "| /remove  | Unlink an existing account |\n"
        "+----------+----------------------------+\n"
        "</pre>\n"
        "<footer>Use the commands directly or manage options from the main dashboard.</footer>"
    )
    b_back = {"text": "← Back", "callback_data": "back_to_main", "style": "primary"}
    if ICON_BACK_ID.strip():
        b_back["icon_custom_emoji_id"] = ICON_BACK_ID.strip()
    return text, InlineKeyboardMarkup([[InlineKeyboardButton(**b_back)]])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await check_user_joined_all(context.bot, user_id):
        await send_join_prompt(update.message)
    else:
        await send_start_menu(context.bot, update.effective_chat.id)


async def check_joined_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if await check_user_joined_all(context.bot, user_id):
        await query.answer("Verification successful!")

        try:
            await query.message.delete()
        except Exception:
            pass

        await send_start_menu(context.bot, query.message.chat_id)

    else:
        await query.answer(
            f"{e('error', '❌')} You haven't joined all channels yet!",
            show_alert=True
        )

async def menu_accounts_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    accounts = get_user_accounts(user_id)

    rows = []

    if not accounts:
        rows.append(
            "<p>"
            "<tg-emoji emoji-id='5210952531676504517'>⚠️</tg-emoji> "
            "<b>No Account Added Yet!</b>"
            "</p>"
            "<p>You haven't linked any Instagram accounts to this bot yet. "
            "Please click the button below to add your account.</p>"
        )

        rows.append(
            '<tg-button-row>'
            '<tg-button type="callback_data" style="success" '
            'data="prompt_add_account">'
            'Add Account'
            '</tg-button>'
            '</tg-button-row>'
        )

    else:
        rows.append(
            "<p>"
            "<tg-emoji emoji-id='5341715473882955310'>⚠️</tg-emoji> "
            "<b>Your Linked Accounts:</b>"
            "</p>"
            "<p>Select an account below to manage:</p>"
        )

        for acc in accounts:
            username = html.escape(str(acc["username"]))
            callback_data = html.escape(
                f"manage_acc_{acc['username']}",
                quote=True
            )

            rows.append(
                '<tg-button-row>'
                '<tg-button type="callback_data" '
                f'data="{callback_data}">'
                f'@{username}'
                '</tg-button>'
                '</tg-button-row>'
            )

        rows.append(
            '<tg-button-row>'
            '<tg-button type="callback_data" style="success" '
            'data="prompt_add_account">'
            'Add Another Account'
            '</tg-button>'
            '</tg-button-row>'
        )

    # Back Button - Default Style
    back_emoji = ""

    if ICON_BACK_ID:
        back_emoji = (
            f'<tg-emoji emoji-id="{html.escape(str(ICON_BACK_ID), quote=True)}">'
            '⬅️</tg-emoji> '
        )

    rows.append(
        '<tg-button-row>'
        '<tg-button type="callback_data" data="back_to_main">'
        f'{back_emoji}Back'
        '</tg-button>'
        '</tg-button-row>'
    )

    rich_text = "".join(rows)

    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": query.message.chat_id,
            "message_id": query.message.message_id,
            "rich_message": {
                "html": rich_text
            }
        }
    )

async def manage_account_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    username = query.data.split("manage_acc_", 1)[1]

    safe_username = html.escape(username)
    safe_callback = html.escape(
        f"rem_acc_{username}",
        quote=True
    )

    back_emoji = ""
    if ICON_BACK_ID:
        back_emoji = (
            f'<tg-emoji emoji-id="{html.escape(str(ICON_BACK_ID), quote=True)}">'
            '⬅️</tg-emoji> '
        )

    rich_text = (
        "<p>"
        "<tg-emoji emoji-id='5341715473882955310'>⚠️</tg-emoji> "
        "<b>Account Management:</b> "
        f"<code>@{safe_username}</code>"
        "</p>"
        "<p>Select an action for this account:</p>"

        '<tg-button-row>'
        '<tg-button type="callback_data" style="danger" '
        f'data="{safe_callback}">'
        'Remove Account'
        '</tg-button>'

        '<tg-button type="callback_data" '
        f'data="chk_acc_{html.escape(username, quote=True)}">'
        'Check Privacy Status'
        '</tg-button>'
        '</tg-button-row>'

        '<tg-button-row>'
        '<tg-button type="callback_data" data="menu_accounts">'
        f'{back_emoji}Back'
        '</tg-button>'
        '</tg-button-row>'
    )

    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": query.message.chat_id,
            "message_id": query.message.message_id,
            "rich_message": {"html": rich_text}
        }
    )


async def remove_account_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    user_id = query.from_user.id
    username = query.data.split("rem_acc_", 1)[1]

    remove_user_account(user_id, username)

    await query.answer(
        f"Removed @{username}",
        show_alert=True
    )

    # Refresh the Accounts menu without answering the callback again
    accounts = get_user_accounts(user_id)

    if not accounts:
        rich_text = (
            "<p>No Instagram accounts are linked yet.</p>"
            '<tg-button-row>'
            '<tg-button type="callback_data" '
            'data="prompt_add_account" style="success">'
            'Add Account'
            '</tg-button>'
            '<tg-button type="callback_data" data="back_to_main">'
            'Back'
            '</tg-button>'
            '</tg-button-row>'
        )
    else:
        rows = []

        for acc in accounts:
            safe_username = html.escape(acc["username"], quote=True)
            callback_data = html.escape(
                f"manage_acc_{acc['username']}",
                quote=True
            )

            rows.append(
                '<tg-button-row>'
                f'<tg-button type="callback_data" '
                f'data="{callback_data}">'
                f'@{safe_username}'
                '</tg-button>'
                '</tg-button-row>'
            )

        rich_text = (
            "<p><b>Linked Instagram Accounts</b></p>"
            + "".join(rows)
            + '<tg-button-row>'
            '<tg-button type="callback_data" '
            'data="prompt_add_account" style="success">'
            'Add Another Account'
            '</tg-button>'
            '<tg-button type="callback_data" data="back_to_main">'
            'Back'
            '</tg-button>'
            '</tg-button-row>'
        )

    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": query.message.chat_id,
            "message_id": query.message.message_id,
            "rich_message": {"html": rich_text}
        }
    )

async def check_account_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    username = query.data.split("chk_acc_", 1)[1]

    accounts = get_user_accounts(user_id)

    target_acc = next(
        (a for a in accounts if a["username"].lower() == username.lower()),
        None
    )

    if not target_acc:
        await context.bot._post(
            "editMessageText",
            data={
                "chat_id": query.message.chat_id,
                "message_id": query.message.message_id,
                "rich_message": {
                    "html": (
                        "<p>❌ <b>Account not found!</b></p>"
                        '<tg-button-row>'
                        '<tg-button type="callback_data" '
                        'data="menu_accounts">Back to Accounts</tg-button>'
                        '</tg-button-row>'
                    )
                }
            }
        )
        return

    safe_username = html.escape(username)

    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": query.message.chat_id,
            "message_id": query.message.message_id,
            "rich_message": {
                "html": (
                    f"<p>{e('loading', '🔄')} "
                    f"<b>Checking privacy settings for "
                    f"@{safe_username}...</b></p>"
                )
            }
        }
    )

    await asyncio.sleep(1.2)

    status_dict = await asyncio.to_thread(
        check_account_status,
        target_acc["sessionid"],
        target_acc["uid"]
    )

    rows = []

    for key, value in status_dict.items():
        icon = "🟢" if value == "ON" else ("🔴" if value == "OFF" else "⚪")
        rows.append(
            f"{icon} {html.escape(str(key))}: "
            f"<b>{html.escape(str(value))}</b>"
        )

    back_emoji = ""
    emoji_id = str(ICON_BACK_ID or "").strip()

    if emoji_id:
        back_emoji = (
            f'<tg-emoji emoji-id="'
            f'{html.escape(emoji_id, quote=True)}">'
            '⬅️</tg-emoji> '
        )

    rich_text = (
        "<p>"
        "<tg-emoji emoji-id='5296369303661067030'>⚠️</tg-emoji> "
        f"<b>Privacy Status:</b> "
        f"<code>@{safe_username}</code>"
        "</p>"
        "<blockquote>"
        + "\n".join(rows)
        + "</blockquote>"
        '<tg-button-row>'
        '<tg-button type="callback_data" data="menu_accounts">'
        f"{back_emoji}Back to Accounts"
        "</tg-button>"
        "</tg-button-row>"
    )

    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": query.message.chat_id,
            "message_id": query.message.message_id,
            "rich_message": {"html": rich_text}
        }
    )

async def show_commands_table(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    text, markup = get_commands_table_message()

    await update.message.reply_text(
        text,
        reply_markup=markup,
        parse_mode=ParseMode.HTML
    )


async def check_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    accounts = get_user_accounts(user_id)

    if not accounts:
        text, markup = get_commands_table_message()

        await update.message.reply_text(
            text,
            reply_markup=markup,
            parse_mode=ParseMode.HTML
        )
        return

    rows = [
        "<p>"
        "<tg-emoji emoji-id='5231012545799666522'>⚠️</tg-emoji> "
        "<b>Select an account to check its privacy status:</b>"
        "</p>"
    ]

    for acc in accounts:
        username = html.escape(str(acc["username"]))
        callback_data = html.escape(
            f"quick_chk_{acc['username']}",
            quote=True
        )

        rows.append(
            '<tg-button-row>'
            f'<tg-button type="callback_data" data="{callback_data}">'
            f'@{username}'
            '</tg-button>'
            '</tg-button-row>'
        )

    back_emoji = ""
    emoji_id = str(ICON_BACK_ID or "").strip()

    if emoji_id:
        back_emoji = (
            f'<tg-emoji emoji-id="'
            f'{html.escape(emoji_id, quote=True)}">'
            '⬅️</tg-emoji> '
        )

    rows.append(
        '<tg-button-row>'
        '<tg-button type="callback_data" data="back_to_main">'
        f'{back_emoji}Cancel'
        '</tg-button>'
        '</tg-button-row>'
    )

    await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message": {"html": "".join(rows)}
        }
    )

async def remove_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.effective_user.id
    accounts = get_user_accounts(user_id)

    if not accounts:
        text, markup = get_commands_table_message()

        await update.message.reply_text(
            text,
            reply_markup=markup,
            parse_mode=ParseMode.HTML
        )
        return

    rows = [
        "<p>"
        "<tg-emoji emoji-id='5445267414562389170'>⚠️</tg-emoji> "
        "<b>Select an account to remove:</b>"
        "</p>"
    ]

    for acc in accounts:
        raw_username = str(acc["username"])
        username = html.escape(raw_username)
        callback_data = html.escape(
            f"rem_acc_{raw_username}",
            quote=True
        )

        rows.append(
            '<tg-button-row>'
            '<tg-button type="callback_data" style="danger" '
            f'data="{callback_data}">'
            f'Remove @{username}'
            '</tg-button>'
            '</tg-button-row>'
        )

    back_emoji = ""
    emoji_id = str(ICON_BACK_ID or "").strip()

    if emoji_id:
        back_emoji = (
            f'<tg-emoji emoji-id="{html.escape(emoji_id, quote=True)}">'
            '⬅️</tg-emoji> '
        )

    rows.append(
        '<tg-button-row>'
        '<tg-button type="callback_data" data="back_to_main">'
        f'{back_emoji}Cancel'
        '</tg-button>'
        '</tg-button-row>'
    )

    await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message": {"html": "".join(rows)}
        }
    )

async def quick_check_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    username = query.data.split("quick_chk_", 1)[1]
    accounts = get_user_accounts(user_id)

    target_acc = next(
        (a for a in accounts if a["username"].lower() == username.lower()),
        None
    )

    if not target_acc:
        await context.bot._post(
            "editMessageText",
            data={
                "chat_id": query.message.chat_id,
                "message_id": query.message.message_id,
                "rich_message": {
                    "html": (
                        "<p>❌ <b>Account not found!</b></p>"
                        '<tg-button-row>'
                        '<tg-button type="callback_data" '
                        'data="back_to_main">Back to Menu</tg-button>'
                        '</tg-button-row>'
                    )
                }
            }
        )
        return

    safe_username = html.escape(username)

    checking_msg = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=(
            f"{e('loading', '🔄')} "
            f"<b>Checking privacy settings for @{safe_username}...</b>"
        ),
        parse_mode=ParseMode.HTML
    )

    try:
        await query.message.delete()
    except Exception:
        pass

    await asyncio.sleep(1.2)

    status_dict = await asyncio.to_thread(
        check_account_status,
        target_acc["sessionid"],
        target_acc["uid"]
    )

    rows = []

    for key, value in status_dict.items():
        icon = "🟢" if value == "ON" else ("🔴" if value == "OFF" else "⚪")
        rows.append(
            f"{icon} {html.escape(str(key))}: "
            f"<b>{html.escape(str(value))}</b>"
        )

    back_emoji = ""
    emoji_id = str(ICON_BACK_ID or "").strip()

    if emoji_id:
        back_emoji = (
            f'<tg-emoji emoji-id="'
            f'{html.escape(emoji_id, quote=True)}">'
            '⬅️</tg-emoji> '
        )

    rich_text = (
        "<p>"
        "<tg-emoji emoji-id='5296369303661067030'>⚠️</tg-emoji> "
        "<b>Privacy Status Report:</b> "
        f"<code>@{safe_username}</code>"
        "</p>"
        "<blockquote>"
        + "\n".join(rows)
        + "</blockquote>"
        '<tg-button-row>'
        '<tg-button type="callback_data" data="back_to_main">'
        f"{back_emoji}Back to Menu"
        "</tg-button>"
        "</tg-button-row>"
    )

    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": checking_msg.chat_id,
            "message_id": checking_msg.message_id,
            "rich_message": {"html": rich_text}
        }
    )

async def help_menu_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    try:
        page = (
            int(query.data.split("help_page_", 1)[1])
            if "help_page_" in query.data else 1
        )
    except (ValueError, IndexError):
        page = 1

    page = max(1, min(page, TOTAL_PAGES))

    rich_text = (
        "<p>"
        "<tg-emoji emoji-id='5341715473882955310'>⚙️</tg-emoji> "
        f"<b>Account Privacy Settings "
        f"(Page {page}/{TOTAL_PAGES}):</b>"
        "</p>"
        "<blockquote>"
        "Select any feature to toggle its setting across "
        "your configured Instagram account."
        "</blockquote>"
        f"{build_help_keyboard(page)}"
    )

    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": query.message.chat_id,
            "message_id": query.message.message_id,
            "rich_message": {
                "html": rich_text
            }
        }
    )

async def edit_rich_html(bot, chat_id, message_id, html_text):
    return await bot._post(
        "editMessageText",
        data={
            "chat_id": chat_id,
            "message_id": message_id,
            "rich_message": {
                "html": html_text
            }
        }
    )


def build_privacy_result_button(style=None):
    emoji_html = ""
    emoji_id = str(ICON_BACK_ID or "").strip()

    if emoji_id:
        emoji_html = (
            f'<tg-emoji emoji-id="{html.escape(emoji_id, quote=True)}">'
            '⬅️</tg-emoji> '
        )

    style_attr = f' style="{html.escape(style, quote=True)}"' if style else ""

    return (
        '<tg-button-row>'
        f'<tg-button type="callback_data"{style_attr} '
        'data="menu_help_page_1">'
        f'{emoji_html}Back to Settings'
        '</tg-button>'
        '</tg-button-row>'
    )

async def privacy_button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    accounts = get_user_accounts(user_id)

    if not accounts:
        warning_html = (
            f"<p>{e('warn', '⚠️')} <b>No Account Found!</b></p>"
            "<p>Please add an account first using "
            "<code>/add</code> command.</p>"
        )

        await context.bot._post(
            "editMessageText",
            data={
                "chat_id": query.message.chat_id,
                "message_id": query.message.message_id,
                "rich_message": {"html": warning_html}
            }
        )

        return

    target_acc = accounts[0]
    action = query.data

    # Only these features are currently verified/working.
    verified_actions = {
        "act_hide_list",
        "act_unhide_list",
        "act_hide_pfp",
        "act_unhide_pfp",
        "act_disable_story_share",
        "act_enable_story_share",
    }

    # Every other feature button shows a temporary "under development" message.
    if action not in verified_actions:
        dev_msg = await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="This feature is currently under development.",
        )

        await asyncio.sleep(3)

        try:
            await dev_msg.delete()
        except Exception:
            pass

        return

    action_labels = {
        "act_hide_list": "Hiding followers",
        "act_unhide_list": "Showing followers",
        "act_hide_pfp": "Disabling DP zoom",
        "act_unhide_pfp": "Enabling DP zoom",
        "act_disable_story_share": "Disabling story sharing",
        "act_enable_story_share": "Enabling story sharing",
    }

    action_text = action_labels.get(action, "Processing")
    username = html.escape(str(target_acc["username"]))

    status_msg = await context.bot._post(
        "editMessageText",
        data={
            "chat_id": query.message.chat_id,
            "message_id": query.message.message_id,
            "rich_message": {
                "html": (
                    f"<p>{e('loading', '🔄')} "
                    f"<b>Applying setting for @{username}...</b></p>"
                )
            }
        }
    )

    # Progress animation
    total_blocks = 10

    for i in range(1, total_blocks + 1):
        filled = "█" * i
        empty = "░" * (total_blocks - i)
        pct = i * 10

        progress_html = (
            f"<p>{e('user', '👤')} "
            f"<b>Account: @{username}</b></p>"
            f"<p>{e('time', '⏳')} "
            f"<b>{html.escape(action_text)}...</b></p>"
            f"<blockquote>"
            f"<code>[{filled}{empty}] {pct}%</code>"
            f"</blockquote>"
        )

        try:
            await edit_rich_html(
                context.bot,
                query.message.chat_id,
                query.message.message_id,
                progress_html
            )

            await asyncio.sleep(0.3)

        except Exception:
            pass

    mutation_map = {
        "act_hide_list": (
            "hide_followers_following_list", True, "account_privacy"
        ),
        "act_unhide_list": (
            "hide_followers_following_list", False, "account_privacy"
        ),
        "act_hide_pfp": (
            "allow_profile_picture_expansion", False, "account_privacy"
        ),
        "act_unhide_pfp": (
            "allow_profile_picture_expansion", True, "account_privacy"
        ),
        "act_disable_story_share": (
            "allow_story_sharing_in_messages", False, "story_settings"
        ),
        "act_enable_story_share": (
            "allow_story_sharing_in_messages", True, "story_settings"
        ),
    }

    try:
        setting_id, target_val, callsite = mutation_map[action]

        ok, reason = await asyncio.to_thread(
            execute_ig_mutation,
            target_acc["sessionid"],
            target_acc["uid"],
            setting_id,
            target_val,
            callsite
        )

        if ok:
            result_html = (
                f"<p>{e('success', '✅')} "
                f"<b>Completed Successfully!</b></p>"
                f"<p>Account: <code>@{username}</code></p>"
                f"<p>Setting: <b>{html.escape(action_text)}</b> "
                f"has been applied.</p>"
                f"{build_privacy_result_button('success')}"
            )

        else:
            result_html = (
                f"<p>{e('error', '❌')} <b>Failed!</b></p>"
                f"<p>Account: <code>@{username}</code></p>"
                f"<p>Reason: "
                f"<code>{html.escape(str(reason))}</code></p>"
                f"{build_privacy_result_button('danger')}"
            )

        await edit_rich_html(
            context.bot,
            query.message.chat_id,
            query.message.message_id,
            result_html
        )

    except Exception as exc:

        error_html = (
            f"<p>{e('error', '❌')} <b>Error Occurred!</b></p>"
            f"<p><code>{html.escape(str(exc))}</code></p>"
            f"{build_privacy_result_button()}"
        )

        await edit_rich_html(
            context.bot,
            query.message.chat_id,
            query.message.message_id,
            error_html
        )

async def prompt_add_account_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    emoji_id = str(ICON_BACK_ID or "").strip()

    cancel_emoji = ""
    if emoji_id:
        cancel_emoji = (
            f'<tg-emoji emoji-id="{html.escape(emoji_id, quote=True)}">'
            '⬅️</tg-emoji> '
        )

    rich_text = (
        "<p>"
        "<tg-emoji emoji-id='5397916757333654639'>⚠️</tg-emoji> "
        "<b>Add Instagram Account</b>"
        "</p>"
        "<p>Please send your Instagram <b>sessionid</b> "
        "cookie below to link your account:</p>"
        "<tg-button-row>"
        '<tg-button type="callback_data" style="danger" '
        'data="cancel_action">'
        f"{cancel_emoji}Cancel"
        "</tg-button>"
        "</tg-button-row>"
    )

    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": query.message.chat_id,
            "message_id": query.message.message_id,
            "rich_message": {"html": rich_text}
        }
    )

    context.user_data["prompt_msg_id"] = query.message.message_id

    return WAITING_FOR_SESSION

async def add_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    emoji_id = str(ICON_BACK_ID or "").strip()

    cancel_emoji = ""
    if emoji_id:
        cancel_emoji = (
            f'<tg-emoji emoji-id="{html.escape(emoji_id, quote=True)}">'
            '⬅️</tg-emoji> '
        )

    rich_text = (
        "<p>"
        "<tg-emoji emoji-id='5397916757333654639'>⚠️</tg-emoji> "
        "<b>Add Instagram Account</b>"
        "</p>"
        "<p>Please send your Instagram <b>sessionid</b> "
        "cookie below to link your account:</p>"
        "<tg-button-row>"
        '<tg-button type="callback_data" style="danger" '
        'data="cancel_action">'
        f"{cancel_emoji}Cancel"
        "</tg-button>"
        "</tg-button-row>"
    )

    sent_msg = await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message": {"html": rich_text}
        }
    )

    context.user_data["prompt_msg_id"] = sent_msg["message_id"]

    return WAITING_FOR_SESSION

async def session_input_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    sid = (update.message.text or "").strip()
    user_id = update.effective_user.id

    # Session cookies are credentials: remove the incoming message immediately.
    try:
        await update.message.delete()
    except Exception:
        pass

    info, err = parse_session(sid)

    if err:
        error_html = (
            f"<p>{e('error', '❌')} <b>Error:</b> "
            f"{html.escape(str(err))}</p>"
            "<p>Try <code>/add</code> again.</p>"
        )

        await context.bot._post(
            "sendRichMessage",
            data={
                "chat_id": update.effective_chat.id,
                "rich_message": {"html": error_html}
            }
        )

        return ConversationHandler.END

    clean_sid = info["raw"]
    uid = info["uid"]

    # Delete previous prompt
    prompt_id = context.user_data.get("prompt_msg_id")

    if prompt_id:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=prompt_id
            )
        except Exception:
            pass

    # Send verification message
    status_msg = await context.bot._post(
        "sendRichMessage",
        data={
            "chat_id": update.effective_chat.id,
            "rich_message": {
                "html": (
                    f"<p>{e('loading', '🔄')} "
                    "<b>Verifying Instagram Session...</b></p>"
                )
            }
        }
    )

    try:
        username = await asyncio.to_thread(
            fetch_username,
            clean_sid,
            uid
        )

        if not username or not re.fullmatch(r"[A-Za-z0-9._]{1,30}", str(username)):
            raise ValueError("Instagram username could not be verified. The account was not saved; check the session and try again.")

        add_user_account(user_id, username, clean_sid, uid)

        emoji_id = str(ICON_ACCOUNTS_ID or "").strip()

        account_emoji = ""
        if emoji_id:
            account_emoji = (
                f'<tg-emoji emoji-id="'
                f'{html.escape(emoji_id, quote=True)}">'
                '👤</tg-emoji> '
            )

        rich_text = (
            f"<p>{e('success', '✅')} "
            "<b>Account Linked Successfully!</b></p>"
            f"<p>Username: <code>@{html.escape(str(username))}</code></p>"
            "<p>You can now manage privacy settings for this account.</p>"
            "<tg-button-row>"
            '<tg-button type="callback_data" data="menu_accounts">'
            f"{account_emoji}Go to Accounts"
            "</tg-button>"
            "</tg-button-row>"
        )

    except Exception as exc:
        rich_text = (
            f"<p>{e('error', '❌')} "
            "<b>Account Linking Failed!</b></p>"
            f"<p>Reason: <code>{html.escape(str(exc))}</code></p>"
            "<p>Please check your session and try <code>/add</code> again.</p>"
        )

    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": status_msg["chat"]["id"],
            "message_id": status_msg["message_id"],
            "rich_message": {"html": rich_text}
        }
    )

    context.user_data.pop("prompt_msg_id", None)

    return ConversationHandler.END

async def cancel_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Operation cancelled.")
    rich_text = get_start_text()["html"] + build_start_keyboard()
    await context.bot._post(
        "editMessageText",
        data={
            "chat_id": query.message.chat_id,
            "message_id": query.message.message_id,
            "rich_message": {"html": rich_text},
        },
    )
    context.user_data.pop("prompt_msg_id", None)
    return ConversationHandler.END

# ----------------- ADMIN BROADCAST (/broadcast) -----------------
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        return

    if not update.message.reply_to_message and not context.args:
        await update.message.reply_text("Usage:\nReply to any text/media with <code>/broadcast</code> or type <code>/broadcast &lt;message&gt;</code>", parse_mode=ParseMode.HTML)
        return

    data = load_data()
    all_chats = data.get("all_chats", [])

    sent_count = 0
    fail_count = 0
    progress_msg = await update.message.reply_text("<tg-emoji emoji-id='5424818078833715060'>⚠️</tg-emoji> <i>Broadcasting in progress...</i>", parse_mode=ParseMode.HTML)

    for cid in all_chats:
        try:
            if update.message.reply_to_message:
                await update.message.reply_to_message.copy(chat_id=cid)
            else:
                raw_text = update.message.text.partition(" ")[2]
                entities = update.message.entities[1:] if len(update.message.entities) > 1 else None
                await context.bot.send_message(chat_id=cid, text=raw_text, entities=entities)
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    await progress_msg.edit_text(
        f"<tg-emoji emoji-id='5206607081334906820'>⚠️</tg-emoji> <b>Broadcast Completed!</b>\n\n"
        f"• Sent: <b>{sent_count}</b>\n"
        f"• Failed: <b>{fail_count}</b>",
        parse_mode=ParseMode.HTML
    )

async def back_to_main_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    rich_text = (
        get_start_text()["html"]
        + build_start_keyboard()
    )

    try:
        await context.bot._post(
            "editMessageText",
            data={
                "chat_id": query.message.chat_id,
                "message_id": query.message.message_id,
                "rich_message": {
                    "html": rich_text
                }
            }
        )

    except Exception as ex:
        print(f"Back to Main Menu Error: {ex}")

async def telegram_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log Telegram network/API errors without terminating the bot process."""
    err = context.error
    if isinstance(err, TimedOut):
        print(
            "[TELEGRAM TIMEOUT] Telegram did not respond in time. "
            "The bot process will stay running; the affected action may need retrying.",
            flush=True,
        )
    elif isinstance(err, NetworkError):
        print(f"[TELEGRAM NETWORK ERROR] {type(err).__name__}: {err}", flush=True)
    elif isinstance(err, RetryAfter):
        print(f"[TELEGRAM RATE LIMIT] Retry after {err.retry_after} seconds.", flush=True)
    else:
        print(f"[TELEGRAM HANDLER ERROR] {type(err).__name__}: {err}", flush=True)


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing. "
            "Set it before starting the bot."
        )

    # Build Telegram Application
    builder = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(45)
        .write_timeout(30)
        .pool_timeout(30)
        .get_updates_connect_timeout(30)
        .get_updates_read_timeout(45)
        .get_updates_write_timeout(30)
        .get_updates_pool_timeout(30)
    )

    app = builder.build()
    app.add_error_handler(telegram_error_handler)

    # Add Account Conversation
    add_conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_command),
            CallbackQueryHandler(
                prompt_add_account_callback,
                pattern="^prompt_add_account$"
            )
        ],
        states={
            WAITING_FOR_SESSION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    session_input_handler
                ),
                CallbackQueryHandler(
                    cancel_callback_handler,
                    pattern="^cancel_action$"
                ),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(
                cancel_callback_handler,
                pattern="^cancel_action$"
            )
        ],
    )

    # Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("help", show_commands_table))
    app.add_handler(CommandHandler("broadcast", broadcast_command))

    # Conversation Handler
    app.add_handler(add_conv)

    # Callback Query Handlers
    app.add_handler(
        CallbackQueryHandler(
            check_joined_callback,
            pattern="^check_joined$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            menu_accounts_callback,
            pattern="^menu_accounts$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            manage_account_callback,
            pattern="^manage_acc_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            remove_account_callback,
            pattern="^rem_acc_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            check_account_callback,
            pattern="^chk_acc_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            quick_check_callback,
            pattern="^quick_chk_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            help_menu_callback,
            pattern="^(menu_help_page_|help_page_)"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            privacy_button_handler,
            pattern="^act_"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            back_to_main_handler,
            pattern="^back_to_main$"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            lambda update, context: update.callback_query.answer(),
            pattern="^noop$"
        )
    )

    print("Bot is successfully running...", flush=True)

    # Start Telegram polling
    app.run_polling(
        bootstrap_retries=-1,
        timeout=30,
        drop_pending_updates=False,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
