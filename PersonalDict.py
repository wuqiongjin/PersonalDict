#coding=utf-8
import tkinter as tk
import os
import sys
import re
import threading
import time
import getpass
import json

USER = getpass.getuser()
DICT_PATH = r'/Example Sentences/'
DICT_INFO = r'C:/Users/{USER}/.dict_info.dat'

config_obj = {}
SPECIAL_SYMBOL_LIST = []
# NAME_MAP2_SPECIAL_SYMBOL: 'Attribute' : '@'
# SPECIAL_SYMBOL_MAP2_PRINT_NAME: '@' : '(Attribute)\n'
NAME_MAP2_SPECIAL_SYMBOL = {}
SPECIAL_SYMBOL_MAP2_PRINT_NAME = {}
INVALIDATION_KEY_LIST = []
DUPLICATE_CONTAIN_SYMBOL_FILTER = {}

file_list = {}      # 单词本的文件列表
my_dict = {}        # key : value, value未经任何格式规划处理
format_dict = {}    # 格式化字典, 里面存储了已经按照 固定格式 的单词内容
key_list = []       # 提供模糊搜索数据来源的key的集合(其实就是所有的key)
special_forms_map2_symbolform_original_lt = {}  # { 特殊变形 : [['(Attribute)', 原型1], ['(Deformation)', 原型2], ...]] } 注意: value是一个二维数组.
phrase_list = []   # 词组列表 （保存词组的列表, 里面存的是key)

lock = threading.Lock()
quit_flag = False
need_update = False

def init_parameters():
    global DICT_INFO, DICT_PATH, config_obj, SPECIAL_SYMBOL_LIST, NAME_MAP2_SPECIAL_SYMBOL, SPECIAL_SYMBOL_MAP2_PRINT_NAME, INVALIDATION_KEY_LIST

    DICT_INFO = DICT_INFO.format(USER=USER)
    cur_file_path = os.path.realpath(__file__)
    index = cur_file_path.rfind("\\")
    DICT_PATH = cur_file_path[:index] + DICT_PATH
    load_file_list()    # 初始化 file_list 变量

    # load config
    with open(f'{cur_file_path[:index]}/pd_config.json', 'r') as f:
        config_obj = json.load(f)

    # init global parameter
    SPECIAL_SYMBOL_LIST = list(config_obj['SYMBOL_MAP'].values())
    NAME_MAP2_SPECIAL_SYMBOL = dict([key, val] for key, val in config_obj['SYMBOL_MAP'].items())    # 注意:列表推导式前面, 必须是 [key, val], 因为dict()方法只接受list转化过来
    SPECIAL_SYMBOL_MAP2_PRINT_NAME = dict([val, f'({key})\n'] for key, val in config_obj['SYMBOL_MAP'].items())
    INVALIDATION_KEY_LIST = config_obj['INVALID_KEY_LIST']

    # DUPLICATE_CONTAIN_SYMBOL_FILTER 用于区分 ~ 和 !~
    for symbol in SPECIAL_SYMBOL_LIST:
        for s in symbol:
            DUPLICATE_CONTAIN_SYMBOL_FILTER[s] = 1

def update_dict(filename : str):
    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()
        if lines == '\n' or lines == '':
            return
        for line in lines:
            line = line.strip()
            if line == '\n' or line == '':
                continue
            try:
                key_value = line.split(':')
                if key_value[0] in key_list:
                    my_dict[key_value[0]] = key_value[1].strip()
                else:
                    my_dict[key_value[0]] = key_value[1].strip()
                    key_list.append(key_value[0])
                    # 判断是否是词组, 如果是的话, 加入到 词组列表 当中
                    if key_value[0].count(' '):
                        phrase_list.append(key_value[0])
            except:
                continue

def load_dict():
    """
        @function: 获取字典目录下的所有单词本，读取这些单词本的内容，将其存入my_dict当中
    """
    for filename in os.listdir(DICT_PATH):
        filename = DICT_PATH + filename # 拼接字典文件的路径前缀
        update_dict(filename)

