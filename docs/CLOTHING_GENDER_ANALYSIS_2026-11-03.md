# 衣物性别分析与修复 · 2026-11-03

用户反馈选了男性仍搭配女装，随后要求修复、测试、更新用例并提交。

## 原因与已确认事实

独立本地会话只读核对：本人资料user_gender与Task.gender均为男，实际选款中仍有标题明确为女款的衬衫／外套，性别已传入任务。Server个人及系统商品模型有gender：0未设置、1男、2女、3通用；product.resolve契约转换为男、女、男女同款或空。修复前衣间Product未保留gender、from_row未映射，选款也未校验，导致约束没有落地。

Server源码依据为internal/biz/biz-user/user_product_base.go、internal/biz/biz-aicloset/product_base.go、internal/data/user/user_product_resolve.go、internal/service/product_resolve/service.go和internal/controller/mcp/tools/product_resolve.go。源码和契约不代表远端已发布；本轮未通过真实接口核验具体商品原标签，标签质量仍可能是额外问题。

## 当前规则与实现

- Product保留并归一化gender，兼容底层数值字符串／整数和文本值；缺失、0、异常值保留未知，旧结果仍可读取。权威返回空值覆盖旧缓存，不默认通用。
- Task.gender确定穿衣对象，用户本轮明确对象优先，助理性别独立。匹配／男女同款优先于未知；未知无明显冲突可保守备选并提示版型／尺码待核对，不保证适合。
- 拦截明确相反的商品标签、标题明确相反或字段与标题冲突；不单凭粉色、裙子、版型风格或人物外观推断性别。商业标题混合男女词时不假定为某一方。
- 个人候选、保存搭配、上传锚点及最终选款均共用校验。旧搭配修改对冻结项重新权威读取，冲突返回frozen_gender_conflict（409），不偷偷替换或把问题包装为衣橱服务失败；合规冻结项仍保留。
- 所有候选被排除时说明本次无匹配、只给文字参考，不宣称整个衣橱为空。重新生成可从旧搭配继续，但新选款必须通过当前性别校验，原历史不改写。

## 必要验证与实际边界

205项Python定向通过：test_product_gender.py、test_dialogue_validation.py、test_images.py、test_upstream.py、test_policy.py、test_wardrobe_only.py、test_partial_wardrobe.py、test_uploaded_anchor.py、test_outfit_regeneration.py、test_companion_identity.py；Ruff通过。新增性别专项58项，覆盖归一化、未知、标题冲突、六人格、本人／他人、匹配优先、保存搭配、局部冻结、上传、历史重新生成、全无匹配和最终校验。使用模拟外部服务与临时数据库，不执行真实收费。

只读旧结果的5件中，有3件标题明确相反，现已能判为冲突；旧结果5件的gender均缺失，这是旧Agent丢字段的存档证据，不是对实时源标签的核验。只记录统计，不复制用户商品ID、完整对话或图片，不修改原数据。

新增四组九轮对话题库，check_reply核对实际选中／保留商品，不只检查Task；公开目录216组427步。题库列出／导出不等于真实模型验收，本轮未执行live文字测试。

本地8466按原环境重载，健康200；未修改原衣橱标签、旧会话或旧MySQL，未执行真实图片／扣退费。证据在忽略目录var/clothing-gender-fix/的targeted-tests.log、local-history-check.json。运行时修复与定向回归已完成；源标签质量和真实模型表现仍需分别验收。
