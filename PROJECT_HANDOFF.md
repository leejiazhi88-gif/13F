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
- `investor_13f_data/`：李录、阿克曼、TCI、Baupost 等 13F 原始数据。

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

- `main` 初始同步提交：`355feb5 Initial 13F project sync`
- `gh-pages` 初始发布提交：`d2ce7d5 Publish static 13F pages`
- 线上页已经成功返回过 `HTTP/2 200`