def load_file_list():
    """
        @function: 遍历DICT_PATH下的单词本, 将单词本的文件名称存储在 file_list 当中, 以便于后续使用file_list
    """
    try:
        with open(DICT_INFO, "r", encoding="utf-8") as f:
            for filename in os.listdir(DICT_PATH):
                filename = DICT_PATH + filename
                while True:
                    line = f.readline()
                    if line == '':
                        break
                    else:
                        res = line.split(':')
                        if len(res) == 2:
                            file_list[res[0]] = res[1].rstrip('\n')
    except Exception as e:
        print(f"[WARNING]: load_key_list error!  --- filename:{e.__traceback__.tb_frame.f_globals['__file__']} - line:{e.__traceback__.tb_lineno}")

def monitor_dict_update():
    while not quit_flag:
        for filename in os.listdir(DICT_PATH):
            filename = DICT_PATH + filename # 拼接字典文件的路径前缀
            file_info = os.stat(filename)

            if filename not in file_list:
                need_update = True
                break
            
            if file_list[filename] != str(file_info.st_mtime) + '+' + str(file_info.st_size):
                need_update = True
                break
            
        if need_update == True:
            with open(DICT_INFO, "w", encoding="utf-8") as f:
                for filename in os.listdir(DICT_PATH):
                    filename = DICT_PATH + filename
                    file_info = os.stat(filename)
                    # file_md5 = hashlib.md5()
                    file_list[filename] = str(file_info.st_mtime) + '+' + str(file_info.st_size)
                    lock.acquire()  # 涉及操作 全局变量, 加锁保护
                    update_dict(filename)
                    format_dict_by_meaning()
                    format_dict_by_special_symbol()
                    lock.release()  # 解锁
                    f.write(filename + ':' +  file_list[filename] + '\n')
                    # f.flush()
        need_update = False
        time.sleep(0.1)

def format_dict_by_meaning():
    global format_dict
    for key in my_dict:
        lt = my_dict[key].split(config_obj['SEPARATOR_MAP']['DIFFERENT_MEANING_SEPERATOR'])
        for index, val in enumerate(lt):
            lt2 = val.split(config_obj['SEPARATOR_MAP']['SAME_MEANING_SEPERATOR'])
            sentence = ''
            for i, v in enumerate(lt2):
                sentence += '\t·' + v.strip('\t') + '\n'
            lt[index] = '(%d)\n' % (index + 1) + sentence.rstrip('\n')  # 处理上一行代码中, 最后多加的一个'\n'
        lt[len(lt) - 1] += '\n' # 处理上一行代码中, 最后多处理了一个'\n', 这里要补回来
        format_dict[key] = lt

