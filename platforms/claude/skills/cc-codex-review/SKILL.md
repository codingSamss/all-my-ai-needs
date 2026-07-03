---
name: cc-codex-review
description: "CC×Codex 交叉讨论。不确定性强的问题(事实核查 / 有争议或乐观的结论 / 重要技术决策)找 codex 交叉验证,避免单模型片面。关键词: 让codex看看, 跟codex讨论, codex审查, 帮我审查, review, 交叉讨论, battle, 发给codex, 继续讨论, 接着聊"
---

# CC×Codex 交叉讨论

不确定性强的问题用 codex 做交叉验证——不同模型 + 独立联网,能暴露单模型盲点。本会话用 codex 核实 AI 视频营收数据,就纠正了一批从媒体抓来、其实无法复核的"硬数字"。

通过本机 `codex` CLI 的 `codex exec` 直接调用,不走 MCP。同一份会话存在 `~/.codex/sessions/`,用 `SESSION_ID` 续接即可保持多轮上下文。

## 何时用

- Sam 点名:"让 codex 看看 / 跟 codex 讨论 / 交叉讨论一下 / 发给 codex";
- 或我自己判断结论不确定、容易片面时,主动发起,不必等指令。

## 怎么做

1. 起会话(默认只读讨论):

   ```bash
   codex exec -s read-only -C <相关目录> "PROMPT"
   ```

   - PROMPT 写清:背景、要它独立核实或反驳的**具体点**、要求联网给出来源、并明确"只给结论不要改文件"。
   - `-C <目录>` 给相关工作根;纯事实核查、不依赖某个仓库时可省略(默认用当前 cwd)。
   - 启动时 codex 会在头部打印 `session id: <uuid>`,**记下这个 SESSION_ID**。
   - 沙箱:讨论一律 `-s read-only`;只有确需 codex 改文件时才用 `-s workspace-write`(本机 config 默认是 `danger-full-access`,不显式指定会让它有权乱改文件)。
   - 带参考图:`-i <file>` 附图,可多个。坑:`-i/--image` 是变长参数,PROMPT 写在它后面会被当成图片路径吞掉,报 `No prompt provided via stdin`。稳妥写法是 PROMPT 走 stdin:`cat <<'EOF' | codex exec -s ... -i a.jpg -i b.jpg -`(末尾 `-` 表示从 stdin 读)。

2. 续接 / 下一轮:传**同一个 SESSION_ID**,不要开新会话——省算力、保连贯:

   ```bash
   codex exec -s read-only resume <SESSION_ID> "PROMPT"
   ```

   接最近一次会话可用 `codex exec -s read-only resume --last "PROMPT"`。

   - `-s`(sandbox)是 `exec` 的顶层选项,必须写在 `resume` 前面;`resume` 子命令自己不接受 `-s`,写反了会报 `unexpected argument '-s' found`。

3. 多轮 battle:重复第 2 步,轮流质疑对方结论,直到达成共识或聊够(默认 1 轮;复杂问题 3–5 轮)。

4. 对账落地:codex 负责查证和给观点,我负责对账、改文件并保证格式质量(codex 直接改文件往往格式糙)。不确定的结论降级标注、附来源,分歧如实呈现给 Sam。

## 代码审查

要 codex 审当前仓库改动,用内置 review 子命令(在目标 git 仓库目录下跑):

```bash
codex exec review --uncommitted        # 审未提交(staged + unstaged + untracked)
codex exec review --base <branch>       # 对某基线分支审改动
codex exec review "自定义审查重点"        # 附加审查指令
```

## 长批次委托(批量生图等几十分钟级任务)

单次 `codex exec` 扛不住长批次(Bash 有 10 分钟硬顶,**后台 Bash 同样会被掐**),用这套已实战验证的组合:

