# 试穿形象：数字分身与身体外观

2026-11-05。H5沿用现有配色规则，只显示数字分身、身体与外观；不迁入iOS的账号昵称／头像、基础信息或Memory。数字分身横排选择，创建入口保留；身高、体重、BMI参考、身材描述及肤色归为同一轻量表单。BMI仅按已填数值计算，不给健康结论。创建与搭配试穿继续分别确认费用。

## iOS契约核对

来源：本机aicloset-IOS当前dev_2.0.0_new_agent分支，`AICloset/Sources/Module2.0/Profile/DigitalTwinService.swift`与`DigitalIdentityViewController.swift`。同时只读核对Server的`internal/service/digital_twin/profile.go`字段与选项结构。

| H5路由 | 复用Server接口 | 用途 |
| --- | --- | --- |
| GET /stylist-api/twins | GET /api/digital_twin/overview | 分身、默认选择、身体资料及版本 |
| GET /stylist-api/twins/options | GET /api/digital_twin/profile/options | 服务端范围、步长、肤色选项与描述长度 |
| POST /stylist-api/twins/profile | POST /api/digital_twin/profile/update | 显式保存身体资料 |

保存字段限`height_cm`、`weight_kg`、`body_description`、`skin_tone`、`skin_description`及`expected_version`。仅提交用户改过的字段；清空数值／肤色传null，清空描述传空字符串。身份使用当前登录凭证，由后端核对，不接受客户端owner。服务端仍负责业务范围与选项校验。45305版本冲突不自动重试，保留当前草稿并提示重新读取。网络失败不宣称保存成功，不另存一份资料或直接写数据库。

交互区别：iOS部分数值编辑完成即提交；H5采用明确的“保存身体资料”，滑动只更新本页草稿。页面关闭、切换账号后忽略迟到读取／保存响应。未读取到选项时提供重试，不伪造可保存的范围。

## 验证

26项后端模拟通过（身份、部分更新、显式清空、额外字段拒绝、版本冲突和原有形象流程），三尺寸×系统／男角色／女角色9组浏览器检查通过，覆盖布局、BMI、保存、清空、描述和请求字段。脚本：`tests/test_twin_body.py`、`scripts/check_twin_body.cjs`。本地8466服务已重载并检查新增路由；未使用真实账号保存，远端部署与真实服务联调不据此宣称完成。

前后对照合并本地`reports/26-11-05/change-log/docs/UI_CHANGELOG.html`的UI-028，旧侧维持fc238fb基线，今日对照及导览使用系统配色模拟资料。

肤色移动端更新：独立底部编辑面板，取消丢弃局部修改，完成将肤色与描述回填本页草稿，最终保存仍走原同一版本接口。面板按VisualViewport高度避让键盘，内部滚动且底部操作固定；输入16px，H5可见文字最小12px。9组短屏／主题模拟通过，真机键盘未验。
