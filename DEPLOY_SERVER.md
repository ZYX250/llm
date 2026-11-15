# 生产环境部署指南（公网常驻在线演示）

> 适用场景：比赛「在线演示」要求提供**可公网访问、评审期间保持可用**的地址。
> 本指南配合仓库内的 `deploy_server.sh` 使用，一步到位地把前后端部署到一台云服务器，并以 `systemd` 托管实现 **24h 常驻 + 崩溃自愈 + 开机自启**——无需你本人守着电脑。

---

## 0. 为什么用云服务器（而不是 Vercel / ngrok）

| 方案 | 是否满足「公网常驻」 | 说明 |
|---|---|---|
| **云服务器 + nginx 反代** ✅ | ✅ 满足 | 本机 24h 在线，评分时间未知也无所谓；脚本已就绪 |
| ngrok 隧道 | ❌ 不满足 | 依赖你**本机一直开机运行**，电脑休眠/关机隧道即断，无法覆盖未知评分时段 |
| Vercel 纯静态部署 | ❌ 不满足 | 本项目是 **FastAPI 有状态后端 + Vite 前端**，无 `vercel.json` 时 Vercel 只托管静态 `dist`，页面一加载 `/api/*` 全 404，问答/上传/图谱全部失效 |

> ⚠️ 请勿把前端单独部署到 Vercel 作为演示地址——它不含后端，评委打开看到的是「已入库 0 篇」的空壳。

---

## 1. 购买云服务器

- **厂商**：腾讯云 / 阿里云「轻量应用服务器」即可
- **镜像**：Ubuntu **22.04** LTS（脚本针对该系统编写）
- **配置**：**2 核 2G** 足够（LLM 与 embedding 均走 DashScope 云端 API，服务器**不需要 GPU**）
- **带宽**：4–6 Mbps 足够
- **费用**：新人首单约 **¥70–100 / 年**
- **地域**：选国内均可

### 购买后在控制台必须做两件事
1. **安全组放行入站端口**：`22`（SSH）+ `80`（HTTP）。否则外网打不开页面。
2. 记下服务器的**公网 IP** 和 **root 密码**（或配置好 SSH 密钥）。

---

## 2. 把项目传到服务器

从**本地（已 `git push` 的仓库）**传项目到服务器。下面三种方式任选其一，目标目录统一为 `/opt/llm_competition`。

### 方式 A：rsync（推荐，干净且快）
在**本地**执行，排除 `.venv`、`node_modules`、`.cache` 等大目录：

```bash
rsync -avz --exclude '.venv' --exclude 'node_modules' --exclude '.cache' \
  --exclude '.git' --exclude '*.log' \
  /d/vue/llm_competition/ root@<服务器公网IP>:/opt/llm_competition/
```

### 方式 B：git clone（最简单，需仓库为 Public 或已授权）
在**服务器**上执行：

```bash
ssh root@<服务器公网IP>
git clone https://github.com/ZYX250/llm.git /opt/llm_competition
```

### 方式 C：scp
在**本地**执行：

```bash
scp -r /d/vue/llm_competition root@<服务器公网IP>:/opt/llm_competition
```

> 注意：`.env`、`ngrok.exe`、`.venv`、`.cache` 等已被 `.gitignore` 排除，不会随 git/rsync 误传到服务器。

---

## 3. 在服务器上执行一键部署

SSH 进服务器后，运行脚本（需 root）：

```bash
ssh root@<服务器公网IP>
cd /opt/llm_competition
sudo bash deploy_server.sh
```

脚本默认把项目放在 `/opt/llm_competition`。若你用别的目录，作为参数传入即可：

```bash
sudo bash deploy_server.sh /your/path/llm_competition
```

### 部署过程中需要你提供

- **`DASHSCOPE_API_KEY`**（必填）：大模型调用密钥。
  - 交互式：脚本会提示你粘贴。
  - 非交互式（CI / 自动化）：`DASHSCOPE_API_KEY=sk-xxxx sudo -E bash deploy_server.sh`
- **`REVIEWER_TOKEN`**（选填）：评审只读模式令牌。不传则脚本自动生成 20 位随机串并打印。

脚本会自动完成 6 步：

