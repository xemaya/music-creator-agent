# AI 音乐创作助手 - a2hmarket Agent

一个为 a2hmarket 平台设计的音乐创建 agent，帮助买家通过对话生成个性化音乐。

## 功能特点

- **对话式音乐创作**：通过与买家对话了解音乐需求（风格、情绪、用途等）
- **AI 音乐生成**：集成 Suno API，支持多种音乐风格生成
- **自动交付**：生成的音乐自动上传到平台存储并交付给买家
- **记忆系统**：支持记住买家的音乐偏好，跨会话使用

## 项目结构

```
music-creator-agent/
├── server.py           # FastAPI 主服务，实现 /chat 端点
├── minimax_client.py   # MiniMax API 客户端封装 (music-2.6)
├── agent.yaml          # Agent 配置清单
├── Dockerfile          # 容器构建文件
├── requirements.txt    # Python 依赖
├── deploy.sh           # 部署脚本
└── README.md           # 说明文档
```

## 快速开始

### 1. 本地开发

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export A2H_TOKEN=dummy
export A2H_API_BASE=http://localhost:9999
export SUNO_API_KEY=your_suno_api_key
export AWS_REGION=us-east-1

# 运行服务
uvicorn server:app --host 0.0.0.0 --port 8080
```

### 2. 测试

```bash
curl -N -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-1",
    "shop_id": 1,
    "works_id": "music001",
    "buyer": {"id": "u1", "nickname": "测试用户"},
    "history": [],
    "message": {"text": "我想创作一首古风的纯音乐"}
  }'
```

### 3. 部署到 a2hmarket

```bash
# 1. 初始化 git 仓库并推送
git init
git remote add origin https://github.com/your-org/music-creator-agent.git
git add .
git commit -m "Initial commit: music creator agent"
git push -u origin main

# 2. 使用 a2h-shopdiy CLI 提交 agent
a2h-shopdiy login  # 首次登录，输入 shopdiy_pat_...

a2h-shopdiy agent:submit \
  --shop <your-shop-id> \
  --source https://github.com/your-org/music-creator-agent.git \
  --version 1.0.0
```

## 配置说明

### agent.yaml

- `metadata.name`: Agent 标识符（`music_creator`）
- `metadata.displayName`: 显示名称（`AI 音乐创作助手`）
- `runtime.concurrency`: 每个 worker 并发处理 5 个聊天
- `resources.memory`: 2048MB（音乐生成需要更多内存）

### 环境变量

| 变量名 | 必需 | 说明 |
|--------|------|------|
| `A2H_TOKEN` | 是 | 平台注入的认证 token |
| `A2H_LLM_TOKEN` | 是 | Claude API 代理凭证 |
| `SUNO_API_KEY` | 是 | Suno API 密钥 |
| `SUNO_API_BASE` | 否 | Suno API 基础 URL（默认 `https://api.suno.com`） |

## 支持的 music 风格

- pop, rock, electronic, classical
- jazz, hip-hop, r&b, folk
- country, ambient, cinematic, lo-fi
- acoustic, piano, orchestral, world

## 工作流程

1. **需求收集**：对话了解买家想要的音乐风格、情绪、用途
2. **确认细节**：确认时长、是否纯音乐等细节
3. **生成音乐**：调用 Suno API 生成音乐（1-3 分钟）
4. **上传存储**：将生成的音乐上传到平台存储
5. **交付买家**：通过 `show_file` UI 动作交付音乐文件

## 定价建议

- 按音乐时长定价（30s/60s/120s 不同价格）
- 按音乐风格复杂度定价
- 可提供加急服务（更快的生成优先级）

## 开发计划

- [ ] 支持歌词生成
- [ ] 支持音乐风格混合
- [ ] 提供音乐预览片段
- [ ] 批量生成多个版本供选择
- [ ] 支持音乐后期调整（变速、调式等）

## License

MIT
