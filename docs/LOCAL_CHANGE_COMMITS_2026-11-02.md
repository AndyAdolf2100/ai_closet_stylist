# 2026-11-02 本地功能提交核对

用户要求将本地改动按功能点提交。以下按依赖顺序整理，共用模型、主Agent和存储的变更按功能分段进入提交，最终页面统一接入已提交组件。

| 提交 | 功能范围 | 标题 |
| --- | --- | --- |
| `a05e541` | 六种助理人格与角色素材 | feat: add six companion personas and character artwork |
| `d777614` | 穿搭手记范围与事实表达 | fix: restrict companion memories to clothing preferences |
| `08b6e08` | 上传入柜、数字人与积分试穿 | feat: connect wardrobe uploads and digital avatar try-on workflows |
| `2963f43` | 当前／历史搭配重新生成 | feat: regenerate selected outfits including historical results |
| `9a96a67` | 城市引导与天气外层选款 | fix: request missing outfit cities and enforce weather layering |
| `0e86b46` | 通用持续加载动画 | feat: add reusable companion loading animations |
| `da5a86c` | 助理选择与独立系统配色 | feat: add companion appearance selection and persistent system colors |
| `31de4aa` | 上传试穿界面、结果来信与交互整合 | feat: integrate themed wardrobe journey cards and result letters |
| `c38318c` | 对话题库、评审与测试skill | test: expand dialogue regression scenarios and audit tooling |
| `9008ca5` | Nginx上传请求大小与发布说明 | fix: raise assistant proxy limits for confirmed image uploads |
| `c04e1e9` | 生成成本、耗时与产品规划 | docs: add generation cost measurements and product planning |
| 本次文档提交 | 当前PRD、接口说明、设计总览与提交依据 | docs: sync current requirements and functional commit evidence |

## 范围与排除项

纳入运行时代码、原创角色与动画素材、模拟测试、QA skill、提示词、通用Nginx配置和公开产品文档。补齐包数据中嵌套角色素材的匹配，核对30份运行时skill／场景PNG均可进入打包范围。

`var/`、本机配置、凭证、账号资料、用户照片和发布镜像包不纳入。`outputs/`保留为本地导出／预览目录并加入忽略规则；两份docs内正式产品文档保留，已核对无嵌入图片。本轮推送源码，不部署服务或执行真实收费业务。

## 本轮必要验证

- 15个相关Python测试文件：343项通过，使用模拟业务和临时数据库。
- 9个相关Node测试文件：110项通过，覆盖设置、手记、上传／试穿、重新选款、城市、加载、账号隔离与报告。
- 改动Python源码的Ruff检查通过；提交差异空白检查通过。
- 待提交文本／文档做凭证和账号模式检查；两处命中为明确synthetic测试占位值。没有将真实凭证或用户图片复制入库。
- 本轮没有新增真实模型、用户资料写入、上传、生成、积分扣退或远端部署测试。此前真实评测和各功能浏览器证据保留在相应专项文档，不把本轮Mock结果当作真实业务验收。

推送目标为现有origin的main；远端是否接收以最终Git操作回执为准。
