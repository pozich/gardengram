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

def render_grid(grid, cursor_pos) -> str:
    """Стабильная эмодзи-сетка"""
    lines = []
    for i in range(GRID_SIZE):
        row = ""
        for j in range(GRID_SIZE):
            pos = i * GRID_SIZE + j
            if pos == cursor_pos:
                row += "📍"
            else:
                item = grid[pos]
                # Use a placeholder for empty cells to keep alignment
                row += item if item != "." else "▫️"
        lines.append(row)
    
    return "\n".join(lines)

def mode_keyboard() -> list:
    return [
        InlineKeyboardButton(text="🌱 Garden", callback_data="mode_garden"),
        InlineKeyboardButton(text="🍳 Kitchen", callback_data="mode_kitchen"),
        InlineKeyboardButton(text="🐴 Donkey", callback_data="mode_donkey")
    ]

def grid_keyboard(mode: str) -> InlineKeyboardMarkup:
    """Ретро клавиатура"""
    action_text = "✅ Взять" if mode == "kitchen" else "✅ Выполнить"
    
    kb = [
        [
            InlineKeyboardButton(text=" ", callback_data="none"),
            InlineKeyboardButton(text="⬆️", callback_data=f"move_up_{mode}"),
            InlineKeyboardButton(text=" ", callback_data="none")
        ],
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"move_left_{mode}"),
            InlineKeyboardButton(text=" ", callback_data="none"), # Placeholder for Take button
            InlineKeyboardButton(text="➡️", callback_data=f"move_right_{mode}")
        ],
        [
            InlineKeyboardButton(text=" ", callback_data="none"),
            InlineKeyboardButton(text="⬇️", callback_data=f"move_down_{mode}"),
            InlineKeyboardButton(text=" ", callback_data="none")
        ]
    ]
    
    # Insert Take button safely
    kb[1][1] = InlineKeyboardButton(text=action_text, callback_data=f"action_execute_{mode}")
    
    if mode == "kitchen":
        # Add appliance buttons
        kb.append([
            InlineKeyboardButton(text="🔪 Нарезать", callback_data="process_physical"),
            InlineKeyboardButton(text="🔥 Пожарить", callback_data="process_thermal")
        ])
    
    # Add mode switchers dynamically
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
    try:
        user_id = message.from_user.id
        registered = await db.is_registered(user_id)
        
        if not registered:
            await message.answer("❌ Сначала зарегистрируйся в личке бота!")
            return
        
        await show_garden(message)
    except Exception as e:
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
    
    # What's under cursor?
    focus_item = grid[cursor_pos]
    focus_text = ""
    if focus_item == "🌾": focus_text = "\n🔍 Наведено на: 🌾 Пшеница"
    elif focus_item == "🍎": focus_text = "\n🔍 Наведено на: 🍎 Яблоко"
    
    text = f"🌱 **Сад** (найди {wheat_count}🌾 и {apple_count}🍎)\n\n{field_text}{focus_text}"
    
    if isinstance(message_or_cb, Message):
        try:
            await message_or_cb.reply(text, reply_markup=kb, parse_mode="Markdown")
        except:
            pass
    else:
        try:
            await message_or_cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except:
            pass

