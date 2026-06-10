# 示例：逐日登录账号数 panel

最小可跑示例，演示用 raw_sql 建 panel。

## 文件

- `panel.sql` —— 一段**动态日期**的 ClickHouse SQL：日期过滤处用 `${dt:date}` 占位
  （系统字段用反引号；脚本会自动转义反引号和 `$`）。panel 常驻刷新，默认就该动态日期。

## 建 panel

```bash
python ../../scripts/create_panel.py \
  --app-id 42 \
  --funnydb-dir <funnydb skill 路径> \
  --title "AI测试-经典派对-逐日登录账号数" \
  --event-model raw_sql \
  --sql-file panel.sql \
  --description "主要内容：统计指定日期范围逐日登录账号数。核心指标：日期、登录账号数"
```

成功后输出 `panel_id` / `panel_url`，并自动拉一次数验证（前 5 行预览）。

## 编排进看板

```bash
python ../../scripts/create_dashboard.py \
  --app-id 42 \
  --funnydb-dir <funnydb skill 路径> \
  --name "AI测试-登录监控看板" \
  --panel-ids <上一步返回的 panel_id>
```
