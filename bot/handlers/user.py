from datetime import datetime, timezone

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramBadRequest

from bot.config import ADMIN_ID
from bot.database import (
    ensure_user, get_user, get_all_texts, get_all_settings, get_all_buttons,
    get_tariffs, get_tariff, get_db, count_user_keys
)
from bot.services import (
    issue_key, reset_user_hwid, create_payment_request,
    get_payment, set_payment_status, user_display_name
)
from bot.utils.keyboards import (
    main_menu_kb, shop_kb, pay_choice_kb, hwid_kb, back_kb
)
from bot.utils.helpers import fmt_date

router = Router()

# ---------- helpers ----------

async def build_main_text():
    texts = await get_all_texts()
    return texts.get("welcome_text", "Добро пожаловать!")

async def build_shop_text():
    texts = await get_all_texts()
    return texts.get("shop_title", "🛒 Магазин ключей")

async def try_edit_or_send(event_msg: Message, bot: Bot, chat_id: int, text: str, kb, parse_mode="HTML"):
    """Пытается отредактировать сообщение, если не выходит — отправляет новое."""
    try:
        await event_msg.edit_text(text, reply_markup=kb, parse_mode=parse_mode)
    except TelegramBadRequest:
        try:
            await event_msg.delete()
        except Exception:
            pass
        await bot.send_message(chat_id, text, reply_markup=kb, parse_mode=parse_mode)

async def send_main_menu(target: Message | CallbackQuery, bot: Bot):
    texts = await get_all_texts()
    btns = await get_all_buttons()
    settings = await get_all_settings()
    welcome = texts.get("welcome_text", "Добро пожаловать!")
    kb = main_menu_kb(btns)
    media_id = settings.get("media_file_id", "")
    media_type = settings.get("media_type", "none")

    if isinstance(target, CallbackQuery):
        # callback — редактируем
        try:
            await target.message.edit_text(welcome, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            # если было медиа — удаляем и шлём заново
            try:
                await target.message.delete()
            except Exception:
                pass
            await _send_welcome_with_media(bot, target.message.chat.id, welcome, kb, media_id, media_type)
        await target.answer()
    else:
        await _send_welcome_with_media(bot, target.chat.id, welcome, kb, media_id, media_type)

async def _send_welcome_with_media(bot: Bot, chat_id: int, text: str, kb, media_id: str, media_type: str):
    try:
        if media_id and media_type == "photo":
            await bot.send_photo(chat_id, media_id, caption=text, reply_markup=kb, parse_mode="HTML")
            return
        if media_id and media_type == "video":
            await bot.send_video(chat_id, media_id, caption=text, reply_markup=kb, parse_mode="HTML")
            return
        if media_id and media_type == "animation":
            await bot.send_animation(chat_id, media_id, caption=text, reply_markup=kb, parse_mode="HTML")
            return
    except Exception:
        pass
    await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")

# ---------- /start ----------

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    await ensure_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await send_main_menu(message, bot)

# /panel обрабатывается только в админ-роутере: для остальных — тишина

# ---------- menu callbacks ----------

@router.callback_query(F.data == "menu:main")
async def cb_main(call: CallbackQuery, bot: Bot):
    await send_main_menu(call, bot)

@router.callback_query(F.data == "menu:shop")
async def cb_shop(call: CallbackQuery, bot: Bot):
    texts = await get_all_texts()
    btns = await get_all_buttons()
    tariffs = await get_tariffs(active_only=True)
    text = texts.get("shop_title", "🛒 Магазин ключей")
    if not tariffs:
        text += "\n\n<i>😔 Тарифы временно недоступны.</i>"
        kb = back_kb(btns.get("btn_back", "◀️ Назад"))
    else:
        kb = shop_kb(tariffs, btns.get("btn_back", "◀️ Назад"))
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "menu:profile")
async def cb_profile(call: CallbackQuery, bot: Bot):
    texts = await get_all_texts()
    btns = await get_all_buttons()
    user = await get_user(call.from_user.id)
    if not user:
        await ensure_user(call.from_user.id, call.from_user.username, call.from_user.full_name)
        user = await get_user(call.from_user.id)
    total, activated = await count_user_keys(call.from_user.id)
    template = texts.get("profile_template", "Профиль {name}")
    reg = fmt_date(user["reg_date"]) if user["reg_date"] else "—"
    hwid = user["hwid"] if user["hwid"] else texts.get("no_hwid", "не привязан")
    text = template.format(
        name=user["full_name"] or call.from_user.full_name,
        user_id=user["user_id"],
        reg_date=reg,
        balance=user["balance"] or 0,
        total_keys=total,
        activated_keys=activated,
        spent_rub=user["spent_rub"] or 0,
        spent_stars=user["spent_stars"] or 0,
        hwid=hwid,
    )
    kb = back_kb(btns.get("btn_back", "◀️ Назад"))
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "menu:hwid")
async def cb_hwid(call: CallbackQuery, bot: Bot):
    texts = await get_all_texts()
    btns = await get_all_buttons()
    settings = await get_all_settings()
    user = await get_user(call.from_user.id)
    hwid = user["hwid"] if user and user["hwid"] else texts.get("no_hwid", "не привязан")
    template = texts.get("hwid_title", "Сброс HWID")
    text = template.format(hwid=hwid)
    price_rub = settings.get("hwid_reset_price_rub", "149")
    price_stars = settings.get("hwid_reset_price_stars", "75")
    kb = hwid_kb(
        btns.get("btn_reset_pay_sbp", "💳 Сбросить (СБП)"),
        btns.get("btn_reset_pay_stars", "⭐️ Сбросить (Звёзды)"),
        price_rub, price_stars,
        btns.get("btn_back", "◀️ Назад"),
    )
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

