import os

from opencc import OpenCC

from common.path import ZHENGZI_PATH, MULCODECHAR_PATH

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
def s2t_pro(字組, level=1):
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
        對應字串 = stVariants.get(字, None)

        if 對應字串 is None and level == 2:
            對應字串 = opencc_s2t.convert(原字)
            # print(f"【OpenCC】{原字} → {對應字串}")  # Debug 用
        elif 對應字串 is None:
            對應字串 = 原字

        對應字串 = n2o(對應字串)

        # 保留候選字列表
        if " " in 對應字串:
            候選 = 對應字串.split()
        else:
            候選 = [對應字串]
        mapping.append((原字, 候選))
        result_chars.extend(候選)

    clean_str = ''.join(result_chars)

    return clean_str, mapping
