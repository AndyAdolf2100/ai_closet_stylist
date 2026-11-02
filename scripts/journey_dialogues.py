"""API/UI multistep journeys; exported as questions, not text-model eval cases."""
SCENARIOS = {
    "journey_upload_consent": [
        ("select", "【选图】选一张常穿衬衫的照片，还没有确认上传。", False),
        ("cancel", "【点击】取消，我先不把这张照片存进衣橱。", False),
        ("submit", "【重新选图并确认】上传并抠图入柜。", False)],
    "journey_upload_recovery": [
        ("processing", "【上传回执】图片正在审核、抠图和识别，先关闭面板。", False),
        ("reopen", "【重新打开记录】看看刚才那件衣服处理好了吗？", False),
        ("lost_response", "【丢失task_id】提交后断网了，查询原上传回执。", False)],
    "journey_uploaded_anchor": [
        ("completed", "【入柜完成】展示真实抠图、识别类别和个人单品。", False),
        ("style", "用我刚上传的这件衣服，结合自己的衣橱搭一套，不考虑天气。", False),
        ("restriction", "不要黄色、绿色；如果刚上传的衣服冲突，先别强行选它。", False)],
    "journey_uploaded_weather": [
        ("city", "【已选城市】北京，今天最低3℃、最高17℃；已有合规外套候选。", False),
        ("completed", "【入柜完成】白色短袖上传成功，绑定当前账号的真实衣物ID。", False),
        ("style", "用我刚上传的这件衣服，结合自己的衣橱搭一套。", False),
        ("missing_outer", "【没有合规外套候选】保留短袖与已有单品，将保暖外套列为未匹配文字参考。", False),
        ("ignore", "这次不考虑天气，还是用刚上传的衣服搭一套。", False),
        ("partial", "只换鞋，其他衣服保持不变。", False)],
    "journey_twin_selection": [
        ("independent", "我选的是男助理，试穿人物仍然由我单独选择。", False),
        ("draft", "【点击另一张人物图】先看看，还没确认使用。", False),
        ("confirm", "【确认使用】将我选中的形象用于接下来的试穿。", False)],
    "journey_person_generation": [
        ("photo", "【上传本人照片】先检查能不能创建数字人。", False),
        ("hat", "【照片检查完成】按可用选项选择保留或摘帽，查看人物生成费用。", False),
        ("cancel", "先不生成人物，取消这次费用确认。", False),
        ("reprice", "【费用变化】重新查看报价，我确认以后再生成。", False)],
    "journey_tryon_billing": [
        ("partial", "这套建议有五件，衣橱只有一件；只试穿已有的这一件。", False),
        ("quote", "【查看报价】看清本次人物、衣物数量和试穿积分。", False),
        ("confirm", "【确认费用】只生成这一次，重复点击不要重复扣积分。", False)],
    "journey_result_recovery": [
        ("unknown", "刚才试穿超时了，不要再生成，帮我查原任务。", False),
        ("still_unknown", "【原任务仍未确认】点击看看试穿进展，明确告诉我还没有确切结果，不打开空白结果、不重复扣积分。", False),
        ("complete", "【原任务成功】展示真实结果图及重新生成穿搭入口，查看结果不自动提交新任务。", False),
        ("regenerate", "【点击重新生成穿搭】沿用所选方案的场景、风格和禁穿条件，按北京时间当天重新查天气并从个人衣橱选一套；不沿用旧日期、自报温度或忽略设置，保留草稿，不重复原组合，不自动试穿或确认积分。", False),
        ("failed", "【原任务失败】明确说明没有生成图片；还没查到退款，只提供核对积分进展，不说积分已经退回。", False),
        ("refunded", "【服务确认已退款】来信写清没有试穿图、积分已退回；移除查看结果及核对积分入口，重新生成穿搭只重新选款。", False)],
    "journey_account_isolation": [
        ("switch", "【处理中切换账号】清空上一账号的照片预览、任务和结果。", False),
        ("late", "【旧账号迟到响应】不要把结果显示到新账号，也不要退出新账号登录。", False),
        ("foreign", "【提交其他账号上传ID】拒绝将它用于当前衣橱搭配。", False)],
}
PURPOSES = {
    "journey_uploaded_weather": "已确定城市后上传短袖继续搭配：温度传递、真实外套选择、缺货文字参考、忽略天气及局部冻结；用合成天气和衣橱验证，不调用收费服务。",
    "journey_upload_consent": "选图在本地预览，取消零写入，明确提交后才调用正式抠图入柜。",
    "journey_upload_recovery": "已有任务只读恢复，原回执找回task_id，不重复上传或入柜。",
    "journey_uploaded_anchor": "完成回执绑定当前账号真实单品，绕过索引延迟并保留硬性限制。",
    "journey_twin_selection": "人物与助理性别独立；选择是草稿，确认时校验最新版本。",
    "journey_person_generation": "照片检查与付费生成分开，帽子选择有效，取消不生成，变价重新确认。",
    "journey_tryon_billing": "只用真实衣物，人物与试穿分别确认；原子抢占防重复扣费。",
    "journey_result_recovery": "乙游来信不使用完成／未完成状态条；成功展示真实图，失败退款后无空转查询，未确认查询须反馈；重新生成穿搭另走选款，不自动试穿。",
    "journey_account_isolation": "切换账号清理预览与结果，拒绝迟到响应、跨账号上传引用和费用动作。",
}
EXPECTATIONS = {
    f"{scenario}/{turn}": {"execution": "api_ui_journey", "purpose": PURPOSES[scenario],
                           "real_charge": "not_executed_by_default"}
    for scenario, rows in SCENARIOS.items() for turn, _, _ in rows
}
