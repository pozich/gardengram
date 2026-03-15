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

def mode_keyboard() -> list:
    return [
        InlineKeyboardButton(text="🌱 Garden", callback_data="mode_garden"),
        InlineKeyboardButton(text="🍳 Kitchen", callback_data="mode_kitchen"),
        InlineKeyboardButton(text="🐴 Donkey", callback_data="mode_donkey")
    ]

def grid_keyboard(mode: str) -> InlineKeyboardMarkup:
    """Ретро клавиатура"""
    kb = [
        [
            InlineKeyboardButton(text=" ", callback_data="none"),
            InlineKeyboardButton(text="⬆️", callback_data=f"move_up_{mode}"),
            InlineKeyboardButton(text=" ", callback_data="none")
        ],
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"move_left_{mode}"),
            InlineKeyboardButton(text="✅ Выполнить", callback_data=f"action_execute_{mode}"),
            InlineKeyboardButton(text="➡️", callback_data=f"move_right_{mode}")
        ],
        [
            InlineKeyboardButton(text=" ", callback_data="none"),
            InlineKeyboardButton(text="⬇️", callback_data=f"move_down_{mode}"),
            InlineKeyboardButton(text=" ", callback_data="none")
        ]
    ]
    
    # Add mode switchers dynamically, excluding the current mode
    mode_btns = mode_keyboard()
    bottom_row = [btn for btn in mode_btns if btn.callback_data != f"mode_{mode}"]
    kb.append(bottom_row)
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

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
    print(f"DEBUG: Received /garden from {message.from_user.id} in {message.chat.type}")
    try:
        user_id = message.from_user.id
        registered = await db.is_registered(user_id)
        
        if not registered:
            print(f"DEBUG: User {user_id} is not registered")
            await message.answer("❌ Сначала зарегистрируйся в личке бота!")
            return
        
        print(f"DEBUG: Showing garden for {user_id}")
        await show_garden(message)
    except Exception as e:
        print(f"ERROR in garden_command: {e}")
        await message.answer(f"❌ Произошла ошибка: {e}")

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
    kb = grid_keyboard("garden")
    
    text = f"🌱 **Сад** (найди {wheat_count}🌾 и {apple_count}🍎)\n\n{field_text}"
    
    if isinstance(message_or_cb, Message):
        try:
            await message_or_cb.reply(text, reply_markup=kb, parse_mode="Markdown")
        except Exception as e:
            print(f"ERROR replying in show_garden: {e}")
    else:
        try:
            await message_or_cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception as e:
            print(f"ERROR editing text in show_garden: {e}")

@router.callback_query(F.data == "action_execute_garden")
async def action_execute_garden(callback: CallbackQuery):
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

def get_kitchen_grid(inventory: dict) -> List[str]:
    grid = ["."] * 16
    
    # 0-11 for inventory ingredients that can be cooked
    idx = 0
    for item_key, count in inventory.items():
        if getattr(db, 'models', None) is None:
            # Fallback direct lookup just in case
            emoji = INGREDIENTS.get(item_key, {}).get('emoji') or RECIPES.get(item_key, {}).get('emoji') or "?"
        else:
            emoji = INGREDIENTS.get(item_key, {}).get('emoji') or RECIPES.get(item_key, {}).get('emoji') or "?"
            
        if idx < 12 and count > 0:
            grid[idx] = emoji
            idx += 1
            
    # Bottom row (12-15) for appliances
    grid[12] = "🔪" # Physical
    grid[13] = "🔥" # Thermal
    grid[14] = "🧫" # Bio
    grid[15] = "💧" # Water
    return grid

async def show_kitchen(callback: CallbackQuery):
    user_id = callback.from_user.id
    inventory = await db.get_inventory(user_id)
    cursor_pos = await db.get_cursor_pos(user_id)
    selected_item = await db.get_selected_item(user_id)
    
    # Generate ephemeral kitchen grid
    grid = get_kitchen_grid(inventory)
    
    inv_text = "📦 **Инвентарь**:\n"
    if not inventory:
        inv_text += "Пусто\n"
    for item, count in inventory.items():
        emoji = INGREDIENTS.get(item, {}).get('emoji') or RECIPES.get(item, {}).get('emoji') or ""
        inv_text += f"{emoji} {item}: {count}\n"
        
    field_text = render_grid(grid, cursor_pos)
    kb = grid_keyboard("kitchen")
    
    sel_text = f"В руке: {selected_item if selected_item else 'Ничего'}"
    text = f"🍳 **Кухня**\n\n{inv_text}\n{sel_text}\n\n{field_text}"
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except:
        pass
    await callback.answer()
async def action_execute_kitchen(callback: CallbackQuery):
    user_id = callback.from_user.id
    pos = await db.get_cursor_pos(user_id)
    inventory = await db.get_inventory(user_id)
    grid = get_kitchen_grid(inventory)
    item = grid[pos]
    
    if item == ".":
        await callback.answer("❌ Пусто!")
        return
        
    if pos < 12: # Pick up item
        # Find item id by emoji
        item_id = None
        for k, v in INGREDIENTS.items():
            if v.get('emoji') == item: item_id = k
        for k, v in RECIPES.items():
            if v.get('emoji') == item: item_id = k
            
        if item_id:
            await db.set_selected_item(user_id, item)
            await callback.answer(f"✋ Взято: {item}")
        else:
            await callback.answer("❌ Не удалось взять")
    else: # Appliance action
        await process_appliance(user_id, item, callback)
        
    await show_kitchen(callback)
    
