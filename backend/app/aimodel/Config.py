
from pathlib import Path  # 路径相关常用库
current_path = Path(__file__)  # 获取当前文件config.py的路径
# print(current_path)
# print(current_path.parent)  # 获取当前文件config.py的上一层路径


# 1 定义一个类 包含全部路径
class Config:
    def __init__(self):
        self.root_path = current_path.parent

        self.model_file_path=self.root_path / 'model' / 'bert-base-chinese'

        # bert模型保存路径
        self.model_path = self.root_path / 'model' / 'bert_model.pt' #pytorch框架