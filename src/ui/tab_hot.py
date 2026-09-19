import tkinter as tk
from tkinter import ttk

class HotMixin:
    def _batch_hotmoney_from_sector(self, tree):        """批量扫描选中行的游资心法"""        sel = tree.selection()        if not sel:            sel = tree.get_children()[:10]  # 没选中就扫前10        self._do_batch_hotmoney(tree, list(sel))
    def _batch_hotmoney_topn(self, tree, n=10):        """批量扫描 Top N"""        self._do_batch_hotmoney(tree, list(tree.get_children()[:n]))

__all__ = ["HotMixin"]
