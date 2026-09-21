# 双击持仓股打开日K线图修复 @ 20260921_102555
## 改动文件
- src/ui/tab_cangwei.py (2处持仓按钮: 主界面 + 管理弹窗)
- src/stockyidong mac003.py (窗口标题加文件名)

## 方案
- macOS Tkinter Label 不触发 <Double-1> 事件
- 改用单一 <Button-1> + event.time 时间戳判定双击(<350ms)
- 双击: 后台线程拉 Tushare 120 天日K, 调 _show_daily_kline_zoom 放大图
- 单击: 延迟 350ms 执行 _show_holding_detail 详情窗口
