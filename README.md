# 崩坏：星穹铁道卡池追踪服务

该项目自动从biligame维基爬取崩坏：星穹铁道的卡池信息，并通过API提供JSON格式的数据。

## 功能

- 每天自动更新卡池数据（北京时间10:00和22:00）
- 提供最新卡池信息（角色池、光锥池）
- 提供版本更新信息（当前版本、前瞻直播日期、下版本更新时间）

## API 端点

- 最新数据：`https://zisekongling.github.io/hsr-wish-tracker/api/hsr_wish`
- 原始数据文件：`https://raw.githubusercontent.com/zisekongling/hsr-wish-tracker/master/data.json`

## 部署到本地

1. 克隆仓库：
   ```bash
   git clone https://github.com/zisekongling/hsr-wish-tracker.git
   cd hsr-wish-tracker
