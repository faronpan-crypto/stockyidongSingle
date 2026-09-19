# [RESOLVED] Debug Session: skill-dashboard-popup

## 症状 ✅ 已修复
Skill 浏览器运行脚本后，Canvas 图形界面（_try_popup_skill_dashboard）不弹出。

## 根因分析（按发现顺序）

### H3（确认，最直接的根因）: 函数定义顺序导致 NameError
**现象**：用户运行 skill 后 stderr 出现 `[dashboard error] market-sentiment-guard: cannot access local variable '_redraw' where it is not associated with a value`

**根因**：
- L82512 `ttk.Button(..., command=_redraw)` 是**立即求值**（不是 lambda 延迟求值）
- 但 `def _redraw():` 要到 L82515 才定义
- Python 创建按钮时直接抛 `NameError`，整个 dashboard 创建过程中断

**修复**：重排代码顺序 — 先创建 UI 框架（dlg, top_bar 框架, canvas），然后定义所有绘图函数（_redraw + 10 个 _draw_*），最后创建按钮和 Radiobutton。

### H1（确认，防御性修复）: Toplevel(win) 在 win 已销毁时崩溃
**现象**：如果用户关闭 skill 浏览器窗口后，后台 skill 完成尝试弹出 dashboard

**根因**：
- `win.after(0, show_result)` 即使 win 已 destroy 也能成功投递 callback
- 但 callback 内 `tk.Toplevel(win)` 会抛 `TclError: bad window path name ".!toplevel"`

**修复**：
- `_try_popup_skill_dashboard` 入口安全获取 `_parent = win if win.winfo_exists() else self.root`
- `_exec_skill` 内 `win.after()` 改成 `_safe_after()` 检查 winfo_exists 后回退到 self.root
- `_try_popup_skill_dashboard` 内首次绘制用 `dlg.after()` 代替 `win.after()`（dlg 就是刚创建的 dashboard 窗口）

### H2（已修正，辅助调试）: 'win' in dir() 错误的 debug 检查
**现象**：原来的 debug 日志 `win_exists={'win' in dir()}` 永远打印 False

**根因**：`dir()` 只返回当前函数的局部变量和全局变量，不包括闭包外层函数的局部变量

**修复**：改成 `_parent = win if win.winfo_exists() else self.root` 直接访问并检查

## 修复验证

```
[dashboard DEBUG] ENTER skill=market-sentiment-guard stdout_len=1684 _parent=.!toplevel3
[dashboard DEBUG] PARSED JSON keys=[...]
[dashboard DEBUG] COLLECTED 57 numbers: [...]
[dashboard DEBUG] DLG CREATED: .!toplevel3.!toplevel, _parent=.!toplevel3
[dashboard DEBUG] ALL UI CREATED, radiobuttons + buttons + canvas OK
```

✅ 无 error，两个 skill 都成功弹出 dashboard
✅ 用户确认看到了图形界面

## 临时文件
- `/tmp/test_toplevel_destroy.py` — 验证 H1 的独立测试脚本
- `/tmp/test_toplevel_auto.py` — 自动验证 H1 的测试脚本
- `/tmp/test_dashboard_alive.py` — 验证 H3 的测试脚本
- `/tmp/stockyidong_stderr.log` — 运行时日志（可以删）

## 清理计划
- [ ] 移除 `_dbg = True` 和所有 `_log()` 调用（L82328-82331, L82398-82404, L82425, L82477, L82922）
- [ ] 移除 `debug-point` region 标记
- [ ] 删除 `/tmp/test_*.py` 临时文件
- [ ] 删除 `/tmp/stockyidong_stderr.log`
- [ ] 删除本 debug 文件
