# IP 趋势雷达

每天自动采集北美和中国市场的公开数据，找出关注度正在加速上升的 IP，生成每个地区的上升榜：

- **网页看板**：<https://zhuangdanfa.github.io/ip-radar/>（排行、筛选、每个 IP 近一年的趋势图）
- **Markdown 版**：北美 [`reports/latest.md`](reports/latest.md)，中国 [`reports/cn/latest.md`](reports/cn/latest.md)

这是 4 周原型的第一阶段：先用 4 个官方或公开的数据源，覆盖约 50 个种子 IP，验证「动量分」能不能提前发现走红的 IP。

## 数据源

| 数据源 | 采集内容 | 需要密钥 | 历史数据 |
| --- | --- | --- | --- |
| Wikipedia | 英文条目每日浏览量 | 不需要 | 可回溯到 2015 年，第一次运行就能回测 |
| Google Trends | 美国搜索热度（近 12 个月，每周一个点） | 不需要 | 近 12 个月 |
| YouTube | 近 7 天相关视频数、播放量前 50 视频的总播放量 | `YOUTUBE_API_KEY` | 只能从开始采集那天起累积 |
| Reddit | 近 7 天提及帖子数和互动量、相关板块订阅数 | `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET` | 只能从开始采集那天起累积 |
| B站（中国） | 近 7 天相关新视频数和这些视频的总播放量 | 不需要 | 新视频数可回填约 26 周，播放量从开始采集那天起累积 |

没设置密钥的数据源会自动跳过，不影响其他数据源。

## 它怎么运行

不需要自己的服务器。GitHub Actions 每天北京时间 18:00 运行一次（`.github/workflows/daily.yml`）：

1. 采集数据，追加到 `data/metrics.csv`
2. 计算动量分，生成 `reports/latest.md` 和 `data/scores_latest.json`
3. 把更新提交回仓库
4. 采集完成后，「发布网页看板」（`.github/workflows/pages.yml`）重新生成网页看板并发布到 GitHub Pages

## 第一次使用

0. **打开网页看板**：仓库 **Settings → Pages**，「Build and deployment」下的 Source 选 **GitHub Actions**。然后在 Actions 页面运行一次「发布网页看板」，看板地址见本页顶部。
1. **回填历史数据**：打开仓库的 **Actions** 页面，选「每日采集与上升榜」，点 **Run workflow**，「回溯天数」填 `400`，「数据源」填 `wikipedia,trends`，运行。几分钟后 `reports/latest.md` 就会出现第一份上升榜。
2. **加上 YouTube**：在 [Google Cloud Console](https://console.cloud.google.com/) 新建项目，启用 YouTube Data API v3，创建一个 API 密钥。
3. **加上 Reddit**：在 [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) 创建一个 *script* 类型的应用，记下 client id 和 secret。
4. **保存密钥**：仓库 **Settings → Secrets and variables → Actions → New repository secret**，分别添加 `YOUTUBE_API_KEY`、`REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET`。之后每天的自动运行就会带上这两个数据源。

## 动量分怎么算

对每个 IP 的每个指标，按周汇总后计算：

- **增速**：近 4 周均值相对前 4 周均值的对数变化，至少需要 8 周数据
- **加速度**：本期增速减去 4 周前的增速，至少需要 12 周数据
- **广度**：有指标增速超过约 10% 的数据源占比，多个平台同时上升比单一平台更可信

原始分 = 0.45 × 增速 + 0.25 × 加速度 + 0.30 × 广度，再换算成这批 IP 里的 0–100 排名。权重是初始值，回测后再调。

阶段：增速超过约 22% 时，关注度在后一半为「萌芽」，前一半为「爆发」；增速低于约 −18% 为「衰退」；其余为「成熟」或「平稳」。

## 本地运行

```bash
pip install -r requirements-dev.txt
python -m ipradar collect --sources wikipedia,trends --days 400   # 采集
python -m ipradar report                                          # 生成上升榜
python -m ipradar site && python -m http.server -d _site 8000     # 生成网页看板，浏览器打开 localhost:8000
python -m ipradar backtest labubu --weeks 52                      # 看某个 IP 过去每周的排名
python -m pytest -q                                               # 测试
```

## 地区

| 地区 | 种子清单 | 数据 | 数据源 |
| --- | --- | --- | --- |
| 北美 `na` | `seeds/na_seed.csv` | `data/metrics.csv` | Wikipedia、Google Trends、YouTube、Reddit |
| 中国 `cn` | `seeds/cn_seed.csv` | `data/cn/metrics.csv` | B站 |

命令行加 `--region cn` 处理中国，例如 `python -m ipradar collect --region cn --days 180`。中国的抖音、小红书、微博、百度指数没有免费开放的接口，需要商业合作或第三方数据服务，接入后作为新的数据源加进来。

## 增加或修改种子 IP

编辑对应地区的种子清单（北美 [`seeds/na_seed.csv`](seeds/na_seed.csv)，中国 [`seeds/cn_seed.csv`](seeds/cn_seed.csv)），每行一个 IP：

| 列 | 说明 |
| --- | --- |
| `ip_id` | 唯一英文 ID，如 `labubu` |
| `name_zh` / `name_en` | 中英文名 |
| `type` | 类型，如 动画、游戏、潮玩角色 |
| `wikipedia_title` | 英文 Wikipedia 条目标题，重定向会自动解析，找不到会在日志里提示 |
| `search_term` | 搜索词：北美用于 Google Trends、YouTube、Reddit；中国用于 B站搜索 |
| `subreddit` | 相关的 Reddit 板块，没有可留空 |

## 已知限制

- Wikipedia 浏览量是全球英文读者，不只美国。
- Google Trends 用的是非官方库 pytrends，可能被限速，失败时当天跳过，不影响其他数据源。
- B站数据来自网页搜索的公开接口，没有官方承诺，接口变动或限流时当天跳过；每个 IP 每周最多数 200 条新视频，特别热门的 IP 会封顶。
- Reddit 免费接口面向非商业用途，公司长期使用前需确认 Reddit 的数据使用条款。
- YouTube 免费配额每天 10,000 单位，每个 IP 约用 101 单位，种子 IP 超过约 90 个时需要申请提高配额。
