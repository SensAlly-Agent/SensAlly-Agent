"""
共享的侧边栏导航组件
===================

用于在所有页面显示统一的自定义导航菜单。
配合 .streamlit/config.toml 中的 client.showSidebarNavigation = false 使用。
"""

import streamlit as st


def render_sidebar_nav():
    """
    渲染侧边栏导航菜单
    
    使用 st.page_link 创建自定义导航，可以自定义页面显示名称和图标，
    而不需要重命名文件。
    
    注意：需要在 .streamlit/config.toml 中设置 client.showSidebarNavigation = false
    """
    st.markdown('### <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px"><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/></svg> 功能', unsafe_allow_html=True)

    # 单词详解（主页）
    st.page_link("app.py", label="单词详解", icon=":material/menu_book:")

    # Agent 模块学习
    st.page_link("pages/fsrs_modular_learning.py", label="Agent 模块学习", icon=":material/smart_toy:")

    # 额度管理
    st.page_link("pages/pricing.py", label="额度管理", icon=":material/bolt:")
    
    st.markdown("---")

    # 客服联系方式
    st.markdown('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px"><path d="M2.992 16.342a2 2 0 0 1 .094 1.167l-1.065 3.29a1 1 0 0 0 1.236 1.168l3.413-.998a2 2 0 0 1 1.099.092 10 10 0 1 0-4.777-4.719"/></svg> **联系客服**', unsafe_allow_html=True)
    st.markdown('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg> [support@sensally.com](mailto:support@sensally.com)', unsafe_allow_html=True)

    st.markdown("---")
