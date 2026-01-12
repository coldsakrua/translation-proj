"""
带超时的输入函数
支持Windows和Linux系统
使用线程实现超时功能
"""
import sys
import threading
import queue


def input_with_timeout(prompt: str, timeout: float = 15.0, default: str = "") -> str:
    """
    带超时的输入函数
    
    Args:
        prompt: 提示信息
        timeout: 超时时间（秒），默认15秒
        default: 超时后的默认返回值，默认为空字符串（表示接受/跳过）
    
    Returns:
        用户输入的内容，如果超时则返回default值
    
    Note:
        在Windows上，input()是阻塞的，无法真正中断。
        超时后主线程会继续执行，但input()线程可能仍在等待输入。
        这通常不是问题，因为下一个提示会捕获用户的输入。
    """
    result_queue = queue.Queue()
    
    def input_thread():
        try:
            # 使用标准input函数
            user_input = input(prompt)
            result_queue.put(user_input)
        except (EOFError, KeyboardInterrupt):
            # 用户按Ctrl+C或EOF，返回默认值
            result_queue.put(default)
        except Exception as e:
            # 其他异常，返回默认值
            result_queue.put(default)
    
    # 启动输入线程
    thread = threading.Thread(target=input_thread, daemon=True)
    thread.start()
    
    # 等待线程完成或超时
    thread.join(timeout=timeout)
    
    # 检查是否有结果
    try:
        result = result_queue.get_nowait()
        return result
    except queue.Empty:
        # 超时，返回默认值
        # 注意：在Windows上，input()线程可能仍在运行，但主线程会继续
        print(f"\n超时（{timeout}秒），自动跳过...")
        return default

