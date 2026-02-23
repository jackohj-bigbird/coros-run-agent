# 跑步 AI Agent（COROS PACE 3）

这个项目是给你当前目标定制的：
- 目标比赛：**半马**
- 目标成绩：**1:40（100分钟）**
- 比赛日期：**2026-05-01**
- 每周训练日：**周二 / 周四 / 周六 / 周日**
- 提醒渠道：**邮件**

## 当前功能（MVP）
- 从 Strava 拉取跑步数据（你只需要把 COROS 同步到 Strava）
- 支持 Strava Webhook（跑步上传后自动回调入库）
- 生成半马训练计划（自动按目标配速计算）
- 产出每周训练总结
- 对话式问答（支持 AI，对应 OPENAI_API_KEY）
- 邮件提醒（训练日提醒 + 周总结）

## 1. 安装
```bash
cd /Users/jackou/Desktop/Personal/coros-run-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 2. 配置 `.env`
你至少要填这些：
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_REFRESH_TOKEN`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`

可选：
- `OPENAI_API_KEY`（启用自然语言 AI 对话）
- `STRAVA_WEBHOOK_VERIFY_TOKEN`（用于 Strava 回调校验）
- `STRAVA_WEBHOOK_CALLBACK_URL`（公网可访问地址，例如 `https://xxx.ngrok-free.app/webhook/strava`）
- `CORS_ORIGINS`（前端域名白名单，多个用逗号分隔；本地开发可先用 `*`）
- `ENABLE_SCHEDULER`（是否启用内置定时任务，Render free 建议 `false`）

### Strava 权限注意
如果你发现同步报 `401 Unauthorized`，通常是 token scope 只有 `read`，缺少活动读取权限。  
需要重新授权拿到包含 `activity:read_all` 的 refresh token。

```bash
cd /Users/jackou/Desktop/Personal/coros-run-agent
source .venv/bin/activate
python scripts/strava_oauth_helper.py \
  --client-id 你的ClientID \
  --client-secret 你的ClientSecret
```

打开脚本打印的 URL，授权后从回调地址里复制 `code` 参数，再执行：

```bash
python scripts/strava_oauth_helper.py \
  --client-id 你的ClientID \
  --client-secret 你的ClientSecret \
  --code 这里填code
```

把输出里的 `refresh_token` 覆盖到 `.env` 的 `STRAVA_REFRESH_TOKEN`。

## 3. 启动服务
```bash
cd /Users/jackou/Desktop/Personal/coros-run-agent
source .venv/bin/activate
uvicorn app.main:app --reload
```

## 4. 一次性初始化训练计划
```bash
curl -X POST http://127.0.0.1:8000/plan/setup \
  -H 'Content-Type: application/json' \
  -d '{
    "start_date":"2026-02-22",
    "race_date":"2026-05-01",
    "target_time_min":100
  }'
```

## 5. 常用接口
1. 健康检查
```bash
curl http://127.0.0.1:8000/health
```

2. 手动同步 Strava 跑步
```bash
curl -X POST http://127.0.0.1:8000/sync/strava
```

3. 查看训练计划
```bash
curl http://127.0.0.1:8000/plan
```

4. 查看本周总结
```bash
curl http://127.0.0.1:8000/summary/weekly
```

5. 对话问答
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"我这周状态怎么样，下次跑什么？"}'
```

6. 发送测试邮件
```bash
curl -X POST http://127.0.0.1:8000/reminder/test
```

7. 注册 Strava Webhook（需要先配置公网回调）
```bash
curl -X POST http://127.0.0.1:8000/webhook/strava/register
```

8. 查看当前 Webhook 订阅
```bash
curl http://127.0.0.1:8000/webhook/strava/subscriptions
```

## 6. 自动任务说明
服务启动后会自动调度：
- 每天 06:10 同步 Strava
- 每天 19:00 检查今天是否是训练日，是则发提醒
- 每周日 20:30 发周总结

时区默认 `Asia/Shanghai`，可在 `.env` 里改。

## 7. 开通 Webhook 自动同步
Strava Webhook 需要你的回调地址是公网 HTTPS。你本地开发可用 ngrok。

1. 启动本地服务
```bash
cd /Users/jackou/Desktop/Personal/coros-run-agent
source .venv/bin/activate
uvicorn app.main:app --reload
```

2. 开 ngrok 隧道（把公网请求转发到本地 8000）
```bash
ngrok http 8000
```

3. 把 ngrok 给出的 HTTPS 地址写入 `.env`
```env
STRAVA_WEBHOOK_CALLBACK_URL=https://你的ngrok域名/webhook/strava
STRAVA_WEBHOOK_VERIFY_TOKEN=你自定义一串随机字符串
```

4. 重启服务后注册订阅
```bash
curl -X POST http://127.0.0.1:8000/webhook/strava/register
```

5. 验证订阅是否成功
```bash
curl http://127.0.0.1:8000/webhook/strava/subscriptions
```

订阅成功后，你上传新活动到 Strava，会触发 `POST /webhook/strava` 自动入库。

## 8. Netlify 网页部署
本项目已经包含可直接部署到 Netlify 的前端目录：`web/`。

1. 在 Netlify 新建站点，项目根目录选 `/Users/jackou/Desktop/Personal/coros-run-agent`
2. Build command 留空（纯静态）
3. Publish directory 填 `web`
4. 部署后打开网页，在「连接设置」里填你的后端 API 域名
5. 后端 `.env` 里把 `CORS_ORIGINS` 改成你的 Netlify 域名，例如：
```env
CORS_ORIGINS=https://your-site.netlify.app
```

本地预览网页：
```bash
cd /Users/jackou/Desktop/Personal/coros-run-agent
python3 -m http.server 5173 -d web
```
然后打开 `http://127.0.0.1:5173`。

## 9. Render 长期后端部署
项目根目录已经提供 `render.yaml`，可在 Render 用 Blueprint 一键创建后端服务和 Postgres。

1. 把项目推到 GitHub（不要提交 `.env`）
2. 打开 Render -> `New` -> `Blueprint`
3. 选择这个仓库，Render 会自动识别 `render.yaml`
4. 创建后进入 Web Service，补齐密钥类环境变量（参考 `render.env.example`）
5. 首次部署成功后，你会得到固定后端域名：`https://<your-service>.onrender.com`
6. 把 Netlify 页面里的后端地址改成这个域名
7. 把 `STRAVA_WEBHOOK_CALLBACK_URL` 设为：
```env
STRAVA_WEBHOOK_CALLBACK_URL=https://<your-service>.onrender.com/webhook/strava
```
8. 调用注册接口：
```bash
curl -X POST https://<your-service>.onrender.com/webhook/strava/register
```

如果你不想用 Blueprint，也可以手工建 Web Service，并使用：
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

## 10. 注意
- COROS 官方 API 申请可能需要审批，MVP 先使用 `COROS -> Strava -> 本服务`。
- 训练建议仅用于运动参考，如有伤病请先咨询医生或专业教练。
