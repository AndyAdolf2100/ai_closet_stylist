from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .personas import PersonaId

MAX_WEATHER_LOCATIONS = 10


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Slot(StrEnum):
    TOP = "top"
    BOTTOM = "bottom"
    DRESS = "dress"
    OUTER = "outer"
    SHOES = "shoes"
    ACCESSORY = "accessory"


class TripStop(Model):
    city_name: str = Field(min_length=1, max_length=80, pattern=r"^[^/→、|;；]+$")
    province_name: str = Field(default="", max_length=80)
    event_date: date | None = None


class Task(Model):
    occasion: str = "日常"
    scene: str = ""
    style: str = ""
    gender: Literal["男", "女"] | None = None
    height_cm: float | None = Field(default=None, ge=30, le=280)
    event_date: date | None = None
    city: str | None = None
    itinerary: list[TripStop] = Field(default_factory=list, max_length=MAX_WEATHER_LOCATIONS)
    weather_policy: Literal["auto", "ignored", "provided"] = "auto"
    weather_description: str = ""
    temp_min: float | None = None
    temp_max: float | None = None
    walk_minutes: int | None = Field(default=None, ge=0, le=1440)
    indoor_temperature: float | None = None
    budget_yuan: float | None = Field(default=None, ge=0)
    source: Literal["wardrobe", "hybrid", "catalog"] = "wardrobe"
    no_heels: bool = False
    no_bare_shoulders: bool = False
    excluded_materials: list[str] = Field(default_factory=list, max_length=20)
    excluded_colors: list[str] = Field(default_factory=list, max_length=20)
    excluded_categories: list[str] = Field(default_factory=list, max_length=20)
    preferences: list[str] = Field(default_factory=list, max_length=30)
    owned_descriptions: list[str] = Field(default_factory=list, max_length=30)
    target_description: str | None = None


class Change(Model):
    value: Any
    evidence: str | list[str]


TaskField = Literal["occasion", "scene", "style", "gender", "height_cm", "event_date", "city",
                    "weather_policy", "weather_description", "temp_min", "temp_max", "walk_minutes",
                    "indoor_temperature", "budget_yuan", "source", "no_heels", "no_bare_shoulders",
                    "excluded_materials", "excluded_colors", "excluded_categories", "preferences",
                    "owned_descriptions", "target_description", "itinerary"]


class Plan(Model):
    mode: Literal["consult", "recommend", "modify", "weekly"]
    conversation_only: bool = False
    weather_only: bool = False
    location_limit_exceeded: bool = False
    weather_scope: Literal["none", "day", "week", "next7"] = "none"
    use_inventory: bool = True
    new_task: bool = False
    changes: dict[TaskField, Change] = Field(default_factory=dict)
    replace_slots: list[Slot] = Field(default_factory=list, max_length=6)
    search_query: str = Field(default="", max_length=500)
    clarification: str | None = None


class ProductRef(Model):
    source: Literal["user", "system"]
    product_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")

    @property
    def key(self):
        return f"{self.source}:{self.product_id}"


class Product(ProductRef):
    title: str = ""
    class_name: str = ""
    secondary_class_name: str = ""
    color: str = ""
    material: str = ""
    description: str = ""
    styles: list[str] = Field(default_factory=list)
    occasions: list[str] = Field(default_factory=list)
    original_image: str = ""
    cutout_image: str = ""
    # Unknown is distinct from zero. Old catalog prices have no verified unit here.
    incremental_price_yuan: float | None = None
    slot: Slot
    warnings: list[str] = Field(default_factory=list)

    @property
    def display_name(self):
        category = self.secondary_class_name or self.class_name
        return f"{self.color}{category}" if category else (self.title[:45] or "未命名单品")

    @property
    def evidence_text(self):
        return " ".join([self.title, self.class_name, self.secondary_class_name,
                         self.color, self.material, self.description])


class LookDraft(Model):
    title: str = Field(min_length=1, max_length=100)
    selected_keys: list[str] = Field(default_factory=list, max_length=10)
    pieces: list[str] = Field(default_factory=list, max_length=10)
    why: list[str] = Field(min_length=1, max_length=5)
    how: list[str] = Field(min_length=1, max_length=6)
    notes: list[str] = Field(default_factory=list, max_length=6)


class Draft(Model):
    message: str = Field(min_length=1, max_length=4000)
    looks: list[LookDraft] = Field(default_factory=list, max_length=7)
    follow_ups: list[str] = Field(default_factory=list, max_length=3)


class Look(Model):
    title: str
    items: list[Product] = Field(default_factory=list)
    pieces: list[str] = Field(default_factory=list)
    why: list[str] = Field(default_factory=list)
    how: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Reply(Model):
    conversation_only: bool = False
    weather_only: bool = False
    conversation_id: str
    version: int
    mode: Literal["consult", "recommend", "modify", "weekly"]
    delivery: Literal["advice", "outfit", "concept", "clarification"]
    message: str
    task: Task
    weather: dict | None = None
    looks: list[Look] = Field(default_factory=list)
    retained_items: list[Product] = Field(default_factory=list, max_length=10)
    warnings: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    pending_confirmation: bool = False
    request_id: str | None = None


class SessionState(Model):
    task: Task = Field(default_factory=Task)
    mode: Literal["consult", "recommend", "modify", "weekly"] = "consult"
    looks: list[Look] = Field(default_factory=list)
    messages: list[dict[str, str]] = Field(default_factory=list)


class ChatRequest(Model):
    message: str = Field(min_length=1, max_length=6000)
    conversation_id: str | None = Field(default=None, pattern=r"^sty_[a-f0-9]{32}$")
    expected_version: int = Field(default=0, ge=0)
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    weather_policy: Literal["auto", "ignored", "provided"] | None = None
    source: Literal["wardrobe", "hybrid", "catalog"] | None = None
    location: "CitySelection | None" = None
    confirm_plan: bool = False
    assistant_persona: PersonaId | None = None

    @model_validator(mode="after")
    def validate_message(self):
        self.message = self.message.strip()
        if not self.message:
            raise ValueError("请输入搭配需求")
        return self


class CitySelection(Model):
    city_name: str = Field(min_length=1, max_length=80)
    province_name: str = Field(default="", max_length=80)


class LocateRequest(Model):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_system: Literal["wgs84", "gcj02", "bd09"] = "wgs84"


class ForecastRequest(Model):
    location: CitySelection
    scope: Literal["day", "week", "next7"] = "day"
    event_date: date | None = None


ChatRequest.model_rebuild()
