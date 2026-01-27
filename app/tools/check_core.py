"""
Check工具核心逻辑
从 app/service/utils/check/checks.py 提取
只包含API需要的2个函数，保持原有逻辑完全不变
"""
import re

# 常量定义（原checks.py的第101-102行）
RU_FINALS = set("ptkʔˀᵖᵏᵗbdg")
SUPER_TO_NORMAL = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def 處理自定義編輯指令(df, col_hanzi, col_ipa, command):
    """
    处理自定义编辑指令
    原函数：checks.py 第105-163行

    Args:
        df: DataFrame
        col_hanzi: 汉字列名
        col_ipa: 音标列名
        command: 指令字符串，例如 "c-帥-好; i-帥-jat4"

    Returns:
        (results, errors): 成功消息列表和错误消息列表
    """
    results = []
    errors = []

    commands = [cmd.strip() for cmd in command.split(";") if cmd.strip()]
    for cmd in commands:
        if not cmd:
            continue

        # ✅ 處理「聲調替換」指令：r33>35（入聲） 或 s21>22（平聲）
        tone_match = re.match(r"([rs])(\d{1,4})>(\d{1,4})", cmd)
        if tone_match:
            mode, from_tone, to_tone = tone_match.groups()
            mode_name = "入聲" if mode == "r" else "平聲"
            replaced_count = 0

            for i, row in df.iterrows():
                ipa = str(row.get(col_ipa, "")).strip()
                if not ipa:
                    continue

                # 提取調值
                match = re.search(r"([0-9¹²³⁴⁵⁶⁷⁸⁹⁰]{1,4}[ABCDabcd]?)$", ipa)
                if not match:
                    continue

                tone_raw = match.group(1)
                tone = tone_raw.translate(SUPER_TO_NORMAL)
                head = ipa[:-len(tone_raw)]
                prev_char = head[-1] if head else ""
                ends_with_ru = prev_char in RU_FINALS

                # 判斷是否符合替換條件
                if tone == from_tone:
                    if (mode == 'r' and ends_with_ru) or (mode == 's' and not ends_with_ru):
                        new_ipa = head + to_tone
                        df.at[i, col_ipa] = new_ipa
                        replaced_count += 1

            results.append(f"✅ {mode_name}調替換：{from_tone} → {to_tone}（替換 {replaced_count} 處）")
            continue

        parts = cmd.split("-")

        if len(parts) < 3:
            errors.append(f"❌ 無效指令格式：{cmd}")
            continue

        action = parts[0]
        key = parts[1]
        value = parts[2]
        row_id = int(parts[3]) if len(parts) == 4 and parts[3].isdigit() else None

        # ✅ 處理「全表音標替換」指令：p-原字元-新字元
        if action == "p":
            df[col_ipa] = df[col_ipa].astype(str).str.replace(key, value, regex=False)
            results.append(f"✅ 全表音標替換：{key} → {value}")
            continue

        # ✅ 其他指令（需定位漢字）
        matches = df[df[col_hanzi] == key]
        if len(matches) == 0:
            errors.append(f"❌ 找不到漢字：{key}")
            continue
        elif len(matches) > 1 and not row_id:
            ids = matches.index.tolist()
            suggestion = "; ".join([f"{idx} {key}" for idx in ids])
            errors.append(
                f"⚠️ 找到多個\"{key}\" → 請使用行號區分：\n"
                + f"→ 建議指令：{cmd}-{ids[0]} 或 {cmd}-{ids[1]} 等\n"
                + suggestion
            )
            continue

        # 🔍 確定目標行
        target_row = row_id if row_id is not None else matches.index[0]

        if action == "c":
            if value == "d":
                df.loc[target_row] = ""
                results.append(f"✅ 已清空行 {target_row}（漢字：{key}）")
            else:
                df.at[target_row, col_hanzi] = value
                results.append(f"✅ 替換漢字：{key} → {value}（行 {target_row}）")

        elif action == "i":
            df.at[target_row, col_ipa] = value
            results.append(f"✅ 修改音標：{key} → {value}（行 {target_row}）")

        else:
            errors.append(f"❌ 不支援的指令類型：{action}")

    return results, errors


