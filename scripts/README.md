# 上游图鉴自动同步

`sync_upstreams.py` 按仓库根目录的 `sync_sources.json`，从指定上游复制受管图片到本站目录。远程仓库使用部分克隆和稀疏检出，只下载映射中的目录。默认行为是新增和覆盖有变化的图片，不删除目标目录中的额外文件。

GitHub Actions 每天北京时间 04:23 自动执行，也可以在 Actions 页手动运行 `Sync upstream atlases`。同步产生变化时，工作流会一并刷新 `md5.json`、`genshin/alias.json`，然后提交到 `main`。

## 本地使用

先预览远程上游会带来的变化：

```bash
python3 scripts/sync_upstreams.py --dry-run
```

使用与本站仓库同级的本地检出，避免重新下载：

```bash
# 先在各上游仓库执行 git pull，避免用旧检出覆盖较新的站点文件
python3 scripts/sync_upstreams.py --source-root .. --dry-run
python3 scripts/sync_upstreams.py --source-root ..
```

只同步一个仓库：

```bash
python3 scripts/sync_upstreams.py --only star-rail-atlas
python3 scripts/sync_upstreams.py --only zzz-atlas
```

`--delete` 会删除目标受管目录中已不在对应上游的图片；`md5.json` 等非图片文件不受影响。自动定时任务默认不启用删除，手动运行工作流时可以显式打开。

## 增加上游

在 `sync_sources.json` 的 `repositories` 中加入仓库 URL、分支和一组 `source`/`destination` 映射。路径必须位于各自仓库根目录内；同一目标目录只能由一个映射管理。脚本只同步 `.png`、`.jpg`、`.jpeg` 和 `.webp` 文件。
