# database/food.py
from sqlalchemy.orm import Session
from database.models import Food, FoodStatus, FoodCategory
from datetime import datetime, timedelta
from config import FOOD_STATUS_MULT

def cook_food(db: Session, user_id: int, ingredient_ids: list[int], result_type_data: dict):
    ingredients = db.query(Food).filter(
        Food.id.in_(ingredient_ids), 
        Food.user_id == user_id
    ).all()

    if not ingredients:
        return None

    res_proteins = 0
    res_fats = 0
    res_carbs = 0
    res_satiety = 0
    res_poison = 0

    for ing in ingredients:
        mult = FOOD_STATUS_MULT.get(ing.status.name, FOOD_STATUS_MULT["RAW"])
        
        res_proteins += ing.proteins
        res_fats += ing.fats
        res_carbs += ing.carbs
        
        res_satiety += ing.satiety * mult["satiety"]
        res_poison += ing.poison_chance * mult["poison"]

    new_status = FoodStatus.BOILED 
    
    final_mult = FOOD_STATUS_MULT[new_status.name]
    
    combined_item = Food(
        user_id=user_id,
        item_type=result_type_data["item_type"],
        display_name=result_type_data["display_name"],
        category=None,
        proteins=res_proteins,
        fats=res_fats,
        carbs=res_carbs,
        satiety=res_satiety * final_mult["satiety"],
        poison_chance=res_poison * final_mult["poison"],
        status=new_status,
        parents=ingredients, 
        tier=max([i.tier for i in ingredients]) + 1
    )

    for ing in ingredients:
        ing.user_id = None

    db.add(combined_item)
    db.commit()
    db.refresh(combined_item)
    return combined_item