# ---------- tariff -> pay choice ----------

@router.callback_query(F.data.startswith("tariff:"))
async def cb_tariff(call: CallbackQuery, bot: Bot):
    tariff_id = int(call.data.split(":")[1])
    tariff = await get_tariff(tariff_id)
    if not tariff:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return
    texts = await get_all_texts()
    btns = await get_all_buttons()
    # красиво показываем тариф
    exp = "навсегда ♾️" if tariff["days"] == 0 else f"{tariff['days']} дней"
    text = (
        f"<b>🔑 {tariff['label']}</b> — {exp}\n\n"
        f"💰 Цена: <b>{tariff['price_rub']} ₽</b> / <b>{tariff['price_stars']} ⭐️</b>\n\n"
        f"{texts.get('payment_choose', '💳 Выбери способ оплаты:')}"
    )
    kb = pay_choice_kb(
        tariff_id,
        btns.get("btn_pay_sbp", "💳 Оплатить СБП"),
        btns.get("btn_pay_stars", "⭐️ Оплатить Звёздами"),
        btns.get("btn_back", "◀️ Назад"),
    )
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

# ---------- payments ----------

@router.callback_query(F.data.startswith("pay:sbp:"))
async def cb_pay_sbp(call: CallbackQuery, bot: Bot):
    tariff_id = int(call.data.split(":")[2])
    tariff = await get_tariff(tariff_id)
    if not tariff:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return
    from bot.config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
    # если настроена YooKassa — пробуем создать платёж
    if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
        await _create_yookassa_payment(call, tariff, bot)
    else:
        await _create_sbp_request(call, bot, "tariff", tariff["price_rub"], tariff)
    await call.answer()

