"""
单词书管理模块

提供单词书的扫描、加载、选择等功能，支持跨页面共享单词书选择。
"""

import os
import json
from typing import Dict, List, Optional
import streamlit as st


# 单词书根目录
WORDBOOK_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "processed_vocabulary")


@st.cache_data(ttl=36000)  # 缓存 10 小时，避免每次 rerun 都读取 62 个文件
def get_available_wordbooks() -> List[Dict]:
    """
    扫描 processed_vocabulary 目录，返回所有可用单词书

    返回:
        [{'name': 'TOEFL', 'category': '出国', 'path': '...', 'display': '出国 / TOEFL', 'size': 4264}]

    注意：
        - 使用 @st.cache_data 缓存，首次调用后不再重复读取文件
        - 如需刷新缓存（如添加新单词书），可按 C 键或调用 get_available_wordbooks.clear()
    """
    wordbooks = []

    if not os.path.exists(WORDBOOK_ROOT):
        return wordbooks

    # 遍历分类目录
    for category in sorted(os.listdir(WORDBOOK_ROOT)):
        category_path = os.path.join(WORDBOOK_ROOT, category)
        if not os.path.isdir(category_path):
            continue

        # 遍历该分类下的 sorted_*.json 文件
        for filename in sorted(os.listdir(category_path)):
            if filename.startswith("sorted_") and filename.endswith(".json"):
                file_path = os.path.join(category_path, filename)
                # 从文件名提取单词书名称（去掉 sorted_ 前缀和 .json 后缀）
                book_name = filename[7:-5]  # sorted_TOEFL.json -> TOEFL

                # 读取文件获取单词数量
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        size = data.get('size', len(data.get('wordList', [])))
                except Exception:
                    size = 0

                wordbooks.append({
                    'name': book_name,
                    'category': category,
                    'path': file_path,
                    'display': f"{category} / {book_name}",
                    'size': size
                })

    return wordbooks


def get_current_wordbook() -> Optional[Dict]:
    """
    从 session_state 获取当前选择的单词书

    返回:
        当前选择的单词书信息，如果没有选择则返回 None
    """
    return st.session_state.get('selected_wordbook', None)


def set_current_wordbook(wordbook: Optional[Dict]) -> None:
    """
    设置当前单词书到 session_state，并清空学习计划

    参数:
        wordbook: 单词书信息字典，或 None 表示清除选择
    """
    st.session_state.selected_wordbook = wordbook

    # 清空学习相关的 session_state
    if 'learning_plan' in st.session_state:
        st.session_state.learning_plan = []
    if 'batch_index' in st.session_state:
        st.session_state.batch_index = 0
    if 'module_index' in st.session_state:
        st.session_state.module_index = 0
    if 'word_index_in_batch' in st.session_state:
        st.session_state.word_index_in_batch = 0
    if 'ai_content_checked' in st.session_state:
        st.session_state.ai_content_checked = False

    # 重置学习状态，防止切换单词书后 book_name=None 时全库取词
    # 修复 bug: 学习中切换分类会清空 selected_wordbook，但 learning_started 不关闭
    if 'learning_started' in st.session_state:
        st.session_state.learning_started = False

    # 清理 AI 生成相关的 session_state（切换单词书后需要重新检查）
    # 注意：后台任务会继续运行，这里只是清除前端引用
    if 'ai_generation_task_id' in st.session_state:
        del st.session_state.ai_generation_task_id
    if 'last_ai_words_key' in st.session_state:
        del st.session_state.last_ai_words_key
    if 'last_ai_task_time' in st.session_state:
        del st.session_state.last_ai_task_time

    # 清理 AI 互动模块缓存（防止切换单词书后复用旧词数据）
    # 与 fsrs_modular_learning.py 中用户切换时的清理逻辑保持一致
    keys_to_delete = [k for k in st.session_state.keys()
                      if k.startswith(('question_type_', 'random_sentence_',
                                       'random_sentence_meaning_', 'random_translation_',
                                       'random_fill_blank_', 'current_word_data_',
                                       'answer_'))]
    for key in keys_to_delete:
        del st.session_state[key]


