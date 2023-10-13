#coding=utf-8
import tkinter as tk
import os
import sys
import re
import threading
import time
import hashlib
import getpass

USER = getpass.getuser()
DICT_PATH = r'/Example Sentences/'
DICT_INFO = r'C:/Users/{USER}/.dict_info.dat'

SAME_MEANING_SEPERATOR = r'/'
DIFFERENT_MEANING_SEPERATOR = r'//'
ATTRIBUTE = r'@'
SYNONYM = r'~'
ANTONYM = r'!~'
DEFORMATION = r'->'
EQUIVALENCE = r'<=>'
SPECIAL_SYMBOL_LIST = [ATTRIBUTE, SYNONYM, ANTONYM, DEFORMATION, EQUIVALENCE]
SPECIAL_SYMBOL_MAP = {
    ATTRIBUTE : '(Attribute)\n',
    SYNONYM : '(Synonym)\n',
    ANTONYM : '(Antonym)\n',
    DEFORMATION : '(Deformation)\n',
    EQUIVALENCE : '(Equivalence)\n'
}
DUPLICATE_CONTAIN_SYMBOL_FILTER = {}
INVALIDATION_KEY_LIST = ['', ' ', '\n', '\\', '\\\\\\']
NEED_UPDATE = False

file_list = {}      # 单词本的文件列表
my_dict = {}        # key : value, value未经任何格式规划处理
format_dict = {}    # 格式化字典, 里面存储了已经按照 固定格式 的单词内容
key_list = []       # 提供模糊搜索数据来源的key的集合(其实就是所有的key)
special_forms_map = {}  # special_form : [symbol, orignal] 提供 特殊变形->原型 的映射, 方便用户通过搜索特殊变形来查找原型. symbol表示它是哪种变形, orignal存储的是原型key

lock = threading.Lock()
quit_flag = False

def init_parameter():
    global DICT_INFO, DICT_PATH
    DICT_INFO = DICT_INFO.format(USER=USER)
    cur_file_path = os.path.realpath(__file__)
    index = cur_file_path.rfind("\\")
    DICT_PATH = cur_file_path[:index] + DICT_PATH

    for symbol in SPECIAL_SYMBOL_LIST:
        for s in symbol:
            DUPLICATE_CONTAIN_SYMBOL_FILTER[s] = 1

def update_dict(filename : str):
    with open(filename, "r") as f:
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
            except:
                continue

def load_dict():
    # 获取字典目录下的所有单词本
    for filename in os.listdir(DICT_PATH):
        filename = DICT_PATH + filename # 拼接字典文件的路径前缀
        update_dict(filename)

def load_file_list():
    try:
        with open(DICT_INFO, "r") as f:
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
    except:
        print(f"[WARNING]: load_key_list error!")

def monitor_dict_update():
    while not quit_flag:
        for filename in os.listdir(DICT_PATH):
            filename = DICT_PATH + filename # 拼接字典文件的路径前缀
            file_info = os.stat(filename)

            if filename not in file_list:
                NEED_UPDATE = True
                break
            
            if file_list[filename] != str(file_info.st_mtime) + '+' + str(file_info.st_size):
                NEED_UPDATE = True
                break
            
        if NEED_UPDATE == True:
            with open(DICT_INFO, "w") as f:
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
        NEED_UPDATE = False
        time.sleep(0.1)

def format_dict_by_meaning():
    global format_dict
    for key in my_dict:
        lt = my_dict[key].split(DIFFERENT_MEANING_SEPERATOR)
        for index, val in enumerate(lt):
            lt2 = val.split(SAME_MEANING_SEPERATOR)
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
        
        index_map = {}
        min_index = len(last_sentence)

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

        def find_symbol_by_KMP(last_sentence : str, symbol : str) -> int:
            next = get_next(symbol)
            i : int = 0
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

        for symbol in SPECIAL_SYMBOL_LIST:
            # index = last_sentence.find(symbol)    # 无法区分 !~ 和~
            index = find_symbol_by_KMP(last_sentence, symbol)   # 无法区分 !~ 和~
            # 下面的判断就是解决 !~和~ 这样的问题的
            if last_sentence[index - 1] and (last_sentence[index - 1] in DUPLICATE_CONTAIN_SYMBOL_FILTER 
                                             or last_sentence[index + len(symbol)] in DUPLICATE_CONTAIN_SYMBOL_FILTER):
                index = -1
            if index >= 0:
                index_map[symbol] = index
                min_index = min(min_index, index)   # 确保index不是-1
        
        # 证明存在special symbol
        if len(index_map) > 0:
            # 1. 处理last_sentence, 将特殊符号部分的字符串全部删除
            result_sentence = last_sentence[0:min_index]
            result_sentence = result_sentence.rstrip('\t')
            lt[len(lt) - 1] = result_sentence

            # 2. 将特殊符号部分的字符串append到lt后面
            for index_key in index_map:
                core_word = last_sentence[index_map[index_key] + len(index_key) + 1 : last_sentence.find(')', index_map[index_key])]
                
                symbol_oringal_lt = [SPECIAL_SYMBOL_MAP[index_key].rstrip('\n'), key]    # special_forms_map的valu
                
                # 判断同一个 special symbol 中是否存在多个 word
                if core_word.find(',') > 0:
                    core_word_lt = core_word.split(',')
                    core_word = ''
                    for word in core_word_lt:
                        core_word += '\t·' + word.strip(' ') + '\n'
                        if index_key != ATTRIBUTE:
                            special_forms_map[word.strip(' ')] = symbol_oringal_lt
                    core_word = core_word.rstrip('\n')  # 多加了一个'\n' 要删除掉
                else:
                    if index_key != ATTRIBUTE:
                        special_forms_map[core_word] = symbol_oringal_lt
                    core_word = '\t·' + core_word

                symbol_sentence = SPECIAL_SYMBOL_MAP[index_key] + core_word
                lt.append(symbol_sentence)

            lt[len(lt) - 1] += '\n' # 在字典的最后一个成员后, 追加'\n' 来分割不同的单词查询
            format_dict[key] = lt   # 修改字典

def check_validation(search_word : str, possible_search_result_len : int) -> int:
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

        elif ret == 1 and search_word in special_forms_map:  # 判断搜索的是否是特殊变形
            orignal_word = special_forms_map[search_word][1]
            print(f"{search_word}\t-\t{special_forms_map[search_word][0]} of [{orignal_word}]")
            print(f"{orignal_word}:")
            for s in format_dict[orignal_word]:
                print(f"{s}")
        
            possible_search_result.clear()

        elif ret == 2 and len(possible_search_result) > 0:
            search_word = possible_search_result[int(search_word) - 1]   # 将 单词索引下标(int) 转变为 单词(string)
            print(f"{search_word}:")
            for s in format_dict[search_word]:
                print(f"{s}")
            # possible_search_result.clear()    # 这里就不清理了, 允许用户多次通过数字查询(只要用户不输入单词, 可以一直查询先前的possible_search_result)
        else:
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


def read_line_dict():
    lock.acquire()
    for key in format_dict:
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


mode_dict = {
    0 : exit_dict,
    1 : search_dict,
    2 : read_line_dict
}

def select_mode():
    try:
        mode = int(input("choose a mode to use:\n"))
        if mode in mode_dict:
            mode_dict[mode]()
        else:
            raise KeyError
    except KeyError:
        print("mode is not in range!")
    except ValueError:
        print("Wrong Input!")

if __name__ == '__main__':
    init_parameter()
    load_dict()
    format_dict_by_meaning()
    format_dict_by_special_symbol()
    load_file_list()
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