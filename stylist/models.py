import unicodedata
from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .personas import PersonaId

MAX_WEATHER_LOCATIONS = 10

MALE_DRESSING_PRIORITIES = frozenset({"舒适自在", "方便走动", "容易打理", "合身自然", "适合场合"})
FEMALE_DRESSING_PRIORITIES = frozenset({"轻松舒适", "显瘦遮肉", "职业干练", "温柔甜美", "活力阳光"})


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
    operation: Literal["update", "replace", "remove"] = "update"


TaskField = Literal["occasion", "scene", "style", "gender", "height_cm", "event_date", "city",
                    "weather_policy", "weather_description", "temp_min", "temp_max", "walk_minutes",
                    "indoor_temperature", "budget_yuan", "source", "no_heels", "no_bare_shoulders",
                    "excluded_materials", "excluded_colors", "excluded_categories", "preferences",
                    "owned_descriptions", "target_description", "itinerary"]


class MemorySave(Model):
    content: str = Field(min_length=1, max_length=240)
    category: Literal["穿衣习惯"] = "穿衣习惯"
    authorization: str = Field(min_length=1, max_length=160)


class Plan(Model):
    outfit_weather_adjustment: bool = False
    outfit_weather_evidence: str = Field(default="", max_length=6000)
    attachment_wardrobe_required: bool = False
    attachment_action_evidence: str = Field(default="", max_length=6000)
    unsupported_image_request: bool = False
    image_request_evidence: str = Field(default="", max_length=6000)
    new_clothes_intent: bool = False
    new_clothes_evidence: str = Field(default="", max_length=6000)
    avatar_intent: Literal["upload", "view", "tryon"] | None = None
    avatar_evidence: str = Field(default="", max_length=6000)
    avatar_declined: bool = False
    avatar_look_index: int | None = Field(default=None, ge=0, le=6)
    upload_intent: Literal["garment", "unspecified"] | None = None
    upload_evidence: str = Field(default="", max_length=6000)
    upload_declined: bool = False
    mode: Literal["consult", "recommend", "modify", "weekly"]
    technical_question: bool = False
    use_profile_gender: bool = True
    use_profile_preferences: bool = True
    conversation_only: bool = False
    weather_only: bool = False
    location_limit_exceeded: bool = False
    weather_scope: Literal["none", "day", "week", "next7"] = "none"
    use_inventory: bool = True
    new_task: bool = False
    changes: dict[TaskField, Change] = Field(default_factory=dict)
    replace_slots: list[Slot] = Field(default_factory=list, max_length=6)
    memory_save: MemorySave | None = None
    memory_changes: dict[Literal["style", "no_heels", "no_bare_shoulders", "excluded_materials", "excluded_colors", "excluded_categories", "preferences"], Change] = Field(default_factory=dict)
    requested_look_count: int | None = Field(default=None, ge=1, le=7)
    look_count_evidence: str = Field(default="", max_length=120)
    search_query: str = Field(default="", max_length=500)
    clarification: str | None = None


class ProductRef(Model):
    source: Literal["user", "system"]
    product_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")

    @property
    def key(self):
        return f"{self.source}:{self.product_id}"


class SavedOutfitRef(Model):
    source: Literal["user"] = "user"
    outfit_id: int = Field(gt=0, le=9007199254740991)


class Product(ProductRef):
    gender: Literal["男", "女", "男女同款"] | None = None
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

    @field_validator("gender", mode="before")
    @classmethod
    def normalize_gender(cls, value):
        if value is None or isinstance(value, bool):
            return None
        return {"1": "男", "男": "男", "男装": "男", "male": "男",
                "2": "女", "女": "女", "女装": "女", "female": "女",
                "3": "男女同款", "男女同款": "男女同款", "男女通用": "男女同款",
                "通用": "男女同款", "中性": "男女同款", "unisex": "男女同款"}.get(str(value).strip().lower())

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
    style_name: str = Field(default="", max_length=16, description="简短风格名，例如简约通勤、休闲运动，用于搭配标签")
    selected_keys: list[str] = Field(default_factory=list, max_length=10)
    pieces: list[str] = Field(default_factory=list, max_length=10)
    reference_pieces: list[str] = Field(default_factory=list, max_length=10,
                                      description="本方案未匹配到个人衣物的品类建议，仅文字参考，不进入组合图")
    unmatched_reason: str = Field(default="", max_length=300,
                                  description="候选存在却未选任何真实衣物时，说明本方案不适配的具体原因")
    why: list[str] = Field(min_length=1, max_length=5)
    how: list[str] = Field(min_length=1, max_length=6)
    notes: list[str] = Field(default_factory=list, max_length=6)


