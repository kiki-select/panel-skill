"""
创建 FunnyDB dashboard（把若干已建 panel 编排进一个看板）。

核心约束（详见 references/create-api-spec.md）：
- dashboards/create 永远「新建」：即使传已有 dashboard_id 也会被忽略、另建新看板（名字加 "(1)"）。
- 没有「往已有看板追加 panel」的接口 —— 想把多个 panel 放一个看板，
  必须在创建这一次把 panel_ids 全列上。
- 看板创建在当前登录用户的「私有空间」。

用法：
  python create_dashboard.py \
      --app-id 42 --funnydb-dir <funnydb skill 路径> \
      --name "AI-登录监控看板" \
      --panel-ids 19404,19406

环境变量回退：FUNNYDB_APP_ID / FUNNYDB_SKILL_DIR
"""
import argparse
import sys

import funnydb_client as fc

CREATE_PATH = "/api/v1/open/skillhub/tools/dashboards/create"


def main() -> None:
    p = argparse.ArgumentParser(description="创建 FunnyDB dashboard")
    p.add_argument("--app-id", type=int, default=None)
    p.add_argument("--funnydb-dir", type=str, default=None)
    p.add_argument("--name", required=True, help="看板名（命名规范见 references/naming-governance.md）")
    p.add_argument("--panel-ids", default="",
                   help="逗号分隔的 panel_id 列表，建库时一次性带入（无追加接口）")
    args = p.parse_args()

    app_id, funnydb_dir = fc.resolve_env(args.app_id, args.funnydb_dir)

    panel_ids = [int(x) for x in args.panel_ids.split(",") if x.strip()]
    payload = {"app_id": app_id, "name": args.name}
    if panel_ids:
        payload["panel_ids"] = panel_ids

    resp = fc.call(funnydb_dir, CREATE_PATH, payload)
    print("=== dashboard 创建成功 ===")
    print(f"dashboard_id : {resp.get('dashboard_id')}")
    print(f"name         : {resp.get('name')}")
    print(f"dashboard_url: {resp.get('dashboard_url')}")
    print(f"panel_ids    : {resp.get('panel_ids')}")

    returned_name = resp.get("name", "")
    if returned_name.endswith(")") and "(" in returned_name and returned_name != args.name:
        print()
        print(f"⚠️ 注意：返回名是 {returned_name!r}，与你给的 {args.name!r} 不同 —— "
              "可能重名被自动加后缀，或你试图追加到已有看板（该接口不支持，只会新建）。")


if __name__ == "__main__":
    main()
