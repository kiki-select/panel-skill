# panel-skill：FunnyDB 报表沉淀技能

把**已校验的取数 query** 持久化成 FunnyDB panel / dashboard。是数据技能流水线里「埋点设计 → 取数(ds) → 报表沉淀」的最后一环。

## 它是什么

- **输入**：一个已经校验过口径的查询（raw_sql 的 SQL，或非 raw_sql 模型的 `data_setting`，通常来自 ds-skill）。
- **输出**：FunnyDB 上的 panel / dashboard（返回 `panel_url` / `dashboard_url`），团队可长期查看、监控、分享。
- **不做**：写口径、探查、抽样校验（ds-skill 的活）、分析、下结论。

## 与其它技能的关系

```
funnydb（接口底座）
  └← ds-skill（取数 + 校验引擎）
        └← panel-skill（把已校验 query 沉淀成 panel/dashboard）  ← 本技能
```

- 依赖 **funnydb skill** 调 `panels/create` / `dashboards/create`。
- 依赖 **ds-skill** 提供已校验的 query。**铁律：未校验的 query 不准建 panel。**

## 安装

放到你的 Agent skills 目录（与 funnydb / ds 同级），例如 `.claude/skills/panel`。

## 用法

详见 [SKILL.md](SKILL.md)。最常用：

```bash
# 建 panel（raw_sql）
python scripts/create_panel.py \
  --app-id 42 --funnydb-dir <funnydb skill 路径> \
  --title "AI-经典模式-逐日登录账号数" --event-model raw_sql \
  --sql-file examples/sample-panel/panel.sql \
  --description "主要内容：统计逐日登录账号数。核心指标：日期、登录账号数"

# 把 panel 编排进看板
python scripts/create_dashboard.py \
  --app-id 42 --funnydb-dir <funnydb skill 路径> \
  --name "AI-登录监控看板" --panel-ids <panel_id1>,<panel_id2>
```

## 关键约束

- raw_sql 反引号会被 WSL bash -c 吃空，脚本自动转 `\u0060` 规避。
- 只传 `data_setting`，不传 `setting`（服务端生成）。
- `description` 必填，格式「主要内容 + 核心指标」——与 ds 看板检索 description-优先闭环。
- `dashboards/create` 永远新建、无追加接口；多 panel 一次性 `panel_ids` 带全。
- 看板默认建在当前用户私有空间；测试产物加 `AI测试-` 前缀用完即删。

## 目录

```
panel-skill/
  SKILL.md                      工作流入口
  scripts/
    funnydb_client.py           FunnyDB 调用封装（含反引号转义）
    create_panel.py             建 panel + 验证出数
    create_dashboard.py         建 dashboard
  references/
    create-api-spec.md          接口规范 + 实测约束
    data-setting-schema.md      各 event_model 的 data_setting 结构
    naming-governance.md        命名/空间/description 治理
  examples/sample-panel/        示例
```
