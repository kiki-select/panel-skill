# data_setting 结构速查（按 event_model）

创建 panel 只传后端 `data_setting`，服务端据此生成前端 `setting`。不同 `event_model` 的 `data_setting` 结构不同。

## raw_sql（本技能最常用，自己写 SQL）

```json
{
  "datasource": "clickhouse",
  "events": { "sql": "<ClickHouse SQL>" },
  "event_view": { "variables": [] }
}
```

- `events.sql`：完整 SQL。系统字段（#dt/#event/#time）用反引号；脚本会自动把反引号转成 `\u0060` 转义。
- 静态日期：直接 `` `#dt` between '2026-06-01' and '2026-06-07' ``。
- 动态/可交互日期：SQL 里用 `${dt:date}` 模板，并在 `event_view.variables[]` 声明变量：

```json
{
  "event_view": {
    "variables": [
      {
        "name": "date", "type": "dt", "title": "日期",
        "param": { "dynamic_start_value": 7, "dynamic_end_value": 1, "dynamic_granularity": "day" }
      }
    ]
  }
}
```

> selector 类变量（平台/模式/段位）结构较复杂，建议从一个**现成同类 panel** 的 `panels/details`
> 拷贝 `data_setting.event_view.variables[]` 改造，不要从零手搓。

## 非 raw_sql 模型（event / retention / ltv / distribution / funnel / interval）

**不要手搓**。正确姿势：让 ds-skill 用 funnydb `analyse/query` 跑出对应模型的分析，
直接复用它返回的 `data_setting`，原样传给 `panels/create`。

- ds 文档：`docs/get --data '{"index":"analyse"}'` 及其子文档（analyse_event / analyse_retention / ...）
- `analyse/query` 返回里通常带 saveable 的 `data_setting`，落成 JSON 文件后用
  `create_panel.py --event-model <模型> --data-setting-file <文件>` 创建。

## 自定义公式指标

把 query-state 扁平化公式写进 `data_setting.events[].name`，例如：

```
login.total_times/pay.amount.sum
```

服务端会展开成前端 `setting.searchParams.events[].data`。
