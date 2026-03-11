import os

from opencc import OpenCC

from app.common.path import ZHENGZI_PATH, MULCODECHAR_PATH

opencc_s2t = OpenCC('s2t.json')

# 全局缓存（启动时加载一次）
_variant_cache = None

def _load_variant_data():
    """加载并缓存正字表和 mulcode 数据（只执行一次）"""
    global _variant_cache

    # 如果已缓存，直接返回
    if _variant_cache is not None:
        return _variant_cache

    variant_file = os.path.join(os.path.dirname(__file__), ZHENGZI_PATH)
    mulcode_file = os.path.join(os.path.dirname(__file__), MULCODECHAR_PATH)

    stVariants = {}
    n2o_dict = {}

    # 读取正字表（只执行一次）
    for 行 in open(variant_file, encoding="utf-8"):
        if 行.startswith("#"):
            continue  # 行首為註解，跳過

        行 = 行.rstrip("\n")
        列 = 行.split("\t")
        if len(列) < 2:
            continue

        原字 = 列[0].strip()
        對應字串 = 列[1].split("#")[0].strip()  # 去除 # 後的註解
        stVariants[原字] = 對應字串

    # 读取 mulcodechar.dt（只执行一次）
    for 行 in open(mulcode_file, encoding="utf-8"):
        if not 行 or 行[0] == "#":
            continue
        列 = 行.strip().split("-")
        if len(列) < 2:
            continue
        n2o_dict[列[0]] = 列[1]

    # 缓存结果
    _variant_cache = (stVariants, n2o_dict)
    return _variant_cache

# ========== 繁體轉換函數 ==========
def s2t_pro(字組, level=1, keep_all_layers=False):
    """
    简繁转换函数，支持三层转换：正字表 → OpenCC → 新旧字形(n2o)

    Args:
        字組: 输入字符列表或字符串
        level: 转换级别 (1=仅正字表, 2=正字表+OpenCC)
        keep_all_layers: 是否保留各层转换结果
            - False: 只保留最终结果（默认，保持向后兼容）
            - True: 保留各层转换的中间结果（不含原始输入）

    Returns:
        (clean_str, mapping)
        - clean_str: 所有候选字拼接的字符串
        - mapping: [(原字, [候选字列表]), ...]
    """
    # 使用缓存的数据
    stVariants_all, n2o_dict = _load_variant_data()

    # 根据 level 过滤
    if level == 1:
        # 过滤掉包含多个候选字的条目和带 # 注释的条目
        stVariants = {}
        for 原字, 對應字串 in stVariants_all.items():
            if " " not in 對應字串:
                stVariants[原字] = 對應字串
    else:
        stVariants = stVariants_all

    def n2o(s):
        return ''.join(n2o_dict.get(i, i) for i in s)

    result_chars = []
    mapping = []

    for 字 in 字組:
        原字 = 字

        if keep_all_layers:
            candidates_set = set()

        # 第1层：正字表
        對應字串_1 = stVariants.get(字, None)
        if 對應字串_1 is not None:
            if keep_all_layers:
                # 保留第1层的结果
                if " " in 對應字串_1:
                    candidates_set.update(對應字串_1.split())
                else:
                    candidates_set.add(對應字串_1)
            對應字串 = 對應字串_1
        else:
            對應字串 = None

        # 第2层：OpenCC
        if 對應字串 is None and level == 2:
            對應字串_2 = opencc_s2t.convert(原字)
            if keep_all_layers:
                candidates_set.add(對應字串_2)
            對應字串 = 對應字串_2
            # print(f"【OpenCC】{原字} → {對應字串}")  # Debug 用
        elif 對應字串 is None:
            對應字串 = 原字

        # 第3层：n2o 新旧字形转换
        對應字串_3 = n2o(對應字串)

        if keep_all_layers:
            # 保留第3层的结果
            if " " in 對應字串_3:
                candidates_set.update(對應字串_3.split())
            else:
                candidates_set.add(對應字串_3)
            候選 = list(candidates_set)
        else:
            # 默认行为：只保留最终结果
            if " " in 對應字串_3:
                候選 = 對應字串_3.split()
            else:
                候選 = [對應字串_3]

        mapping.append((原字, 候選))
        result_chars.extend(候選)

    clean_str = ''.join(result_chars)

    return clean_str, mapping
