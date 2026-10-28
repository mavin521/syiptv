# syiptv

面向 PotPlayer、TiviMate、OTT Navigator 等播放器的 M3U 订阅；其他播放器请自行测试。

## 订阅列表

- [live.m3u（大陆频道）](https://raw.githubusercontent.com/mavin521/syiptv/main/live.m3u)
- [gat.m3u（香港、澳门、台湾频道）](https://raw.githubusercontent.com/mavin521/syiptv/main/gat.m3u)
- [migu.m3u（咪咕体育）](https://raw.githubusercontent.com/mavin521/syiptv/main/migu.m3u)
- [sports.m3u（综合体育）](https://raw.githubusercontent.com/mavin521/syiptv/main/sports.m3u)

也可使用 jsDelivr CDN，例如：
`https://cdn.jsdelivr.net/gh/mavin521/syiptv@main/live.m3u`

## 自动更新

GitHub Actions 每天自动运行一次，也支持在仓库的 **Actions → Update IPTV playlists → Run workflow** 中手动运行。生成的四个列表均会把仓库内的宣传链接固定放在第一条。

更新脚本会从公开来源聚合频道、按名称关键词分类、去重，并对频道地址做 HTTP 可访问性检查。HTTP 检查成功不代表流一定能播放；频道分类和可用性会随上游源变化。若所有来源均获取失败，脚本会停止并保留现有列表。
