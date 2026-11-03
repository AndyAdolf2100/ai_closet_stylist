# 衣物性别与实际选款验收

先区分本人资料、助理性别、Task穿衣对象和衣物gender四层。助理形象不决定衣物对象；本轮明确男／女装或给别人搭配优先于本人默认资料。

## 数据与校验矩阵

| 数据／入口 | 必须验证 |
| --- | --- |
| 原字段1／2／3、男／女／男女同款 | 读取后归一化并进入Product、候选及所选商品 |
| 0、空、缺失或异常值 | 保留未知，不冒充男女通用；权威空值不沿用旧缓存 |
| 男装任务+女款，或女装任务+男款 | 候选、上传锚点、保存搭配及最终选款均不得绕过 |
| 标签为男但标题明确女士，或未知标题明确相反 | 拦截明显冲突；不通过改写标题掩盖源信息 |
| 通用款、混合男女标题 | 通用字段可复用；未知混合标题不自动升级为已确认通用 |
| 未知且无明确冲突 | 可作保守备选，保留版型／尺码待核对说明，优先匹配／通用标签 |
| 颜色、裙子、风格、人物外观 | 不能仅凭这些推断衣物性别 |
| 旧搭配局部冻结 | 权威重读；冲突明确拒绝，不偷偷换冻结项；合规项仍冻结 |
| 旧卡重新生成 | 来源是旧结果，选款仍按当前Task性别重新校验；不重写旧历史 |
| 候选全部不匹配 | 说明本次无匹配，不宣称整个衣橱为空、不拿冲突款凑图 |

## 多轮题库与执行

`scripts/garment_gender_dialogues.py`提供四组九轮：`garment_gender_male`、`garment_gender_female`、`garment_gender_unset`、`garment_gender_no_match`。保留本人→局部修改→更换穿衣对象的前置上下文，检查实际items与retained_items，不只检查task或正文性别词。夹具混合标签和标题异常，使用合成数据；真实用户历史只用于只读定位，不复制到题库。

必要范围先跑`tests/test_product_gender.py`，再按改动涉及的入口选用policy、wardrobe_only、partial_wardrobe、uploaded_anchor、outfit_regeneration、companion_identity、images、dialogue_validation测试；无需默认全量。检查六人格与本人性别交叉、当轮对象覆盖、无真实收费调用、失败保留旧状态及请求重放。

用`python -m scripts.evaluate_personas --list --only garment_gender_male garment_gender_female garment_gender_unset garment_gender_no_match`核对题库。列出或导出不是模型验收；真实模型另行显式--live、合成衣橱与临时库执行并保留首次结果。源数据标签质量须由带身份的真实只读接口验证，不能把源码契约或旧存档当作远端实时标签证据。程序修复、真实模型和真实标签三类证据分别报告。
