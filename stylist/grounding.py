"""Conservative checks for common garment claims unsupported by the current product schema."""
import re

from .models import Draft

PREFIX = "属性依据不足："
_PATTERNS = {
    "fit": re.compile(r"(?:不会|不易|不容易|不太会|不)(?:再|有|太|会)?(?:勒|贴身|贴肚|紧绷)|(?:没有|无|不会有)(?:任何|明显|一点)?(?:压迫感|压迫|束缚感)|(?:坐下|坐着|坐久|久坐|走路|活动|抬手|走动|吃饭).{0,8}(?:都|更|比较|也|很|会)?(?:自在|轻松|舒服|舒适|自如|放松)|(?:对腰腹|对肚子|对腹部).{0,16}(?:更友好|更轻松|更自在|更舒适|更舒服|无负担)|(?:腰腹|肚子|腹部|腰部).{0,16}(?:不|无|更|充足|足够|容易|友好|自在|舒服|舒适|宽松|空间|松量|余量|压迫|受压)|(?:不|不会)(?:压|勒)(?:肚|腹|腰)"),
    "design": re.compile(r"宽松|松紧腰|弹性腰头|弹力腰|腰头有弹性|有弹性|富有弹性|松紧设计|有伸缩余量"),
    "weather": re.compile(r"防水|防雨|防滑|挡雨|挡风|(?:更?不容易|不易|不会|不太会).{0,12}(?:湿|雨|水)|(?:防止|减少|少让|降低).{0,24}(?:湿|淋|雨|水)|(?:雨|雨水|雨点).{0,16}(?:面积|机会|概率).{0,8}(?:少|小|降低)"),
}
_UNKNOWN_BEFORE = re.compile(r"(?:不能|无法|没法|不敢|尚不能|暂不能|不要|不应|别).{0,12}(?:保证|确认|确定|判断|断定|证明|说明|当作|看作|推断|推导)|不一定|未必|不代表|不等于|别指望|不能指望|不要指望|尚不清楚")
_UNKNOWN_AFTER = re.compile(r"^(?:(?:、|和|及|与|或|/)?(?:防水|防雨|防滑|挡雨|挡风)){0,3}(?:性|性能|功能|效果|能力|等级|程度|信息|数据|资料|参数)?(?:还|尚|暂|目前)?(?:未|没有|没|无法|不能|不明|未知|不确定|缺少|需核对|要核对|待确认|需要确认)")
_CRITERION = re.compile(r"^(?:请|可以|尽量|优先|建议|先)?(?:选择|挑选|找一|选一|选用|优先选|优先找|建议选|建议找|裤子选|鞋子选|上衣选|选择时)|^(?:如果|若|要是).{0,28}(?:试穿|试走|实际穿|腰头|腰围|有弹性)|(?:确认|检查|核对|试试|试穿看看|试走看看).{0,10}$|(?:是否|会不会|能否|是不是).{0,6}$")
_ATTRIBUTION = re.compile(r"(?:款名|商品名|名称|品类|标注|标为|注明|写着)")
_LABELS = ("宽松", "松紧腰", "弹性腰头", "弹力腰", "防水", "防雨", "防滑", "挡风")


def attribute_context(products):
    """Labels are catalog wording, not verified measurements or wearer-specific performance."""
    return {
        "measurements_and_personal_fit": "unknown",
        "waist_structure_and_elasticity": "unknown",
        "weather_performance_ratings": "unknown",
        "descriptions": "参考描述，不能据此确认尺寸、实际贴合或防护性能",
        "catalog_labels": [{"key": p.key, "labels": [label for label in _LABELS if label in
            " ".join([p.title, p.class_name, p.secondary_class_name])]} for p in products],
    }


