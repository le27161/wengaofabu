import torch.nn.functional as F
# 包内相对导入：aimodel 作为 app 的子包被引用时，Config.py 与 predict.py 同目录
# from Config import Config
from .Config import Config
import torch
import torch.nn as nn # 提供一些模型训练基础函数
from transformers import BertModel # 模型框架相关
from transformers import BertTokenizer # bert模型读取相关
from transformers.utils import PaddingStrategy # 句子向量化相关参数
import json

config = Config()
# 有 GPU 用 GPU，没有则自动退回 CPU（避免启动直接报错）
device = 'cuda' if torch.cuda.is_available() else 'cpu'

classification_dict={0:'金融',
                     1:'房产',
                     2:'股票',
                     3:'教育',
                     4:'科学',
                     5:'社会',
                     6:'政治',
                     7:'运动',
                     8:'游戏',
                     9:'娱乐'}


def load_knowledge_base() -> dict:
    """加载 AI 知识库（关键词 → 分类强兜底）

    优先级：
    1. 后台系统设置 system_settings.ai_knowledge_base（在线修改，实时生效）
    2. 本地文件 knowledge_base.json（兼容老环境/未初始化场景，兜底）
    3. 都不可用时返回空字典（走模型预测）
    """
    try:
        from ..database import SessionLocal
        from ..models.system_setting import SystemSetting
        db = SessionLocal()
        try:
            row = db.query(SystemSetting).filter(
                SystemSetting.config_key == "ai_knowledge_base"
            ).first()
            if row and row.config_value:
                value = json.loads(row.config_value)
                if isinstance(value, dict) and value:
                    return value
        finally:
            db.close()
    except Exception:
        pass
    # 本地文件兜底
    try:
        with open(config.root_path / "knowledge_base.json", "r", encoding="utf-8") as f:
            value = json.load(f)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


# 1 定义pytorch模型框架和各类参数
class BertLinear(nn.Module):
    def __init__(self):
        super().__init__()
        self.bert = BertModel.from_pretrained(config.root_path / 'model' / 'bert-base-chinese')  # 加载BERT预训练模型
        # Bert模型默认输出768维度
        self.fc = nn.Linear(768, 10)  # 768到10类别

    # 前向过程 输入到输出的运行流程
    def forward(self, input_ids, attention_mask):  # 输入格式 0填充的句子向量 标注填充位置的向量
        _, first = self.bert(input_ids=input_ids, attention_mask=attention_mask, return_dict=False)
        # _ bert每个位置 first第一个位置
        out = self.fc(first)
        return out
tokenizer = BertTokenizer.from_pretrained(config.model_file_path)  # 加载BERT向量化器
# 1 加载保存的模型
model = BertLinear()  # 或者你的模型类
# map_location=device：权重文件在 GPU 机器上保存（cuda 张量），
# 无 GPU 机器加载时自动映射到 CPU，否则 torch.load 会直接报错
model.load_state_dict(torch.load(config.model_path, weights_only=True, map_location=device))
model = model.eval().to(device)

# dataloader会自己用textDataset拿数据 然后传给这个函数进行格式转化
def collate_fn(data): # 传进来的data [('我喜欢看电影', 2), ('王者荣耀好玩', 1), (..... ]
    # 把data数据拆成两部分 一边全是文本 一边全是标签
    text, label = zip(*data)
    # * ('我喜欢看电影', 2), ('王者荣耀好玩', 1), (.....
    # zip (我喜欢电影, 王者荣耀, ...)   (2,1, ...)

    text_tokens = tokenizer(
        text, padding=PaddingStrategy.MAX_LENGTH, max_length=32,  # 每一句都填充到最大
        truncation=True, return_tensors='pt'
    )
    #         [   '我', '喜', '欢']
    #         [  101,   437,  389]  根据 vocab.txt
    #         [101, 437, 389, 0, 0, 0] 对应的 [1,1,1, 0, 0, 0] 0填充成固定长度  标记哪些0是填充的

    return text_tokens['input_ids'].to(device), text_tokens['attention_mask'].to(device), torch.tensor(label).to(device)



# 2 预测过程封装成一个函数 输入文本返回分类结果
def predict_fun(text):
    # 希望可以用之前的collate_fn来实现文本转model需要的格式
    title=text
    text = [(text, 2)]  # 凑成collate_fn格式处理函数的输入
    input_ids, attention_mask, labels = collate_fn(text)
    with torch.no_grad():
        output = model(input_ids, attention_mask)  # 模型输入输出
        probs = F.softmax(output, dim=1)
        print('probs',probs)
        top2_probs, _ = torch.topk(probs, 2, dim=1)  # 取最大的两个概率
        margin = (top2_probs[:, 0] - top2_probs[:, 1]).item()
        print('margin',margin)
        # 2. 取最大概率作为置信度
        confidence, pred_idx = torch.max(probs, dim=1)  # confidence 是 tensor，pred_idx 是类别索引
        # 3. 转成普通数字
        conf = confidence.item()  # 如 0.92
        pred = pred_idx.item()  # 类别编号
        print('pred',pred,'conf',conf,'name',classification_dict[pred])
        # AI 知识库：后台系统设置在线配置优先，本地文件兜底（见 load_knowledge_base）
        kb = load_knowledge_base()
        # 2. 命中人物库，直接返回预置分类（强兜底）
        print('kb',kb)
        for name, info in kb.items():
            print('name', name,'info',info,'title',title,'判定',name in title)
            if name in title:
                return info["category"]  # 直接返回 "时政"，绕过模型
        return classification_dict[pred]

        # 4. 得到类别名称
        # id2name = [i.strip() for i in open(config.class_path, encoding='utf-8')]
        # name = id2name[pred]

        return conf


if __name__ == '__main__':
    text = '“两弹一星”元勋、中国科学院院士王希季逝世，享年105岁'
    result = predict_fun(text)
    print(result)
