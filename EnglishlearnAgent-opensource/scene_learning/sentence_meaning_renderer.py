"""
句子意思问答渲染器
=====================================

功能：
- 随机选择包含目标单词的句子
- 询问整句话的意思（不问单词意思）
- 高亮目标单词但问题关注整句

使用方式：
    from sentence_meaning_renderer import render_sentence_meaning_question

    render_sentence_meaning_question(
        scene_content=word_info['scene_content'],
        target_word=current_word,
        current_index=current_index,
        exchange=word_info['exchange']
    )
"""

import streamlit as st
import random
from .register_ai_button import register_ai_button
from .scene_utils import (
    parse_scene_content,
    contains_target_word,
    highlight_word_in_text
)

MAX_ANSWER_CHARS = 1500


@st.fragment
def _render_input_fragment(answer_key, placeholder, button_id, input_selector, question_type, question_data):
    """
    Fragment: 输入框和AI按钮注册
    使用 @st.fragment 避免点击空白处时rerun整个页面
    """
    input_container = st.container()
    with input_container:
        user_answer = st.text_area(
            "请输入你的理解：",
            key=answer_key,
            placeholder=placeholder,
            label_visibility="collapsed",
            max_chars=MAX_ANSWER_CHARS
        )

    register_ai_button(
        button_id=button_id,
        input_selector=input_selector,
        question_type=question_type,
        question_data=question_data
    )


def render_sentence_meaning_question(scene_content, target_word, word_forms, current_index):
    """
    渲染句子意思问答模式
    - 随机选择一句包含目标单词的句子
    - 高亮显示目标单词
    - 问题：这句话是什么意思？

    参数:
        scene_content: 场景内容文本
        target_word: 目标单词基本形式
        word_forms: 词形变化列表
        current_index: 当前单词索引
    """
    sentence_pairs = parse_scene_content(scene_content)

    if not sentence_pairs:
        st.warning("场景内容格式异常", icon=":material/warning:")
        return

    # 收集所有包含目标单词的句子
    target_sentences = []
    for idx, pair in enumerate(sentence_pairs):
        english = pair['english']
        if not english.strip():
            continue

        # 检查是否包含目标单词（包括词形变化）
        if contains_target_word(english, target_word, word_forms):
            target_sentences.append({
                'idx': idx,
                'english': english,
                'chinese': pair['chinese']
            })

    if not target_sentences:
        st.warning("没有找到包含目标单词的句子", icon=":material/warning:")
        return

    # 使用 session_state 保存随机选择的句子索引（保证刷新时不变）
    random_key = f"random_sentence_meaning_{current_index}"
    if random_key not in st.session_state:
        st.session_state[random_key] = random.randint(0, len(target_sentences) - 1)

    selected_idx = st.session_state[random_key]

    # 越界检查：如果缓存的索引无效，重新随机选择
    if selected_idx < 0 or selected_idx >= len(target_sentences):
        selected_idx = random.randint(0, len(target_sentences) - 1)
        st.session_state[random_key] = selected_idx

    selected_sentence = target_sentences[selected_idx]

    # 显示选中的句子
    english = selected_sentence['english']
    original_idx = selected_sentence['idx']

    # 高亮显示（包括词形）
    highlighted_english = highlight_word_in_text(english, target_word, word_forms)
    st.markdown(f'<div class="english-sentence">{highlighted_english}</div>', unsafe_allow_html=True)

    # 显示问题（询问整句话的意思）
    st.markdown(f"""
    <div class="question-prompt">
        <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-0.125em"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg> 这句话是什么意思？
    </div>
    """, unsafe_allow_html=True)

    # 🔥 使用 Fragment 包装输入框，避免点击空白处触发整个页面rerun
    answer_key = f"answer_sentence_{current_index}_{original_idx}"
    button_id = f"ai_feedback_btn_type2_{current_index}_{original_idx}"
    input_selector = f'[data-testid="stTextArea"]'

    question_data = {
        "sentence": english,
        "target_word": target_word
    }

    _render_input_fragment(
        answer_key=answer_key,
        placeholder="这句话的意思是...",
        button_id=button_id,
        input_selector=input_selector,
        question_type=2,
        question_data=question_data
    )