def format_dict_by_special_symbol():
    global format_dict
    for key in list(format_dict.keys()):
        lt = format_dict[key]
        last_sentence = lt[len(lt) - 1] # '(1)\n\t·That is in large part because of a dearth of money.\n\t·a dearth of evidence\t~(lack)\n' 保证last_sentence存的是最后一句，因为最后一句中才包含了特殊符号(这里的最后一句指的是(num)这里的num数字是最大的)

        def get_next(pattern) -> list:
            # a a b a a f
            # 0 1 0 1 2 0
            if len(pattern) == 1:
                return [0]
            result : list = [0] * len(pattern)

            prefix_end : int = 0
            result[prefix_end] = prefix_end

            suffix_end : int = 1
            while suffix_end < len(pattern):
                while prefix_end > 0 and pattern[prefix_end] != pattern[suffix_end]:
                    prefix_end = result[prefix_end - 1]

                if pattern[prefix_end] == pattern[suffix_end]:
                    prefix_end += 1
                
                result[suffix_end] = prefix_end
                suffix_end += 1

            return result

        def find_symbol_by_KMP(last_sentence : str, symbol : str, startIndex : int = 0) -> int:
            next = get_next(symbol)
            i : int = startIndex
            j : int = 0
            while i < len(last_sentence) and j < len(symbol):
                while j != 0 and last_sentence[i] != symbol[j]:
                    j = next[j - 1]
                
                if last_sentence[i] == symbol[j]:
                    i += 1
                    j += 1
                else:
                    i += 1
            
            if j != len(symbol):
                return -1
            else:
                return i - j
            
        def findMatchBorderIndex(target : str, startIndex : int, left_sep : str, right_sep : str):
            """ Find the startIndex's sep corresponding right_sep
            "*(abc(123), 456) ~(qwe)"
            Args:
                target (str): last_sentence
                startIndex (int): the target's left_sep
                left_sep (str): left_sep symbol
                right_sep (str): right_sep symbol
            """
            stack = []
            i = startIndex
            while i < len(target):
                if target[i] == left_sep:
                    stack.append(left_sep)
                elif target[i] == right_sep:
                    stack.pop()
                    if len(stack) == 0:
                        return i
                i += 1
            return i

        index_map = {}
        min_index = len(last_sentence)

        for symbol in SPECIAL_SYMBOL_LIST:
            index = 0
            while index != -1:  # 这里用循环的原因: 当遇到 !~ 和 ~ 同时存在时, 为了找 ~, 需要找2次才能匹配到.
                index = find_symbol_by_KMP(last_sentence, symbol, index)   # 无法区分 !~ 和~
                # 下面的判断就是解决 !~和~ 这样的问题的: '将!~识别2次, 一次是作为!~, 一次是作为~'
                if index != -1 and (last_sentence[index - 1] in DUPLICATE_CONTAIN_SYMBOL_FILTER\
                                    or last_sentence[index + len(symbol)] in DUPLICATE_CONTAIN_SYMBOL_FILTER):
                    index += len(symbol)
                    continue

                if index >= 0:
                    index_map[symbol] = index
                    min_index = min(min_index, index)   # 确保index不是-1
                    index += len(symbol)
        
        # 证明存在special symbol
        if len(index_map) > 0:
            # 1. 处理last_sentence, 将特殊符号部分的字符串全部删除
            result_sentence = last_sentence[0:min_index]
            result_sentence = result_sentence.rstrip('\t')
            lt[len(lt) - 1] = result_sentence

            # 2. 将特殊符号部分的字符串append到lt后面
            for index_key in index_map:
                startIndex = index_map[index_key] + len(index_key)
                endIndex = findMatchBorderIndex(last_sentence, startIndex, '(', ')')
                core_word = last_sentence[startIndex + 1 : endIndex]
                
                symbol_original_lt = [SPECIAL_SYMBOL_MAP2_PRINT_NAME[index_key].rstrip('\n'), key]    # special_forms_map的value: [(Attribute), 原单词]
                
                # 判断同一个 special symbol 中是否存在多个 word (多个近义词等)
                if core_word.find(',') > 0:
                    core_word_lt = core_word.split(',')
                    core_word = ''
                    for word in core_word_lt:
                        word = word.strip()
                        core_word += '\t·' + word + '\n'
                        if index_key != NAME_MAP2_SPECIAL_SYMBOL['Attribute']:
                            if word not in special_forms_map2_symbolform_original_lt:
                                special_forms_map2_symbolform_original_lt[word] = []
                            if symbol_original_lt not in special_forms_map2_symbolform_original_lt[word]:   # 因为format_dict需要实时更新, 这里必须判断 变形对应的 symbol_original 中不存在要添加的 symbol_original_lt. 否则每次 wb 文件更新, 都会新增之前添加过的 symbol_original_lt
                                special_forms_map2_symbolform_original_lt[word].append(symbol_original_lt)
                    core_word = core_word.rstrip('\n')  # 多加了一个'\n' 要删除掉
                else:
                    if index_key != NAME_MAP2_SPECIAL_SYMBOL['Attribute']:
                        if core_word not in special_forms_map2_symbolform_original_lt:
                            special_forms_map2_symbolform_original_lt[core_word] = []
                        if symbol_original_lt not in special_forms_map2_symbolform_original_lt[core_word]:   # 因为format_dict需要实时更新, 这里必须判断 变形对应的 symbol_original 中不存在要添加的 symbol_original_lt. 否则每次 wb 文件更新, 都会新增之前添加过的 symbol_original_lt
                            special_forms_map2_symbolform_original_lt[core_word].append(symbol_original_lt)
                    core_word = '\t·' + core_word

                symbol_sentence = SPECIAL_SYMBOL_MAP2_PRINT_NAME[index_key] + core_word
                lt.append(symbol_sentence)

            lt[len(lt) - 1] += '\n' # 在字典的最后一个成员后, 追加'\n' 来分割不同的单词查询
            format_dict[key] = lt   # 修改字典

