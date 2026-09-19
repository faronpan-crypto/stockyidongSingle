# 迁移自 stockyidong mac003.py ranges=[(97, 109), (110, 124), (126, 136), (137, 151), (153, 161)]
import os
import sys
import contextlib
import io
import warnings

@contextlib.contextmanager
def suppress_stderr():
    """临时抑制stderr输出的上下文管理器"""
    old_stderr = sys.stderr
    try:
        # 创建一个空的StringIO对象来捕获所有stderr输出
        sys.stderr = io.StringIO()
        yield
    except Exception:
        # 即使发生异常也要恢复stderr
        pass
    finally:
        sys.stderr = old_stderr

@contextlib.contextmanager
def suppress_all_output():
    """临时抑制stdout和stderr输出的上下文管理器"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        # 同时抑制stdout和stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        yield
    except Exception:
        pass
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

class SilentIO(io.StringIO):
    """静默的IO类,完全抑制所有输出"""
    def write(self, *args, **kwargs):
        # 完全忽略所有写入操作
        pass
    def flush(self, *args, **kwargs):
        # 忽略刷新操作
        pass
    def getvalue(self):
        # 返回空字符串
        return ""

@contextlib.contextmanager
def suppress_tkinterweb_errors():
    """专门用于抑制TkinterWeb错误的上下文管理器"""
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        # 使用静默IO完全抑制输出
        sys.stdout = SilentIO()
        sys.stderr = SilentIO()
        yield
    except Exception:
        pass
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

def suppress_all_errors(func):
    """装饰器:抑制函数执行过程中的所有stderr输出"""
    def wrapper(*args, **kwargs):
        with suppress_stderr():
            try:
                return func(*args, **kwargs)
            except Exception:
                return None
    return wrapper

__all__ = ['SilentIO', 'suppress_all_errors', 'suppress_all_output', 'suppress_stderr', 'suppress_tkinterweb_errors']
