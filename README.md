# 13F 投资人持仓研究页

这个仓库保存 13F 项目的源码、原始数据、处理脚本和 HTML 输出文件，方便在多台电脑之间同步迭代。

## 主要入口

- `outputs/investors.html`：大佬持仓一览页。
- `outputs/berkshire_13f_single_file.html`：巴菲特/Berkshire 单页。
- `outputs/investor_*.html`：各投资人单独页面。
- `investors.html`、`index.html`：当前主要源码页面。
- `work/`：数据构建、页面生成和语法检查脚本。
- `investor_13f_data/`：已拉取的投资人 13F 原始数据。

## 常用检查

```bash
node work/check-investors-syntax.js
node work/check-index-syntax.js
```

## 同步约定

后续每次迭代完成后，把源码和 `outputs/` 一起提交并推送到 GitHub，确保另一台电脑可以直接拉取最新页面。

