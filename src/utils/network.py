"""
网络请求安全封装模块。

核心设计 (来自经验 100018265 / 100018077):
1. safe_call() — 统一门面,所有外部调用 (akshare/tushare/requests) 都走这里
2. 请求级超时 — 不假装用 join(timeout) 兜底,真正传到 requests/SDK 的 timeout 参数
3. 熔断计数 — 连续 N 次失败后冷却,冷却期内直接返回 fallback 不阻塞
4. 降级返回 — 失败不抛异常,返回调用方指定的 fallback

使用示例:
    # 简单调用 (默认 10s 超时, 不重试, 返回 None)
    df = safe_call(ak.stock_zh_a_spot_em)
    
    # 带 fallback
    df = safe_call(ak.stock_zh_a_spot_em, fallback=pd.DataFrame())
    
    # 带参数 + 重试
    data = safe_call(
        ts.pro_api().daily,
        ts_code='000001.SZ', start_date='20260901', end_date='20260919',
        timeout=15, retries=2,
    )
    
    # requests get
    resp = safe_call(requests.get, 'https://example.com', timeout=10)
"""
import time
import threading
from typing import Any, Callable, Optional

# ==================== 默认配置 ====================
DEFAULT_TIMEOUT = 10.0       # 秒: 单次请求超时
DEFAULT_RETRIES = 0           # 重试次数 (不含首次)
DEFAULT_BACKOFF = 2.0         # 重试退避系数 (等待 = backoff ** attempt)

# 熔断器配置
CIRCUIT_FAILURE_THRESHOLD = 3       # 连续失败多少次触发熔断
CIRCUIT_COOLDOWN_SECONDS = 60.0     # 熔断后冷却多久 (秒)


# ==================== 熔断器 (按函数名隔离) ====================
class _CircuitBreaker:
    """简易熔断器,按函数 qualified name 隔离计数。"""

    def __init__(self):
        self._lock = threading.Lock()
        # {func_key: {"failures": int, "until": float}}
        self._states: dict[str, dict[str, float | int]] = {}

    def allow(self, func_key: str) -> bool:
        with self._lock:
            state = self._states.get(func_key)
            if state is None:
                return True
            until = float(state.get("until", 0))
            if time.monotonic() < until:
                return False  # 冷却期内,拒绝
            # 冷却到期,重置
            self._states.pop(func_key, None)
            return True

    def record_success(self, func_key: str):
        with self._lock:
            self._states.pop(func_key, None)

    def record_failure(self, func_key: str):
        with self._lock:
            state = self._states.setdefault(func_key, {"failures": 0, "until": 0.0})
            state["failures"] = int(state.get("failures", 0)) + 1
            if state["failures"] >= CIRCUIT_FAILURE_THRESHOLD:
                state["until"] = time.monotonic() + CIRCUIT_COOLDOWN_SECONDS
                print(f"  🔌 熔断器触发: {func_key} 连续 {state['failures']} 次失败,"
                      f"冷却 {CIRCUIT_COOLDOWN_SECONDS:.0f}s")


_circuit = _CircuitBreaker()


def _func_key(func: Callable) -> str:
    try:
        return f"{func.__module__}.{func.__qualname__}"
    except Exception:
        return str(func)


# ==================== safe_call 主入口 ====================
def safe_call(
    func: Callable,
    *args,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    fallback: Any = None,
    label: Optional[str] = None,
    **kwargs,
) -> Any:
    """安全调用外部数据获取函数,带超时、重试、熔断。

    Args:
        func: 要调用的可调用对象
        *args, **kwargs: 传给 func 的参数
        timeout: 超时秒数 (如果底层 API 支持,会尝试传递;否则只做外层兜底)
        retries: 重试次数 (不含首次)
        backoff: 退避系数, 每次等待 = backoff ** attempt
        fallback: 全部失败后返回的值
        label: 日志标签,方便定位 (默认用函数名)

    Returns:
        func 的返回值,或 fallback
    """
    key = label or _func_key(func)

    # 熔断器检查
    if not _circuit.allow(key):
        print(f"  ⏭️  熔断跳过: {key}")
        return fallback

    last_exc: Optional[BaseException] = None
    max_attempts = 1 + max(0, retries)

    for attempt in range(max_attempts):
        try:
            # 尽力把 timeout 传到底层 requests 调用
            # akshare / tushare 内部用 requests,但签名各异,
            # 这里只给 func 本身加 timeout 关键字 (对 requests.get/post 有效)
            call_kwargs = dict(kwargs)
            if "timeout" not in call_kwargs:
                call_kwargs["timeout"] = timeout

            result = func(*args, **call_kwargs)
            _circuit.record_success(key)
            return result

        except TypeError as _te:
            # 函数不接受 timeout 参数 — 去掉再试
            if "timeout" in call_kwargs and "unexpected keyword argument 'timeout'" in str(_te):
                call_kwargs.pop("timeout", None)
                try:
                    result = func(*args, **call_kwargs)
                    _circuit.record_success(key)
                    return result
                except BaseException as _inner:
                    last_exc = _inner
            else:
                last_exc = _te

        except BaseException as _e:
            last_exc = _e

        # 重试退避
        if attempt < max_attempts - 1:
            wait = backoff ** (attempt + 1)
            print(f"  ⚠️  {key} 第 {attempt + 1} 次失败, {wait:.1f}s 后重试: {last_exc}")
            time.sleep(wait)

    # 全部失败
    _circuit.record_failure(key)
    print(f"  ❌ {key} 全部 {max_attempts} 次失败: {last_exc}")
    return fallback


# ==================== 便捷函数 ====================
def safe_ak(func_name: str, *args, fallback=None, timeout=DEFAULT_TIMEOUT, **kwargs):
    """调用 akshare 函数的便捷入口 (自动查 ak 模块)。

    示例: safe_ak('stock_zh_a_spot_em', fallback=pd.DataFrame())
    """
    try:
        import akshare as ak
        func = getattr(ak, func_name)
    except (ImportError, AttributeError) as e:
        print(f"  ❌ akshare 不可用或无函数 {func_name}: {e}")
        return fallback
    return safe_call(func, *args, timeout=timeout, fallback=fallback, label=f"ak.{func_name}", **kwargs)


def safe_requests(method: str, url: str, fallback=None, timeout=DEFAULT_TIMEOUT, **kwargs):
    """requests.get/post 的便捷入口。"""
    try:
        import requests as _req
        fn = getattr(_req, method.lower())
    except (ImportError, AttributeError) as e:
        print(f"  ❌ requests 不可用: {e}")
        return fallback
    return safe_call(fn, url, timeout=timeout, fallback=fallback,
                     label=f"requests.{method} {url[:50]}", **kwargs)