def check_validation(search_word : str, possible_search_result_len : int = 0) -> int:
    if search_word in INVALIDATION_KEY_LIST or search_word[0] in INVALIDATION_KEY_LIST: # 防止 " xxx" 这样的写法
        return 0

    if search_word.isalpha():
        return 1

    if possible_search_result_len > 0 and search_word.isdigit():
        if int(search_word) <= possible_search_result_len and int(search_word) > 0:
            return 2
        else:
            return 0

    for s in search_word:
        if s == ' ' or s.isalpha():
            continue
        else:
            return 0

    return 1

def print_special_form_result(search_word, symbolform, original_word):
    print(f"{search_word}\t-\t{symbolform} of [{original_word}]")
    print(f"{original_word}:")
    for s in format_dict[original_word]:
        print(f"{s}")

def search_dict():
    possible_search_result = []
    while True:
        try:
            search_word = input("Please input the word you want to search!\n")        
        except:
            return
        ret = check_validation(search_word, len(possible_search_result))
        if ret == 0:
            print("[WARNING]: Invalid Input!")
            continue
        search_word = search_word.lower()
        global format_dict
        if ret == 1 and search_word in format_dict:
            print(f"{search_word}:")
            for s in format_dict[search_word]:
                print(f"{s}")

            possible_search_result.clear()

        elif ret == 1 and search_word in special_forms_map2_symbolform_original_lt:  # 判断搜索的是否是特殊变形
            """
                Generic special form search (include all attributes)
            """
            if len(special_forms_map2_symbolform_original_lt[search_word]) == 1:
                print_special_form_result(search_word, special_forms_map2_symbolform_original_lt[search_word][0][0], special_forms_map2_symbolform_original_lt[search_word][0][1])
            else:
                print("There are multiple original results here, please choose one to view:")
                index = 0
                for symbolform_original in special_forms_map2_symbolform_original_lt[search_word]:
                    symbolform, original = symbolform_original[0], symbolform_original[1]
                    print(f"[{index + 1}] - {symbolform} \tof\t [{original}]")
                    index += 1
                try:
                    search_original = int(input("Choose a number\n"))
                except ValueError as e:
                    print(f"Error Input!!! --- filename:{e.__traceback__.tb_frame.f_globals['__file__']} - line:{e.__traceback__.tb_lineno}")
                    possible_search_result.clear()
                    continue
                symbolform = special_forms_map2_symbolform_original_lt[search_word][search_original - 1][0]
                original_word = special_forms_map2_symbolform_original_lt[search_word][search_original - 1][1]
                print_special_form_result(search_word, symbolform, original_word)

            possible_search_result.clear()

        elif ret == 2 and len(possible_search_result) > 0:
            search_word = possible_search_result[int(search_word) - 1]   # 将 单词索引下标(int) 转变为 单词(string)
            print(f"{search_word}:")
            for s in format_dict[search_word]:
                print(f"{s}")
            # possible_search_result.clear()    # 这里就不清理了, 允许用户多次通过数字查询(只要用户不输入单词, 可以一直查询先前的possible_search_result)
        else:
            # 进行模糊搜索
            possible_search_result.clear()
            for s in key_list:
                result = re.search(search_word, s)
                if result is not None:
                    possible_search_result.append(s)
            if len(possible_search_result) == 0:
                print(f"can not find {search_word}!!!\n")
            else:
                print(f"Maybe you want to search ?")
                for index, s in enumerate(possible_search_result):
                    print(f"[{index + 1}] - {s}")
        
        # if search_word in my_dict:
        #     print(f"{search_word} : {my_dict[search_word]}\n")
        # else:
        #     print(f"can not find {search_word}!!!\n")

# def visual_search_dict():
#     search_word = search_Entry.get()
#     search_word = search_word.lower()
#     result = ''
#     if search_word in format_dict:
#         result += f"{search_word}\n"
#         for s in format_dict[search_word]:
#             result += f"{s}\n"
#     else:
#         result += f"can not find {search_word}!!!\n"
#     result_text.delete("1.0", "end")
#     result_text.insert("end", result)


