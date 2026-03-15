import aiosqlite
import json
from typing import Dict, List, Optional

from .models import INGREDIENTS, RECIPES
from .queries import init_db

class GardenGramDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def init(self):
        await init_db(self.db_path)
    
    async def register_player(self, user_id: int, nick: str):
        import json
        async with aiosqlite.connect(self.db_path) as db:
            default_inventory = json.dumps({'sugar': 1, 'water': 1})
            await db.execute(
                'INSERT OR REPLACE INTO players (user_id, nick, state, inventory) VALUES (?, ?, ?, ?)',
                (user_id, nick, 'tutorial', default_inventory)
            )
            await db.commit()
    
    async def is_registered(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT 1 FROM players WHERE user_id = ?', (user_id,)) as cur:
                return await cur.fetchone() is not None
    
    async def get_player(self, user_id: int) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            # Add columns if they don't exist yet (migration)
            try:
                await db.execute('ALTER TABLE players ADD COLUMN cursor_pos INTEGER DEFAULT 0')
                await db.commit()
            except aiosqlite.OperationalError:
                pass 
                
            try:
                await db.execute('ALTER TABLE players ADD COLUMN last_spawn_time REAL DEFAULT 0')
                await db.commit()
            except aiosqlite.OperationalError:
                pass

            try:
                await db.execute('ALTER TABLE players ADD COLUMN selected_item TEXT DEFAULT NULL')
                await db.commit()
            except aiosqlite.OperationalError:
                pass
                
            try:
                await db.execute('ALTER TABLE players ADD COLUMN last_ferment_check REAL DEFAULT 0')
                await db.commit()
            except aiosqlite.OperationalError:
                pass
                
            async with db.execute(
                'SELECT nick, state, grid, inventory, tutorial_step, money, cursor_pos, last_spawn_time, selected_item, last_ferment_check FROM players WHERE user_id = ?',
                (user_id,)
            ) as cur:
                row = await cur.fetchone()
                if row:
                    return {
                        'nick': row[0],
                        'state': row[1],
                        'grid': json.loads(row[2]) if row[2] else [],
                        'inventory': json.loads(row[3]) if row[3] else {},
                        'tutorial_step': row[4],
                        'money': row[5],
                        'cursor_pos': row[6] if len(row) > 6 and row[6] is not None else 0,
                        'last_spawn_time': row[7] if len(row) > 7 and row[7] is not None else 0.0,
                        'selected_item': row[8] if len(row) > 8 else None,
                        'last_ferment_check': row[9] if len(row) > 9 and row[9] is not None else 0.0
                    }
                return None
    
    async def set_player_grid(self, user_id: int, grid: List[str]):
        grid_json = json.dumps(grid)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE players SET grid = ? WHERE user_id = ?',
                (grid_json, user_id)
            )
            await db.commit()
    
    async def get_player_grid(self, user_id: int) -> List[str]:
        player = await self.get_player(user_id)
        return player['grid'] if player else []
    
    async def add_inventory(self, user_id: int, item: str, quantity: int = 1):
        async with aiosqlite.connect(self.db_path) as db:
            player = await self.get_player(user_id)
            inventory = player['inventory'] if player else {}
            inventory[item] = inventory.get(item, 0) + quantity
            
            inventory_json = json.dumps(inventory)
            await db.execute(
                'UPDATE players SET inventory = ? WHERE user_id = ?',
                (inventory_json, user_id)
            )
            await db.commit()
    
    async def get_inventory(self, user_id: int) -> Dict[str, int]:
        await self.process_fermentation(user_id)
        player = await self.get_player(user_id)
        return player['inventory'] if player else {}
        
    async def process_fermentation(self, user_id: int):
        import time
        player = await self.get_player(user_id)
        if not player: return
        
        last_check = player.get('last_ferment_check', 0)
        current_time = time.time()
        
        if last_check == 0:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('UPDATE players SET last_ferment_check = ? WHERE user_id = ?', (current_time, user_id))
                await db.commit()
            return

        elapsed = current_time - last_check
        inventory = player['inventory']
        changed = False
        
        # Check each item if it can ferment
        new_inventory = inventory.copy()
        for r_id, r in RECIPES.items():
            if r.get('process') == 'bio' and 'ferment_time' in r:
                reqs = r.get('from', [])
                if len(reqs) == 1:
                    item_id, qty = reqs[0]
                    if inventory.get(item_id, 0) >= qty:
                        # How many times can it ferment since last check?
                        # This is a bit simplified: we check if enough total time has passed.
                        # Real "background" fermentation should probably track per-item start time,
                        # but for now we'll do global check.
                        if elapsed >= r['ferment_time']:
                            can_ferment_count = inventory[item_id] // qty
                            new_inventory[item_id] -= can_ferment_count * qty
                            if new_inventory[item_id] == 0: del new_inventory[item_id]
                            new_inventory[r['result']] = new_inventory.get(r['result'], 0) + can_ferment_count
                            changed = True
        
        if changed:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'UPDATE players SET inventory = ?, last_ferment_check = ? WHERE user_id = ?',
                    (json.dumps(new_inventory), current_time, user_id)
                )
                await db.commit()
        elif elapsed > 60: # Update anyway to avoid huge elapsed jumps
             async with aiosqlite.connect(self.db_path) as db:
                await db.execute('UPDATE players SET last_ferment_check = ? WHERE user_id = ?', (current_time, user_id))
                await db.commit()
    
    async def remove_inventory(self, user_id: int, item: str, quantity: int = 1):
        async with aiosqlite.connect(self.db_path) as db:
            player = await self.get_player(user_id)
            inventory = player['inventory'] if player else {}
            
            if item in inventory and inventory[item] >= quantity:
                inventory[item] -= quantity
                if inventory[item] == 0:
                    del inventory[item]
                
                inventory_json = json.dumps(inventory)
                await db.execute(
                    'UPDATE players SET inventory = ? WHERE user_id = ?',
                    (inventory_json, user_id)
                )
                await db.commit()

    async def get_cursor_pos(self, user_id: int) -> int:
        player = await self.get_player(user_id)
        return player['cursor_pos'] if player else 0

    async def set_cursor_pos(self, user_id: int, pos: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE players SET cursor_pos = ? WHERE user_id = ?',
                (pos, user_id)
            )
            await db.commit()
            
    async def get_last_spawn_time(self, user_id: int) -> float:
        player = await self.get_player(user_id)
        return player['last_spawn_time'] if player else 0.0

    async def set_last_spawn_time(self, user_id: int, time_val: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE players SET last_spawn_time = ? WHERE user_id = ?',
                (time_val, user_id)
            )
            await db.commit()

    async def get_selected_item(self, user_id: int) -> Optional[str]:
        player = await self.get_player(user_id)
        return player['selected_item'] if player else None

    async def set_selected_item(self, user_id: int, item: Optional[str]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE players SET selected_item = ? WHERE user_id = ?',
                (item, user_id)
            )
            await db.commit()

