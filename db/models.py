from enum import Enum
from typing import Dict, List, Optional

class GameMode(Enum):
    GARDEN = "garden"
    KITCHEN = "kitchen"
    DONKEY = "donkey"

GRID_SIZE = 4

INGREDIENTS = {
    'wheat': {'emoji': '🌾', 'rarity': 1, 'collectable': True},
    'apple': {'emoji': '🍎', 'rarity': 2, 'collectable': True},
    'sugar': {'emoji': '🍬', 'rarity': 3, 'collectable': True},
    'salt': {'emoji': '🧂', 'rarity': 4, 'collectable': True},
}

PROCESSES = {
    'physical': '🔪 Physical processing',
    'thermal': '🔥 Thermal processing',
    'bio': '🧫 Bio processing'
}

RECIPES = {
    'flour': {'from': [('wheat', 1)], 'process': 'physical', 'emoji': '🌾', 'result': 'flour'},
    'dough': {'from': [('flour', 1), ('water', 1)], 'process': None, 'emoji': '🍞', 'result': 'dough'},
    'apple_slices': {'from': [('apple', 1)], 'process': 'physical', 'emoji': '🍎', 'result': 'apple_slices'},
    'apple_pie_raw': {'from': [('dough', 1), ('apple_slices', 1)], 'process': None, 'emoji': '🥧', 'result': 'apple_pie_raw'},
    'apple_pie': {'from': [('apple_pie_raw', 1)], 'process': 'thermal', 'emoji': '🍰', 'result': 'apple_pie'},
}

TUTORIAL_STEPS = [
    "Combine 🌾 wheat + 🔪 physical → flour",
    "Combine flour + 💧 water → dough",
    "Combine 🍎 apple + 🔪 physical → slices",
    "Combine dough + slices → raw pie",
    "Combine raw pie + 🔥 thermal → 🍰 pie"
]

