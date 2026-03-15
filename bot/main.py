import asyncio
import logging
import random
import sys
import os
from typing import List

# ФИКС ИМПОРТА
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from .config import BOT_TOKEN, DB_PATH
from db.database import GardenGramDB
from db.models import GRID_SIZE, INGREDIENTS, RECIPES

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = GardenGramDB(DB_PATH)
router = Router()
dp.include_router(router)

GRID_SIZE = 4

class FarmStates(StatesGroup):
    registration_nick = State()

def render_grid(grid: List[str], cursor_pos: int = 0) -> str:
    """ЧИСТОЕ ASCII поле"""
    field_text = "```\n"
    for i in range(GRID_SIZE):
        row_items = []
        for j in range(4):
            pos = i * 4 + j
            item = grid[pos]
            if pos == cursor_pos:
                row_items.append(f"[{item}]")
            else:
                row_items.append(f" {item} ")
        
        row = "|".join(row_items)
        field_text += f"{row}\n"
    field_text += "```"
    return field_text

def grid_keyboard() -> InlineKeyboardMarkup:
    """Ретро клавиатура"""
    kb = [
        [
            InlineKeyboardButton(text=" ", callback_data="none"),
            InlineKeyboardButton(text="⬆️", callback_data="move_up"),
            InlineKeyboardButton(text=" ", callback_data="none")
        ],
        [
            InlineKeyboardButton(text="⬅️", callback_data="move_left"),
            InlineKeyboardButton(text="✅ Выполнить", callback_data="action_execute"),
            InlineKeyboardButton(text="➡️", callback_data="move_right")
        ],
        [
            InlineKeyboardButton(text=" ", callback_data="none"),
            InlineKeyboardButton(text="⬇️", callback_data="move_down"),
            InlineKeyboardButton(text=" ", callback_data="none")
        ],
        [
            InlineKeyboardButton(text="🍳 Кухня", callback_data="mode_kitchen"),
            InlineKeyboardButton(text="🐴 Осёл", callback_data="mode_donkey")
        ]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

def mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌱 Garden", callback_data="mode_garden")],
        [InlineKeyboardButton(text="🍳 Kitchen", callback_data="mode_kitchen")],
        [InlineKeyboardButton(text="🐴 Donkey", callback_data="mode_donkey")]
    ])

@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    registered = await db.is_registered(user_id)
    if not registered and message.chat.type == "private":
        await message.answer(
            "👋 Привет! Придумай ник (до 32 символов):\n"
            "Просто напиши текст без /"
        )
        await state.set_state(FarmStates.registration_nick)
        return
    
    if not registered:
        await message.answer("❌ Регистрация только в личке бота!")
        return
    
    if message.chat.type == "private":
        await message.answer("✅ Игра только в групповых чатах!\nПиши /garden в чате.")
    else:
        await show_garden(message)

@router.message(FarmStates.registration_nick)
async def register_nick(message: Message, state: FSMContext):
    nick = message.text.strip()[:32]
    if len(nick) < 3:
        await message.answer("❌ Ник слишком короткий! Минимум 3 символа.")
        return
    
    await db.register_player(message.from_user.id, nick)
    await state.clear()
    await message.answer(
        f"✅ Зарегистрирован как **{nick}**!\n\n"
        "🎮 Играй в групповых чатах: **/garden**",
        parse_mode="Markdown"
    )

@router.message(Command("garden"))
async def garden_command(message: Message):
    user_id = message.from_user.id
    registered = await db.is_registered(user_id)
    
    if not registered:
        await message.answer("❌ Сначала зарегистрируйся в личке бота!")
        return
    
    await show_garden(message)