def load_wordbook_to_database(
    book_name: str,
    user_id: str,
    fsrs_system
) -> int:
    """
    为用户创建单词书的学习记录

    静态内容（翻译、音标等）已由运维脚本预加载到 global_words 和 global_word_books 表。
    此函数只为用户创建缺少的 fsrs_words 记录。

    参数:
        book_name: 单词书名称
        user_id: 用户 ID
        fsrs_system: FSRSPostgreSQLSystem 实例

    返回:
        为用户新创建的单词记录数量
    """
    # 静态内容已由运维脚本预加载到 global_words 和 global_word_books 表
    # 部署前执行: python ops/init_all_wordbooks.py

    # 为用户创建缺少的 fsrs_words 记录
    words_to_create = fsrs_system.get_words_to_create(user_id, book_name)

    if not words_to_create:
        return 0  # 所有单词已存在，无需创建

    # 显示进度条
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, word in enumerate(words_to_create):
        fsrs_system.add_word_for_user(word=word, user_id=user_id)

        # 更新进度
        progress = (i + 1) / len(words_to_create)
        progress_bar.progress(progress)
        status_text.text(f"Creating user records: {i+1}/{len(words_to_create)}")

    # 清除进度条
    progress_bar.empty()
    status_text.empty()

    return len(words_to_create)


def _on_category_change():
    """
    分类选择器的 on_change 回调

    根据 Streamlit 官方文档：回调在 rerun 之前执行，可避免额外的 st.rerun()
    参考：https://docs.streamlit.io/develop/concepts/app-design/button-behavior-and-examples
    """
    # 获取新选择的分类（回调执行时，session_state 已更新为新值）
    selected_category = st.session_state.get('wordbook_category_selector')
    current_book = get_current_wordbook()

    # 如果分类变了，清除旧的单词书选择
    if current_book and selected_category and current_book['category'] != selected_category:
        set_current_wordbook(None)
        st.session_state._skip_db_restore = True

        # 清除 wordbook_book_selector 的旧值，避免 ValueError
        # 参考：https://github.com/streamlit/streamlit/issues/3598
        if 'wordbook_book_selector' in st.session_state:
            del st.session_state['wordbook_book_selector']