async def _create_sbp_request(call: CallbackQuery, bot: Bot, kind: str, amount_rub: int, tariff=None):
    """Заявка на оплату СБП: создаёт платёж и уведомляет админа."""
    pid = await create_payment_request(
        call.from_user.id, kind, amount_rub, tariff["id"] if tariff else None
    )
    texts = await get_all_texts()
    btns = await get_all_buttons()

    if kind == "tariff":
        item = f"Ключ «{tariff['label']}»"
    else:
        item = "Сброс HWID"

    # уведомление админу
    who = await user_display_name(call.from_user.id)
    try:
        await bot.send_message(
            ADMIN_ID,
            f"<b>💰 Заявка на оплату СБП #{pid}</b>\n\n"
            f"👤 {who}\n"
            f"🆔 <code>{call.from_user.id}</code>\n"
            f"📦 {item}\n"
            f"💵 <b>{amount_rub} ₽</b>\n\n"
            f"<i>Проверь поступление и подтверди.</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"adm:pay_ok:{pid}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:pay_no:{pid}"),
            ]]),
            parse_mode="HTML",
        )
    except Exception:
        pass

    template = texts.get(
        "sbp_request_created",
        "<b>💳 Заявка #{payment_id}</b>\n\n📦 {item}\n💵 К оплате: <b>{amount} ₽</b>\n\n{requisites}\n\n"
        "<i>После перевода нажми «Я оплатил».</i>",
    )
    text = template.format(
        payment_id=pid,
        item=item,
        amount=amount_rub,
        requisites=texts.get("sbp_requisites", ""),
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btns.get("btn_pay_sent", "✅ Я оплатил"), callback_data=f"pay:sent:{pid}")],
        [InlineKeyboardButton(text=btns.get("btn_back", "◀️ Назад"), callback_data="menu:main")],
    ])
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("pay:sent:"))
async def cb_pay_sent(call: CallbackQuery, bot: Bot):
    pid = int(call.data.split(":")[2])
    payment = await get_payment(pid)
    if not payment or payment["user_id"] != call.from_user.id:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return
    if payment["status"] == "paid":
        await call.answer("✅ Эта заявка уже оплачена", show_alert=True)
        return
    who = await user_display_name(call.from_user.id)
    try:
        await bot.send_message(
            ADMIN_ID,
            f"<b>🔔 Пользователь сообщил об оплате #{pid}</b>\n\n"
            f"👤 {who} · <code>{call.from_user.id}</code>\n"
            f"💵 <b>{payment['amount_rub']} ₽</b>\n\n"
            f"<i>Проверь поступление СБП.</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"adm:pay_ok:{pid}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:pay_no:{pid}"),
            ]]),
            parse_mode="HTML",
        )
    except Exception:
        pass
    await call.answer("🔔 Админ уведомлён, ожидай подтверждения", show_alert=True)


async def _create_yookassa_payment(call: CallbackQuery, tariff, bot: Bot):
    import uuid, aiohttp, base64
    from bot.config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
    amount = str(tariff["price_rub"]) + ".00"
    idem = str(uuid.uuid4())
    auth = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()
    payload = {
        "amount": {"value": amount, "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/"},
        "capture": True,
        "description": f"KeyPulse {tariff['label']}",
        "metadata": {"user_id": str(call.from_user.id), "tariff_id": str(tariff["id"])},
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                "https://api.yookassa.ru/v3/payments",
                json=payload,
                headers={"Idempotence-Key": idem, "Authorization": f"Basic {auth}", "Content-Type": "application/json"},
            ) as r:
                data = await r.json()
        url = data.get("confirmation", {}).get("confirmation_url", "")
        pid = data.get("id", "")
        # сохраняем pending
        async with get_db() as db:
            await db.execute(
                "INSERT INTO pending_payments(user_id,tariff_id,kind,amount_rub,status,created_at) VALUES(?,?,?,?,?,?)",
                (call.from_user.id, tariff["id"], "tariff", tariff["price_rub"], f"yookassa:{pid}", datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Перейти к оплате", url=url)],
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"yookassa_check:{pid}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"tariff:{tariff['id']}")],
        ])
        text = f"<b>💳 Оплата СБП — {tariff['label']}</b>\nСумма: <b>{tariff['price_rub']} ₽</b>\n\nНажми кнопку ниже чтобы оплатить."
        try:
            await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            await call.message.delete()
            await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        text = f"❌ Ошибка создания платежа YooKassa: {e}\n\nПопробуй позже или оплати звёздами."
        from bot.utils.keyboards import back_kb
        btns = await get_all_buttons()
        kb = back_kb(btns.get("btn_back", "◀️ Назад"), f"tariff:{tariff['id']}")
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest:
            await call.message.delete()
            await bot.send_message(call.message.chat.id, text, reply_markup=kb)

