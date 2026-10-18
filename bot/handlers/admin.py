from datetime import datetime, timezone

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

from bot.config import ADMIN_ID
from bot.database import (
    get_all_texts, get_all_settings, get_all_buttons, get_tariffs, get_tariff,
    get_db, set_text, set_button, set_setting, get_setting
)
from bot.utils.keyboards import (
    admin_main_kb, admin_back_kb, admin_texts_kb, admin_buttons_kb,
    admin_settings_kb, admin_tariffs_kb, admin_tariff_edit_kb, back_kb
)
from bot.utils.keygen import generate_key, parse_key_format, calc_expires
from bot.services import issue_key, reset_user_hwid, get_payment, set_payment_status

router = Router()

class AdminStates(StatesGroup):
    edit_text = State()
    edit_button = State()
    edit_setting = State()
    edit_tariff_field = State()
    gen_amount = State()
    gen_days = State()
    gen_format = State()
    find_key = State()
    add_tariff_label = State()
    add_tariff_days = State()
    add_tariff_rub = State()
    add_tariff_stars = State()
    set_media = State()

# pending storage for multi-step flows
_add_tariff_buf: dict[int, dict] = {}
_gen_buf: dict[int, dict] = {}

def _is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

# middleware: silently ignore non-admin
@router.message(Command("panel"))
async def cmd_panel(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await send_admin_panel(message, bot)

async def send_admin_panel(target: Message | CallbackQuery, bot: Bot):
    # stats quick
    async with get_db() as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        users_cnt = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM license_keys")
        keys_cnt = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM license_keys WHERE is_activated=1")
        act_cnt = (await cur.fetchone())[0]
    text = (
        f"<b>⚙️ Админ-панель KeyPulse</b>\n\n"
        f"👥 Пользователей: <b>{users_cnt}</b>\n"
        f"🔑 Ключей всего: <b>{keys_cnt}</b> (активировано: <b>{act_cnt}</b>)\n\n"
        f"<i>Выбери раздел:</i>"
    )
    kb = admin_main_kb()
    if isinstance(target, Message):
        try:
            await target.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await bot.send_message(target.chat.id, text, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            await target.message.delete()
            await bot.send_message(target.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        await target.answer()

# ---------- main nav ----------

@router.callback_query(F.data == "adm:main")
async def cb_adm_main(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        await call.answer("🚫 Нет доступа", show_alert=True)
        return
    await state.clear()
    await send_admin_panel(call, bot)

@router.callback_query(F.data == "adm:close")
async def cb_adm_close(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()

# ---------- texts ----------

@router.callback_query(F.data == "adm:texts")
async def cb_adm_texts(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    texts = await get_all_texts()
    kb = admin_texts_kb(texts)
    # show current values
    lines = "\n".join([f"• <code>{k}</code>: {v[:60]}..." if len(v) > 60 else f"• <code>{k}</code>: {v}" for k, v in texts.items()])
    text = f"<b>📝 Тексты бота</b>\nНажми чтобы редактировать:\n\n{lines}"
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("adm:edit_text:"))
async def cb_adm_edit_text(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    key = call.data.split(":", 2)[2]
    texts = await get_all_texts()
    cur_val = texts.get(key, "")
    await state.set_state(AdminStates.edit_text)
    await state.update_data(edit_key=key)
    kb = admin_back_kb()
    text = f"<b>✏️ Редактирование текста</b>\nКлюч: <code>{key}</code>\n\nТекущее значение:\n{cur_val}\n\n<i>Отправь новое значение (HTML поддерживается) или /cancel для отмены.</i>"
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@router.message(AdminStates.edit_text)
async def msg_edit_text(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await send_admin_panel(message, bot)
        return
    data = await state.get_data()
    key = data.get("edit_key")
    await set_text(key, message.text or "")
    await state.clear()
    await message.answer(f"✅ Текст <code>{key}</code> обновлён!", parse_mode="HTML", reply_markup=admin_main_kb())

# ---------- buttons ----------

@router.callback_query(F.data == "adm:buttons")
async def cb_adm_buttons(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    btns = await get_all_buttons()
    kb = admin_buttons_kb(btns)
    lines = "\n".join([f"• <code>{k}</code>: {v}" for k, v in btns.items()])
    text = f"<b>🔘 Кнопки бота</b>\n\n{lines}\n\n<i>Нажми чтобы редактировать:</i>"
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("adm:edit_btn:"))
async def cb_adm_edit_btn(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    key = call.data.split(":", 2)[2]
    btns = await get_all_buttons()
    cur = btns.get(key, "")
    await state.set_state(AdminStates.edit_button)
    await state.update_data(edit_key=key)
    text = f"<b>✏️ Редактирование кнопки</b>\n<code>{key}</code>\nТекущая: <b>{cur}</b>\n\n<i>Отправь новый текст кнопки (можно с эмодзи):</i>"
    try:
        await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

@router.message(AdminStates.edit_button)
async def msg_edit_button(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await send_admin_panel(message, bot)
        return
    data = await state.get_data()
    key = data.get("edit_key")
    await set_button(key, message.text or "")
    await state.clear()
    await message.answer(f"✅ Кнопка <code>{key}</code> обновлена: <b>{message.text}</b>", parse_mode="HTML", reply_markup=admin_main_kb())

# ---------- settings ----------

@router.callback_query(F.data == "adm:settings")
async def cb_adm_settings(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    settings = await get_all_settings()
    kb = admin_settings_kb(settings)
    lines = "\n".join([f"• <code>{k}</code> = <code>{v}</code>" for k, v in settings.items()])
    text = f"<b>⚙️ Настройки</b>\n\n{lines}\n\n<i>Нажми чтобы редактировать. Также:</i>\n— <code>media_file_id</code> — отправь фото/видео боту и перешли file_id\n— <code>key_format</code> — например KP-XXXX-XXXX-XXXX"
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("adm:edit_set:"))
async def cb_adm_edit_set(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    key = call.data.split(":", 2)[2]
    settings = await get_all_settings()
    cur = settings.get(key, "")
    await state.set_state(AdminStates.edit_setting)
    await state.update_data(edit_key=key)
    text = f"<b>✏️ Настройка</b> <code>{key}</code>\nТекущая: <code>{cur}</code>\n\n<i>Отправь новое значение:</i>"
    try:
        await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

@router.message(AdminStates.edit_setting)
async def msg_edit_setting(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    if message.text == "/cancel":
        await state.clear()
        await send_admin_panel(message, bot)
        return
    data = await state.get_data()
    key = data.get("edit_key")
    val = message.text or ""
    # if media file_id sent as photo/video
    if message.photo:
        val = message.photo[-1].file_id
        key = "media_file_id"
        await set_setting("media_type", "photo")
    elif message.video:
        val = message.video.file_id
        key = "media_file_id"
        await set_setting("media_type", "video")
    elif message.animation:
        val = message.animation.file_id
        key = "media_file_id"
        await set_setting("media_type", "animation")
    await set_setting(key, val)
    await state.clear()
    await message.answer(f"✅ Настройка <code>{key}</code> = <code>{val}</code>", parse_mode="HTML", reply_markup=admin_main_kb())

# ---------- tariffs ----------

@router.callback_query(F.data == "adm:tariffs")
async def cb_adm_tariffs(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    tariffs = await get_tariffs()
    kb = admin_tariffs_kb(tariffs)
    lines = "\n".join([f"{'✅' if t['is_active'] else '🚫'} <b>{t['label']}</b> — {t['days']}д / {t['price_rub']}₽ / {t['price_stars']}⭐ (id:{t['id']})" for t in tariffs]) or "<i>нет тарифов</i>"
    text = f"<b>💰 Тарифы</b>\n\n{lines}\n\n<i>Нажми на тариф чтобы редактировать:</i>"
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("adm:tariff:") )
async def cb_adm_tariff_detail(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    # distinguish tariff:XX vs tariff_price etc — this handler for adm:tariff:<id>
    suffix = call.data[len("adm:tariff:"):]
    # if suffix contains underscore — it's edit action, skip
    if "_" in suffix:
        return
    try:
        tid = int(suffix)
    except ValueError:
        return
    t = await get_tariff(tid)
    if not t:
        await call.answer("❌ Не найден", show_alert=True)
        return
    text = (
        f"<b>💰 Тариф #{t['id']}</b>\n"
        f"Название: <b>{t['label']}</b>\n"
        f"Дней: <b>{t['days']}</b> (0 = навсегда)\n"
        f"Цена: <b>{t['price_rub']} ₽</b> / <b>{t['price_stars']} ⭐️</b>\n"
        f"Статус: {'✅ активен' if t['is_active'] else '🚫 скрыт'}\n"
        f"Сорт: {t['sort']}"
    )
    kb = admin_tariff_edit_kb(t["id"], t["is_active"])
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

# inline tariff field edits

@router.callback_query(F.data.startswith("adm:tariff_price_rub:"))
async def cb_tariff_price_rub(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    tid = int(call.data.split(":")[1].split("_")[-1] if False else call.data.split(":")[1] if False else 0)
    # actually "adm:tariff_price_rub:ID"
    tid = int(call.data.split(":")[-1])
    await state.set_state(AdminStates.edit_tariff_field)
    await state.update_data(tariff_id=tid, field="price_rub")
    await call.message.edit_text(f"<b>✏️ Цена ₽ для тарифа #{tid}</b>\nОтправь новое число:", reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("adm:tariff_price_stars:"))
async def cb_tariff_price_stars(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    tid = int(call.data.split(":")[-1])
    await state.set_state(AdminStates.edit_tariff_field)
    await state.update_data(tariff_id=tid, field="price_stars")
    await call.message.edit_text(f"<b>✏️ Цена ⭐ для тарифа #{tid}</b>\nОтправь новое число:", reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("adm:tariff_label:"))
async def cb_tariff_label(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    tid = int(call.data.split(":")[-1])
    await state.set_state(AdminStates.edit_tariff_field)
    await state.update_data(tariff_id=tid, field="label")
    await call.message.edit_text(f"<b>✏️ Название для тарифа #{tid}</b>\nОтправь новый текст:", reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("adm:tariff_days:"))
async def cb_tariff_days(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    tid = int(call.data.split(":")[-1])
    await state.set_state(AdminStates.edit_tariff_field)
    await state.update_data(tariff_id=tid, field="days")
    await call.message.edit_text(f"<b>✏️ Кол-во дней для тарифа #{tid}</b>\n(0 = навсегда)\nОтправь число:", reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data.startswith("adm:tariff_toggle:"))
async def cb_tariff_toggle(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    tid = int(call.data.split(":")[-1])
    async with get_db() as db:
        cur = await db.execute("SELECT is_active FROM tariffs WHERE id=?", (tid,))
        row = await cur.fetchone()
        if not row:
            await call.answer("❌ Не найден", show_alert=True)
            return
        new_val = 0 if row["is_active"] else 1
        await db.execute("UPDATE tariffs SET is_active=? WHERE id=?", (new_val, tid))
        await db.commit()
    await call.answer("✅ Обновлено")
    # refresh
    t = await get_tariff(tid)
    text = f"<b>💰 Тариф #{t['id']}</b>\nНазвание: <b>{t['label']}</b>\nДней: <b>{t['days']}</b>\nЦена: <b>{t['price_rub']} ₽</b> / <b>{t['price_stars']} ⭐️</b>\nСтатус: {'✅ активен' if t['is_active'] else '🚫 скрыт'}"
    try:
        await call.message.edit_text(text, reply_markup=admin_tariff_edit_kb(t["id"], t["is_active"]), parse_mode="HTML")
    except TelegramBadRequest:
        pass

@router.callback_query(F.data.startswith("adm:tariff_del:"))
async def cb_tariff_del(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    tid = int(call.data.split(":")[-1])
    async with get_db() as db:
        await db.execute("DELETE FROM tariffs WHERE id=?", (tid,))
        await db.commit()
    await call.answer("🗑 Удалено")
    # back to list
    tariffs = await get_tariffs()
    kb = admin_tariffs_kb(tariffs)
    lines = "\n".join([f"{'✅' if t['is_active'] else '🚫'} <b>{t['label']}</b> — {t['days']}д / {t['price_rub']}₽" for t in tariffs]) or "<i>нет тарифов</i>"
    text = f"<b>💰 Тарифы</b>\n\n{lines}"
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        pass

@router.message(AdminStates.edit_tariff_field)
async def msg_edit_tariff_field(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    data = await state.get_data()
    tid = data["tariff_id"]
    field = data["field"]
    val = (message.text or "").strip()
    if field in ("price_rub", "price_stars", "days"):
        try:
            val = int(val)
        except ValueError:
            await message.answer("❌ Введи число!")
            return
    async with get_db() as db:
        if field == "price_rub":
            await db.execute("UPDATE tariffs SET price_rub=? WHERE id=?", (val, tid))
        elif field == "price_stars":
            await db.execute("UPDATE tariffs SET price_stars=? WHERE id=?", (val, tid))
        elif field == "label":
            await db.execute("UPDATE tariffs SET label=? WHERE id=?", (val, tid))
        elif field == "days":
            await db.execute("UPDATE tariffs SET days=? WHERE id=?", (val, tid))
        await db.commit()
    await state.clear()
    await message.answer(f"✅ Обновлено: <code>{field}</code> = <code>{val}</code>", parse_mode="HTML", reply_markup=admin_main_kb())

# ---------- add tariff ----------

@router.callback_query(F.data == "adm:tariff_add")
async def cb_tariff_add(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    _add_tariff_buf[call.from_user.id] = {}
    await state.set_state(AdminStates.add_tariff_label)
    await call.message.edit_text("<b>➕ Новый тариф</b>\n\nШаг 1/4 — отправь <b>название</b> (например: 7 дней):", reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

@router.message(AdminStates.add_tariff_label)
async def msg_add_label(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    _add_tariff_buf[message.from_user.id]["label"] = message.text.strip()
    await state.set_state(AdminStates.add_tariff_days)
    await message.answer("Шаг 2/4 — отправь <b>кол-во дней</b> (0 = навсегда):", parse_mode="HTML")

@router.message(AdminStates.add_tariff_days)
async def msg_add_days(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        d = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи число!")
        return
    _add_tariff_buf[message.from_user.id]["days"] = d
    await state.set_state(AdminStates.add_tariff_rub)
    await message.answer("Шаг 3/4 — отправь <b>цену в ₽</b>:", parse_mode="HTML")

@router.message(AdminStates.add_tariff_rub)
async def msg_add_rub(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        r = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи число!")
        return
    _add_tariff_buf[message.from_user.id]["price_rub"] = r
    await state.set_state(AdminStates.add_tariff_stars)
    await message.answer("Шаг 4/4 — отправь <b>цену в звёздах (⭐)</b>:", parse_mode="HTML")

@router.message(AdminStates.add_tariff_stars)
async def msg_add_stars(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        s = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введи число!")
        return
    buf = _add_tariff_buf.get(message.from_user.id, {})
    buf["price_stars"] = s
    # insert
    async with get_db() as db:
        cur = await db.execute("SELECT COALESCE(MAX(sort),0) FROM tariffs")
        mx = (await cur.fetchone())[0]
        await db.execute(
            "INSERT INTO tariffs(label,days,price_rub,price_stars,is_active,sort) VALUES(?,?,?,?,1,?)",
            (buf["label"], buf["days"], buf["price_rub"], buf["price_stars"], mx + 1),
        )
        await db.commit()
    _add_tariff_buf.pop(message.from_user.id, None)
    await state.clear()
    await message.answer(f"✅ Тариф <b>{buf['label']}</b> добавлен!", parse_mode="HTML", reply_markup=admin_main_kb())

# ---------- gen keys ----------

@router.callback_query(F.data == "adm:genkey")
async def cb_genkey(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    _gen_buf[call.from_user.id] = {}
    await state.set_state(AdminStates.gen_amount)
    await call.message.edit_text(
        "<b>🔑 Генерация ключей</b>\n\nШаг 1/3 — сколько ключей сгенерировать? (1-50)\n<i>Отправь число:</i>",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await call.answer()

@router.message(AdminStates.gen_amount)
async def msg_gen_amount(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        n = int(message.text.strip())
        if not 1 <= n <= 50:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число от 1 до 50!")
        return
    _gen_buf[message.from_user.id]["amount"] = n
    await state.set_state(AdminStates.gen_days)
    await message.answer("Шаг 2/3 — на сколько дней? (0 = навсегда)\n<i>Отправь число дней:</i>", parse_mode="HTML")

@router.message(AdminStates.gen_days)
async def msg_gen_days(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    try:
        d = int(message.text.strip())
        if d < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введи число (0 = навсегда)!")
        return
    _gen_buf[message.from_user.id]["days"] = d
    await state.set_state(AdminStates.gen_format)
    settings = await get_all_settings()
    cur_fmt = settings.get("key_format", "KP-XXXX-XXXX-XXXX")
    await message.answer(
        f"Шаг 3/3 — формат ключа (текущий: <code>{cur_fmt}</code>)\n"
        f"Отправь формат (например <code>KP-XXXX-XXXX-XXXX</code>) или «-» чтобы использовать текущий.\n"
        f"Также можешь указать кому выдать: добавь через пробел ID (например <code>KP-XXXX-XXXX-XXXX 123456</code> — пропустит выдачу владельцу).",
        parse_mode="HTML"
    )

@router.message(AdminStates.gen_format)
async def msg_gen_format(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    parts = raw.split()
    fmt_input = parts[0] if parts else "-"
    owner_id = None
    if len(parts) > 1:
        try:
            owner_id = int(parts[1])
        except ValueError:
            pass
    settings = await get_all_settings()
    if fmt_input == "-" or not fmt_input:
        fmt = settings.get("key_format", "KP-XXXX-XXXX-XXXX")
    else:
        fmt = fmt_input
    prefix, segs, seg_len = parse_key_format(fmt)
    charset = settings.get("key_charset", "ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
    buf = _gen_buf.get(message.from_user.id, {})
    amount = buf.get("amount", 1)
    days = buf.get("days", 30)
    label = f"Админ-выдача {days}д" if days else "Админ-выдача навсегда"
    generated = []
    async with get_db() as db:
        for _ in range(amount):
            for attempt in range(20):
                key = generate_key(prefix, segs, seg_len, charset)
                expires = calc_expires(days)
                now_iso = datetime.now(timezone.utc).isoformat()
                try:
                    await db.execute(
                        "INSERT INTO license_keys(key,tariff_days,label,owner_id,created_at,expires_at) VALUES(?,?,?,?,?,?)",
                        (key, days, label, owner_id, now_iso, expires),
                    )
                    generated.append(key)
                    break
                except Exception:
                    continue
        await db.commit()
    _gen_buf.pop(message.from_user.id, None)
    await state.clear()
    if not generated:
        await message.answer("❌ Не удалось сгенерировать ключи.")
        return
    keys_text = "\n".join([f"<code>{k}</code>" for k in generated])
    await message.answer(
        f"✅ Сгенерировано <b>{len(generated)}</b> ключ(ей) на <b>{days if days else 'навсегда'}</b> дней:\n\n{keys_text}\n\n"
        f"Формат: <code>{fmt}</code>",
        parse_mode="HTML", reply_markup=admin_main_kb()
    )

# ---------- find / list keys ----------

@router.callback_query(F.data == "adm:findkey")
async def cb_findkey(call: CallbackQuery, bot: Bot, state: FSMContext):
    if not _is_admin(call.from_user.id):
        return
    await state.set_state(AdminStates.find_key)
    await call.message.edit_text("<b>🔍 Поиск ключа</b>\nОтправь ключ или его часть:", reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

@router.message(AdminStates.find_key)
async def msg_findkey(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    q = (message.text or "").strip()
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM license_keys WHERE key LIKE ? LIMIT 20", (f"%{q}%",))
        rows = await cur.fetchall()
    if not rows:
        await message.answer("😔 Ничего не найдено.", reply_markup=admin_main_kb())
    else:
        lines = []
        for r in rows:
            status = "✅ актив." if r["is_activated"] else "⏳ не акт."
            lines.append(
                f"<code>{r['key']}</code> — {r['label']} ({r['tariff_days']}д) | {status} | owner:{r['owner_id']} | hwid:{r['hwid'] or '—'} | exp:{r['expires_at'] or '♾️'}"
            )
        await message.answer("🔍 Результаты:\n\n" + "\n".join(lines), parse_mode="HTML", reply_markup=admin_main_kb())
    await state.clear()

@router.callback_query(F.data == "adm:listkeys")
async def cb_listkeys(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM license_keys ORDER BY id DESC LIMIT 15")
        rows = await cur.fetchall()
    if not rows:
        await call.message.edit_text("📋 Ключей пока нет.", reply_markup=admin_back_kb(), parse_mode="HTML")
    else:
        lines = []
        for r in rows:
            status = "✅" if r["is_activated"] else "⏳"
            lines.append(f"{status} <code>{r['key']}</code> | {r['label']} | owner:{r['owner_id']}")
        text = "<b>📋 Последние 15 ключей:</b>\n\n" + "\n".join(lines)
        try:
            await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
        except TelegramBadRequest:
            await call.message.delete()
            await bot.send_message(call.message.chat.id, text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

# ---------- stats ----------

@router.callback_query(F.data == "adm:stats")
async def cb_stats(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    async with get_db() as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        u = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM license_keys")
        k = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM license_keys WHERE is_activated=1")
        a = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COALESCE(SUM(spent_rub),0), COALESCE(SUM(spent_stars),0) FROM users")
        row = await cur.fetchone()
        sr, ss = row[0], row[1]
        cur = await db.execute("SELECT * FROM pending_payments ORDER BY id DESC LIMIT 5")
        pend = await cur.fetchall()
    pend_lines = "\n".join([f"• #{p['id']} u:{p['user_id']} {p['kind']} {p['amount_rub'] or p['amount_stars']} {p['status']}" for p in pend]) or "нет"
    text = (
        f"<b>📊 Статистика KeyPulse</b>\n\n"
        f"👥 Юзеров: <b>{u}</b>\n"
        f"🔑 Ключей: <b>{k}</b> (активировано {a})\n"
        f"💰 Выручка: <b>{sr} ₽</b> + <b>{ss} ⭐️</b>\n\n"
        f"<b>Последние платежи:</b>\n{pend_lines}"
    )
    try:
        await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")
    except TelegramBadRequest:
        await call.message.delete()
        await bot.send_message(call.message.chat.id, text, reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

# ---------- подтверждение заявок СБП ----------

@router.callback_query(F.data.startswith("adm:pay_ok:"))
async def cb_pay_ok(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    pid = int(call.data.split(":")[-1])
    payment = await get_payment(pid)
    if not payment:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return
    if payment["status"] == "paid":
        await call.answer("✅ Уже подтверждена", show_alert=True)
        return

    await set_payment_status(pid, "paid")
    user_id = payment["user_id"]

    if payment["kind"] == "tariff":
        tariff = await get_tariff(payment["tariff_id"])
        if not tariff:
            await call.answer("❌ Тариф удалён", show_alert=True)
            return
        _key, text = await issue_key(user_id, tariff, rub_paid=payment["amount_rub"] or 0)
    else:
        text = await reset_user_hwid(user_id, rub_paid=payment["amount_rub"] or 0)

    btns = await get_all_buttons()
    kb = back_kb(btns.get("btn_back", "◀️ Назад"))
    try:
        await bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await call.answer("⚠️ Заявка подтверждена, но пользователь заблокировал бота", show_alert=True)

    try:
        await call.message.edit_text(
            (call.message.html_text or "") + f"\n\n<b>✅ Подтверждено админом</b>",
            reply_markup=None, parse_mode="HTML",
        )
    except Exception:
        pass
    await call.answer("✅ Ключ выдан")


@router.callback_query(F.data.startswith("adm:pay_no:"))
async def cb_pay_no(call: CallbackQuery, bot: Bot):
    if not _is_admin(call.from_user.id):
        return
    pid = int(call.data.split(":")[-1])
    payment = await get_payment(pid)
    if not payment:
        await call.answer("❌ Заявка не найдена", show_alert=True)
        return
    await set_payment_status(pid, "rejected")
    try:
        await bot.send_message(
            payment["user_id"],
            f"<b>❌ Заявка #{pid} отклонена</b>\n\nЕсли ты оплатил — напиши в поддержку.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    try:
        await call.message.edit_text(
            (call.message.html_text or "") + "\n\n<b>❌ Отклонено</b>",
            reply_markup=None, parse_mode="HTML",
        )
    except Exception:
        pass
    await call.answer("Отклонено")

# ---------- cancel ----------

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, bot: Bot, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    _add_tariff_buf.pop(message.from_user.id, None)
    _gen_buf.pop(message.from_user.id, None)
    await send_admin_panel(message, bot)
