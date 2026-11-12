"""User-controlled, account-scoped long-term notes; conservative preference extraction."""
import json
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


class ClothingMemoryEntry(MemoryEntry):
    category: Literal["穿衣习惯"] = "穿衣习惯"


class MemoryBookWrite(MemoryBook):
    entries: list[ClothingMemoryEntry] = Field(default_factory=list, max_length=30)


_CLOTHING = re.compile(
    r"穿|衣|衫|裤|裙|鞋|靴|袜|外套|风衣|西装|毛衣|针织|卫衣|T恤|短袖|长袖|"
    r"围巾|帽子|手套|包包|手提包|背包|首饰|项链|耳环|耳饰|配饰|面料|羊毛|棉质|棉麻|真丝|"
    r"材质|单品|纯色|条纹|基础款|潮流款|款式|尺码|版型|宽松|修身|高腰|低腰|领口|袖口|腰线|腰头|裤脚|搭配|配色|极简|休闲|优雅|复古|街头|运动风|通勤|平时走路|聚酯|涤纶|亚麻|皮革|羊绒|"
    r"(?:黑|白|灰|红|黄|绿|蓝|紫|粉|棕|米|橙|青|银|金)色")
_OUTSIDE = re.compile(
    r"喝|吃|乌龙|茶|咖啡|饮料|饭|电影|音乐|游戏|宠物|杯子|汽车|手机|电脑|"
    r"昵称|称呼|叫我|叫你|宝贝|亲爱的|说话|回复|回答|安慰|听我|语气|陪我|"
    r"起床|闹钟|合照|去年|昨天|昨晚|那天|上次|今天|明天|这次|今晚|"
    r"扣费|密钥|接口|系统指令|忽略.{0,6}规则")


# These descriptions need an established clothing context, rather than making
# words such as "舒服" sufficient to classify unrelated notes as clothing.
_CLOTHING_DESCRIPTION = re.compile(
    r"松弛|清爽|利落|大方|得体|合身|舒适|紧绷|拖沓|低饱和|百搭|耐看|"
    r"花哨|夸张|简约|简洁|基础款|小众|好打理|透气|耐穿|难伺候|繁杂|多余装饰")


def clothing_content(content):
    """Keep clothing clauses only; do not reinterpret diary or interaction rules as outfits."""
    text = content.strip()
    chunks = re.split(r"([，,。！!；;\n])", text)
    selected, all_relevant, clothing_context = [], True, False
    for i in range(0, len(chunks), 2):
        part = chunks[i].strip()
        if not part:
            continue
        excluded = bool(_OUTSIDE.search(part) or re.search(
            r"我(?:朋友|妈妈|同事|家人)|(?:他|她|朋友|同事)(?:喜欢|不喜欢|偏爱|穿)", part))
        direct = bool(_CLOTHING.search(part))
        relevant = not excluded and (direct or clothing_context and bool(_CLOTHING_DESCRIPTION.search(part)))
        clothing_context = bool(relevant)
        if relevant:
            delimiter = chunks[i - 1] if i else ""
            if selected and delimiter in {"，", ","} and preference_list_item(part):
                selected[-1] += delimiter + part
            else:
                selected.append(part)
        else:
            all_relevant = False
    return text if all_relevant and selected else "；".join(selected)


def decode_memory_book(raw):
    """Exclude obsolete notes without deleting their original stored text on a normal write."""
    document = json.loads(raw) if raw else {}
    retired = document.pop("_retired_entries", [])
    original = MemoryBook.model_validate(document)
    entries = []
    for entry in original.entries:
        if entry.category == "穿衣习惯":
            entries.append(entry)
            continue
        content = clothing_content(entry.content)
        if content != entry.content or entry.category != "穿衣习惯":
            if entry.model_dump() not in retired:
                retired.append(entry.model_dump())
        if content:
            entries.append(entry.model_copy(update={"content": content, "category": "穿衣习惯"}))
    return original.model_copy(update={"entries": entries}), retired


def encode_memory_book(book, retired):
    document = book.model_dump(mode="json")
    if retired:
        document["_retired_entries"] = retired
    return json.dumps(document, ensure_ascii=False)


def validate_clothing_book(book):
    if any(entry.category != "穿衣习惯" or not clothing_content(entry.content)
           or clothing_content(entry.content) != entry.content for entry in book.entries):
        raise StylistError("memory_scope", "手记只记录穿搭相关的喜好、禁忌和穿衣信息；日常片段与相处约定不用写在这里。", 422)


def memory_intent(message):
    """A guard for unresolved explicit requests, never sufficient to save content."""
    plain = re.sub(r'[“「『\"].*?[”」』\"]', '', message)
    if re.search(r"(?:不[要用必]|别|无需).{0,3}(?:记住|记着|记下|保存)|不用.*记|不要.*存", plain):
        return False
    if re.search(r"(?:记住|记着|记得|保存)(?:了)?[吗么？?]|(?:举例|比如|假如|假设|如果|他说|她说|我妈说)", plain):
        return False
    if re.search(r"(?:记住|记着|保存).{0,60}(?:了吗|了么|什么|是否|是不是|[?？])", plain):
        return False
    return bool(re.search(r"一定要记住|以后(?:都)?记着|(?:请|帮我|替我|给我|要)记住|把.{0,16}记下来|记住[我：:]|别忘了|保存到长记忆|这(?:个|件事)记住", plain))