class Draft(Model):
    message: str = Field(min_length=1, max_length=4000)
    looks: list[LookDraft] = Field(default_factory=list, max_length=7)
    follow_ups: list[str] = Field(default_factory=list, max_length=3)


class Look(Model):
    title: str
    style_name: str = Field(default="", max_length=16)
    items: list[Product] = Field(default_factory=list)
    pieces: list[str] = Field(default_factory=list)
    reference_pieces: list[str] = Field(default_factory=list)
    wardrobe_complete: bool | None = None
    why: list[str] = Field(default_factory=list)
    how: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TryonReference(Model):
    conversation_id: str = Field(pattern=r"^sty_[a-f0-9]{32}$")
    version: int = Field(ge=1)
    look_index: int = Field(ge=0, le=6)


class Reply(Model):
    retrieval_diagnostics: dict = Field(default_factory=dict)
    new_clothes: bool = False
    new_clothes_auto_enabled: bool = False
    new_clothes_notice: str | None = None
    wardrobe_gap: bool = False
    city_selection_required: bool = False
    avatar_intent: Literal["upload", "view", "tryon"] | None = None
    tryon_context: TryonReference | None = None
    tryon_title: str | None = None
    upload_intent: Literal["garment", "unspecified"] | None = None
    attachment_wardrobe_required: bool = False
    upload_suggestion: bool = False
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
    product_entry: dict | None = None
    subject_product: ProductRef | None = None
    outfit_entry: dict | None = None
    subject_outfit: SavedOutfitRef | None = None


class SessionState(Model):
    task: Task = Field(default_factory=Task)
    mode: Literal["consult", "recommend", "modify", "weekly"] = "consult"
    looks: list[Look] = Field(default_factory=list)
    messages: list[dict[str, str]] = Field(default_factory=list)


class CompanionProfile(Model):
    user_name: str = Field(default="", max_length=24)
    user_gender: Literal["男", "女"] | None = None
    agent_name: str = Field(default="衣衣", min_length=1, max_length=24)
    assistant_persona: PersonaId = "male_calm_v1"
    color_scheme: Literal["companion", "system"] = "companion"

    mbti: Literal['INFJ', 'INFP', 'INTJ', 'INTP', 'ISFJ', 'ISFP', 'ISTJ', 'ISTP', 'ENFJ', 'ENFP', 'ENTJ', 'ENTP', 'ESFJ', 'ESFP', 'ESTJ', 'ESTP'] | None = None
    zodiac: Literal["白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座", "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座"] | None = None
    conversation_style: Literal["自然相处", "温柔鼓励", "直接坦诚", "轻松幽默"] = "自然相处"
    reply_detail: Literal["适中", "简洁重点", "细致解释"] = "适中"
    style_preferences: list[Literal["简约", "休闲", "通勤", "温柔", "复古", "运动", "街头", "优雅"]] = Field(default_factory=list, max_length=3)
    dressing_priorities: list[Literal["舒适自在", "方便走动", "容易打理", "合身自然", "适合场合", "已有衣物优先", "尝试新风格", "轻松舒适", "显瘦遮肉", "职业干练", "温柔甜美", "活力阳光"]] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_names(self):
        self.user_name, self.agent_name = self.user_name.strip(), self.agent_name.strip()
        if not self.agent_name:
            raise ValueError("请给助理留一个名字")
        if any(unicodedata.category(c).startswith("C") or c in "<>" for c in self.user_name + self.agent_name):
            raise ValueError("称呼请使用普通文字，不包含换行或特殊控制符")
        return self

    def dialogue_data(self, *, outfit_gender=None):
        data = self.model_dump(mode="json", exclude={"color_scheme"})
        # Keep stored choices intact while only activating the current user's set.
        def applicable(label):
            if label in FEMALE_DRESSING_PRIORITIES:
                return self.user_gender == "女" and outfit_gender != "男"
            if label in MALE_DRESSING_PRIORITIES:
                return self.user_gender == "男" and outfit_gender != "女"
            return True
        data["dressing_priorities"] = [label for label in self.dressing_priorities if applicable(label)]
        return data

    def dressing_priority_tags(self, *, outfit_gender=None):
        gender_type = {"男": "male", "女": "female"}.get(self.user_gender, "unspecified")
        return [{"label": label, "gender_type": gender_type,
                 "applicable_gender": ("female" if label in FEMALE_DRESSING_PRIORITIES else
                                       "male" if label in MALE_DRESSING_PRIORITIES else "unisex")}
                for label in self.dialogue_data(outfit_gender=outfit_gender)["dressing_priorities"]]



