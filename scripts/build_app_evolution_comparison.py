# -*- coding: utf-8 -*-
"""Add source-checked product rationale to both existing review pages (no account data)."""

import shutil
from html import escape
from pathlib import Path

root = Path(__file__).resolve().parents[1]
base = root / "stylist/static/closet-app/comparison/evolution"
base.mkdir(parents=True, exist_ok=True)
(base / "screenshots").mkdir(exist_ok=True)
for name in ["home", "profile", "profile-services", "agent"]:
    shutil.copyfile(root / f"var/app-native-audit/after/{name}.png", base / f"screenshots/yijian-{name}.png")
for name in ["home", "profile"]:
    shutil.copyfile(
        root / f"var/app-native-audit/reference-ios-html/{name}.png",
        base / f"screenshots/ios-html-{name}.png",
    )
private = base / "screenshots/private"
private.mkdir(exist_ok=True)
for shot in (root / "var/app-native-audit/authenticated").glob("*.png"):
    shutil.copyfile(shot, private / shot.name)
sections = [
    dict(
        id="home",
        title="首页：从找功能，到有一个自然的开场",
        old="功能入口 → 我的搭配／推荐搭配",
        new="造型册／发现灵感／潮流玩法 → 动态Agent卡 → 聊天记录",
        current="角色问候与头像 → 聊聊／每日签到 → 三栏内容",
        rows=[
            (
                "第一眼看到什么",
                "场景搭配、单品搭配、Copy Look、DIY等工具入口；我的搭配／推荐搭配切换，默认推荐。",
                "三栏内容首页；具备服务端动态Agent观察卡，不是没有个性化。",
                "顶部增加当前角色精灵头像与独立预制问候，下方保留三栏内容。",
            ),
            (
                "如何开始对话",
                "从具体搭配工具或单品场景进入。",
                "聊天记录入口与动态卡片动作进入Stylist；旧任务不直接重放。",
                "明确的“和伙伴聊聊”；未登录先登录，不自动发送，角色和称呼延续。",
            ),
            (
                "日常回访",
                "以内容与功能需求为主要入口。",
                "首页内容、观察卡与历史对话承接。",
                "首页放每日签到；已签改文案与颜色，个人页去掉重复领积分入口。",
            ),
            (
                "内容表达",
                "以搭配任务和推荐列表组织。",
                "造型册、灵感、玩法三类已分开。",
                "保留分类，各有对应说明；造型册增加手记语气与纸面感。",
            ),
        ],
        why="用户未必带着明确任务进入。先给一个容易接话的开场，再让需要找内容的人继续浏览；同时保留iOS新版已建立的三栏结构，避免重新学习整套导航。",
        benefit="预期降低首次发问的心理门槛，增强角色辨识度和跨次使用的连续感；签到放在日常场景中更容易理解。",
        tradeoff="角色区占据首屏空间。熟练用户可能更想直接看搭配，因此内容分类继续清晰可达，角色区要克制高度。预制问候不是实时理解用户心情，也不能冒充服务端个性化观察卡。",
        measure="验证首次进入后的首条对话发起率、找到造型册所需时间，以及角色问候是否被认为自然；本轮没有这些增长数据。",
        sources=[
            "Main/Home/Page/Controller/HomeController.swift",
            "Module2.0/Home/HomeFeedViewController.swift",
            "Module2.0/Home/HomeAgentCardView.swift",
        ],
    ),
    dict(
        id="profile",
        title="我的：把资料管理，整理成用户自己的日常",
        old="账号信息 → 订单／消息／反馈／联系／设置",
        new="头像与数字分身 → 积分 → Memory → 生成记录／我的搭配 → 服务菜单",
        current="陪伴小笺 → 积分 → 我们的手记 → 我的数字分身 → 记录／搭配 → 衣橱小记 → 服务菜单",
        rows=[
            (
                "身份与形象",
                "以账号资料、消息及服务菜单为中心。",
                "账号头像、昵称与编辑数字分身入口靠前；积分与会员保留。",
                "伙伴小笺与用户自己的数字分身分开；数字分身只使用custom_twin，不拿伙伴或账号头像代替。",
            ),
            (
                "偏好和记忆",
                "当前旧个人页主体没有新版Memory卡。",
                "Memory有偏好为空时的“开始进化”和有记录时的最近变化，进入独立偏好页面。",
                "改成“我们的手记”，在卡片直接打开现有偏好手记编辑；这是另一套数据入口，不能宣称旧Memory已经迁移。",
            ),
            (
                "入口优先级",
                "账号与服务工具集中排列。",
                "顶部统计／领积分；生成记录与我的搭配双卡；订单等菜单。",
                "去掉个人页领积分；统计改“衣橱小记”放到双卡下面；角色和偏好从设置进入。",
            ),
            (
                "列表与空态",
                "以原有列表、原有资源为准。",
                "业务列表及原生导航／刷新方式。",
                "详情单层居中导航、轻分段、下拉更新；新插画区分空列表与未开放功能；搭配图下不重复写“我的搭配”。",
            ),
        ],
        why="“我的”既要让用户找到记录和设置，也要看得出这是自己的空间。把伙伴、个人试穿形象、偏好手记各自说清楚，减少头像与身份混淆；常用的记录保持直接可达。",
        benefit="预期让偏好更容易被发现和维护，降低寻找搭配与生成记录的成本；减少重复入口及无意义文案，页面更安静。",
        tradeoff="统计下移后不如顶部显眼；陪伴小笺也会增加滚动长度，因此已压缩卡片。会员、统计等Web页面尚未接入完整能力，不能把视觉调整描述为业务补齐。",
        measure="验证用户能否区分“伙伴形象”和“我的数字分身”，是否能迅速找到记录／手记／统计；不要只用“更好看”替代可用性证据。",
        sources=[
            "Main/Profile/Main/ProfileViewController.swift",
            "Module2.0/Profile/ProfilePageViewController.swift",
            "Module2.0/Profile/ProfileHeaderView.swift",
        ],
    ),
    dict(
        id="agent",
        title="Agent：从通用对话入口，到可辨识的陪伴角色",
        old="旧Main首页／我的不是独立Agent版本，不另造一套Agent界面",
        new="AI搭配师／新建聊天／历史 → 通用欢迎与建议 → 语音／文字／附件",
        current="历史图标 → 定位城市 → 角色欢迎 → 三条建议 → 上传／试穿／记录 → 来源与输入",
        rows=[
            (
                "版本依据",
                "Main旧主页作为宿主结构参考；本次没有独立旧Agent运行版本。",
                "dev_2.0.0分支48e77c24的AgentChatViewController和AgentWelcomeView；排除未提交Stylist替换。",
                "本地衣间Web；并非声称这套改版已经存在于2.0.0原生分支。",
            ),
            (
                "欢迎区",
                "不将旧宿主页面推断成另一套Agent。",
                "“今天想聊点什么？”及日程、天气、衣服引导；单品／搭配上下文会改变欢迎文案。没有六角色欢迎头像。",
                "使用当前角色头像、称呼与主题，提供明确的今日／本周／旧衣新搭入口，让用户感到是同一位伙伴。",
            ),
            (
                "快捷提问",
                "本列不单独评判。",
                "建议按钮直接调用session.send；任务入口则走sendComposerMessage。",
                "点击先填入草稿，再由用户发送；增加一步确认，降低误触执行，代价是多一次操作。",
            ),
            (
                "导航与定位",
                "本列不单独评判。",
                "标题AI搭配师，聊天记录图标和新建聊天按钮；欢迎首屏没有衣间式独立城市定位行。",
                "保留单层标题与历史图标，城市入口显式可见；点击申请定位、确认后使用，拒绝授权仍可手选。",
            ),
            (
                "输入与工具",
                "本列不单独评判。",
                "底部紧凑输入条，支持语音切换与附件；按会话状态切换发送／停止。",
                "输入区展开，上传衣服、试穿形象、生成记录直接展示，并标明我的衣橱／邂逅新衣；Web未复现原生语音交互，不宣称全功能一致。",
            ),
            (
                "签到",
                "旧主页面不作为Agent发奖依据。",
                "该分支Agent欢迎页没有前次所述的Stylist“对话解锁10体验积分”入口；那属于未提交替换版。",
                "衣间首页签到对接原App业务接口，以服务端金额和状态为准，不要求先聊一轮。",
            ),
        ],
        why="从泛化的“聊什么”转为有角色辨识、明确穿搭帮助与可见城市的开场。头像和称呼负责连续感，任务入口负责可发现性；同时保留用户决定发送的权利。",
        benefit="预期降低不知道如何开口的门槛，让用户更容易找到上传、试穿和历史；一致的人物、称呼和配色有助于形成熟悉感。这些是设计目标，尚无用户增长实验支持。",
        tradeoff="新版欢迎内容更丰富，也占用更多空间；旧版紧凑输入和语音有其效率优势。亲密感不能靠虚构关系或推断情绪，定位、图片费用和真实业务状态仍应准确。",
        measure="对比首次提问完成率、误触发送、工具查找时间与欢迎区自然度；本轮只读访问及截图不等于语音、模型对话、收费功能验收。",
        sources=[
            "Module2.0/Agent/AgentChatViewController.swift",
            "Module2.0/Agent/AgentWelcomeView.swift",
            "Module2.0/Agent/Input/AgentComposerView.swift",
        ],
    ),
]

