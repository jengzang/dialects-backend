import re
from itertools import product
from typing import Tuple, Union, List, Optional

from app.common.constants import HIERARCHY_COLUMNS, COLUMN_VALUES, S2T_T2S_MAPPING, default_priority
from app.common.s2t import s2t_pro


def auto_convert_single(user_input: str) -> Union[Tuple[str, int], Tuple[bool, int]]:
    # ▶ 簡體沒匹配，嘗試繁體
    user_input = ''.join(S2T_T2S_MAPPING.get(ch, ch) for ch in user_input)
    # print(user_input)

    def process(input_text: str, priority_key: Optional[str] = None) -> Union[Tuple[str, int], Tuple[bool, int]]:
        result = []
        match_count = 0
        used_columns = set()
        i = 0
        pending_clear = []

        extended_column_values = COLUMN_VALUES.copy()
        extended_column_values["母"] = COLUMN_VALUES["母"] + ["@清"]
        extended_column_values["韻"] = COLUMN_VALUES["韻"] + ["#清"]

        value_to_columns = {}
        for col, values in extended_column_values.items():
            for val in values:
                value_to_columns.setdefault(val, set()).add(col)

        # 優先順序產生器
        def generate_priority(priority_key: Optional[str]):
            if not priority_key:
                return default_priority

            key_order = list(priority_key)
            key_index = {k: i for i, k in enumerate(key_order)}

            ordered = []
            unordered = default_priority.copy()

            # 先把用戶指定的欄位轉為單欄位群組
            for key in key_order:
                ordered.append((key, [key]))

            for label, cols in default_priority:
                new_cols = [c for c in cols if c not in key_order]
                if new_cols:
                    ordered.append((label, new_cols))

            return ordered

        priority = generate_priority(priority_key)

        while i < len(input_text):
            matched = False
            for j in range(3, 0, -1):
                frag = input_text[i:i + j]

                if frag in {"清", "@清", "#清"}:
                    pending_clear.append((frag, i, j))
                    i += j
                    matched = True
                    break
                # 特別優先處理清濁的多字值
                if frag in COLUMN_VALUES.get("清濁", []) and "清濁" not in used_columns:
                    result.append(f"[{frag}]{{清濁}}")
                    used_columns.add("清濁")
                    match_count += 1
                    i += j
                    matched = True
                    break

                for col in sorted(HIERARCHY_COLUMNS, key=len, reverse=True):  # 長欄位名優先
                    if col == "入":
                        continue
                    if frag.endswith(col) and len(frag) > len(col):
                        val = frag[:-len(col)]
                        # print(f"🧪 嘗試匹配 frag='{frag}' → val='{val}', col='{col}'")
                        if val in COLUMN_VALUES.get(col, []):
                            if col not in used_columns:
                                # print(f"[OK] 命中：[ {val} ]{{ {col} }}")
                                result.append(f"[{val}]{{{col}}}")
                                used_columns.add(col)
                                match_count += 1
                                i += j
                                matched = True
                                break  # [OK] 跳出 col 的排序迴圈

                if matched:
                    break  # [OK] 跳出 j 的迴圈（for j in 3,2,1）

                if frag not in value_to_columns:
                    continue

                possible_columns = value_to_columns[frag]
                best_group = None
                for group_key, group_members in priority:
                    if any(col in possible_columns for col in group_members):
                        best_group = group_members
                        break

                if not best_group:
                    continue

                matched_in_group = False
                for col in best_group:
                    if col in possible_columns and col not in used_columns:
                        result.append(f"[{frag}]{{{col}}}")
                        used_columns.add(col)
                        match_count += 1
                        i += j
                        matched = True
                        matched_in_group = True
                        break

                if matched_in_group:
                    break

            if not matched:
                return False, 0

        for frag, _, _ in pending_clear:
            options = value_to_columns.get(frag, set())
            voice_used = "母" in used_columns
            rhyme_used = "韻" in used_columns

            if frag == "@清":
                if "母" in options and "母" not in used_columns:
                    result.append(f"[清]{{母}}")
                    used_columns.add("母")
                    match_count += 1
                else:
                    return False, 0
            elif frag == "#清":
                if "韻" in options and "韻" not in used_columns:
                    result.append(f"[清]{{韻}}")
                    used_columns.add("韻")
                    match_count += 1
                else:
                    return False, 0
            elif frag == "清":
                if "母" in options and "韻" in options:
                    if not voice_used and not rhyme_used:
                        print("[!]『清』有歧義（可屬於母或韻），請使用 @清 或 #清 來明確指定。")
                        return False, 0
                    elif voice_used and not rhyme_used:
                        result.append(f"[清]{{韻}}")
                        used_columns.add("韻")
                        match_count += 1
                    elif rhyme_used and not voice_used:
                        result.append(f"[清]{{母}}")
                        used_columns.add("母")
                        match_count += 1
                    else:
                        return False, 0
                elif "母" in options and "母" not in used_columns:
                    result.append(f"[清]{{母}}")
                    used_columns.add("母")
                    match_count += 1
                elif "韻" in options and "韻" not in used_columns:
                    result.append(f"[清]{{韻}}")
                    used_columns.add("韻")
                    match_count += 1
                else:
                    return False, 0

        return "-".join(result), match_count

    if '-' in user_input:
        prefix, suffix = user_input.split('-', 1)

        fields = []
        temp = suffix
        while temp:
            matched = False
            for field in HIERARCHY_COLUMNS:
                if temp.startswith(field):
                    fields.append(field)
                    temp = temp[len(field):]
                    matched = True
                    break

            # if not matched:
            #     # 嘗試進行簡體轉繁體再匹配
            #     converted = ""
            #     i = 0
            #     while i < len(temp):
            #         ch = temp[i]
            #         converted += s2t_column.get(ch, ch)
            #         i += 1
            #
            #     # 再次嘗試用轉換後的字串匹配
            #     for field in HIERARCHY_COLUMNS:
            #         if converted.startswith(field):
            #             fields.append(field)
            #             temp = temp[len(field):]  # 注意這裡仍用原本的 temp 切除
            #             matched = True
            #             break

            if not matched:
                print(f"[X] 無效欄位名：「{suffix}」中斷於「{temp}」")
                return False, 0

        # 優先順序：傳入的順序最優先
        priority_key = ''.join(fields)

        # 簡體轉繁體邏輯（保留您的原來邏輯）
        clean_str, _ = s2t_pro(user_input, level=2)
        # print(f"[DEBUG] 原輸入：{user_input} → 繁體轉換後再嘗試：{clean_str}")
        user_input = clean_str

        # 取得每個欄位的合法值
        try:
            value_lists = [COLUMN_VALUES[f] for f in fields]
        except KeyError:
            return (False, 0)

        all_results = []
        for combo in product(*value_lists):
            full_input = prefix + ''.join(combo)
            # print("prio")
            # print(priority_key)
            # print(full_input)
            # 使用 generate_priority 動態產生的優先順序
            res = process(full_input, priority_key=priority_key)
            # print(res)
            # res = process(full_input)
            if res[0] is False:
                print(f"[!] 略過非法組合：{full_input}")
                continue
            all_results.append(res)

        if not all_results:
            return (False, 0)
        return all_results

    else:
        # ▶ 先試原始輸入（簡體）
        res = process(user_input)
        if res[0] is not False:
            return res

        # ▶ 簡體沒匹配，嘗試繁體
        translated = ''.join(S2T_T2S_MAPPING.get(ch, ch) for ch in user_input)
        # print(f"[DEBUG] 原輸入：{user_input} → 字典轉換後再嘗試：{translated}")
        return process(translated)