def division_search():
    print("""--------- Welcome to Division Search of PersonalDict! ----------
          0. Exit Division Search""")
    for search_index, key in enumerate(NAME_MAP2_SPECIAL_SYMBOL.keys(), 1):
        print(f"          {search_index}. Search by {key}")
    search_index += 1
    print(f"          {search_index}. Phrase's Search")
    print("----------------------------------------------------------------")
    while True:
        try:
            select = int(input("Choose a search option: "))
            if select > search_index or select < 0:
                raise ValueError
        except ValueError as e:
            print(f"Error Input! --- filename:{e.__traceback__.tb_frame.f_globals['__file__']} - line:{e.__traceback__.tb_lineno}")
            continue
        except:
            return
        
        if select == 0:
            print("Quit Division Search!")
            return
        elif select == search_index:    # Phrase's Search
            pass
        else:   # special form search
            search_helper = dict([i, f"({key})"] for i, key in enumerate(NAME_MAP2_SPECIAL_SYMBOL.keys(), 1))
            symbol_form = search_helper[select]
            possible_results = []   # 二维数组, 存放的是 [['(Attribute)', 原型1]， ['Deformation', 原型2], ...]
            
            search_word = input("Input the word you want to search: ")
            if search_word not in special_forms_map2_symbolform_original_lt:
                print(f"Sorry, PersonalDict does not contain {symbol_form} for {search_word} currently.")
                return
            
            symbolform_original_lt_lt = special_forms_map2_symbolform_original_lt[search_word]
            for symbol_form_original_lt in symbolform_original_lt_lt:
                if symbol_form_original_lt[0] == symbol_form:
                    possible_results.append(symbol_form_original_lt)
            
            if len(possible_results) == 0:
                print(f"Sorry, PersonalDict does not contain {symbol_form} for {search_word} currently.")
            elif len(possible_results) == 1:
                original_word = possible_results[0][1]
                print_special_form_result(search_word, symbol_form, original_word)
            else:
                print(f"There are multiple {symbol_form} of original results here, please choose one to view:")
                index = 0
                for symbolform, original in possible_results:
                    print(f"[{index + 1}] - {symbolform} \tof\t [{original}]")
                    index += 1
                try:
                    search_original = int(input("Choose a number: "))
                except Exception as e:
                    print(f"Error Input!!! --- filename:{e.__traceback__.tb_frame.f_globals['__file__']} - line:{e.__traceback__.tb_lineno}")
                    return
                original_word = possible_results[search_original - 1][1]
                print_special_form_result(search_word, symbol_form, original_word)
            return


def read_line_dict(target=format_dict):
    lock.acquire()
    for key in target:
        print(f"{key}:")
        for s in format_dict[key]:
            print(f"{s}")
        try:
            ret = input()
        except KeyboardInterrupt:
            lock.release()
            return
        except:
            print("")
    lock.release()

def exit_dict():
    os._exit()

def generate_final_value_to_mydict(word : str, results):
    value = ""
    for index, _ in enumerate(results):
        if len(results[index]) == 0:
            continue
        if index == 1:
            for s in results[index]:
                value += s.rstrip("\t/")
                value += "\t//\t"
            value = value.rstrip("\t/")
            value += "\t"
        else:
            # 处理分多次输入的 单词变形 ['history', 'historic, historian'] 这种，将它们合并到一起
            combined_value = f"{SPECIAL_SYMBOL_LIST[index - 3]}("
            for s in results[index]:
                combined_value += s + ", "
            combined_value = combined_value.rstrip(", ")
            combined_value += ")"
            value += combined_value + "\t"
    
    value = value.rstrip("\t")
    value += "\n"

    print(f"{word} : {value}")
    return value

def write_new_word_to_file(word : str, value : str, file_name : str):
    with open(file_name, 'a', encoding="utf-8") as f:
        f.write(f"{word}: {value}\n")

