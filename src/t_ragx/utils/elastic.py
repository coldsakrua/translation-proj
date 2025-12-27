# import json
# import logging
# from hashlib import sha1

# import numpy as np
# import pandas as pd
# from elasticsearch import Elasticsearch
# from tqdm.notebook import tqdm

# from .heuristic import clean_text, is_noise
# from .heuristic import lang_detect as heuristic_lang_detect
# from ..processors.constants import DEFAULT_MEMORY_INDEX
# from ..models.constants import LANG_BY_LANG_CODE

# logger = logging.getLogger("t_ragx")


# def index_doc(df, index="translation_memory_demo"):
#     """
#     Formatted index action generator helper to help upload records to Elasticsearch

#     Args:
#         df:
#         index:

#     Returns:

#     """
#     for record in df.to_dict(orient="records"):
#         # pop none
#         for k in record:
#             if record[k] is None:
#                 record.pop(k)
#         yield ('{ "index" : { "_index" : "%s", "_id": "%s"}}' % (
#             index, sha1(record[record['id_key']].encode('utf8')).hexdigest()))
#         yield json.dumps(record, default=int)


# def upsert_doc(df: pd.DataFrame, index: str = None):
#     """
#     Formatted upsert action generator helper to help upload records to Elasticsearch

#     Args:
#         df:
#         index:

#     Returns:

#     """
#     if index is None:
#         index = DEFAULT_MEMORY_INDEX

#     for record in df.to_dict(orient="records"):
#         # pop none
#         pop_list = []
#         for k in record:
#             if record[k] is None:
#                 pop_list.append(k)

#         for k in pop_list:
#             record.pop(k)
#         yield ('{ "update" : {"_index" : "%s", "_id" : "%s", "retry_on_conflict" : 3} }' % (
#             index, sha1(record[record['id_key']].encode('utf8')).hexdigest()))
#         yield '{ "doc" : %s, "doc_as_upsert" : true }' % json.dumps(record, default=int)


# def filter_df(df: pd.DataFrame, source_lang: str = 'ja', lang_cols: list = None):
#     if lang_cols is None:
#         lang_cols = list(LANG_BY_LANG_CODE.keys())

#     lang_cols = list(set(lang_cols).intersection(df.columns))

#     df.dropna(subset=lang_cols, how='all', inplace=True)
#     df.drop_duplicates(subset=[source_lang], inplace=True)
#     df[source_lang] = df[source_lang].apply(clean_text)
#     df = df[~df[source_lang].map(is_noise)]
#     df.reset_index(drop=True, inplace=True)

#     for c in lang_cols:
#         df = df[~df[c].str.contains("\n", na=False)]

#     for c in lang_cols:
#         if c in ['ja', 'zh']:
#             str_len = df[c].str.len()
#             df = df[
#                 ((350 > str_len) & (str_len > 4)) | (str_len.isna())
#                 ]
#         elif c in ['en']:
#             word_count = df[c].str.split(" ").str.len()
#             df = df[
#                 ((100 > word_count) & (word_count > 3)) | (word_count.isna())
#                 ]

#     for c in lang_cols:
#         detected_lang = df[c].apply(heuristic_lang_detect)
#         df = df[(c == detected_lang) | (detected_lang.isna())]

#     df.reset_index(drop=True, inplace=True)

#     return df


# def upload_df(df: pd.DataFrame, es_client: Elasticsearch, id_key: str = 'ja', batch_size: int = 10000,
#               index: str = None) -> None:
#     """
#     upload_df

#     Args:
#         df:
#         es_client:
#         id_key: The language column to hash (sha1) as ID. Duplicate records with common id will be merged.
#                         id_key should be in df.columns
#         batch_size:
#         index: Defaulted to be "translation_memory". Should be explicitly set for in-task memories

#     Returns:

#     """
#     df = filter_df(df, source_lang=id_key)
#     df['id_key'] = id_key
#     if len(df) < 1:
#         print("Empty dataset")
#         return
#     batch_idx = np.array_split(range(len(df)), max(int(len(df) / batch_size), 1))
#     for select_idx in tqdm(batch_idx):
#         try:
#             r = es_client.bulk(upsert_doc(df.iloc[select_idx]), index)  # return a dict
#         except:
#             raise r


