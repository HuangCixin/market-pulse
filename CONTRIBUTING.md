# Contributing · 贡献指南

Thanks for your interest in Market Pulse! Issues and pull requests are welcome.
感谢关注 Market Pulse！欢迎提交 Issue 和 Pull Request。

## Setup · 环境

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
python run_daily.py --demo --open
```

## Guidelines · 规范

- **Add markets in `config.yaml`, not in code.** Include a `name_zh` for the Chinese view.
  **新增市场请修改 `config.yaml`**，并填写 `name_zh` 中文名称。
- **Keep the methodology rules** in [docs/METHODOLOGY.md](docs/METHODOLOGY.md): correlate moves rather
  than prices, never forward-fill holidays, and use σ for comparisons.
  **遵守方法说明中的规则**：比较涨跌而不是价格，不填充节假日，用 σ 做比较。
- **The page must stay a single self-contained file** with no CDN or external scripts, and must work
  in light and dark mode and at phone width.
  **网页必须保持为单个独立文件**，不依赖 CDN，并支持浅色、深色和手机宽度。
- **Every visible string needs both languages.** Add new text to both `I18N.en` and `I18N.zh` in
  `market/template.html`, and to both branches of `headlines()` in `market/report.py`.
  **所有可见文字都需要中英文两个版本。**
- **Run `pytest` and check the demo page** before opening a pull request.
  提交前请运行 `pytest` 并检查演示页面。
- **Never commit market data** (`data/`, `reports/`). It is excluded by `.gitignore`.
  **不要提交市场数据**（已在 `.gitignore` 中排除）。

## Commit messages · 提交信息

Use a short imperative summary line, e.g. `Add Nikkei 225 to config`, followed by a blank line and
details if needed.