async def show_garden(message_or_cb):
    user_id = message_or_cb.from_user.id
    
    grid = await db.get_player_grid(user_id)
    cursor_pos = await db.get_cursor_pos(user_id)
    last_spawn_time = await db.get_last_spawn_time(user_id)
    
    import time
    current_time = time.time()
    
    if not grid:
        grid = ["."] * 16
        
    if current_time - last_spawn_time >= 1200 or all(item == "." for item in grid):
        wheat_count = random.randint(3, 6)
        apple_count = random.randint(2, 4)
        
        # Don't spawn more than what fits in the empty space
        empty_spaces = [i for i, x in enumerate(grid) if x == "."]
        
        for _ in range(wheat_count):
            if not empty_spaces: break
            pos = random.choice(empty_spaces)
            empty_spaces.remove(pos)
            grid[pos] = "🌾"
            
        for _ in range(apple_count):
            if not empty_spaces: break
            pos = random.choice(empty_spaces)
            empty_spaces.remove(pos)
            grid[pos] = "🍎"
            
        await db.set_player_grid(user_id, grid)
        await db.set_last_spawn_time(user_id, current_time)
    
    wheat_count = grid.count("🌾")
    apple_count = grid.count("🍎")
    
    field_text = render_grid(grid, cursor_pos)
    kb = grid_keyboard()
    
    text = f"🌱 **Сад** (найди {wheat_count}🌾 и {apple_count}🍎)\n\n{field_text}"
    
    if isinstance(message_or_cb, Message):
        await message_or_cb.reply(text, reply_markup=kb, parse_mode="Markdown")
    else:
        try:
            await message_or_cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except:
            pass

@router.callback_query(F.data == "action_execute")
async def action_execute(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    grid = await db.get_player_grid(user_id)
    pos = await db.get_cursor_pos(user_id)
    item = grid[pos]
    
    if item in ["🌾", "🍎"]:
        grid[pos] = "."
        await db.set_player_grid(user_id, grid)
        await db.add_inventory(user_id, item, 1)
        await callback.answer(f"✅ Собрано {item}!")
    else:
        await callback.answer("❌ Пусто!")
        
    await show_garden(callback)

@router.callback_query(F.data.startswith("mode_"))
async def switch_mode(callback: CallbackQuery):
    mode = callback.data.split("_")[1]
    if mode == "garden":
        await show_garden(callback)
    elif mode == "kitchen":
        await show_kitchen(callback)
    elif mode == "donkey":
        await show_donkey(callback)
    await callback.answer()

async def show_kitchen(callback: CallbackQuery):
    user_id = callback.from_user.id
    inventory = await db.get_inventory(user_id)
    
    inv_text = "📦 **Инвентарь**:\n"
    if not inventory:
        inv_text += "Пусто\n"
    for item, count in inventory.items():
        inv_text += f"{item}: {count}\n"
    
    text = f"🍳 **Кухня**\n\n{inv_text}\nВыбери рецепт или перейди в другой режим!"
    
    kb = []
    kb.append([InlineKeyboardButton(text="💧 Набрать воды", callback_data="get_water")])
    
    for recipe_id, recipe in RECIPES.items():
        res_name = recipe['result']
        res_emoji = recipe['emoji']
        cost_text = ", ".join(f"{c}x {ing}" for ing, c in recipe['from'])
        kb.append([InlineKeyboardButton(
            text=f"Сделать {res_emoji} {res_name} ({cost_text})",
            callback_data=f"craft_{recipe_id}"
        )])
    
    kb.extend(mode_keyboard().inline_keyboard)
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "get_water")
async def get_water_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    await db.add_inventory(user_id, "water", 1)
    await callback.answer("💧 Вы набрали воды!")
    await show_kitchen(callback)

@router.callback_query(F.data.startswith("craft_"))
async def craft_item(callback: CallbackQuery):
    recipe_id = callback.data.split("craft_")[1]
    user_id = callback.from_user.id
    
    if recipe_id not in RECIPES:
        await callback.answer("❌ Неизвестный рецепт!")
        return
        
    recipe = RECIPES[recipe_id]
    inventory = await db.get_inventory(user_id)
    
    # Check ingredients
    for ing, count in recipe['from']:
        if inventory.get(ing, 0) < count:
            await callback.answer(f"❌ Не хватает {ing} (нужно {count})")
            return
            
    # Deduct ingredients
    for ing, count in recipe['from']:
        await db.remove_inventory(user_id, ing, count)
        
    await db.add_inventory(user_id, recipe['result'], 1)
    await callback.answer(f"✅ Приготовлено: {recipe['result']} {recipe['emoji']}!")
    
    await show_kitchen(callback)

