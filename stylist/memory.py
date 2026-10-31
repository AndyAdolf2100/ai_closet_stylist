"""User-controlled, account-scoped long-term notes; conservative preference extraction."""
import re
import unicodedata
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from .errors import StylistError
from .models import Change, Model, Task


class MemoryEntry(Model):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    category: Literal["穿衣习惯", "日常片段", "相处约定"] = "穿衣习惯"
    content: str = Field(min_length=1, max_length=240)

    @field_validator("content")
    @classmethod
    def clean_content(cls, value):
        value = value.strip()
        if not value or any(unicodedata.category(c) in {"Cc", "Cf"} and c != "\n" for c in value):
            raise ValueError("请写下 1—240 字的清晰文字。")
        return value


class MemoryBook(Model):
    revision: int = Field(default=0, ge=0)
    enabled: bool = True
    entries: list[MemoryEntry] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_entries(self):
        if len({x.id for x in self.entries}) != len(self.entries):
            raise ValueError("手记编号不能重复。")
        if len({x.content for x in self.entries}) != len(self.entries):
            raise ValueError("这件事已写在手记里，不必重复添加。")
        return self


def memory_intent(message):
    """A guard for unresolved explicit requests, never sufficient to save content."""
    plain = re.sub(r'[“「『\"].*?[”」』\"]', '', message)
    if re.search(r"(?:不[要用必]|别|无需).{0,3}(?:记住|记着|记下|保存)|不用.*记|不要.*存", plain):
        return False
    if re.search(r"(?:记住|记着|记得|保存)(?:了)?[吗么？?]|(?:举例|比如|假如|假设|如果|他说|她说|我妈说)", plain):
        return False
    return bool(re.search(r"一定要记住|以后(?:都)?记着|(?:请|帮我|替我|给我|要)记住|把.{0,16}记下来|记住[：:]|别忘了|保存到长记忆|这(?:个|件事)记住", plain))


def explicit_memory(message):
    """Resolve only complete, unambiguous save commands from verbatim user text."""
    text = message.strip()
    command = r"(?:(?:请|你|帮我|替我|给我|请帮我)?(?:一定要)?记住|以后(?:都)?记着|把这(?:个|件事)记下来|这(?:个|件事)(?:一定要)?记住|别忘了|保存到长记忆)"
    match = re.fullmatch(r"(?:请帮我记住|帮我记住|请记住|记住)[：:]\s*(.+)", text, re.S)
    content = match[1] if match else None
    if content is None and memory_intent(text):
        # A first-person statement followed by an entire authorization clause.
        suffix = re.fullmatch(r"(我[^\n。！？!?]+?)[，,。；;]\s*(?:这(?:个|件事)[，,]?\s*)?" + command + r"[。！!]*", text)
        prefix = re.fullmatch(command + r"[：:，,]?\s*(我[^\n。！？!?]+)[。！!]*", text)
        if suffix:
            content = suffix[1]
        elif prefix:
            content = prefix[1]
    if content is None:
        return None
    try:
        return MemoryEntry(id="pending", content=content).content
    except ValidationError:
        raise StylistError("invalid_memory", "请把要记住的内容控制在 1—240 字，也可以到设置里的「我们的手记」分成几页整理。", 422) from None


def preference_list_item(text):
    """Only unambiguous clothing/color nouns may extend a comma-separated list."""
    item = (r"(?:(?:浅|深|亮|暗)?(?:黑|白|灰|红|黄|绿|蓝|紫|粉|棕|米|橙|青|银|金)色"
            r"|短袖|长袖|衬衫|T恤|毛衣|开衫|卫衣|外套|风衣|西装|夹克|裙子|长裙|短裙"
            r"|长裤|短裤|牛仔裤|平底鞋|运动鞋|高跟鞋|靴子|围巾|帽子)")
    return bool(re.fullmatch(item + r"(?:[、和及与]" + item + r")*", text))