async def process_appliance(user_id, appliance_emoji, callback):
    appliance_map = {"🔪": "physical", "🔥": "thermal", "🧫": "bio", "💧": "water"}
    process = appliance_map.get(appliance_emoji)
    
    if process == "water":
        await db.add_inventory(user_id, "water", 1)
        await callback.answer("💧 Вы набрали воды!")
        return
        
    selected_emoji = await db.get_selected_item(user_id)
    if not selected_emoji:
        await callback.answer("❌ Ничего не выбрано!")
        return
        
    # Find item ID from emoji
    selected_id = None
    for k, v in INGREDIENTS.items():
        if v.get('emoji') == selected_emoji: selected_id = k
    for k, v in RECIPES.items():
        if v.get('emoji') == selected_emoji: selected_id = k
        
    if not selected_id:
        await callback.answer("❌ Ошибка предмета")
        return
        
    # Find recipe
    matched_recipe_id = None
    for r_id, r in RECIPES.items():
        if r.get('process') == process and any(ing[0] == selected_id for ing in r.get('from', [])):
            matched_recipe_id = r_id
            break
            
    # Allow combining two ingredients if 'process' is None (like dough from flour and water)
    if not matched_recipe_id and appliance_emoji == "🔪": # Use knife for combining as a fallback
        for r_id, r in RECIPES.items():
            if r.get('process') is None and any(ing[0] == selected_id for ing in r.get('from', [])):
                reqs = r.get('from', [])
                other_ing = reqs[1][0] if reqs[0][0] == selected_id and len(reqs) > 1 else reqs[0][0]
                
                inventory = await db.get_inventory(user_id)
                if inventory.get(other_ing, 0) > 0 and other_ing != selected_id:
                    await db.remove_inventory(user_id, selected_id, 1)
                    await db.remove_inventory(user_id, other_ing, 1)
                    await db.add_inventory(user_id, r_id, 1)
                    await db.set_selected_item(user_id, None)
                    await callback.answer(f"✅ Приготовлено: {r.get('emoji')}!")
                    return
                elif len(reqs) == 1 or other_ing == selected_id: # Single ingredient combination?
                     pass
                else:
                    await callback.answer(f"❌ Не хватает {other_ing}")
                    return
                    
    if not matched_recipe_id:
        await callback.answer("❌ Нет рецепта!")
        return
        
    recipe = RECIPES[matched_recipe_id]
    await db.remove_inventory(user_id, selected_id, 1)
    await db.add_inventory(user_id, recipe['result'], 1)
    await db.set_selected_item(user_id, None)
    await callback.answer(f"✅ Приготовлено: {recipe['result']} {recipe['emoji']}!")

async def show_donkey(callback: CallbackQuery):
    user_id = callback.from_user.id
    inventory = await db.get_inventory(user_id)
    
    donkey_phrases = [
        "🐴 Говорят, тут лучшие фермеры. Угостишь?",
        "🐴 Не знаю зачем, но мне нужен яблочный пирог. Сделаешь — будешь молодец.",
        "🐴 Хватит ковыряться в грядках, принеси мне нормальной еды!"
    ]
    
    text = "🐴 **Осёл**\n\n" + random.choice(donkey_phrases)
    kb = [mode_keyboard()]
    
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
    kb = InlineKeyboardMarkup(inline_keyboard=[mode_keyboard()])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer("✅ Ты накормил осла!")

def move_handlers():
    """Обработчики действий"""
    @router.callback_query(F.data.startswith("move_left_"))
    async def move_left(callback: CallbackQuery):
        mode = callback.data.split("_")[2]
        user_id = callback.from_user.id
        pos = await db.get_cursor_pos(user_id)
        if pos % 4 > 0:
            await db.set_cursor_pos(user_id, pos - 1)
            await (show_garden(callback) if mode == "garden" else show_kitchen(callback))
        else:
            await callback.answer("🛑 Стена!")
            
    @router.callback_query(F.data.startswith("move_right_"))
    async def move_right(callback: CallbackQuery):
        mode = callback.data.split("_")[2]
        user_id = callback.from_user.id
        pos = await db.get_cursor_pos(user_id)
        if pos % 4 < 3:
            await db.set_cursor_pos(user_id, pos + 1)
            await (show_garden(callback) if mode == "garden" else show_kitchen(callback))
        else:
            await callback.answer("🛑 Стена!")
            
    @router.callback_query(F.data.startswith("move_up_"))
    async def move_up(callback: CallbackQuery):
        mode = callback.data.split("_")[2]
        user_id = callback.from_user.id
        pos = await db.get_cursor_pos(user_id)
        if pos >= 4:
            await db.set_cursor_pos(user_id, pos - 4)
            await (show_garden(callback) if mode == "garden" else show_kitchen(callback))
        else:
            await callback.answer("🛑 Стена!")
            
    @router.callback_query(F.data.startswith("move_down_"))
    async def move_down(callback: CallbackQuery):
        mode = callback.data.split("_")[2]
        user_id = callback.from_user.id
        pos = await db.get_cursor_pos(user_id)
        if pos < 12:
            await db.set_cursor_pos(user_id, pos + 4)
            await (show_garden(callback) if mode == "garden" else show_kitchen(callback))
        else:
            await callback.answer("🛑 Стена!")

    @router.callback_query(F.data == "none")
    async def ignore_press(callback: CallbackQuery):
        await callback.answer()

@router.message()
async def any_message_handler(message: Message):
    if message.text:
        print(f"DEBUG: Message in {message.chat.type} from {message.from_user.id}: {message.text[:50]}")

move_handlers()

async def main():
    await db.init()
    print("🚀 GardenGram запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

