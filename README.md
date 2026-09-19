# stockyidong_project

本目录由 `scripts/organize_root_python_projects.py` 从仓库根目录整理生成。

## 运行

- Windows: `scripts\run.bat`
- PowerShell: `scripts\run.ps1`

启动器会把**仓库根目录**以及各兄弟项目下的 `*_project/src` 加入 `sys.path`，这样分散在不同项目文件夹里的 `.py` 仍可按模块名互导（避免 PYTHONPATH 过长）。

## 目录说明

- `src/`：入口脚本与本项目独占的 `.py` 文件
- `modules/`、`utils/`、`config/`、`assets/`：按需在代码中调整路径后迁移文件
- `tests/`、`docs/`：测试与文档
