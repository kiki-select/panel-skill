select `#dt` as "日期", count(distinct pid) as "登录账号数"
  from events
  where `#event` = 'gameserver_login'
    and ${dt:date}
    and login_type = 0
  group by 1
  order by 1