style = """<style>.ev{margin:32px auto;padding:28px;max-width:1280px;background:#fffdfa;border:1px solid #e5ddd2;border-radius:20px;color:#354139;font:15px/1.85 -apple-system,"PingFang SC",sans-serif}.ev *{box-sizing:border-box}.ev h2{font:28px/1.5 Georgia,"Songti SC",serif;margin:6px 0 15px}.ev h3{font-size:20px;margin:26px 0 12px}.ev h4{font-size:16px;margin:0 0 8px}.ev p{margin:8px 0}.ev .ev-kicker{font-size:11px;letter-spacing:2px;color:#7c816f}.ev .ev-note{font-size:13px;color:#777f75}.ev .ev-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:20px 0}.ev button{font:inherit;padding:9px 20px;border:1px solid #dce2d5;background:transparent;color:inherit;border-radius:24px;cursor:pointer}.ev button[aria-selected=true]{background:#62755c;color:white}.ev [hidden]{display:none!important}.ev .ev-flow,.ev .ev-rationale{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.ev .ev-flow>div,.ev .ev-rationale>div{padding:18px;background:#f3f5ef;border-radius:12px}.ev .ev-table{overflow-x:auto}.ev table{table-layout:fixed;border-collapse:collapse;width:100%;min-width:900px;font-size:14px}.ev col:first-child{width:16%}.ev col:not(:first-child){width:28%}.ev th,.ev td{width:auto;min-width:0;white-space:normal;overflow-wrap:anywhere;padding:18px 16px;border-bottom:1px solid #e8e3da;vertical-align:top;text-align:left}.ev th{background:#f2f4ed}.ev td:first-child{width:auto;min-width:0;font-weight:600}.ev th:last-child,.ev td:last-child{background:#f5f7f1}.ev th{white-space:nowrap}.ev .ev-shots{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;align-items:start}.ev figure{margin:12px 0}.ev img{display:block;width:100%;max-width:330px;border:1px solid #ddd;border-radius:12px;height:auto}.ev figcaption{font-size:13px;color:#747a71;margin-bottom:10px}.ev details{margin-top:16px;padding:16px;border-top:1px solid #ddd}.ev summary{cursor:pointer}.ev code{overflow-wrap:anywhere;font-size:12px}.ev .ev-rationale{grid-template-columns:repeat(2,minmax(0,1fr));margin-top:20px}.ev a{color:#425e79}.ev .ev-boundary{padding:18px;border-left:3px solid #a9b79b;background:#f6f6f1;margin-top:22px}@media(max-width:700px){.ev{padding:18px;margin:20px 0}.ev .ev-flow,.ev .ev-rationale,.ev .ev-shots{grid-template-columns:1fr}.ev h2{font-size:23px}.ev img{max-width:100%}}</style>"""
html = (
    style
    + """<section class="ev" id="app-evolution"><p class="ev-kicker">WHY WE CHANGED · 产品演进对照</p><h2>从衣橱工具，到有温度的日常陪伴</h2><p>保留管理衣物与完成搭配的能力，用原创角色、可编辑的偏好和更自然的开场，降低使用门槛。视觉更克制，操作更像App，业务信息仍然清楚。</p><div class="ev-boundary"><strong>先区分三个版本</strong><p>① iOS旧版：仓库保留的Main旧页面和旧Agent代码；不是当前线上版本断言。② iOS新版：dev_2.0.0分支的Module2.0首页／我的／Agent，排除未提交Stylist替换。③ 当前衣间：本地 /app/?design=yijian，包含本轮未提交改动。</p><p class="ev-note">2026-11-03源码核对：iOS 48e77c24、Stylist df91be7及各自工作区。原生截图来自dev_2.0.0独立构建与iPhone 17模拟器；临时启动入口用于打开现有页面、读取登录态并跳过定位弹窗／新手遮罩／自动奖励检查，页面布局不改。登录后只读数据用于演示；截图仅在本机保留、不纳入提交。</p></div><div class="ev-tabs" role="tablist" aria-label="选择对比页面">"""
)
for i, s in enumerate(sections):
    html += f'<button role="tab" id="ev-tab-{s["id"]}" aria-selected="{str(i == 0).lower()}" aria-controls="ev-{s["id"]}" tabindex="{0 if i == 0 else -1}">{["首页", "我的", "Agent首页"][i]}</button>'
