from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Премиум эмодзи — используем Unicode (совместимо везде) + custom_emoji_id можно подставить позже
# Источник: https://emoji.wivvi.net/ — там собраны премиум emoji, id берутся из Telegram

def main_menu_kb(btns: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=btns.get("btn_get_key", "🔑 Получить ключ"), callback_data="menu:shop")
    kb.button(text=btns.get("btn_profile", "👤 Мой профиль"), callback_data="menu:profile")
    kb.button(text=btns.get("btn_reset_hwid", "🔧 Сбросить HWID"), callback_data="menu:hwid")
    kb.adjust(2, 1)
    return kb.as_markup()


def shop_kb(tariffs, btn_back: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in tariffs:
        price = f"{t['price_rub']}₽ / {t['price_stars']}⭐"
        label = f"{t['label']} — {price}"
        kb.button(text=label, callback_data=f"tariff:{t['id']}")
    kb.button(text=btn_back, callback_data="menu:main")
    # 1 кнопка в ряд если 4 тарифа — 3 сверху + 1 снизу как в ТЗ? делаем 1 в ряд для читаемости
    # Если 3 тарифа — 2+1, если 4 — 3+1, иначе 1 в ряд
    n = len(tariffs)
    if n == 4:
        kb.adjust(3, 1, 1)
    elif n == 3:
        kb.adjust(2, 1, 1)
    else:
        kb.adjust(1)
    return kb.as_markup()


def pay_choice_kb(tariff_id: int, btn_sbp: str, btn_stars: str, btn_back: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=btn_sbp, callback_data=f"pay:sbp:{tariff_id}")
    kb.button(text=btn_stars, callback_data=f"pay:stars:{tariff_id}")
    kb.button(text=btn_back, callback_data="menu:shop")
    kb.adjust(2, 1)
    return kb.as_markup()


def hwid_kb(btn_sbp: str, btn_stars: str, price_rub: str, price_stars: str, btn_back: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"{btn_sbp} — {price_rub}₽", callback_data="hwid:pay:sbp")
    kb.button(text=f"{btn_stars} — {price_stars}⭐", callback_data="hwid:pay:stars")
    kb.button(text=btn_back, callback_data="menu:main")
    kb.adjust(2, 1)
    return kb.as_markup()


def back_kb(btn_back: str, target: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=btn_back, callback_data=target)]
    ])


# ========== ADMIN KEYBOARDS ==========

def admin_main_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📝 Тексты", callback_data="adm:texts")
    kb.button(text="🔘 Кнопки", callback_data="adm:buttons")
    kb.button(text="⚙️ Настройки", callback_data="adm:settings")
    kb.button(text="💰 Тарифы", callback_data="adm:tariffs")
    kb.button(text="🔑 Генерация ключей", callback_data="adm:genkey")
    kb.button(text="📊 Статистика", callback_data="adm:stats")
    kb.button(text="🔍 Найти ключ", callback_data="adm:findkey")
    kb.button(text="📋 Последние ключи", callback_data="adm:listkeys")
    kb.button(text="❌ Закрыть", callback_data="adm:close")
    kb.adjust(2, 2, 2, 2, 1)
    return kb.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:main")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="adm:close")],
    ])


def admin_texts_kb(texts: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for k in texts:
        label = k.replace("_", " ")[:30]
        kb.button(text=f"✏️ {label}", callback_data=f"adm:edit_text:{k}")
    kb.button(text="◀️ Назад", callback_data="adm:main")
    kb.adjust(2)
    return kb.as_markup()


def admin_buttons_kb(buttons: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for k in buttons:
        kb.button(text=f"✏️ {k}", callback_data=f"adm:edit_btn:{k}")
    kb.button(text="◀️ Назад", callback_data="adm:main")
    kb.adjust(2)
    return kb.as_markup()


def admin_settings_kb(settings: dict) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for k in settings:
        kb.button(text=f"✏️ {k}", callback_data=f"adm:edit_set:{k}")
    kb.button(text="◀️ Назад", callback_data="adm:main")
    kb.adjust(2)
    return kb.as_markup()


def admin_tariffs_kb(tariffs) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in tariffs:
        status = "✅" if t["is_active"] else "🚫"
        kb.button(text=f"{status} {t['label']} ({t['price_rub']}₽)", callback_data=f"adm:tariff:{t['id']}")
    kb.button(text="➕ Добавить тариф", callback_data="adm:tariff_add")
    kb.button(text="◀️ Назад", callback_data="adm:main")
    kb.adjust(1)
    return kb.as_markup()


def admin_tariff_edit_kb(tariff_id: int, is_active: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Изменить цену ₽", callback_data=f"adm:tariff_price_rub:{tariff_id}")
    kb.button(text="✏️ Изменить цену ⭐", callback_data=f"adm:tariff_price_stars:{tariff_id}")
    kb.button(text="✏️ Изменить название", callback_data=f"adm:tariff_label:{tariff_id}")
    kb.button(text="✏️ Изменить дни", callback_data=f"adm:tariff_days:{tariff_id}")
    toggle = "🚫 Деактивировать" if is_active else "✅ Активировать"
    kb.button(text=toggle, callback_data=f"adm:tariff_toggle:{tariff_id}")
    kb.button(text="🗑 Удалить", callback_data=f"adm:tariff_del:{tariff_id}")
    kb.button(text="◀️ Назад", callback_data="adm:tariffs")
    kb.adjust(2, 1, 1, 1)
    return kb.as_markup()
