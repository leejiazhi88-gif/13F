# 13F 项目交接与同步约定

这个文档记录本项目的固定地址、验收入口和后续每次迭代的执行方式，方便换电脑后继续用同一套流程。

## 固定地址

- GitHub 仓库：<https://github.com/leejiazhi88-gif/13F>
- 线上总览页：<https://leejiazhi88-gif.github.io/13F/outputs/investors.html?v=latest>
- 线上根入口：<https://leejiazhi88-gif.github.io/13F/?v=latest>
- 当前本地项目路径：`/Users/fuguiplus/Documents/Codex/2026-05-26/bili-13f`
- 当前本地总览页：`/Users/fuguiplus/Documents/Codex/2026-05-26/bili-13f/outputs/investors.html`

## 主要文件

- `investors.html`：投资人大览页源码。
- `index.html`：Berkshire/巴菲特页面源码。
- `outputs/investors.html`：线上和本地验收用的大览页输出。
- `outputs/berkshire_13f_single_file.html`：Berkshire/巴菲特输出页。
- `outputs/investor_*.html`：各投资人单页输出。
- `work/`：数据处理、页面生成、语法检查脚本。
- `investor_13f_data/`：SEC 原始数据的本地重建缓存。仓库继续跟踪原有四家缓存；其余经理的原始附件不提交，运行生成脚本会自动重新下载。

## 每次迭代后的交付格式

每次完成一个任务后，最后回复里固定包含：

- 本地验收文件路径。
- 线上页面 URL。
- GitHub 仓库 URL。
- 当前 commit。
- 是否已经推送 `main` 和更新 `gh-pages`。
- 运行过的检查；如果没有跑，要说明原因。

## 推荐检查

优先运行：

```bash
node work/check-investors-syntax.js
node work/check-index-syntax.js
```

如果当前 shell 里 `node` 不在 `PATH`，不要直接跳过检查。先尝试：

```bash
command -v node
command -v nodejs
ls -1 /opt/homebrew/bin/node /usr/local/bin/node 2>/dev/null
```

若仍找不到 Node，需要在最终回复里明确说明“未跑 JS 语法检查”的原因。同步仓库和线上页面本身不依赖 Node，但页面代码改动后建议尽量补跑检查。

## Git 同步流程

常规源码分支是 `main`：

```bash
git status --short --branch
git add -A
git commit -m "描述本次改动"
git push origin main
```

不要提交 `.DS_Store`、日志、`.env`、`node_modules/`。这些已在 `.gitignore` 里排除。

## GitHub Pages 发布流程

线上页面发布在 `gh-pages` 分支。每次 `outputs/` 有变化后，需要更新 `gh-pages`：

```bash
PAGES_DIR=$(mktemp -d /tmp/13f-gh-pages.XXXXXX)
git worktree add --detach "$PAGES_DIR" HEAD
cd "$PAGES_DIR"
git switch --orphan gh-pages
git rm -rf . >/dev/null 2>&1 || true
cp -R /Users/fuguiplus/Documents/Codex/2026-05-26/bili-13f/outputs ./outputs
cat > index.html <<'HTML'
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url=outputs/investors.html">
  <title>13F 大佬持仓一览</title>
</head>
<body>
  <main>
    <h1>13F 大佬持仓一览</h1>
    <p>正在打开总览页：<a href="outputs/investors.html">outputs/investors.html</a></p>
  </main>
</body>
</html>
HTML
printf '%s\n' '# 13F Pages' '' 'Static build for GitHub Pages.' > README.md
touch .nojekyll
git add -A
git commit -m "Publish static 13F pages"
git push -f origin gh-pages
cd /Users/fuguiplus/Documents/Codex/2026-05-26/bili-13f
git worktree remove "$PAGES_DIR"
```

发布后用下面的地址验证：

```bash
curl -I -L --max-time 15 "https://leejiazhi88-gif.github.io/13F/outputs/investors.html?v=latest"
```

返回 `HTTP/2 200` 表示线上页可访问。GitHub Pages 有 CDN 缓存，必要时 URL 后面加 `?v=latest` 或其它参数绕过旧缓存。

## 当前已知状态

- 总览覆盖 20 位经理，当前运行时状态为 `20/20` 已接入。
- 19 位非 Berkshire 经理均有统一详情页：季度下拉、核心持仓趋势、前十大、完整持仓、季度变动和季度解读。
- Pershing Square 的 2026 Q2 为 `13F-NT`，没有本主体完整信息表，页面显示最后可直接解析的 2026 Q1。
- Scion 当前最后完整披露期为 2025 Q3，页面按真实最后披露期展示。
- Trian 的 2023 Q1 SEC 归档缺少信息表附件；该季度留空，并重置下一季度的变动比较基线。
- 13F 不披露现金；页面中的“其他13F持仓”不能解释为现金或空仓。
- 文艺复兴科技和 D. E. Shaw 的历史季度保留趋势与前十大摘要，最新季度保留完整明细，以控制单文件体积。
- 数据生成入口：`python3 work/build_investor_history.py` 和 `python3 work/build_full_investor_pages.py`。
- 线上页已成功返回过 `HTTP/2 200`；发布提交与源码提交以 `git log -1` 为准。
