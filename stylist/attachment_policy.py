"""A photo is a reference, never an execution or wardrobe-ingestion permission."""
import re


def _action_clauses(message):
    text = re.sub(r'“[^”]*”|「[^」]*」|"[^"]*"|‘[^’]*’', '', message)
    for clause in re.split(r'[，。！？；\n]', text):
        if re.search(r'假如|假设|比如|举例|转述|朋友说|别人说|原理|收费|多少钱|费用|怎么实现', clause):
            continue
        if re.search(r'(?:只|仅)(?:分析|看看|看图|描述|讲原理)|不(?:要|用|想|需要)?(?:生成|合成|试穿|搭配)|别(?:生成|合成|试穿|搭配)', clause):
            continue
        yield clause


def requires_wardrobe_upload(plan, message, *, has_image):
    """Use cited semantic intent, with narrow explicit-action protection on new photos."""
    clauses = list(_action_clauses(message))
    if not clauses:
        return False
    photo_reference = has_image or bool(re.search(r'这张|那张|刚才.{0,8}(?:图|照片)|图片|照片|图里', message))
    evidence = plan.attachment_action_evidence.strip()
    if (photo_reference and plan.attachment_wardrobe_required and evidence
            and evidence in message and any(evidence in clause for clause in clauses)):
        return True
    if not has_image:
        return False
    intents = [
        (plan.unsupported_image_request, plan.image_request_evidence),
        (plan.avatar_intent in {'upload', 'tryon'} and not plan.avatar_declined, plan.avatar_evidence),
        (plan.upload_intent == 'garment' and not plan.upload_declined, plan.upload_evidence),
    ]
    if any(enabled and quote.strip() and quote in message and any(quote in clause for clause in clauses)
           for enabled, quote in intents):
        return True
    return any(re.search(r'合成|生成|生图|试穿|换装|写真|合照|改背景|换(?:个)?背景|P图|修图|怎么搭|如何搭|搭配一下|搭[一两几三四五六七]套|配一套|^搭配$|帮.{0,12}搭配', clause, re.I)
               for clause in clauses)