html += "</div>"
for i, s in enumerate(sections):
    html += (
        f'<article id="ev-{s["id"]}" role="tabpanel" aria-labelledby="ev-tab-{s["id"]}"'
        + (" hidden" if i else "")
        + "><h3>"
        + s["title"]
        + '</h3><div class="ev-flow">'
    )
    for title, key in [
        ("iOS旧版 · 源码结构", "old"),
        ("iOS新版 · 源码结构", "new"),
        ("当前衣间 · 已实现结构", "current"),
    ]:
        html += f"<div><h4>{title}</h4><p>{s[key]}</p></div>"
    html += '</div><h3>具体差在哪里</h3><div class="ev-table" tabindex="0" role="region" aria-label="版本差异对照表，可横向滚动"><table><colgroup><col><col><col><col></colgroup><thead><tr><th>对比项</th><th>iOS旧版</th><th>iOS新版</th><th>当前衣间</th></tr></thead><tbody>'
    for row in s["rows"]:
        html += "<tr>" + "".join("<td>" + escape(c) + "</td>" for c in row) + "</tr>"
    html += '</tbody></table></div><div class="ev-rationale">'
    for title, key in [
        ("为什么这样改", "why"),
        ("预期好处 · 尚非增长结论", "benefit"),
        ("保留的取舍与限制", "tradeoff"),
        ("下一步如何验证", "measure"),
    ]:
        html += f"<div><h4>{title}</h4><p>{s[key]}</p></div>"
    html += '</div><h3>界面证据</h3><div class="ev-shots">'
    for version, label in [("ios", "iOS 2.0.0 · iPhone 17原生截图"), ("yijian", "当前衣间 · 登录后Web截图")]:
        filename = f"{version}-{s['id']}.png"
        html += f'<figure><figcaption>{label}</figcaption><a href="ASSET_PREFIX/screenshots/private/{filename}" target="_blank"><img loading="lazy" src="ASSET_PREFIX/screenshots/private/{filename}" alt="{label}"></a></figure>'
    html += "</div>"
    if s["id"] != "agent":
        html += f'<details><summary>展开查看旧版原生页面</summary><p class="ev-note">同分支保留的Main旧控制器，以临时启动入口打开；不是旧版本发布包。</p><img loading="lazy" src="ASSET_PREFIX/screenshots/private/ios-old-{s["id"]}.png" alt="旧版原生页面"></details>'
    if s["id"] == "home":
        html += '<details><summary>展开查看衣间首页实际搭配内容</summary><img loading="lazy" src="ASSET_PREFIX/screenshots/private/yijian-home-feed.png" alt="登录后首页搭配列表"></details>'
    if s["id"] == "profile":
        html += '<details><summary>展开查看衣间记录与服务菜单位置</summary><img loading="lazy" src="ASSET_PREFIX/screenshots/private/yijian-profile-services.png" alt="我的页面下半部分"></details>'
    html += (
        "<details><summary>源码依据与实现边界</summary><p>iOS路径相对于 AICloset/Sources/：</p>"
        + "".join("<p><code>" + escape(x) + "</code></p>" for x in s["sources"])
        + "<p>衣间路径：stylist/static/closet-app/ 内的 app.js、yijian.js、agent-integration.js、native-polish.css 与各业务组件。</p></details></article>"
    )
