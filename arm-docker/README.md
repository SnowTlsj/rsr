# RSR 串口采集上传 Agent

该目录是面向 ARM 工控机 / Docker 部署的独立采集 agent。

## 功能

- 读取 STM32 64 字节二进制串口帧
- 自动组帧、校验、重同步
- 自动创建 run / 停止 run
- 上传到 `/api/v1/ingest`
- 断网时缓存完整 payload，恢复后回放
- 长时间无有效帧自动结束任务
- 写心跳文件，便于外部 watchdog 检查

## 配置加载顺序

优先级从高到低：

1. 环境变量
2. `settings.json`
3. 代码默认值

先复制：

```bash
cp settings.example.json settings.json
```

然后修改以下关键项：

- `API_HOST`
- `API_PORT`
- `ADMIN_TOKEN`
- `INGEST_TOKEN`
- `FAILED_CACHE_PATH`
- `LOG_FILE`

## 运行方式

### 本地/裸机

```bash
pip install -r requirements.txt
python main.py --config ./settings.json
```

可选参数：

- `--self-check`
- `--port /dev/ttyUSB0`
- `--log-file ./logs/agent.log`
- `--once`
- `--no-cache-replay`
- `--debug`

### Docker

构建：

```bash
docker build -t rsr-serial-agent .
```

运行示例：

```bash
docker run -d \
  --name rsr-serial-agent \
  --restart always \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  -v $(pwd)/settings.json:/app/settings.json:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/runtime:/app/runtime \
  rsr-serial-agent
```

如果设备枚举复杂，也可以使用 `--privileged`，但不建议默认这么做。

## systemd

示例服务文件见：

- `systemctl/rsr-serial-bridge.service`

部署后执行：

```bash
sudo cp systemctl/rsr-serial-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rsr-serial-bridge
sudo systemctl start rsr-serial-bridge
```

## 日志与缓存

- 日志默认写到 `./logs/serial-bridge.log`
- 缓存默认写到 `./data/serial_cache.jsonl`
- 心跳默认写到 `./runtime/heartbeat.json`

程序每隔一段时间会写心跳摘要，可供外部脚本检查：

- 当前状态
- 当前串口
- 当前 run
- 最近有效帧时间
- 已解析帧数
- 校验失败数
- 缓存积压
- 上传失败次数

## 自检与测试

协议自检：

```bash
python main.py --self-check
```

pytest：

```bash
pytest -q
```

## 状态机

主状态包括：

- `waiting_port`
- `probing`
- `waiting_stable_frames`
- `running`
- `idle_stopping`
- `stopped`

串口读线程只负责读字节和组帧；主线程只负责状态管理、上传、缓存回放和退出收口。