@router.callback_query(F.data == "action_execute_garden")
async def action_execute_garden(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    grid = await db.get_player_grid(user_id)
    pos = await db.get_cursor_pos(user_id)
    item = grid[pos]
    
    if item in ["🌾", "🍎"]:
        grid[pos] = "."
        item_id = "wheat" if item == "🌾" else "apple"
        await db.set_player_grid(user_id, grid)
        await db.add_inventory(user_id, item_id, 1)
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
    
    # Fill up to 16 slots with inventory ingredients
    idx = 0
    for res_emoji, count in inventory.items():
        if idx >= 16: break
        if count <= 0: continue
        
        # If it's already an emoji, use it. Otherwise, look it up.
        if len(res_emoji) <= 2: 
            grid[idx] = res_emoji
        else:
            emoji = INGREDIENTS.get(res_emoji, {}).get('emoji') or RECIPES.get(res_emoji, {}).get('emoji') or "📦"
            grid[idx] = emoji
        idx += 1
            
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
        if len(item) <= 2: # Already emoji
            inv_text += f"{item}: {count}\n"
        else:
            emoji = INGREDIENTS.get(item, {}).get('emoji') or RECIPES.get(item, {}).get('emoji') or "📦"
            inv_text += f"{emoji} {item}: {count}\n"
        
    field_text = render_grid(grid, cursor_pos)
    kb = grid_keyboard("kitchen")
    
    # What's under cursor?
    # grid in kitchen is items_in_inv
    items_in_inv = [k for k, v in inventory.items() if v > 0]
    focus_text = ""
    if cursor_pos < len(items_in_inv):
        item_id = items_in_inv[cursor_pos]
        emoji = INGREDIENTS.get(item_id, {}).get('emoji') or RECIPES.get(item_id, {}).get('emoji') or "📦"
        focus_text = f"\n🔍 Наведено на: {emoji} {item_id}"
    
    # Selected item display
    sel_emoji = ""
    if selected_item:
        sel_emoji = INGREDIENTS.get(selected_item, {}).get('emoji') or RECIPES.get(selected_item, {}).get('emoji') or "📦"
    
    sel_text = f"В руке: {sel_emoji} {selected_item if selected_item else 'Ничего'}"
    text = f"🍳 **Кухня**\n\n{inv_text}\n{sel_text}\n\n{field_text}{focus_text}"
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except:
        pass
    await callback.answer()
async def action_execute_kitchen(callback: CallbackQuery):
    user_id = callback.from_user.id
    pos = await db.get_cursor_pos(user_id)
    inventory = await db.get_inventory(user_id)
    
    # Get items list from inventory (only those count > 0)
    items_in_inv = [k for k, v in inventory.items() if v > 0]
    
    if pos >= len(items_in_inv):
        await callback.answer("❌ Пусто!")
        return
        
    selected_id = items_in_inv[pos]
    emoji = INGREDIENTS.get(selected_id, {}).get('emoji') or RECIPES.get(selected_id, {}).get('emoji') or "📦"
    
    await db.set_selected_item(user_id, selected_id)
    await callback.answer(f"✋ Взято: {emoji} {selected_id}")
    await show_kitchen(callback)


@router.callback_query(F.data.startswith("process_"))
async def handle_process_button(callback: CallbackQuery):
    user_id = callback.from_user.id
    proc_type = callback.data.split("_")[1] # physical, thermal, bio, water
    
    # Map back to symbols for compatibility with process_appliance if needed, 
    # but let's just use the proc_type directly.
    symbol_map = {"physical": "🔪", "thermal": "🔥", "bio": "🧫", "water": "💧"}
    symbol = symbol_map.get(proc_type)
    
    await process_appliance(user_id, symbol, callback)
    await show_kitchen(callback)
    
async def process_appliance(user_id, appliance_emoji, callback):
    appliance_map = {"🔪": "physical", "🔥": "thermal", "🧫": "bio", "💧": "water"}
    process = appliance_map.get(appliance_emoji)
    
    if process == "water":
        await db.add_inventory(user_id, "water", 1)
        await callback.answer("💧 Вы набрали воды!")
        return
        
    selected_id = await db.get_selected_item(user_id)
    if not selected_id:
        await callback.answer("❌ Сначала выберите предмет в сетке!")
        return
        
    # Find recipe
    matched_recipe_id = None
    for r_id, r in RECIPES.items():
        if r.get('process') == process and any(ing[0] == selected_id for ing in r.get('from', [])):
            matched_recipe_id = r_id
            break
            
    # Handle combination recipes (process: None)
    if not matched_recipe_id:
        for r_id, r in RECIPES.items():
            if r.get('process') is None and any(ing[0] == selected_id for ing in r.get('from', [])):
                reqs = r.get('from', [])
                # If it's a 2-ingredient recipe, check if we have the other one
                if len(reqs) == 2:
                    other_ing = reqs[1][0] if reqs[0][0] == selected_id else reqs[0][0]
                    inventory = await db.get_inventory(user_id)
                    if inventory.get(other_ing, 0) > 0:
                        matched_recipe_id = r_id
                        # We'll need to remove the other ingredient too
                        await db.remove_inventory(user_id, other_ing, 1)
                        break
                elif len(reqs) == 1:
                    matched_recipe_id = r_id
                    break            
            # Allow combining two ingredients if 'process' is None (like dough from flour and water)
            if not matched_recipe_id and appliance_emoji == "🔪": # Use knife for combining
                for r_id, r in RECIPES.items():
                    if r.get('process') is None and any(ing[0] == selected_id for ing in r.get('from', [])):
                        reqs = r.get('from', [])
                        # If it's a 2-ingredient recipe, check if we have the other one
                        if len(reqs) == 2:
                            other_ing = reqs[1][0] if reqs[0][0] == selected_id else reqs[0][0]
                            inventory = await db.get_inventory(user_id)
                            if inventory.get(other_ing, 0) > 0:
                                matched_recipe_id = r_id
                                # We'll need to remove the other ingredient too
                                await db.remove_inventory(user_id, other_ing, 1)
                                break
                        elif len(reqs) == 1:
                            matched_recipe_id = r_id
                            break
    
    if not matched_recipe_id:
        await callback.answer("❌ Нет рецепта для этого действия!")
        return
        
    recipe = RECIPES[matched_recipe_id]
    await db.remove_inventory(user_id, selected_id, 1)
    await db.add_inventory(user_id, recipe['result'], 1)
    await db.set_selected_item(user_id, None)
    await callback.answer(f"✅ Приготовлено: {recipe['emoji']} {recipe['result']}!")

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
        actions.append(InlineKeyboardButton(text="🍰 Дать пирог", callback_data="give_donkey_apple_pie"))
    if inventory.get('apple', 0) > 0:
        actions.append(InlineKeyboardButton(text="🍎 Сменять яблоко на 💧 воду (x2)", callback_data="give_donkey_apple"))
        
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

    pass

move_handlers()

async def main():
    await db.init()
    print("🚀 GardenGram запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