def 檢查資料格式(df, col_hanzi, col_ipa, display=False, col_note=None):
    """
    检查数据格式
    原函数：checks.py 第166-241行

    Args:
        df: DataFrame
        col_hanzi: 汉字列名
        col_ipa: 音标列名
        display: 是否显示所有数据（默认False）
        col_note: 解释列名（可选）

    Prints:
        检查结果到stdout
    """
    def is_single_chinese(char):
        return len(char) == 1 and '\u4e00' <= char <= '\u9fff'

    def is_normal_ipa(s):
        allowed = set(
            "abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "ŋɑɐɒɓʙβɔɕçðɖɗɘəɚɛɜɞɟʄɡɢʛɣʰɥʜɦɪʝɭɬɫʟɮɰɱɲȵɳŋɳɴɵøœæɶɸɹɻʁʀɽɾʃʂʈʊʋʌʍχʎʑʐʒʔʕʡʢʘʞθʼˈˌːˑ⁰¹²³⁴⁵⁶⁷⁸⁹ⁿˡʲʳˀ"
            "ʦʧʨʂʐʑʒʮʰʲː˞ˠˤ~^̃"
            "ıſɩɷʅɥʯεɝɚᴇãẽĩỹõúαɤᵘᶷᶤᶶᵚʸᶦᵊⁱ◌∅ɯʦʒɿ̍ʷ̯̩"
            "0123456789"
        )
        return all(c in allowed for c in s)

    errors = {
        "非單字漢字": [],
        "異常音標": [],
        "缺聲調": []
    }
    # print(df)
    for i, row in df.iterrows():
        hanzi = str(row.get(col_hanzi, "")).strip()
        ipa = str(row.get(col_ipa, "")).strip()

        if not hanzi or not ipa:
            continue  # 跳過空行或空漢字/音標

        if not is_single_chinese(hanzi):
            errors["非單字漢字"].append((i, hanzi))


        # 邏輯：數字(1-4位) + 可選的(ABCDabcd) + 結尾
        pattern = r"[0-9¹²³⁴⁵⁶⁷⁸⁹⁰]{1,4}[ABCDabcd]?$"
        match = re.search(pattern, ipa.strip())
        if not match:
            # 既不符合純數字結尾，也不符合數字+字母結尾
            errors["缺聲調"].append((i, hanzi))
            continue

        if any(sep in ipa for sep in ",;/\\"):
            # 如果包含分隔符，拆分成多个部分
            parts = re.split(r"[,;/\\]", ipa)
        else:
            # 如果没有分隔符，直接将 ipa 字符串作为一个整体检查
            parts = [ipa]
        if ipa.isdigit():
            errors["異常音標"].append((i, hanzi, ipa))
            continue
        if not all(is_normal_ipa(p.strip()) for p in parts if p.strip()):
            errors["異常音標"].append((i, hanzi, ipa))

    # 錯誤輸出
    for k, v in errors.items():
        if v:
            print(f"\n⚠️ [{k}] 發現 {len(v)} 項：")
            count = 0  # 用於控制每行最多顯示4個錯誤
            for item in v:
                if count == 4:  # 每4个错误换行
                    print()  # 换行
                    count = 0  # 重置计数器
                print(item, end="   ")  # 不换行，条目之间加空格
                count += 1

    if not any(errors.values()):
        print("✅ 格式檢查通過，無異常")

    # 額外：顯示每一行內容（可選）
    if display:
        print("\n🧾 所有資料（行號｜漢字｜音標｜註釋）：")
        for i, row in df.iterrows():
            hanzi = str(row.get(col_hanzi, "")).strip()
            ipa = str(row.get(col_ipa, "")).strip()
            note = str(row.get(col_note, "")).strip() if col_note and col_note in row else ""

            # 跳過漢字與音標都為空的行
            if not hanzi and not ipa:
                continue

            print(f"[{i}] {hanzi}｜{ipa}｜{note}")


def 整理並顯示調值(df, col_hanzi, col_ipa):
    """
    统计并返回各调值的字数和具体字符

    Args:
        df: DataFrame
        col_hanzi: 汉字列名
        col_ipa: 音标列名

    Returns:
        dict: {
            "ru_tones": {  # 入声
                "5": {"count": 10, "chars": ["食", "得", ...]},
                "3": {"count": 8, "chars": [...]},
                ...
            },
            "shu_tones": {  # 舒声
                "55": {"count": 20, "chars": [...]},
                "22": {"count": 15, "chars": [...]},
                ...
            }
        }
    """
    ru_tones = {}  # 入声调值统计
    shu_tones = {}  # 舒声调值统计

    for i, row in df.iterrows():
        hanzi = str(row.get(col_hanzi, "")).strip()
        ipa = str(row.get(col_ipa, "")).strip()

        if not hanzi or not ipa:
            continue

        # 提取调值
        match = re.search(r"([0-9¹²³⁴⁵⁶⁷⁸⁹⁰]{1,4}[ABCDabcd]?)$", ipa)
        if not match:
            continue

        tone_raw = match.group(1)
        tone = tone_raw.translate(SUPER_TO_NORMAL)
        head = ipa[:-len(tone_raw)]
        prev_char = head[-1] if head else ""
        ends_with_ru = prev_char in RU_FINALS

        # 根据类型统计
        if ends_with_ru:
            # 入声
            if tone not in ru_tones:
                ru_tones[tone] = {"count": 0, "chars": []}
            ru_tones[tone]["count"] += 1
            if len(ru_tones[tone]["chars"]) < 20:  # 最多显示20个字
                ru_tones[tone]["chars"].append(hanzi)
        else:
            # 舒声
            if tone not in shu_tones:
                shu_tones[tone] = {"count": 0, "chars": []}
            shu_tones[tone]["count"] += 1
            if len(shu_tones[tone]["chars"]) < 20:  # 最多显示20个字
                shu_tones[tone]["chars"].append(hanzi)

    return {
        "ru_tones": ru_tones,
        "shu_tones": shu_tones
    }