def _issues(text, products):
    issues = set()
    # Evaluate each assertion separately: a later caveat cannot cancel an earlier guarantee.
    for clause in re.split(r"[，,。！？!?；;\n]+|但是|不过|然而|可是|而且|并且|但|却", text):
        for kind, pattern in _PATTERNS.items():
            for match in pattern.finditer(clause):
                before, after = clause[:match.start()], clause[match.end():]
                if kind == "fit" and re.search(r"不舒服|不舒适|不自在|不自如|不轻松", match.group()):
                    continue
                if kind in {"fit", "design"} and (re.search(r"是否|会不会|有没有|能否|不一定|未知|未确认|不清楚", match.group())
                        or re.search(r"再(?:穿|选|决定|保留|出门)|为准", after)):
                    continue
                if (match.group().startswith("不会") and before.endswith("会")) or (
                        match.group().startswith("不易") and before.endswith("易")):
                    continue  # A-not-A questions such as 会不会湿 are not assertions.
                if _UNKNOWN_BEFORE.search(before) or _UNKNOWN_AFTER.search(after):
                    continue
                if kind == "weather" and re.search(r"撑伞|带好雨具|走有遮蔽|避开积水", before):
                    continue
                if kind == "weather" and re.search(r"^(?:、|和|及|与|或).{0,18}(?:需|需要|要|请).{0,12}(?:核对|确认|验证|实测|检查|判断)", after):
                    continue
                if kind == "weather" and re.search(r"^(?:和|及|与|或)?.{0,12}(?:很重要|是重点|需留意|要留意|需要.{0,12}(?:核对|确认|判断|检查|实物))", after):
                    continue
                criterion = _CRITERION.search(before)
                verification = re.search(r"确认|检查|核对|试穿|试走|试试|是否|会不会|能否|是不是", before)
                if criterion and (verification or not re.search(r"这件|这条|这双|这款|选中的|所选", before)):
                    continue
                if re.search(r"^(?:如果|若|要是).{0,24}(?:是|有|带|标注|实测|确实)$", before):
                    continue
                if re.search(r"^(?:如果|若|要是).{0,24}(?:试穿|穿上|坐下|走动|抬手)", before):
                    continue
                if clause.startswith("以") and re.search(r"为(?:准|目标|优先)$", clause):
                    continue
                if re.search(r"(?:你|您|我)(?:想要|希望|需要|要求|喜欢).{0,12}$", before):
                    continue
                if re.search(r"(?:没|没有|缺少|未见|暂无).{0,8}$", before) and re.search(r"标注|资料|信息|证据|说明|标识|测试|等级", after):
                    continue
                if kind != "fit" and _ATTRIBUTION.search(before) and any(
                        match.group() in " ".join([p.title, p.class_name, p.secondary_class_name]) for p in products):
                    continue
                issues.add(kind)
    return issues


def _fields(draft, pool):
    selected = [pool[key] for look in draft.looks for key in look.selected_keys if key in pool]
    yield "message", draft.message, selected
    for index, look in enumerate(draft.looks):
        products = [pool[key] for key in look.selected_keys if key in pool]
        yield f"looks.{index}.title", look.title, products
        yield f"looks.{index}.style_name", look.style_name, products
        for field in ("pieces", "why", "how", "notes"):
            for item_index, text in enumerate(getattr(look, field)):
                yield f"looks.{index}.{field}.{item_index}", text, products


def attribute_claim_problems(draft, pool):
    return [f"{PREFIX}{path} 缺少尺寸、腰头或防护性能证据，改为选款条件、试穿核对或未知说明，不能先保证再补免责声明"
            for path, text, products in _fields(draft, pool) if _issues(text, products)]


def ground_attribute_fallback(draft: Draft, pool, persona):
    """After one failed rewrite, replace only unsupported fields and preserve selected IDs."""
    male = persona == "male_calm_v1"
    fit = "是否合身、腰腹会不会受压，还要看尺寸和试穿感受。" if male else "这件穿着是否合身，还要试穿看看腰腹有没有受压。"
    weather = "还不能确认防水或防滑效果，雨天带好雨具，留意湿滑路面。" if male else "还不能确认防水或防滑效果，雨天记得带好雨具，也留意脚下。"
    result = draft.model_dump()
    for path, text, products in _fields(draft, pool):
        kinds = _issues(text, products)
        if not kinds:
            continue
        fragments = re.split(r"([，,。！？!?；;\n]+|但是|不过|然而|可是|而且|并且|但|却)", text)
        rewritten, seen = [], set()
        for i in range(0, len(fragments), 2):
            clause = fragments[i]
            clause_kinds = _issues(clause, products)
            if clause_kinds:
                replacements = []
                for group, sentence in (("fit", fit), ("weather", weather)):
                    applies = bool(clause_kinds & {"fit", "design"}) if group == "fit" else "weather" in clause_kinds
                    if applies and group not in seen:
                        replacements.append(sentence)
                        seen.add(group)
                if not replacements:
                    continue
                clause = "".join(replacements).rstrip("。")
            rewritten.append(clause)
            if i + 1 < len(fragments):
                rewritten.append(fragments[i + 1])
        replacement = "".join(rewritten).strip()
        parts = path.split(".")
        if parts == ["message"]:
            result["message"] = replacement
        elif parts[-1] == "title":
            result["looks"][int(parts[1])]["title"] = "穿搭参考"
        elif parts[-1] == "style_name":
            result["looks"][int(parts[1])]["style_name"] = "日常参考"
        else:
            result["looks"][int(parts[1])][parts[2]][int(parts[3])] = replacement
    return Draft.model_validate(result)