def render_wordbook_selector(user_id: str, fsrs_system) -> bool:
    """
    在侧边栏渲染单词书选择器（两级级联菜单）

    参数:
        user_id: 用户 ID
        fsrs_system: FSRSPostgreSQLSystem 实例

    返回:
        是否切换了单词书（需要 rerun）
    """
    # 获取可用单词书
    available_books = get_available_wordbooks()

    if not available_books:
        st.warning("No wordbooks found in processed_vocabulary/")
        return False

    # 提取所有分类（去重，保持顺序）
    categories = []
    for book in available_books:
        if book['category'] not in categories:
            categories.append(book['category'])

    # 获取当前选择（优先从 session_state，其次从数据库）
    current_book = get_current_wordbook()

    # 如果 session_state 中没有，尝试从数据库获取上次使用的单词书
    # 注意：如果是分类切换触发的 rerun，跳过数据库恢复
    if current_book is None and not st.session_state.get('_skip_db_restore', False):
        last_book = fsrs_system.get_last_wordbook(user_id)
        if last_book:
            # 在可用单词书中找到匹配的
            for book in available_books:
                if book['name'] == last_book['name'] and book['category'] == last_book['category']:
                    current_book = book
                    set_current_wordbook(book)  # 同步到 session_state
                    st.session_state._skip_db_restore = False  # 恢复成功后清除标志
                    # 记录用户已加载此单词书（更新 loaded_at 时间戳）
                    fsrs_system.add_loaded_book(user_id, book['name'], book['category'])
                    break
    # 注意：不在这里无条件清除 _skip_db_restore，而是在成功设置单词书后清除

    # 确定当前分类的索引
    current_category = current_book['category'] if current_book else None
    current_category_index = categories.index(current_category) if current_category in categories else None

    # ===== 第一个 selectbox：选择分类 =====
    # 使用 on_change 回调代替 st.rerun()，避免额外的 rerun
    selected_category = st.selectbox(
        "![](data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiMzMTMzM0YiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMjAgMjBhMiAyIDAgMCAwIDItMlY4YTIgMiAwIDAgMC0yLTJoLTcuOWEyIDIgMCAwIDEtMS42OS0uOUw5LjYgMy45QTIgMiAwIDAgMCA3LjkzIDNINGEyIDIgMCAwIDAtMiAydjEzYTIgMiAwIDAgMCAyIDJaIi8+PC9zdmc+) 分类",
        categories,
        index=current_category_index,
        key="wordbook_category_selector",
        placeholder="请选择分类...",
        on_change=_on_category_change  # 回调在 rerun 之前执行，清除旧选择
    )

    if selected_category is None:
        return False

    # 注意：分类切换的逻辑已移至 _on_category_change() 回调中
    # 回调在 rerun 之前执行，所以不需要额外的 st.rerun()

    # ===== 第二个 selectbox：选择该分类下的单词书 =====
    books_in_category = [b for b in available_books if b['category'] == selected_category]
    book_options = [f"{b['name']} ({b['size']} words)" for b in books_in_category]

    # 构建书名显示字符串到书对象的映射（避免索引错位问题）
    book_display_to_book = {f"{b['name']} ({b['size']} words)": b for b in books_in_category}

    # 确定当前单词书的显示名称
    current_book_display = None
    if current_book and current_book['category'] == selected_category:
        current_book_display = f"{current_book['name']} ({current_book['size']} words)"

    # 计算当前书在选项中的索引（用于 index 参数）
    current_book_index = None
    if current_book_display and current_book_display in book_options:
        current_book_index = book_options.index(current_book_display)

    selected_book_display = st.selectbox(
        "![](data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNiIgaGVpZ2h0PSIxNiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiMzMTMzM0YiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cGF0aCBkPSJNMTIgN3YxNCIvPjxwYXRoIGQ9Ik0xNiAxMmgyIi8+PHBhdGggZD0iTTE2IDhoMiIvPjxwYXRoIGQ9Ik0zIDE4YTEgMSAwIDAgMS0xLTFWNGExIDEgMCAwIDEgMS0xaDVhNCA0IDAgMCAxIDQgNCA0IDQgMCAwIDEgNC00aDVhMSAxIDAgMCAxIDEgMXYxM2ExIDEgMCAwIDEtMSAxaC02YTMgMyAwIDAgMC0zIDMgMyAzIDAgMCAwLTMtM3oiLz48cGF0aCBkPSJNNiAxMmgyIi8+PHBhdGggZD0iTTYgOGgyIi8+PC9zdmc+) 单词书",
        options=book_options,  # 直接使用书名字符串列表，而非整数索引
        index=current_book_index,
        key="wordbook_book_selector",
        placeholder="请选择单词书..."
    )

    if selected_book_display is None:
        return False

    # 通过书名查找书对象（而非通过索引，避免列表变化导致选错书）
    selected_book = book_display_to_book.get(selected_book_display)
    if selected_book is None:
        # 书已被删除或不存在，清除选择并重新渲染
        set_current_wordbook(None)
        st.rerun()

    # 检查是否切换了单词书
    switched = False
    if current_book is None or selected_book['name'] != current_book.get('name') or selected_book['category'] != current_book.get('category'):
        # 切换到新单词书
        set_current_wordbook(selected_book)
        st.session_state._skip_db_restore = False  # 成功设置后清除标志

        # 保存到数据库（下次打开页面时恢复）
        fsrs_system.set_last_wordbook(user_id, selected_book['name'], selected_book['category'])

        # 记录用户已加载此单词书
        fsrs_system.add_loaded_book(user_id, selected_book['name'], selected_book['category'])

        # 为用户创建学习记录
        with st.spinner(f"Loading {selected_book['name']}..."):
            load_wordbook_to_database(
                selected_book['name'],
                user_id,
                fsrs_system
            )

        switched = True
        st.success(f"Loaded: {selected_book['display']}")

    return switched
