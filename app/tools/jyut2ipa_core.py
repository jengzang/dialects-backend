"""
Jyut2IPA工具核心逻辑
从 app/service/utils/jyut2ipa/replace.py 提取
保持原有逻辑完全不变
"""
import re
import pandas as pd

# 元音集合（原replace.py第8行）
vowels = set('aeuioy')

# 替换规则DataFrame（全局变量，需要在使用前初始化）
replace_df = None


def init_replace_df(replace_data):
    """
    初始化替换规则DataFrame

    Args:
        replace_data: 替换规则列表，格式 [[to_replace, replacement, condition], ...]
    """
    global replace_df
    replace_df = pd.DataFrame(replace_data, columns=['to_replace', 'replacement', 'condition']).astype(str)


def clean_and_extract_notes_fixed(text):
    """
    清理并提取注释
    原函数：replace.py 第11-19行

    Args:
        text: 粤拼文本

    Returns:
        (cleaned, notes): 清理后的文本和注释
    """
    if not text:
        return "", ""
    symbols = re.findall(r'[？?＊*]', text)
    chinese = re.findall(r'[\u4e00-\u9fa5]', text)
    notes = ''.join([c for c in chinese if c != '或'] + symbols)
    cleaned = re.sub(r'[？?＊*]', '', text)
    cleaned = ''.join(c for c in cleaned if c not in chinese or c == '或')
    return cleaned, notes


def split_pinyin(pinyin):
    """
    拆分粤拼
    原函数：replace.py 第22-57行

    Args:
        pinyin: 粤拼字符串

    Returns:
        (initial, final, tone, medial, coda): 声母、韵母、音调、韵腹、韵尾
    """
    initial = final = tone = medial = coda = ''
    for ch in pinyin:
        if ch.isdigit():
            tone += ch
        else:
            if tone:
                final += ch
            else:
                initial += ch
    for i, ch in enumerate(initial):
        if ch in vowels:
            final = initial[i:] + final
            initial = initial[:i]
            break
    else:
        # ❗ 如果没有元音，检查是否结尾是 ng/n/m，作为韵母处理
        if initial.endswith(('ng', 'n', 'm')):
            final = initial[-2:] + final if initial.endswith('ng') else initial[-1:] + final
            initial = initial[:-2] if initial.endswith('ng') else initial[:-1]
    # === 新增特殊处理 ===
    if final in ['ng', 'n', 'm']:
        medial = final  # ✅ 作为韵腹处理
        coda = ""
    elif len(final) == 1 and final[0] in vowels:
        medial = final
        coda = ""
    elif len(final) > 1:
        if final[-1] in 'iu' and len([char for char in final if char in vowels]) > 1:
            medial = final[:-1]
            coda = final[-1]
        else:
            medial = "".join([char for char in final if char in vowels])
            coda = "".join([char for char in final if char not in vowels])

    return initial, final, tone, medial, coda


def replace(component, condition, rules_df=None):
    """
    应用替换规则
    原函数：replace.py 第61-72行

    Args:
        component: 要替换的组件（声母/韵腹/韵尾/音调）
        condition: 条件（sm/wf/wm/jd）
        rules_df: 替换规则DataFrame（可选，默认使用全局replace_df）

    Returns:
        替换后的结果
    """
    if not component:
        return ''

    # 使用传入的rules_df或全局replace_df
    df_to_use = rules_df if rules_df is not None else replace_df
    
    # 验证DataFrame不为空
    if df_to_use is None or len(df_to_use) == 0:
        print(f"  [{condition}] 警告: 规则DataFrame为空，无法替换: {component}")
        return component

    # 筛选匹配condition的规则
    filtered_df = df_to_use[df_to_use['condition'] == condition]
    if len(filtered_df) == 0:
        print(f"  [{condition}] 无匹配规则: {component}")
        return component
    
    sorted_df = filtered_df.sort_values(
        by='to_replace', key=lambda x: x.str.len(), ascending=False)
    
    for _, row in sorted_df.iterrows():
        if row['to_replace'] in component:
            result = component.replace(row['to_replace'], row['replacement'])
            # print(f"  [{condition}] 替换: {component} → {result}")
            return result
    print(f"  [{condition}] 无替换: {component}")
    return component


