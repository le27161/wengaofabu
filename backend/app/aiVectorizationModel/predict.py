from transformers import AutoTokenizer, AutoModel
import torch
# 本地运行时选择
# from Config import Config
# 全局启动时选择
from .Config import Config
config = Config()
# 有 GPU 用 GPU，没有则自动退回 CPU（避免启动直接报错）
device = 'cuda' if torch.cuda.is_available() else 'cpu'

# 1. 加载模型（会自动从 HuggingFace 下载所需文件）
tokenizer = AutoTokenizer.from_pretrained(config.model_file_path)
model = AutoModel.from_pretrained(config.model_file_path)
model.eval()



def predict_fun(sentences):
    # 3. 编码 & 获取向量
    encoded_input = tokenizer(sentences, padding=True, truncation=True, return_tensors='pt')

    with torch.no_grad():
        model_output = model(**encoded_input)
        # 取 [CLS] 位置的向量作为句子表征
        sentence_embeddings = model_output[0][:, 0]
        # L2 归一化（推荐，便于后续计算余弦相似度）
        sentence_embeddings = torch.nn.functional.normalize(sentence_embeddings, p=2, dim=1)

    # 返回 (N, 512) numpy 数组，供调用方入库 / 相似度计算（L2 已归一化，点积即余弦相似度）
    return sentence_embeddings.cpu().numpy()




if __name__ == '__main__':
    # 2. 准备待向量化的文本（你的文稿标题+分类）
    sentences = [
        "政治：特朗普宣布参加2024年总统选举"
    ]
    predict_fun(sentences)