async def show_donkey(callback: CallbackQuery):
    user_id = callback.from_user.id
    inventory = await db.get_inventory(user_id)
    
    donkey_phrases = [
        "🐴 Говорят, тут лучшие фермеры. Угостишь?",
        "🐴 Не знаю зачем, но мне нужен яблочный пирог. Сделаешь — будешь молодец.",
        "🐴 Хватит ковыряться в грядках, принеси мне нормальной еды!"
    ]
    
    text = "🐴 **Осёл**\n\n" + random.choice(donkey_phrases)
    kb = mode_keyboard().inline_keyboard
    
    actions = []
    if inventory.get('apple_pie', 0) > 0:
        actions.append(InlineKeyboardButton(text="🍰 Дать яблочный пирог", callback_data="give_donkey_apple_pie"))
    if inventory.get('apple', 0) > 0:
        actions.append(InlineKeyboardButton(text="🍎 Дать яблоко", callback_data="give_donkey_apple"))
        
    if actions:
        kb.insert(0, actions)
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("give_donkey_"))
async def give_donkey(callback: CallbackQuery):
    item = callback.data.split("give_donkey_")[1]
    user_id = callback.from_user.id
    inventory = await db.get_inventory(user_id)
    
    if inventory.get(item, 0) < 1:
        await callback.answer(f"❌ У тебя нет {item}!")
        return
        
    await db.remove_inventory(user_id, item, 1)
    
    if item == "apple_pie":
        msg = "🐴 ВАУ! Какой пирог! Огромное спасибо, фермер! ✨"
    else:
        msg = "🐴 Ммм, вкусное яблочко! Спасибо."
        
    text = "🐴 **Осёл**\n\n" + msg
    kb = mode_keyboard()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer("✅ Ты накормил осла!")

def move_handlers():
    """Обработчики действий"""
    @router.callback_query(F.data == "move_left")
    async def move_left(callback: CallbackQuery):
        user_id = callback.from_user.id
        pos = await db.get_cursor_pos(user_id)
        if pos % 4 > 0:
            await db.set_cursor_pos(user_id, pos - 1)
            await show_garden(callback)
        else:
            await callback.answer("🛑 Стена!")
            
    @router.callback_query(F.data == "move_right")
    async def move_right(callback: CallbackQuery):
        user_id = callback.from_user.id
        pos = await db.get_cursor_pos(user_id)
        if pos % 4 < 3:
            await db.set_cursor_pos(user_id, pos + 1)
            await show_garden(callback)
        else:
            await callback.answer("🛑 Стена!")
            
    @router.callback_query(F.data == "move_up")
    async def move_up(callback: CallbackQuery):
        user_id = callback.from_user.id
        pos = await db.get_cursor_pos(user_id)
        if pos >= 4:
            await db.set_cursor_pos(user_id, pos - 4)
            await show_garden(callback)
        else:
            await callback.answer("🛑 Стена!")
            
    @router.callback_query(F.data == "move_down")
    async def move_down(callback: CallbackQuery):
        user_id = callback.from_user.id
        pos = await db.get_cursor_pos(user_id)
        if pos < 12:
            await db.set_cursor_pos(user_id, pos + 4)
            await show_garden(callback)
        else:
            await callback.answer("🛑 Стена!")

    @router.callback_query(F.data == "none")
    async def ignore_press(callback: CallbackQuery):
        await callback.answer()

move_handlers()

async def main():
    await db.init()
    print("🚀 GardenGram запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