# def csv_to_elastic(file_path,
#                    id_key='ja',
#                    elasticsearch_host: str = "localhost",
#                    es_client: Elasticsearch = None,
#                    batch_size=10000,
#                    read_csv_config: dict = {},
#                    index=None,
#                    elastic_client_args: dict = {}):
#     """
#     Upload a CSV file to Elasticsearch
#     The input csv should be parallel texts with the language code as their header
#     For example:
#         | ja  | en        | zh    |
#         |-----|-----------|-------|
#         | 例1 | example 1 | 範例1 |
#         |     |           |       |
#         |     |           |       |


#     Args:

#         file_path:
#         id_key: The language column to hash (sha1) as ID. Duplicate records with common id will be merged.
#                         id_key should be in df.columns
#         elasticsearch_host:
#         es_client:
#         batch_size:
#         read_csv_config:
#         index: Defaulted to be "translation_memory". Should be explicitly set for in-task memories
#         elastic_client_args:

#     Returns:

#     """

#     if es_client is None:
#         es_client = Elasticsearch(
#             elasticsearch_host,  # Elasticsearch endpoint
#             **elastic_client_args
#         )

#     df = pd.read_csv(file_path, **read_csv_config)
#     assert len(df.columns) > 1, "The CSV file has only one column"

#     if len(set(df.columns).intersection(LANG_BY_LANG_CODE.keys())) < 2:
#         logger.warning(f"The columns of the CSV are {df.columns}")

#     upload_df(df, es_client, id_key=id_key, batch_size=batch_size, index=index)
import json
import logging
from hashlib import sha1

import numpy as np
import pandas as pd
from elasticsearch import Elasticsearch
from tqdm import tqdm

from .heuristic import clean_text, is_noise
from .heuristic import lang_detect as heuristic_lang_detect
from ..processors.constants import DEFAULT_MEMORY_INDEX

logger = logging.getLogger("t_ragx")

# 仅保留中英文语言配置
EN_ZH_LANG_CODES = {
    'en': 'English',
    'zh': 'Chinese'
}


def index_doc(df, index="translation_memory_demo"):
    """生成索引操作的格式化数据"""
    for record in df.to_dict(orient="records"):
        # 移除空值字段
        for k in list(record.keys()):
            if record[k] is None:
                record.pop(k)
        # 基于id_key生成唯一ID
        yield ('{ "index" : { "_index" : "%s", "_id": "%s"}}' % (
            index, sha1(record[record['id_key']].encode('utf8')).hexdigest()))
        yield json.dumps(record, default=int)


def upsert_doc(df: pd.DataFrame, index: str = None):
    """生成更新/插入操作的格式化数据"""
    if index is None:
        index = DEFAULT_MEMORY_INDEX

    for record in df.to_dict(orient="records"):
        # 移除空值字段
        pop_list = [k for k in record if record[k] is None]
        for k in pop_list:
            record.pop(k)
        # 基于id_key生成唯一ID，存在则更新，不存在则插入
        yield ('{ "update" : {"_index" : "%s", "_id" : "%s", "retry_on_conflict" : 3} }' % (
            index, sha1(record[record['id_key']].encode('utf8')).hexdigest()))
        yield '{ "doc" : %s, "doc_as_upsert" : true }' % json.dumps(record, default=int)


