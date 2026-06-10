---
name: panel
description: |
  报表沉淀 skill。把「已校验的取数 query」持久化成 FunnyDB panel/dashboard：构造 data_setting、
  调 panels/create 建报表、可选 dashboards/create 编排看板，治理命名/空间/description，建完验证出数、
  上报 panel_url/dashboard_url。依赖 ds-skill 提供已校验 query，不自己写口径、不做分析。
  触发：用户使用 `/建报表` `/建看板` 命令，或表达「把这个做成报表/看板」「沉淀成 panel」「保存到 FunnyDB」等意图。
---

# panel：报表沉淀 skill（把已校验 query 做成 FunnyDB panel/dashboard）

把一个**已经校验过口径**的查询，固化成 FunnyDB 上可复用、可监控、可分享的 panel / dashboard。

## 触发条件

- 用户使用 `/建报表` 或 `/建看板` 命令
- 用户表达「做成报表/看板」「沉淀成 panel」「保存到 FunnyDB」「建个看板监控」等意图

---

## 边界

- **要做**：拿已校验 query → 构造/获取 data_setting → 建 panel → 验证出数 → 可选编排 dashboard → 上报 URL；治理命名/空间/description
- **不做**：写口径、探查、抽样校验（那是 **ds-skill** 的活，作为前置依赖）；不做分析、不下结论

> 取数（ds）交付一次性 CSV 给分析师用完即弃；报表沉淀（本技能）交付**持久化 BI 资产**给团队长期看。两者方法论同源、交付物不同。

---

## 前置依赖

1. **Python ≥ 3.8**
2. **funnydb skill** 已安装授权（与 ds-skill 同一个）：创建接口走它的 `panels/create` / `dashboards/create`
3. **ds-skill**（强依赖）：提供**已校验的 query**（raw_sql 的 SQL，或非 raw_sql 模型的 `data_setting`）。
   - **铁律：未经校验的 query 禁止建 panel。** 脏看板长期误导团队，危害远大于一次性错 CSV。
4. **app_id**：不猜，未指定先 `apps/list` 或问用户

---

## 完整执行流程

```
Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6
拿已校验   定模型+    治理三件套   建 panel   可选建      上报
 query     data_setting (命名/空间/desc) +验证出数  dashboard   URL
```

### Step 1：拿到已校验的 query

来源二选一：
- **来自 ds-skill**（推荐）：ds 跑完探查 + 抽样校验、交付了主查询 SQL（raw_sql），或 `analyse/query` 返回的 `data_setting`（其它模型）。
- **用户直接给现成 query**：必须确认它**已被校验**（口径对、数值核过）。没校验 → 退回让 ds 先校验，别直接建。

> 这一步不写口径、不调口径。只接收「可信的查询」。

### Step 2：确定 event_model + 构造/获取 data_setting

支持的模型：`event` / `retention` / `ltv` / `raw_sql` / `distribution` / `funnel` / `interval`（详见 [references/data-setting-schema.md](references/data-setting-schema.md)）。

- **raw_sql**：把 SQL 落成 `.sql` 文件即可（脚本自动转义反引号和 `$`）。
  - **SQL 书写规范统一**：遵循 ds-skill 的 [`references/clickhouse-sql-conventions.md`](../ds-skill/references/clickhouse-sql-conventions.md)（命名、缩进、系统字段反引号、左连接、不做展示格式化等）。
  - **⚠️ 与 ds 唯一的差异——日期**：ds 取数写**静态日期**（一次性落 CSV，禁用模板占位符）；**panel 必须用动态日期** `${dt:date}`（报表常驻刷新）。这是两个技能最关键的分野。
  - 默认动态：SQL 日期过滤处写 `${dt:date}`，脚本自动生成 dt 变量（`--date-start-offset`/`--date-end-offset` 控制窗口，默认近7天到昨天）。要写死日期需显式 `--static-date`。
  - 复杂变量（平台/模式/段位 selector）：从同类现成 panel 的 `panels/details` 拷 `variables[]` 改造，用 `--variables-file` 完整接管。
- **非 raw_sql**：**不要手搓** `data_setting`，直接复用 ds `analyse/query` 返回的 `data_setting`，落成 JSON 文件。

### Step 3：治理三件套（建库前必做）

按 [references/naming-governance.md](references/naming-governance.md)：

1. **命名**：`[前缀] 业务域-指标-粒度`，**业务域用现有看板目录的标准叫法**（经典派对/摸金/BR…），与飞书 wiki 看板目录统一、能对号入座到对应空间。具体可检索、防重名（重名会被自动加 `(1)`）。
2. **空间/防污染**：测试产物用 `AI测试-` 前缀且用完即删；正式沉淀用 `AI-` 前缀。看板默认落当前用户私有空间。
3. **description（必填）**：格式 `主要内容：<口径/回答什么问题>。核心指标：<列名>`。
   - **这是与 ds 看板检索的闭环**：ds 已改为 description-优先检索；不写 description 就是给下游挖坑。

### Step 4：建 panel + 验证出数

```bash
# 假设 panel-skill 装在 .claude/skills/panel，funnydb 装在 .claude/skills/funnydb
# 默认动态日期：SQL 里日期过滤处写 ${dt:date}，下面 --date-* 控制窗口
PYTHONIOENCODING=utf-8 python -X utf8 \
  .claude/skills/panel/scripts/create_panel.py \
  --app-id <APP_ID> \
  --funnydb-dir <funnydb skill 路径> \
  --title "AI-<业务域-指标-粒度>" \
  --event-model raw_sql \
  --sql-file <path/to/panel.sql> \
  --date-start-offset 7 --date-end-offset 1 \
  --description "主要内容：...。核心指标：..."
```

