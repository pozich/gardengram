# database/models.py
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, String, Float, 
    ForeignKey, Enum as SQLEnum, DateTime, Boolean, Table
)
from sqlalchemy.orm import DeclarativeBase, relationship, backref
from datetime import datetime

class Base(DeclarativeBase):
    pass

class FoodCategory(PyEnum):
    PLANT = "Растительная"
    ANIMAL = "Животная"
    SEAFOOD = "Морепродукты"
    WASTE = "Продукты жизнедеятельности"

class FoodStatus(PyEnum):
    RAW = "Свежий"
    DIRTY = "Грязный"
    FRIED = "Жареный"
    BOILED = "Вареный"
    FROZEN = "Замороженный"
    DRIED = "Сушеный"
    ROTTEN = "Гниль"

item_history = Table(
    "item_history",
    Base.metadata,
    Column("parent_id", Integer, ForeignKey("foods.id"), primary_key=True),
    Column("child_id", Integer, ForeignKey("foods.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    inventory = relationship("Food", backref="owner")

class Food(Base):
    __tablename__ = "foods"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    item_type = Column(String, nullable=False) 
    
    display_name = Column(String, nullable=False)
    
    category = Column(SQLEnum(FoodCategory), nullable=True)
    
    proteins = Column(Float, default=0.0)
    fats = Column(Float, default=0.0)
    carbs = Column(Float, default=0.0)
    satiety = Column(Float, default=0.0) 
    poison_chance = Column(Float, default=0.0) 
    expiration_time = Column(Integer, nullable=True) 
    created_at = Column(DateTime, default=datetime.utcnow)
    
    status = Column(SQLEnum(FoodStatus), default=FoodStatus.RAW)    
    tier = Column(Integer, default=0)

    parents = relationship(
        "Food",
        secondary=item_history,
        primaryjoin=id == item_history.c.child_id,
        secondaryjoin=id == item_history.c.parent_id,
        backref="children"
    )

    def get_full_history_name(self):
        prefix = "(грязный) " if self.status == FoodStatus.DIRTY else ""
        
        if not self.parents:
            return f"{prefix}{self.display_name}"
        
        parent_names = " + ".join([p.get_full_history_name() for p in self.parents])
        return f"{self.display_name} из [{parent_names}]"

class Building(Base):
    __tablename__ = "buildings" 
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String(16)) 
    
    quality = Column(Float, default=1.00) # Влияет на шанс уменьшения poison_chance
    
    __mapper_args__ = {
        "polymorphic_on": type,
        "polymorphic_identity": "building",
    }

class Garden(Building):
    __tablename__ = "gardens"    
    id = Column(Integer, ForeignKey("buildings.id"), primary_key=True) 
    __mapper_args__ = {"polymorphic_identity": "garden"}

class Kitchen(Building): 
    __tablename__ = "kitchens"
    id = Column(Integer, ForeignKey("buildings.id"), primary_key=True)
    __mapper_args__ = {"polymorphic_identity": "kitchen"}

class Donkey(Building): 
    __tablename__ = "donkeys"
    id = Column(Integer, ForeignKey("buildings.id"), primary_key=True)
    __mapper_args__ = {"polymorphic_identity": "donkeys"}

class CookingProcess(Base):
    __tablename__ = "cooking_processes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    ingredient_ids = Column(String) 
    
    result_type = Column(String) # Какой тип из JSON получится
    finish_time = Column(DateTime)