def auto_convert_batch(input_string: str) -> List[Union[Tuple[str, int], Tuple[bool, int]]]:
    import re
    parts = re.split(r"[,;/，；、]+", input_string.strip())
    results = []
    for idx, part in enumerate(parts):
        if part:
            # print(f"🔹 處理第 {idx + 1} 段：{part}")
            res = auto_convert_single(part)
            if isinstance(res, list):
                results.extend(res)
            else:
                results.append(res)
            # print(f"   ⮡ 結果: {res}")
    return results


def split_pho_input(input_value: Union[str, List[str]]) -> List[str]:
    """
    將輸入字串或字串列表，依照常見分隔符（空格、逗號、分號、句號）拆分為項目列表。

    參數：
        input_value: str 或 List[str]

    回傳：
        List[str]
    """
    # 支援的分隔符：空格、, 、； 、. 、tab、中文頓號、全形逗號
    delimiters = r"[ ,;.;、，；\t]+"

    # 確保轉為列表統一處理
    if isinstance(input_value, str):
        input_value = [input_value]

    result = []
    for item in input_value:
        item = item.strip()
        if item:
            parts = re.split(delimiters, item)
            parts = [p for p in parts if p]  # 過濾空字串
            result.extend(parts)

    return result


# result = auto_convert_batch('影组-声')