1. **幂等指令**:提示词写成"全量清单 + 目录里已存在的跳过 + 你缓存里已生成未拷出的先捞出",任意中断点续跑都不重复生成。
2. **监工循环 + nohup 脱离**:

   ```bash
   # supervisor.sh:首轮开全新会话,断流后 resume --last 续跑
   for attempt in 1 2 3 4 5 6; do
     n=$(ls 目标目录/*.png 2>/dev/null | wc -l); [ "$n" -ge 目标数 ] && break
     if [ "$attempt" -eq 1 ]; then
       cat 全量规格.txt | codex exec -s workspace-write -i 参考图.png -
     else
       echo "继续按本会话开头清单补齐,已存在跳过" | codex exec -s workspace-write resume --last -
     fi
   done
   # 启动:nohup ./supervisor.sh > run.log 2>&1 &
   ```

3. **文件监视器**报落盘进度;监工存活检查用 `kill -0 <PID>`,不要 `ps|grep`(高负载下会误报"已退出")。

三个实战踩过的坑:

- **会话膨胀(最隐蔽)**:`image_gen` 的结果 base64 全量记进会话历史,几十张图后会话文件可达 200MB+,每次 resume 都向服务器重放,服务器直接掐流。表象:早期顺利、越跑越断、`Reconnecting 2/5...5/5`、`websocket closed by server`,换代理无效。解法:**弃旧会话,开全新会话轻装续跑**(重附参考图 + 全量清单),别在臃肿会话上恋战。
- **残留孤儿**:被掐的 Bash 会留下 codex exec 孤儿在旧会话上继续跑,可能拿旧版指令覆盖新产物。重启前 `ps -eo pid,ppid,command | grep "codex exec"` 按血统精确清理;`codex app-server`(桌面应用)和 `codexmcp`(MCP)不要动。
- **谎报落盘**:codex 可能报告"已保存"但目标路径为空——生成物实际在 `~/.codex/generated_images/<session-id>/`。指令里必须要求"每张落盘后 ls 确认";翻车后可按 md5/生成时序从该缓存目录捞回,不用重新生成。

## 续接很久以前的讨论

codex 把会话存在 `~/.codex/sessions/`(按日期分目录,文件名形如 `rollout-<时间>-<UUID>.jsonl`)。要接旧讨论:`codex exec resume --last`,或从目录里找出 `UUID` 传给 `codex exec resume <UUID>`(也支持 thread name)。不需要本地话题文件来管状态。

## 注意

- 本机 config 默认 `danger-full-access`,纯讨论务必显式 `-s read-only`,别让它误改文件。
- 当前目录不是 git 仓库时(比如在 Obsidian Vault 里跑),`codex exec` 会报"不在受信任目录"拒绝执行,需加 `--skip-git-repo-check`:`codex exec -s read-only --skip-git-repo-check resume --last "PROMPT"`(sandbox 仍受 `-s` 约束,不受影响)。
- 中断或拒绝 codex 调用后,先查进程 + `~/.codex/sessions/` 再续,别盲目重提交(会起重复会话烧算力)。Bash 超时杀掉 `codex exec` 就是杀掉整个任务(未落盘产物即丢),但会话已存盘——用启动头部打印的 session id `resume` 续跑;预计超 10 分钟的任务走「长批次委托」节的 nohup 监工模式(后台 Bash 也有 10 分钟硬顶,单靠后台跑不解决)。
- 单轮可能跑较久(`gpt-5.5` + `xhigh`),`codex exec` 每轮是独立进程、跑完即退,不怕长连接断;这正是用 CLI 而非 MCP 的原因。
- 推理档一律用默认 `xhigh`,**不要**用 `-c model_reasoning_effort` 降档(Sam 明确要求:质量优先,不在乎 codex 用量;曾为提速降到 low 被当场纠正)。长任务的时长问题用 `nohup` 脱离进程 + 监工循环自动 resume 解决,不是靠降档。
- 长上下文(1M)下,会话状态我直接在工作上下文里持有,无需文件持久化。
- 行为偏好背景见记忆 `cross-discuss-codex-uncertainty`。
