"""
对话式翻译入口文件
运行此文件启动交互式翻译界面
"""
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from utils.interactive_translator import interactive_translate_loop

if __name__ == "__main__":
    interactive_translate_loop()