@router.callback_query(F.data.startswith("yookassa_check:"))
async def cb_yookassa_check(call: CallbackQuery, bot: Bot):
    pid = call.data.split(":", 1)[1]
    import aiohttp, base64
    from bot.config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
    auth = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"https://api.yookassa.ru/v3/payments/{pid}",
                headers={"Authorization": f"Basic {auth}"},
            ) as r:
                data = await r.json()
        status = data.get("status")
        if status == "succeeded":
            # выдаём ключ
            async with get_db() as db:
                cur = await db.execute("SELECT * FROM pending_payments WHERE status=?", (f"yookassa:{pid}",))
                row = await cur.fetchone()
                if not row:
                    await call.answer("❌ Платёж не найден", show_alert=True)
                    return
                tariff = await get_tariff(row["tariff_id"])
                await _issue_key(call.from_user.id, tariff, call, bot, rub_paid=tariff["price_rub"])
                await db.execute("UPDATE pending_payments SET status='paid' WHERE id=?", (row["id"],))
                await db.commit()
        else:
            await call.answer(f"⏳ Статус: {status} — ещё не оплачено", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ Ошибка проверки: {e}", show_alert=True)

@router.callback_query(F.data.startswith("pay:stars:"))
async def cb_pay_stars(call: CallbackQuery, bot: Bot):
    tariff_id = int(call.data.split(":")[2])
    tariff = await get_tariff(tariff_id)
    if not tariff:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return
    # создаём инвойс в звёздах
    title = f"KeyPulse — {tariff['label']}"
    desc = f"Лицензионный ключ на {tariff['label']} (навсегда)" if tariff["days"] == 0 else f"Лицензионный ключ на {tariff['days']} дней"
    payload = f"tariff:{tariff_id}:{call.from_user.id}"
    prices = [LabeledPrice(label=title, amount=tariff["price_stars"])]
    try:
        await bot.send_invoice(
            chat_id=call.message.chat.id,
            title=title,
            description=desc,
            payload=payload,
            provider_token="",  # для XTR пусто
            currency="XTR",
            prices=prices,
        )
        await call.answer("⭐️ Счёт выставлен — оплати выше")
    except Exception as e:
        await call.answer(f"❌ Ошибка инвойса: {e}", show_alert=True)

# ---------- pre_checkout & successful_payment ----------

@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery, bot: Bot):
    await bot.answer_pre_checkout_query(q.id, ok=True)

@router.message(F.successful_payment)
async def on_successful_payment(message: Message, bot: Bot):
    pay = message.successful_payment
    payload = pay.invoice_payload  # tariff:ID:user_id  или hwid:ID
    # определяем что это
    if payload.startswith("tariff:"):
        parts = payload.split(":")
        tariff_id = int(parts[1])
        tariff = await get_tariff(tariff_id)
        if not tariff:
            await message.answer("❌ Тариф не найден, обратись в поддержку.")
            return
        await _issue_key(message.from_user.id, tariff, message, bot, stars_paid=pay.total_amount)
    elif payload.startswith("hwid:"):
        await _do_hwid_reset(message.from_user.id, message, bot, stars_paid=pay.total_amount)
    else:
        await message.answer(f"✅ Оплата получена: {pay.total_amount} {pay.currency}")

# HWID оплата (СБП/звезды)