html += """<div class="ev-boundary"><h3>已经改善的，与仍需验证的</h3><p><strong>可以直接检查：</strong>去掉重复入口和常驻刷新、二级页标题居中、空态区分清楚、角色与本人分身分开、按钮和标题不重叠；当前模拟流程与截图见上方逐页审阅。</p><p><strong>暂不能下结论：</strong>更亲密、更愿意聊天、年轻用户更喜欢、留存或转化提升，都需要真实用户研究或实验。衣间仍是Web实现，原生键盘、定位、转场等体验不能仅凭CSS宣称一致。</p><p><strong>业务缺口仍保留：</strong>统计、会员、DIY、OOTD、电商导入、分类衣橱完整编辑尚未在这套Web全部接通；新首页的预制角色问候也不等同于iOS动态观察卡。迁移时应逐项保留或补齐，不能只复制视觉。</p><p><strong>乙游表达的边界：</strong>提供陪伴、选择权与被认真对待的感受，不预设恋爱关系，不用占有或情绪施压文案，也不模糊积分与付费确认。</p></div></section>"""
script = """<script>(()=>{const root=document.getElementById('app-evolution');const tabs=[...root.querySelectorAll('[role=tab]')];function pick(t){tabs.forEach(b=>{const selected=b===t;b.setAttribute('aria-selected',selected);b.tabIndex=selected?0:-1;root.querySelector('#'+b.getAttribute('aria-controls')).hidden=!selected;});}tabs.forEach((t,i)=>{t.onclick=()=>pick(t);t.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const n=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;pick(tabs[n]);tabs[n].focus();};});})();</script>"""
(base / "index.html").write_text(
    '<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>衣间与iOS新旧版 · 产品演进</title><body style="margin:0;background:#eef1f4">'
    + html.replace("ASSET_PREFIX", ".")
    + script
    + "</body></html>"
)
for path, prefix in [
    (root / "var/app-native-audit/index.html", "../../stylist/static/closet-app/comparison/evolution"),
    (root / "stylist/static/closet-app/comparison/index.html", "evolution"),
]:
    s = path.read_text()
    start = "<!-- APP_EVOLUTION_START -->"
    end = "<!-- APP_EVOLUTION_END -->"
    if start in s:
        s = s[: s.index(start)] + s[s.index(end) + len(end) :]
    insert = start + html.replace("ASSET_PREFIX", prefix) + script + end
    s = s.replace("</main>", insert + "</main>", 1)
    path.write_text(s)
print("Updated audit + login/onboarding comparison; standalone evolution page built")