1. 安装系统依赖 + Node 22
2. 建 Python 虚拟环境并 `pip install -r requirements.txt`
3. 写入 `$BACKEND/.env`（含 `DASHSCOPE_API_KEY` / `REVIEWER_TOKEN` / `BACKEND_PORT=8000` / `ALLOW_ORIGINS=*`）
4. `npm install && npm run build` 产出前端静态包 `dist/`
5. 注册 `systemd` 服务（开机自启 + 崩溃自动重启）
6. 配置 nginx 反代（`/api/` → uvicorn:8000）并放行防火墙，最后做健康检查

---

## 4. 拿到地址，填进比赛系统

部署成功后脚本会打印类似下面的信息，**直接复制给评委 / 填进「在线演示」栏即可**：

```
============================================================
部署完成 🎉
------------------------------------------------------------
✓ 后端评审链路正常

评委演示地址（公网，评审期间常驻）：
  http://<服务器公网IP>/
评审只读模式（查看检索/RRF/引用判定/图谱来源）：
  http://<服务器公网IP>/api/reviewer/info?token=<随机令牌>
  （或 http://<服务器公网IP>/reviewer/info?token=<随机令牌>）
============================================================
```

- **演示地址**：`http://<服务器公网IP>/` —— 评委打开即是完整 Web 界面。
- **评审只读模式**：`/api/reviewer/info?token=...`（`/reviewer/info`、`/reviewer/search`、`/reviewer/qa`、`/reviewer/graph` 四个端点），用于展示检索排名、RRF 融合、引用判定、图谱边来源等内部证据。

> 后端在启动时会自动加载 `papers/` 下已打包的论文（`lifespan` 里的 `load_state()` + `_restore_vectors()`），所以**评委打开就能看到数据，无需现场手动上传**。

---

## 5. 演示前准备（冲击高分的三条必演）

在网页里依次操作，这三条是评委最容易打高分的演示点：

| 演示目标 | 操作 | 预期效果 |
|---|---|---|
| **去重检测** | 上传 *Attention Is All You Need* 的 **v1 + v7** 两个版本 | 系统识别为同论文不同版本，提示「检测到重复版本」 |
| **引用图谱** | 上传一篇**互相引用**的论文（如引用 Transformer 的后续工作） | 图谱出现**带边的节点**，而非孤立点 |
| **抗幻觉拒答** | 问一个论文里**没有的具体数字**（如「模型在 XXX 数据集上准确率是多少？」而原文无此数） | 引用校验判 `未通过` / `not_found`，触发**程序判定拒答**，而非模型随口编 |

---

## 6. 日常管理命令

```bash
# 查看后端实时日志
journalctl -u llmcompetition -f

# 重启后端（改了代码后）
systemctl restart llmcompetition

# 停止演示
systemctl stop llmcompetition

# 重新部署（代码更新后）
sudo bash /opt/llm_competition/deploy_server.sh
```

> 服务名为 `llmcompetition`，由 `systemd` 托管：服务器重启、进程崩溃都会**自动恢复**，无需人工干预。

---

## 7. 常见问题排查

| 现象 | 原因 | 解决 |
|---|---|---|
| 外网打不开 `http://IP/` | 安全组未放行 80 端口 | 控制台安全组加 `80/tcp` 入站 |
| 页面能开但 `/api` 全 404 | nginx 未正确反代 | `nginx -t` 检查配置，`systemctl restart nginx` |
| 后端健康检查 ⚠ 未通过 | `DASHSCOPE_API_KEY` 无效 / 出网受限 | `journalctl -u llmcompetition` 看报错；确认服务器能访问 `dashscope.aliyuncs.com` |
| 问答无响应 / 超时 | 模型 API 额度或网络问题 | 检查 key 是否过期、服务器出站是否通 |
| 想换域名 + HTTPS | 有域名后 | `certbot --nginx -d 你的域名`（脚本已预留此说明） |

---

## 8. 附：本地联调（不部署到云时的备选）

若仅需在本地本机演示（非公网），用仓库根的 `deploy_demo.ps1`（Windows PowerShell）即可一键拉起前后端：

```powershell
# 局域网模式（评委连同一 WiFi 访问）
pwsh deploy_demo.ps1

# 固定评审令牌
pwsh deploy_demo.ps1 -ReviewerToken abc123xyz

# 停止全部服务
pwsh deploy_demo.ps1 -Stop
```

> `deploy_demo.ps1` 适合「已知时间的现场答辩 / 屏幕共享」，但**不是**「未知时间公网常驻」的答案——常驻请走上面的云服务器方案。