@router.callback_query(F.data == "hwid:pay:sbp")
async def cb_hwid_pay_sbp(call: CallbackQuery, bot: Bot):
    from bot.config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
    settings = await get_all_settings()
    price_rub = int(settings.get("hwid_reset_price_rub", "149"))
    if YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY:
        # YooKassa для HWID
        import uuid, aiohttp, base64
        idem = str(uuid.uuid4())
        auth = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()
        payload = {
            "amount": {"value": f"{price_rub}.00", "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": "https://t.me/"},
            "capture": True,
            "description": "KeyPulse — сброс HWID",
            "metadata": {"user_id": str(call.from_user.id), "kind": "hwid"},
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post("https://api.yookassa.ru/v3/payments", json=payload, headers={"Idempotence-Key": idem, "Authorization": f"Basic {auth}", "Content-Type": "application/json"}) as r:
                    data = await r.json()
            url = data.get("confirmation", {}).get("confirmation_url", "")
            pid = data.get("id", "")
            async with get_db() as db:
                await db.execute("INSERT INTO pending_payments(user_id,kind,amount_rub,status,created_at) VALUES(?,?,?,?,?)",
                    (call.from_user.id, "hwid", price_rub, f"yookassa:{pid}", datetime.now(timezone.utc).isoformat()))
                await db.commit()
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к оплате", url=url)],
                [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"yookassa_check_hwid:{pid}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="menu:hwid")],
            ])
            text = f"<b>🔧 Сброс HWID</b>\nСумма: <b>{price_rub} ₽</b>"
            try:
                await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            except TelegramBadRequest:
                await call.message.delete()
                await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            await call.answer(f"❌ Ошибка: {e}", show_alert=True)
    else:
        await _create_sbp_request(call, bot, "hwid", price_rub)
    await call.answer()

@router.callback_query(F.data.startswith("yookassa_check_hwid:"))
async def cb_yookassa_check_hwid(call: CallbackQuery, bot: Bot):
    pid = call.data.split(":", 1)[1]
    import aiohttp, base64
    from bot.config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
    auth = base64.b64encode(f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}".encode()).decode()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.yookassa.ru/v3/payments/{pid}", headers={"Authorization": f"Basic {auth}"}) as r:
                data = await r.json()
        if data.get("status") == "succeeded":
            async with get_db() as db:
                cur = await db.execute("SELECT * FROM pending_payments WHERE status=?", (f"yookassa:{pid}",))
                row = await cur.fetchone()
                if row:
                    await db.execute("UPDATE pending_payments SET status='paid' WHERE id=?", (row["id"],))
                    await db.commit()
            await _do_hwid_reset(call.from_user.id, call, bot, rub_paid=row["amount_rub"] if row else 0)
        else:
            await call.answer(f"⏳ Статус: {data.get('status')}", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(F.data == "hwid:pay:stars")
async def cb_hwid_pay_stars(call: CallbackQuery, bot: Bot):
    settings = await get_all_settings()
    price_stars = int(settings.get("hwid_reset_price_stars", "75"))
    title = "KeyPulse — Сброс HWID"
    desc = "Сброс привязки ключа к железу. Сможешь активировать ключ заново."
    payload = f"hwid:{call.from_user.id}"
    prices = [LabeledPrice(label=title, amount=price_stars)]
    try:
        await bot.send_invoice(
            chat_id=call.message.chat.id,
            title=title, description=desc,
            payload=payload, provider_token="",
            currency="XTR", prices=prices,
        )
        await call.answer("⭐️ Счёт выставлен")
    except Exception as e:
        await call.answer(f"❌ Ошибка инвойса: {e}", show_alert=True)

# ---------- core issue / reset ----------

async def _issue_key(user_id: int, tariff, event, bot: Bot, rub_paid=0, stars_paid=0):
    _key, text = await issue_key(user_id, tariff, rub_paid=rub_paid, stars_paid=stars_paid)
    btns = await get_all_buttons()
    kb = back_kb(btns.get("btn_back", "◀️ Назад"))
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            await event.message.delete()
            await bot.send_message(event.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        await event.answer("✅ Оплата подтверждена!", show_alert=True)
    else:
        # Message (successful_payment / админское подтверждение)
        await bot.send_message(event.chat.id, text, reply_markup=kb, parse_mode="HTML")

async def _do_hwid_reset(user_id: int, event, bot: Bot, rub_paid=0, stars_paid=0):
    text = await reset_user_hwid(user_id, rub_paid=rub_paid, stars_paid=stars_paid)
    btns = await get_all_buttons()
    kb = back_kb(btns.get("btn_back", "◀️ Назад"))
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            await event.message.delete()
            await bot.send_message(event.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        await event.answer("✅ HWID сброшен!", show_alert=True)
    else:
        await bot.send_message(event.chat.id, text, reply_markup=kb, parse_mode="HTML")