class CompanionProfileWrite(CompanionProfile):
    account_fields: list[Literal["user_name", "user_gender"]] = Field(default_factory=list, max_length=2)


class ChatRequest(Model):
    chat_image: str | None = Field(default=None, max_length=13981039, repr=False)

    @field_validator("chat_image")
    @classmethod
    def validate_chat_image(cls, value):
        if value is not None:
            from .media import image_digest
            image_digest(value)
        return value

    new_clothes: bool | None = None
    regenerate_outfit: bool = False
    regenerate_from_version: int | None = Field(default=None, ge=1)
    upload_action_id: str | None = Field(default=None, pattern=r"^med_[a-f0-9]{32}$")
    message: str = Field(default="", max_length=6000)
    conversation_id: str | None = Field(default=None, pattern=r"^sty_[a-f0-9]{32}$")
    expected_version: int = Field(default=0, ge=0)
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    weather_policy: Literal["auto", "ignored", "provided"] | None = Field(default=None, deprecated=True, description="兼容旧客户端；天气策略以本轮用户消息为准，此字段不再覆盖对话意图")
    source: Literal["wardrobe", "hybrid", "catalog"] | None = None
    location: "CitySelection | None" = None
    confirm_plan: bool = False
    assistant_persona: PersonaId | None = None
    selected_look_index: int | None = Field(default=None, ge=0, le=6)
    companion_profile: CompanionProfile | None = None
    pair_subject_product: bool = False
    subject_product: ProductRef | None = None
    subject_outfit: SavedOutfitRef | None = None

    @model_validator(mode="after")
    def validate_message(self):
        self.message = self.message.strip()
        if self.subject_product is not None and self.subject_outfit is not None:
            raise ValueError("单品和搭配入口不能同时提交")
        if not self.message and self.subject_product is None and self.subject_outfit is None:
            raise ValueError("请输入搭配需求")
        if self.pair_subject_product and (not self.conversation_id or self.expected_version < 1
                or self.subject_product or self.subject_outfit or self.upload_action_id
                or self.regenerate_outfit or self.chat_image or self.confirm_plan):
            raise ValueError("请从当前单品卡片发起搭配")
        if not self.message and (self.conversation_id or self.expected_version or self.chat_image
                                 or self.upload_action_id or self.regenerate_outfit):
            raise ValueError("入口回显请求不能带已有会话或执行参数")
        if self.regenerate_from_version is not None and (not self.regenerate_outfit or self.regenerate_from_version > self.expected_version):
            raise ValueError("重新生成的来源必须是已有搭配版本")
        if self.regenerate_outfit:
            if not self.conversation_id or self.expected_version < 1:
                raise ValueError("请先打开已有穿搭，再重新生成")
            if self.message != "重新生成穿搭" or self.upload_action_id or self.chat_image:
                raise ValueError("重新生成会沿用当前要求；新增条件请直接在对话里说明")
        if self.companion_profile:
            if self.assistant_persona is None:
                self.assistant_persona = self.companion_profile.assistant_persona
            elif self.assistant_persona != self.companion_profile.assistant_persona:
                raise ValueError("助理形象设置不一致，请重新选择")
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
