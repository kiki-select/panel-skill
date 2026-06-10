# FunnyDB 创建 panel / dashboard 接口规范

来源：funnydb skill 文档 `create_dashboard_panel_skill`（`docs/get --data '{"index":"create_dashboard_panel_skill"}'`）。
本文件是该文档的中文要点固化 + 实测补充，避免每次重新拉文档。**接口若有变动以 funnydb 在线文档为准。**

## 总体流程

1. 确认 app_id（不猜，未指定先 `apps/list`）
2. 拿到 saveable 的 `data_setting`（raw_sql 自己写；其它模型复用 ds 的 `analyse/query` 返回）
3. `panels/create` 建 panel → 拿 `panel_id` / `panel_url`
4. 可选 `dashboards/create` 把 panel 编排进看板 → 拿 `dashboard_url`
5. 上报真实返回的 URL（不硬编码域名）

## panels/create

`POST /api/v1/open/skillhub/tools/panels/create`

请求体：
| 字段 | 说明 |
|---|---|
| `app_id` | 应用 ID |
| `title` | panel 标题（**用 `title` 不是 `name`**） |
| `event_model` | 分析模型，见下表 |
| `description` | panel 描述（**本技能强制必填**，格式见 naming-governance.md） |
| `data_setting` | 后端 query 负载 |

支持的 `event_model`：`event` / `retention` / `ltv` / `raw_sql` / `distribution` / `funnel` / `interval`

铁律：
- **只传 `data_setting`，不要传 `setting`** —— 前端 `setting` 由服务端从 `data_setting` 生成。
- **raw_sql 必须 `data_setting.events.sql`**；用到变量则附 `data_setting.event_view.variables[]`。
- 自定义公式指标：把 query-state 扁平化公式写进 `data_setting.events[].name`，如 `login.total_times/pay.amount.sum`，服务端会展开成前端 setting。

返回：`panel_id`、`panel_uid`、`title`、`event_model`、`panel_url`。

## dashboards/create

`POST /api/v1/open/skillhub/tools/dashboards/create`

请求体：
| 字段 | 说明 |
|---|---|
| `app_id` | 应用 ID |
| `name` | 看板名（**用 `name` 不是 `title`**） |
| `panel_ids` | 可选，要放进看板的已有 panel_id 列表 |

返回：`dashboard_id`、`dashboard_uid`、`name`、`dashboard_url`、`panel_ids`。

## ⚠️ 实测约束（文档没明说但务必知道）

1. **反引号 / 美元号坑（头号事故源）**：raw_sql 经 funnydb shim 的 WSL `bash -c` 传参时，
   shell 会吃掉两类字符：
   - 反引号 `\u0060`（命令替换）：如 `` `#dt` `` / `` `#event` `` 会被清空 → `='xxx'` 前字段没了
   - 美元号 `$`（变量展开）：如 `${dt:date}` 动态日期占位符会被整段清空 → `and  and` 语法错
   必须在 JSON payload 里把反引号转 `\u0060`、把 `$` 转 `\u0024`（JSON 解析后还原，但 shell 看不到真实字符）。
   脚本 `funnydb_client.escape_payload` 已自动处理两者；**手动 inline 调接口时务必注意**。
2. **dashboards/create 永远新建**：即使传 `dashboard_id` 也会被忽略、另建新看板（重名自动加 `(1)`）。
3. **没有「往已有看板追加 panel」的接口**：要把多个 panel 放一个看板，
   只能在 `dashboards/create` 这一次把 `panel_ids` 全列上。
4. **看板建在当前登录用户的私有空间**（不是公开业务空间）。
5. **title 重名**：panel 重名会自动加 `(1)` 后缀，不会报错 —— 命名要够具体。

## 失败排查

- `panels/create` 失败 → 核 `title` / `event_model` / `data_setting` 结构。
- 建成但 `panels/data` 拉数 0 行或语法错 → 多半是反引号被吃（SQL 里 `#dt`/`#event` 前字段没了）。
- dashboard 建失败 → 确认 panel_ids 属于同一 app、有权限。
- 返回 URL 缺 origin → app 站点配置不可用，路径仍是前端路由，可补域名前缀。