def process_yutping(text, custom_replace_data=None):
    """
    主处理逻辑：粤拼转IPA
    原函数：replace.py 第76-140行

    Args:
        text: 粤拼文本
        custom_replace_data: 自定义替换规则（可选），格式 [["aa", "a", "wf"], ...]

    Returns:
        pd.Series: [声母, 韵母, 音调, 韵腹, 韵尾, 声母IPA, 韵腹IPA, 韵尾IPA, 音调IPA, IPA, 注释]
    """
    # 如果提供了自定义规则，临时创建DataFrame
    if custom_replace_data is not None and len(custom_replace_data) > 0:
        temp_replace_df = pd.DataFrame(
            custom_replace_data,
            columns=['to_replace', 'replacement', 'condition']
        ).astype(str)
        # 验证DataFrame不为空
        if len(temp_replace_df) > 0:
            rules_df = temp_replace_df
            # print(f"[DEBUG] 使用自定义规则DataFrame，共{len(rules_df)}条规则")
        else:
            # 如果DataFrame为空，回退到默认规则
            # print(f"[WARN] 自定义规则DataFrame为空，使用默认规则")
            if replace_df is None:
                raise RuntimeError("replace_df未初始化，请先调用init_replace_df()")
            rules_df = replace_df
    else:
        # 使用全局默认规则
        if replace_df is None:
            raise RuntimeError("replace_df未初始化，请先调用init_replace_df()")
        rules_df = replace_df
        # print(f"[DEBUG] 使用默认规则DataFrame，共{len(rules_df)}条规则")

    if not text:
        return pd.Series([""] * 11)

    text_cleaned, notes = clean_and_extract_notes_fixed(text)
    # print(f"\n🎯 粤拼原始: {text} → 清理: {text_cleaned} | 注释: {notes}")

    parts = re.split(r'(或|/|\||\\)', text_cleaned)
    # print(f"🧩 分段结构: {parts}")

    fields = {
        '声母': [], '韵母': [], '音调': [], '韵腹': [], '韵尾': [],
        '声母IPA': [], '韵腹IPA': [], '韵尾IPA': [], '音调IPA': [], 'IPA': []
    }

    for part in parts:
        if part in ['或', '/', '|', '\\']:
            for key in fields:
                fields[key].append(part)
        elif part.strip():
            ini, fin, tone, med, coda = split_pinyin(part)
            # print(f"🔍 拆分: {part} => 声母: {ini}, 韵母: {fin}, 音调: {tone}, 韵腹: {med}, 韵尾: {coda}")

            # 使用传入的rules_df进行替换
            ini_ipa = replace(ini, 'sm', rules_df) or 'ʔ'
            if not ini_ipa.strip():
                ini_ipa = 'ʔ'
            if med in ['ng', 'n', 'm']:
                med_ipa = replace(med, 'wm', rules_df)  # ✅ 虽为韵腹，但用韵尾的替换规则
                print("  ✅ 特例: ng/n/m 虽为韵腹，但使用 wm 替换")
            elif med:
                med_ipa = replace(med, 'wf', rules_df)
            else:
                med_ipa = ''
            coda_ipa = replace(coda, 'wm', rules_df)
            tone_ipa = replace(tone, 'jd', rules_df)
            ipa = ini_ipa + med_ipa + coda_ipa + tone_ipa

            fields['声母'].append(ini)
            fields['韵母'].append(fin)
            fields['音调'].append(tone)
            fields['韵腹'].append(med)
            fields['韵尾'].append(coda)
            fields['声母IPA'].append(ini_ipa)
            fields['韵腹IPA'].append(med_ipa)
            fields['韵尾IPA'].append(coda_ipa)
            fields['音调IPA'].append(tone_ipa)
            fields['IPA'].append(ipa)
    
    # 【诊断日志】检查fields是否被填充
    # print(f"[DEBUG] fields填充情况: 声母={len(fields['声母'])}, 韵母={len(fields['韵母'])}, IPA={len(fields['IPA'])}")
    # if len(fields['声母']) > 0:
    #     print(f"[DEBUG] fields内容示例: 声母={fields['声母']}, IPA={fields['IPA']}")

    def conditional_join(parts):
        if not parts:  # 如果列表为空，直接返回空字符串
            return ''
        valid = [p for p in parts if p not in ['或', '/', '|', '\\'] and p.strip()]
        if len(valid) == 0:
            return ''
        if len(set(valid)) == 1:
            return valid[0]  # 所有有效部分相同，返回一个
        if len(valid) >= 2:
            return ''.join(parts)
        else:
            return ''.join(p for p in parts if p not in ['或', '/', '|', '\\'])

    # 【诊断日志】在调用conditional_join之前检查
    # print(f"[DEBUG] 准备调用conditional_join，fields状态:")
    # for key in ['声母', '韵母', '音调', '韵腹', '韵尾', '声母IPA', '韵腹IPA', '韵尾IPA', '音调IPA', 'IPA']:
        # print(f"  {key}: {fields[key]} (长度={len(fields[key])})")
    
    row_result = [conditional_join(fields[key]) for key in [
        '声母', '韵母', '音调', '韵腹', '韵尾',
        '声母IPA', '韵腹IPA', '韵尾IPA', '音调IPA', 'IPA'
    ]] + [notes]
    
    # 【诊断日志】检查conditional_join的结果
    # print(f"[DEBUG] conditional_join结果: {row_result[:10]}")  # 前10个元素

    # 【诊断日志】检查最终结果
    if len(row_result) != 11:
        print(f"[ERROR] 返回结果长度错误: {len(row_result)}, 期望11")
    
    result_series = pd.Series(row_result)
    # print(f"[DEBUG] 最终返回结果: {result_series.tolist()}")
    
    return result_series
