import os

from opencc import OpenCC

from common.config import ZHENGZI_PATH, MULCODECHAR_PATH


opencc_s2t = OpenCC('s2t.json')
# ========== 繁體轉換函數 ==========
def s2t_pro(字組, level=1):
    variant_file = os.path.join(os.path.dirname(__file__), ZHENGZI_PATH)
    mulcode_file = os.path.join(os.path.dirname(__file__), MULCODECHAR_PATH)

    normVariants = {}
    stVariants = {}
    n2o_dict = {}

    # 讀取正字表
    for 行 in open(variant_file, encoding="utf-8"):
        if 行.startswith("#"):
            continue  # 行首為註解，跳過

        行 = 行.rstrip("\n")
        列 = 行.split("\t")
        if len(列) < 2:
            continue

        原字 = 列[0].strip()
        對應字串 = 列[1].split("#")[0].strip()  # 去除 # 後的註解
        候選字列表 = 對應字串.split()

        if level == 1:
            if "#" in 行:
                continue  # 含 # 的行不處理
            if len(候選字列表) > 1:
                continue  # 多候選字，不處理

        stVariants[原字] = 對應字串

    # 讀取 mulcodechar.dt
    for 行 in open(mulcode_file, encoding="utf-8"):
        if not 行 or 行[0] == "#":
            continue
        列 = 行.strip().split("-")
        if len(列) < 2:
            continue
        n2o_dict[列[0]] = 列[1]

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
