"""
视觉连接问答渲染器
=====================================

功能：
- 展示单词和传统单词书的中文释义
- 询问：请问连接这个单词的所有意思的画面是什么？
- 引导用户建立单词多义之间的视觉联系

使用方式：
    from visual_connection_renderer import render_visual_connection_question

    render_visual_connection_question(
        scene_content=word_info['scene_content'],
        target_word=current_word,
        word_forms=None,
        current_index=current_index
    )
"""

import streamlit as st
from .register_ai_button import register_ai_button

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
            "请输入你的画面描述：",
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


def render_visual_connection_question(scene_content, target_word, word_forms, current_index):
    """
    渲染视觉连接问答模式
    - 显示单词及其所有中文释义
    - 问题：请问连接这个单词的所有意思的画面是什么？
    - 引导用户通过视觉画面连接单词的多个意思

    参数:
        scene_content: 场景内容文本（本模块不使用）
        target_word: 目标单词基本形式（本模块不使用，从session_state获取）
        word_forms: 词形变化列表（本模块不使用）
        current_index: 当前单词索引
    """
    # 从 session_state 获取当前单词数据
    current_word_data_key = f"current_word_data_{current_index}"
    if current_word_data_key not in st.session_state:
        st.warning("无法获取单词数据", icon=":material/warning:")
        return

    word_data = st.session_state[current_word_data_key]
    word = word_data.get('word', '')
    translation = word_data.get('translation', '')

    if not word or not translation:
        st.warning("单词或释义数据不完整", icon=":material/warning:")
        return

    # 显示单词和中文释义（使用统一的english-sentence样式）
    translations = translation.split('\n')
    translation_html = '<br>'.join([f"• {trans.strip()}" for trans in translations if trans.strip()])

    st.markdown(f"""
    <div class="english-sentence">
        <div style="font-size: 24px; font-weight: bold; margin-bottom: 15px;">
            {word}
        </div>
        <div style="margin-top: 10px;">
            <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-0.125em"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg> <strong>传统单词书中的中文释义：</strong><br>
            {translation_html}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 显示问题（使用统一的question-prompt样式，不添加内联样式）
    st.markdown(f"""
    <div class="question-prompt">
        <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-0.125em"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg> 请问连接这个单词的所有意思的画面是什么？（词源画面核心）
    </div>
    """, unsafe_allow_html=True)

    # 🔥 使用 Fragment 包装输入框，避免点击空白处触发整个页面rerun
    answer_key = f"answer_visual_connection_{current_index}"
    button_id = f"ai_feedback_btn_type5_{current_index}"
    input_selector = f'[data-testid="stTextArea"]'

    question_data = {
        "word": word,
        "translation": translation
    }

    _render_input_fragment(
        answer_key=answer_key,
        placeholder="我想象的画面是...",
        button_id=button_id,
        input_selector=input_selector,
        question_type=5,
        question_data=question_data
    )