def explicit_memory_content(message):
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


def explicit_memory(message):
    content = explicit_memory_content(message)
    return clothing_content(content) or None if content is not None else None


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
    # A complete first-person long-term clothing instruction may precede the
    # preference verb. Keep the original sentence, without inferring an object.
    if re.fullmatch(r"以后(?:给我)?(?:搭衣服|搭配|穿搭)(?:尽量)?别选[^，。！？!?]{1,30}[，,]我(?:真|真的|很)?不喜欢[。！!]?", message):
        content = clothing_content(message)
        if content:
            return MemoryEntry(id="pending", content=content, category="穿衣习惯")
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
            if clothing_content(part):
                selected.append(part)
                own_subject = True
            else:
                own_subject = False
        elif own_subject and selected and delimiter in {"，", ","} and preference_list_item(part):
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
    return "穿衣习惯"


def usable_memory_entry(entry):
    """Notebook content is user data, without a second keyword gate."""
    return entry["category"] == "穿衣习惯"


def apply_memory(task, plan, entries):
    """Ephemeral defaults only: never contaminate the saved conversation task."""
    if not plan.use_profile_preferences or plan.conversation_only or plan.weather_only or task.target_description:
        return task.model_copy(deep=True)
    contents = {entry["content"] for entry in entries if usable_memory_entry(entry)}
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
    content = clothing_content(content)
    return MemoryEntry(id="pending", category="穿衣习惯", content=content) if content else None


def strip_save_claims(text):
    """The transaction owns save receipts; model prose must not contradict its result."""
    claims = r"手记|保存|收进|记入|写入|记录|记住|记下|记着|记好"
    paragraphs = []
    for paragraph in text.splitlines():
        sentences = re.split(r"(?<=[。！？!?])", paragraph)
        kept = []
        for sentence in sentences:
            if not re.search(claims, sentence):
                kept.append(sentence)
                continue
            # Remove the receipt clause without discarding the user's clothing
            # information in the same sentence ("记住啦，日常走路多……").
            cleaned = re.sub(r"^(?:我(?:已经|也)?)?(?:记住|记下|记着)(?:了|啦|着)?[：:，, ]+", "", sentence.strip())
            cleaned = re.sub(r"我(?:已经|也)?(?:记住|记下)(?:了|啦)?(?=(?:你|您)?(?:不穿|不喜欢|喜欢|平时|每天))", "", cleaned)
            clauses = re.split(r"[，,：:]", cleaned)
            cleaned = "，".join(clause.strip() for clause in clauses if not re.search(claims, clause))
            cleaned = cleaned.strip(" ，,：:")
            if re.search(r"\w", cleaned):
                kept.append(cleaned if cleaned.endswith(("。", "！", "？", "!", "?")) else cleaned + "。")
        if "".join(kept).strip():
            paragraphs.append("".join(kept).strip())
    return "\n\n".join(paragraphs)


def preference_statement(message):
    """Sharing a preference is not authorization to select outfits or change the current task."""
    if re.search(r"怎么搭|如何搭|怎样搭|会怎么搭|帮.{0,4}(?:搭|挑|选)|搭一|搭两|搭配一下|"
                 r"换|改成|调整|保留|这套|这一套|这件|那件|试试|想穿|穿什么|怎么穿|"
                 r"推荐|选款|给(?:我)?[一两二三四五六七1-7]套|从.{0,8}衣[橱柜]|用.{0,8}衣[橱柜]|穿搭方案|"
                 r"(?:这次|今天).{0,6}(?:正式|休闲|优雅|宽松).{0,3}一点", message):
        return False
    return bool(re.search(r"喜欢|讨厌|偏爱|我不穿|我不爱穿|平时走路|没有保存|没保存", message))


def address_boundary(message):
    return bool(re.search(r"(?:别|不要|不许|不用).{0,6}(?:叫我|称呼我|叫.{0,4}宝贝)|别.{0,6}亲昵称呼", message))


def boundary_only(message):
    # A boundary can accompany a real request. Do not swallow that request.
    return address_boundary(message) and not re.search(
        r"怎么搭|怎么穿|搭一|搭两|搭配|推荐|选款|给.{0,4}套|衣橱|衣柜|天气|上传|试穿|记住|保存", message)


def referred_memory(message, history):
    if not memory_intent(message) or not re.search(r"刚才|这个|这件|那句|上面|前面", message):
        return None
    prior = next((row["content"] for row in reversed(history) if row.get("role") == "user"), "")
    if len(prior) <= 240 and preference_statement(prior) and clothing_content(prior):
        return prior
    return None
