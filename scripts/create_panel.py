"""
创建 FunnyDB panel（把已校验的 query 持久化成报表）。

核心约束（详见 references/create-api-spec.md）：
- 只传 data_setting（后端 query），不传 setting（服务端自动生成前端配置）
- raw_sql 的反引号由 funnydb_client.escape_payload 自动转 \u0060
- 强制 description（主要内容 + 核心指标），与 ds 看板检索的 description-优先闭环
- 默认用动态日期 ${dt:date}（panel 常驻刷新），SQL 里写死日期需显式 --static-date
- 建完默认验证一次出数（--no-verify 可关）

用法 A（raw_sql + 动态日期，最常用）:
  # SQL 里日期过滤处写 ${dt:date}，默认近7天到昨天，可用 --date-* 调
  python create_panel.py \
      --app-id 42 --funnydb-dir <funnydb skill 路径> \
      --title "AI-经典模式-逐日登录账号数" --event-model raw_sql \
      --sql-file panel.sql \
      --description "主要内容：xxx。核心指标：xxx"

用法 B（其它 event_model：event/retention/ltv/distribution/funnel/interval）:
  传一个完整的 data_setting JSON 文件（通常来自 ds 的 analyse/query 返回的 data_setting）:
  python create_panel.py \
      --app-id 42 --funnydb-dir <...> \
      --title "..." --event-model event \
      --data-setting-file ds_data_setting.json \
      --description "主要内容：...。核心指标：..."

环境变量回退：FUNNYDB_APP_ID / FUNNYDB_SKILL_DIR
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import funnydb_client as fc

CREATE_PATH = "/api/v1/open/skillhub/tools/panels/create"
DATA_PATH = "/api/v1/open/skillhub/tools/panels/data"
ALLOWED_MODELS = ("event", "retention", "ltv", "raw_sql", "distribution", "funnel", "interval")

# 动态日期模板占位符（panel 常驻刷新必须用它，而非写死日期）
DT_TEMPLATE = "${dt:date}"


def build_dt_variable(args) -> dict:
    """构造标准动态日期变量 ${dt:date}：start_offset 天前 ~ end_offset 天前，按 granularity 取整。

    dynamic_* 是动态刷新的真正来源；start_time/end_time 是快照兜底值（缺了会导致 ${dt:date}
    在 panels/data 拉数时解析失败），按 offset 相对今天算出具体起止填上。
    """
    today = datetime.now()
    start = (today - timedelta(days=args.date_start_offset)).strftime("%Y-%m-%d 00:00:00")
    end = (today - timedelta(days=args.date_end_offset)).strftime("%Y-%m-%d 23:59:59")
    return {
        "name": args.date_var_name,
        "type": "dt",
        "title": "日期",
        "param": {
            "dynamic_start_value": args.date_start_offset,
            "dynamic_end_value": args.date_end_offset,
            "dynamic_granularity": args.date_granularity,
            "start_time": start,
            "end_time": end,
        },
    }


def build_data_setting(args) -> dict:
    if args.event_model == "raw_sql":
        if not args.sql_file:
            sys.exit("error: event_model=raw_sql 需要 --sql-file")
        sql = Path(args.sql_file).read_text(encoding="utf-8")

        # 变量来源优先级：显式 variables-file > 默认动态日期 > 静态(空)
        if args.variables_file:
            variables = json.loads(Path(args.variables_file).read_text(encoding="utf-8"))
        elif args.static_date:
            variables = []
        else:
            # 默认走动态日期：SQL 必须用 ${dt:date} 占位，否则变量不生效
            if DT_TEMPLATE not in sql:
                sys.exit(
                    f"error: 默认按动态日期建 panel，SQL 里必须含占位符 {DT_TEMPLATE}（放在 where 的日期过滤处）。\n"
                    f"       若确实要写死日期，请显式加 --static-date。"
                )
            variables = [build_dt_variable(args)]

        return {
            "datasource": "clickhouse",
            "events": {"sql": sql},
            "event_view": {"variables": variables},
        }
    # 非 raw_sql：必须给完整 data_setting（建议直接复用 ds analyse/query 的返回）
    if not args.data_setting_file:
        sys.exit(f"error: event_model={args.event_model} 需要 --data-setting-file（完整 data_setting JSON）")
    return json.loads(Path(args.data_setting_file).read_text(encoding="utf-8"))


# 埋点/技术细节泄漏关键词：description 是给业务看的，出现这些多半写错了
LEAK_TOKENS = [
    "login_type", "event", "_log", "${", "pid", "select ", "where ", "count(",
    "group by", "#dt", "#event", "=0", "= 0",
    "近7天", "近 7 天", "天窗口", "动态", "时间窗口", "日期范围",
]


def build_description(args) -> str:
    """组装并校验 description：主要内容 + 核心指标，强制分行。"""
    main = (args.main_content or "").strip()
    metrics = (args.core_metrics or "").strip()

    if main or metrics:
        if not (main and metrics):
            sys.exit("error: --main-content 与 --core-metrics 需成对提供")
        # 去掉用户可能自带的前缀，统一拼装
        main = main.replace("主要内容：", "").replace("主要内容:", "").strip()
        metrics = metrics.replace("核心指标：", "").replace("核心指标:", "").strip()
        desc = f"主要内容：{main}\n核心指标：{metrics}"
    elif args.description:
        desc = args.description.strip()
        # 自动补「核心指标」前的换行（业务展示要分行）
        for tag in ("核心指标：", "核心指标:"):
            if tag in desc:
                before, after = desc.split(tag, 1)
                if not before.rstrip().endswith("\n") and not before.endswith("\n"):
                    desc = before.rstrip() + "\n" + tag + after
                break
    else:
        sys.exit("error: 必须提供 --main-content + --core-metrics（推荐）或 --description")

    # 业务化校验：主要内容里不该出现埋点/技术细节/时间窗口
    main_part = desc.split("核心指标")[0]
    hits = [t for t in LEAK_TOKENS if t.lower() in main_part.lower()]
    if hits:
        sys.stderr.write(
            "⚠️ 警告：description「主要内容」疑似含埋点/技术细节或时间窗口，业务看不懂："
            f" {hits}\n   description 应围绕 panel 内容+业务目的，参考飞书《数据看板目录》I 列写法。\n"
        )
    return desc


def main() -> None:
    p = argparse.ArgumentParser(description="创建 FunnyDB panel")
    p.add_argument("--app-id", type=int, default=None)
    p.add_argument("--funnydb-dir", type=str, default=None)
    p.add_argument("--title", required=True, help="panel 标题（命名规范见 references/naming-governance.md）")
    p.add_argument("--event-model", default="raw_sql", choices=ALLOWED_MODELS)
    # description：推荐分别传 主要内容 + 核心指标，脚本按「主要内容：…\n核心指标：…」拼装
    p.add_argument("--main-content", default=None,
                   help="主要内容（业务化）：围绕 panel 内容+目的，「统计…，用于…」。禁埋点细节/事件名/过滤条件/时间窗口")
    p.add_argument("--core-metrics", default=None,
                   help="核心指标：顿号(、)分隔的业务化指标/维度名，与列标题对齐")
    p.add_argument("--description", default=None,
                   help="（高级）直接给完整 description，会自动补 主要内容/核心指标 之间的换行")
    p.add_argument("--sql-file", type=str, default=None, help="raw_sql 的 .sql 文件")
    p.add_argument("--variables-file", type=str, default=None,
                   help="可选，完整接管 event_view.variables[]（含 dt + selector 等复杂变量时用）")
    p.add_argument("--data-setting-file", type=str, default=None, help="非 raw_sql 模型的完整 data_setting JSON")
    # 动态日期（默认开启；SQL 用 ${dt:date} 占位）
    p.add_argument("--static-date", action="store_true",
                   help="关闭默认动态日期，按 SQL 里写死的日期建（不推荐，panel 应常驻刷新）")
    p.add_argument("--date-var-name", default="date", help="动态日期变量名，默认 date")
    p.add_argument("--date-start-offset", type=int, default=7,
                   help="动态起始：N 天前，默认 7（近7天）")
    p.add_argument("--date-end-offset", type=int, default=1,
                   help="动态结束：N 天前，默认 1（到昨天）")
    p.add_argument("--date-granularity", default="day", choices=("day", "week", "month"),
                   help="动态日期粒度，默认 day")
    p.add_argument("--no-verify", action="store_true", help="跳过建完拉数验证")
    args = p.parse_args()

    app_id, funnydb_dir = fc.resolve_env(args.app_id, args.funnydb_dir)

    description = build_description(args)
    data_setting = build_data_setting(args)
    payload = {
        "app_id": app_id,
        "title": args.title,
        "event_model": args.event_model,
        "description": description,
        "data_setting": data_setting,
    }

    resp = fc.call(funnydb_dir, CREATE_PATH, payload)
    panel_id = resp.get("panel_id")
    print("=== panel 创建成功 ===")
    print(f"panel_id  : {panel_id}")
    print(f"title     : {resp.get('title')}")
    print(f"panel_url : {resp.get('panel_url')}")

    if args.no_verify or panel_id is None:
        return

    # 验证：拉一次数据，确认 SQL/口径真能跑（避免存进去是坏 SQL）
    print()
    print("=== 验证出数 ===")
    data = fc.call(funnydb_dir, DATA_PATH, {"app_id": app_id, "panel_id": panel_id})
    total = data.get("total_count")
    rows = data.get("rows", [])
    if not rows:
        print(f"⚠️ 警告：panel 建成但拉数 0 行（total_count={total}）。检查 SQL/口径/日期。")
        return
    cols = [c["name"] if isinstance(c, dict) else c for c in data.get("columns", [])]
    print(f"total_count={total}，预览前 5 行：")
    print("| " + " | ".join(map(str, cols)) + " |")
    print("|" + "|".join(["---"] * len(cols)) + "|")
    for row in rows[:5]:
        print("| " + " | ".join("" if v is None else str(v) for v in row) + " |")


if __name__ == "__main__":
    main()