def filter_df_en_zh(df: pd.DataFrame, source_lang: str = 'en', lang_cols: list = None):
    """
    过滤并清洗中英文翻译数据
    
    Args:
        df: 包含中英文列的数据框
        source_lang: 源语言代码（'en'或'zh'）
        lang_cols: 语言列列表，默认['en', 'zh']
    """
    if lang_cols is None:
        lang_cols = ['en', 'zh']
    
    # 仅保留存在的中英文列
    lang_cols = list(set(lang_cols).intersection(df.columns))
    if not lang_cols:
        raise ValueError("数据框中未找到中英文列（en/zh）")
    
    # 确保源语言列存在
    if source_lang not in lang_cols:
        raise ValueError(f"源语言列 '{source_lang}' 不在数据框列中")
    
    # 移除所有语言列都为空的行
    df.dropna(subset=lang_cols, how='all', inplace=True)
    
    # 基于源语言去重
    df.drop_duplicates(subset=[source_lang], inplace=True)
    
    # 清理源语言文本
    df[source_lang] = df[source_lang].apply(clean_text)
    
    # 移除噪音文本
    df = df[~df[source_lang].map(is_noise)]
    df.reset_index(drop=True, inplace=True)

    # 移除包含换行符的文本（避免格式问题）
    for c in lang_cols:
        df = df[~df[c].str.contains("\n", na=False)]

    # 中英文长度过滤（中文按字符，英文按单词）
    for c in lang_cols:
        if c == 'zh':
            str_len = df[c].str.len()
            df = df[((350 > str_len) & (str_len > 4)) | (str_len.isna())]
        elif c == 'en':
            word_count = df[c].str.split(" ").str.len()
            df = df[((100 > word_count) & (word_count > 3)) | (word_count.isna())]

    # 语言检测验证（确保列内容与语言代码匹配）
    for c in lang_cols:
        detected_lang = df[c].apply(heuristic_lang_detect)
        if c == 'zh':
            # 允许中文变体（zh-cn/zh-tw等）
            df = df[(detected_lang.str.startswith('zh')) | (detected_lang.isna())]
        else:  # en
            df = df[(detected_lang == 'en') | (detected_lang.isna())]

    df.reset_index(drop=True, inplace=True)
    return df


def upload_df_en_zh(df: pd.DataFrame, es_client: Elasticsearch, id_key: str = 'en', batch_size: int = 10000,
                   index: str = None) -> None:
    """
    上传中英文数据到Elasticsearch
    
    Args:
        df: 包含中英文列的数据框
        es_client: Elasticsearch客户端实例
        id_key: 用于生成唯一ID的语言列（'en'或'zh'）
        batch_size: 批量处理大小
        index: 目标索引名称
    """
    # 过滤数据
    df = filter_df_en_zh(df, source_lang=id_key)
    df['id_key'] = id_key  # 记录用于生成ID的字段
    
    if len(df) < 1:
        logger.info("过滤后无有效数据可上传")
        return
    
    # 分批处理
    batch_idx = np.array_split(range(len(df)), max(int(len(df) / batch_size), 1))
    for select_idx in tqdm(batch_idx, desc="上传数据到Elasticsearch"):
        try:
            response = es_client.bulk(upsert_doc(df.iloc[select_idx], index=index), index=index)
            if response.get('errors', False):
                logger.warning(f"批量上传存在错误: {response['errors']}")
        except Exception as e:
            logger.error(f"批量上传失败: {str(e)}")
            raise


def csv_to_elastic(file_path,
                   id_key='en',  # 默认使用英文列作为ID基准
                   elasticsearch_host: str = "localhost",
                   es_client: Elasticsearch = None,
                   batch_size=10000,
                   read_csv_config: dict = {},
                   index=None,
                   elastic_client_args: dict = {}):
    """
    从CSV文件上传中英文翻译数据到Elasticsearch
    
    Args:
        file_path: CSV文件路径
        id_key: 用于生成ID的语言列（'en'或'zh'）
        elasticsearch_host: Elasticsearch主机地址
        es_client: 已初始化的Elasticsearch客户端（可选）
        batch_size: 批量处理大小
        read_csv_config: pandas.read_csv的配置参数
        index: 目标索引名称
        elastic_client_args: Elasticsearch客户端初始化参数
    """
    # 初始化ES客户端
    if es_client is None:
        es_client = Elasticsearch(elasticsearch_host, **elastic_client_args)
    
    # 读取CSV数据
    df = pd.read_csv(file_path,** read_csv_config)
    if len(df.columns) < 2:
        raise ValueError("CSV文件至少需要包含中英文两列")
    
    # 验证是否包含中英文列
    required_cols = {'en', 'zh'}
    if not required_cols.intersection(df.columns):
        raise ValueError(f"CSV文件必须包含'en'和'zh'列，当前列: {df.columns}")
    
    # 上传数据
    upload_df_en_zh(
        df=df,
        es_client=es_client,
        id_key=id_key,
        batch_size=batch_size,
        index=index
    )