def add_words_to_dict():
    latest_wb_file = '0'
    for file in file_list:
        latest_wb_file = max(latest_wb_file, file)

    new_word = input("Please enter the word you want to add: ")
    if not check_validation(new_word):
        print(f"Error Word Input! --- check_validation Failed!")
        return
    if new_word.lower() in my_dict:
        print(f"{new_word} has already existed!")
        return

    print("""
    \t-3. Quit
    \t-2. CLEAR ALL Input (CAN NOT WITHDRAW!)
    \t-1. Withdraw last Input
    \t 0. All Done --- Save this Word to the Dict
    \t 1. Add Sentence
    \t 2. Add Another Meaning Sentence
    \t 3. Add Attribute
    \t 4. Synonym
    \t 5. Antonym
    \t 6. Deformation
    \t 7. Equivalence
    \t 8. Translation
    """)

    value = ""
    results = [[] for _ in range(9)]
    stack = []
    while True:
        select = input("Choose to add additional attributes: ")
        # if not select.isdigit():  # 无法判断负数, 小数
        if not re.match(r"-?\d+", select):
            print("Wrong Input!!!")
            continue
        
        select = int(select)

        if select < -3 or select > 8:
            print("Your select is out of range!")
            continue

        if select == -3:
            break
        elif select == 0:
            value = generate_final_value_to_mydict(new_word, results)
            write_new_word_to_file(new_word, value, latest_wb_file)
            break
        elif select == -1:
            if len(stack) == 0:
                print("Nothing can be withdrew!")
                continue

            operation = stack.pop()
            if operation[0] == 1:
                index = len(results[1]) - 1
                results[1][index] = results[1][index].replace(operation[1], "")
            elif operation[0] == 2:
                results[1].pop()
            else:
                results[operation[0]].pop()

        elif select == -2:
            results = [[] for _ in range(9)]
            stack.clear()
        else:
            raw_value = input("Input the content you want to add: \n")
            if raw_value == "":
                print("You can not input empty content!")
                continue

            if select == 1:
                index = len(results[1])
                if index == 0:
                    results[1].append("")
                    index = index + 1
                results[1][index - 1] += raw_value + "\t/\t"
                stack.append((select, raw_value + "\t/\t"))
            elif select == 2:
                index = len(results[1])
                results[1].append("")
                results[1][index] += raw_value + "\t/\t"
                stack.append((select,))
            else:
                # results[select].append(f"{SPECIAL_SYMBOL_LIST[select - 3]}({raw_value})")
                results[select].append(raw_value)
                stack.append((select,))

mode_dict = {
    0 : exit_dict,
    1 : search_dict,
    2 : add_words_to_dict,
    3 : read_line_dict,
    4 : lambda : read_line_dict(target=phrase_list),
    5 : division_search
}

def select_mode():
    try:
        print("""--------- Welcome to PersonalDict! ----------
            0. Exit Dict
            1. Search for Words
            2. Add New Word to Dict
            3. Browser Dict
            4. Browser Phrase
            5. More Detailed Search Options
---------------------------------------------
        """)
        mode = int(input("choose a mode to use: "))
        if mode in mode_dict:
            mode_dict[mode]()
        else:
            raise KeyError
    except KeyError as e:
        print(f"mode is not in range!  --- filename:{e.__traceback__.tb_frame.f_globals['__file__']} - line:{e.__traceback__.tb_lineno}")
    except ValueError as e:
        print(f"Wrong Input! --- filename:{e.__traceback__.tb_frame.f_globals['__file__']} - line:{e.__traceback__.tb_lineno}")

if __name__ == '__main__':
    init_parameters()
    thread = threading.Thread(target=monitor_dict_update)
    thread.start()
    try:
        while True:
            select_mode()
    except:
        quit_flag = True
        thread.join()



# # 图形化界面

# window = tk.Tk()
# window.title("Personal Dictionary")
# # window.geometry("320x450")
# window.geometry("600x500")

# # initialize dictionary
# load_dict()
# format_dict_by_meaning()

# # mode_LB = tk.Label(window, text="Select a Mode:", width=18)
# # mode_LB.grid(row=0, column=0, columnspan=2)

# # mode_Entry = tk.Entry(window)
# # mode_Entry.grid(row=0, column=2, columnspan=2)

# search_LB = tk.Label(window, text="Input your search Word:", width=25)
# search_LB.grid(row=0, column=0, columnspan=2)

# search_Entry = tk.Entry(window, width=30)
# search_Entry.grid(row=0, column=2, columnspan=2)

# search_Btn = tk.Button(window, text="Search", command=visual_search_dict)
# search_Btn.grid(row=0, column=4)

# result_text = tk.Text(window, height=30)
# result_text.grid(row=1, column=0, columnspan=6)

# window.mainloop()