def automatic_preference(message):
    """Keep only explicit first-person preference clauses, never inferred traits."""
    if re.search(r"不要|别记|不保存|不用记|别存|今天|这次|暂时|如果|假如|假设|比如|举例|他说|她说|说过|[？?“”「」\"]", message):
        return None
    if re.search(r"(?:别|不要|不用|无需|不必).{0,6}(?:写|记|存|收录)|(?:什么|是否|是不是)|[吗么](?:[。！!\s]|$)", message):
        return None
    clauses = re.split(r"([，,。！!；;\n])", message)
    selected, own_subject = [], False
    for index in range(0, len(clauses), 2):
        delimiter = clauses[index - 1] if index else ""
        if delimiter in {"。", "！", "!", "\n"}:
            own_subject = False
        part = clauses[index].strip()
        if not part:
            continue
        preference = re.fullmatch(
            r"(?:但是|不过|而且|并且|但|也)?(?P<subject>我)?(?:一直|平时|通常|特别|很|最)?"
            r"(?:不喜欢|喜欢|讨厌|偏爱)(?P<object>[^，,。！？!?；;]{1,80})", part)
        if (preference and (preference['subject'] or own_subject)
                and not preference['object'].startswith('的')):
            selected.append(part)
            own_subject = True
        elif own_subject and delimiter in {"，", ","} and preference_list_item(part):
            # Keep the user's original nouns and punctuation; do not change polarity
            # or invent an extra first-person statement for an omitted subject.
            selected[-1] += delimiter + part
        else:
            # Another speaker, an unrelated action or a save-status report breaks
            # the local subject chain. Do not infer ownership across it.
            own_subject = False
    content = "；".join(selected)
    if not content or len(content) > 240:
        return None
    return MemoryEntry(id="pending", content=content, category=memory_category(content))


def memory_category(content):
    if re.search(r"穿|衣|鞋|裙|裤|衬衫|短袖|长袖|搭配|面料|羊毛", content):
        return "穿衣习惯"
    if re.search(r"回复|称呼|说话|建议|听我|安慰|叫我", content):
        return "相处约定"
    return "日常片段"


def apply_memory(task, plan, entries):
    """Ephemeral defaults only: never contaminate the saved conversation task."""
    if not plan.use_profile_preferences or plan.conversation_only or plan.weather_only or task.target_description:
        return task.model_copy(deep=True)
    contents = {entry["content"] for entry in entries if entry["category"] == "穿衣习惯"}
    data, defaults = task.model_dump(), Task().model_dump()
    for field, raw in plan.memory_changes.items():
        change = Change.model_validate(raw)
        spans = [change.evidence] if isinstance(change.evidence, str) else change.evidence
        # Current/session requirements win, and only verbatim saved notes are evidence.
        if (field in plan.changes or data[field] != defaults[field] or change.operation != "update"
                or not spans or any(not s or not any(s in note for note in contents) for s in spans)):
            continue
        data[field] = change.value
    try:
        return Task.model_validate(data)
    except ValidationError:
        raise StylistError("invalid_memory_requirement", "这次没能准确理解手记里的穿衣习惯，请调整描述后重试。", 422) from None


def verified_memory_save(action, message, history):
    """Require current explicit authorization and verbatim user-authored content."""
    if action is None:
        return None
    authorization = action.authorization
    if (authorization not in message or not re.search(r"记住|记着|记下来|记下|记好|记牢|别忘|不要忘|存[到进入]|保存|收[到进]", authorization)
            or re.search(r"(?:不[要用必]|别|无需).{0,3}(?:记住|记着|记下|保存)|不用.*记|不要.*存", message)
            or re.search(r"(?:记住|记着|记得|保存)(?:了)?[吗么？?]", message)):
        return None
    content = action.content.strip()
    sources = [message] + [row.get("content", "") for row in history if row.get("role") == "user"]
    if not content or not any(content in source for source in sources):
        return None
    return MemoryEntry(id="pending", category=action.category, content=content)
