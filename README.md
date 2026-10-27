# CMIS — Concert Merchandise Intelligence System

演唱会文创决策辅助系统（Skill）。面向经纪公司、文创设计团队、生产与销售团队，
把"给艺人做周边"变成一套可核算、可落地、可复用的决策流程。

- **当前版本**：v5.4（2026-10-27）
- **Skill 入口**：`cmis-skill/SKILL.md`
- **分发包**：`cmis-skill.skill`（zip，装包用）
- **变更记录**：`cmis-skill/CHANGELOG.md`

## 目录结构

```
cmis-skill/
├── SKILL.md                    入口：定位、Layer 0 分诊、三道闸门、18章输出结构（依据→决策→落地）
├── CHANGELOG.md                版本与变更记录
├── references/
│   ├── layers.md               Layer 0-7 执行规范（主规范）
│   ├── decision-basis.md       依据七册 D1-D7：字段、验收、编号、置信度、反模式
│   ├── agency-authorization.md 经纪公司档案、五方决策链、授权矩阵、合同 12 条
│   ├── quant-model.md          容量/销量/首批量/毛利模型
│   ├── supply-chain.md         品类工期、T-minus 倒排、极限交期降级
│   ├── compliance.md           安检/电池/版权/场馆IP 一票否决清单
│   ├── channel-playbook.md     平台矩阵、投放节奏、私域接龙
│   ├── sku-library.md          品类库、成本、工艺选型
│   ├── city-profiles.md        城市场景与消费画像
│   ├── artist-ip-ecosystem.md  分流来源 A-E、组织与授权可行性
│   ├── artist-archetypes.md    圈层类型、w/λ 参数、赵雷反例
│   └── empirical-data.md       56个SKU实证数据 + 结构占比 + 特殊案例 + 回填规则
└── history/                    v2.0-v5.1 存档（不参与打包）
cases/                         已交付的策划书案例（用于校准与复盘）
```

## 维护约定

1. 改内容后同步 `CHANGELOG.md`，并在 SKILL.md 顶部更新版本号
2. 每次改完重新打包：`cmis-skill.skill` 应包含 `SKILL.md` + `CHANGELOG.md` + `references/*.md`（不含 `history/`）
3. 项目结项 30 天内回填 `references/empirical-data.md`（预测 vs 实际）
4. 定期 review：默认每季度一次，重点查"规范是否又与实战脱节"与"数字口径是否自洽"
5. 提交：`./gitcommit.ps1 "说明"`
6. **结构约定（v5.4）**：方案必须"依据 → 决策 → 落地"三段式。第 2-8 章是依据七册（D1-D7），不得出现具体 SKU 提案；第 1 章结论与第 9 章每个 SKU 都要回引依据编号。依据没有编号、或从未被引用，等于没写