- 脚本只传 `data_setting`，**不传 `setting`**（服务端生成）。
- **默认动态日期**：SQL 必须含 `${dt:date}`，否则脚本报错提示（要静态日期加 `--static-date`）。
- 建完默认 `panels/data` 拉一次数验证（`--no-verify` 可关）：**0 行或语法错多半是反引号/`$` 被 shell 吃**（见踩坑），脚本已自动转义。
- 非 raw_sql：`--event-model <模型> --data-setting-file <json>`。

### Step 5（可选）：编排 dashboard

```bash
PYTHONIOENCODING=utf-8 python -X utf8 \
  .claude/skills/panel/scripts/create_dashboard.py \
  --app-id <APP_ID> --funnydb-dir <funnydb skill 路径> \
  --name "AI-<看板名>" \
  --panel-ids 19404,19406
```

- **`dashboards/create` 永远新建**：传已有 `dashboard_id` 也会被忽略另建新看板。
- **没有「追加 panel」接口**：要把多个 panel 放一个看板，必须这一次把 `panel_ids` 全列上。

### Step 6：上报

回给用户：
1. **panel**：`panel_id` + `title` + `panel_url`（+ 验证出数的预览）
2. **dashboard**（若建）：`dashboard_id` + `name` + `dashboard_url` + 包含的 `panel_ids`
3. **不硬编码域名、不伪造 URL** —— 只用接口真实返回的 URL；失败就报原始错误。

---

## 铁律

1. **未校验的 query 不准建 panel** —— 前置交给 ds，建错口径的常驻看板是长期事故
2. **panel 用动态日期 `${dt:date}`，不写死日期** —— 报表常驻刷新（与 ds 取数写静态日期相反）
3. **raw_sql 反引号和 `$` 必须转义** —— 反引号转 `\u0060`、`$` 转 `\u0024`，脚本已自动；手动 inline 调接口是头号事故源
4. **SQL 书写遵循 ds 的 clickhouse-sql-conventions** —— 除日期用动态外，其余规范与 ds 一致
5. **只传 data_setting，不传 setting** —— 前端配置由服务端生成
6. **description 必填且按格式** —— 主要内容（口径）+ 核心指标（列名），与 ds 检索闭环
7. **命名与看板目录统一** —— 业务域用现有空间/文件夹的标准叫法，对齐飞书 wiki
8. **dashboards/create 不能追加** —— 多 panel 一次性 `panel_ids` 带全
9. **prod 防污染** —— 测试加 `AI测试-` 前缀用完即删，正式加 `AI-` 前缀，默认落私有空间
10. **URL 不硬编码、不伪造** —— 只上报接口真实返回值

---

## 常见踩坑速查

| 问题 | 解决 |
|---|---|
| panel 建成但拉数 0 行 / 语法错（`='xxx'` 前字段没了） | 反引号被 WSL bash -c 吃空，payload 里反引号要转 `\u0060`；用脚本即自动 |
| 动态日期 panel 拉数报 `and  and` 语法错 | `${dt:date}` 的 `$` 被 shell 吃空，要转 `\u0024`；脚本已自动转义 |
| `${dt:date}` 拉数解析失败 | dt 变量 param 缺 start_time/end_time 兜底；脚本按 offset 自动补 |
| 传了 dashboard_id 却新建了看板 | 接口不支持追加，永远新建；多 panel 一次性 `panel_ids` 带全 |
| panel/看板重名 | 自动加 `(1)` 后缀不报错；命名要具体 |
| 下游 ds 检索不到我建的报表 | description 没写或太水；按「主要内容+核心指标」写清口径 |
| 命名和人工报表对不上 | 业务域用现有目录标准叫法，别自造同义词；对照飞书 wiki |
| 返回 URL 缺域名 | app 站点配置不可用，路径仍是前端路由，可补域名前缀，别伪造 |
| 非 raw_sql 模型 data_setting 难搓 | 别手搓，复用 ds `analyse/query` 返回的 data_setting |

---|---|
| panel 建成但拉数 0 行 / 语法错（`='xxx'` 前字段没了） | 反引号被 WSL bash -c 吃空，payload 里反引号要转 `\u0060`；用脚本即自动 |
| 传了 dashboard_id 却新建了看板 | 接口不支持追加，永远新建；多 panel 一次性 `panel_ids` 带全 |
| panel/看板重名 | 自动加 `(1)` 后缀不报错；命名要具体 |
| 下游 ds 检索不到我建的报表 | description 没写或太水；按「主要内容+核心指标」写清口径 |
| 返回 URL 缺域名 | app 站点配置不可用，路径仍是前端路由，可补域名前缀，别伪造 |
| 非 raw_sql 模型 data_setting 难搓 | 别手搓，复用 ds `analyse/query` 返回的 data_setting |

---

## 关键文件

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 本文档（工作流入口） |
| `scripts/funnydb_client.py` | 共享 FunnyDB 调用封装（Git Bash 定位 + 反引号 `\u0060` 转义） |
| `scripts/create_panel.py` | 建 panel + 建完验证出数 |
| `scripts/create_dashboard.py` | 建 dashboard（编排已有 panel） |
| `references/create-api-spec.md` | 创建接口规范 + 实测约束（反引号/不可追加/私有空间…） |
| `references/data-setting-schema.md` | 各 event_model 的 data_setting 结构速查 |
| `references/naming-governance.md` | 命名/空间/description 治理规范 |
| `examples/sample-panel/` | 示例 SQL + 创建命令 |
