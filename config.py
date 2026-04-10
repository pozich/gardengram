import json
import os

class FoodConfig:
    def __init__(self, file_path="data/models.json"):
        self.path = file_path
        self.data = {}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            print(f"Ошибка: Файл {self.path} не найден!")

    def get_item(self, item_type: str):
        for category in self.data.values():
            if item_type in category:
                return category[item_type]
        return None

    def list_ingredients(self):
        return list(self.data.get("ingredients", {}).keys())

FOOD_STATUS_MULT = FoodConfig()
