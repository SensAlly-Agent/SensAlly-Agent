#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Agent 模块化学习系统
==================

支持两种学习模式：
1. 单个学习模式：每个模块学习一个单词，循环无限次
2. 批量学习模式：每个模块学习N个单词（1-10可调），学完停止

可自定义模块组合和顺序（支持拖拽和箭头调整）
"""

import os
import sys
import json
import uuid
import time
import requests
import streamlit as st
import streamlit.components.v1 as components

# ========== 修复模块导入路径 ==========
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入选中播放、翻译和AI对话组件
from selection_player_v2 import render_player
from floating_translate_selector import mount_translate_selector
from floating_chat_widget_fastapi import render_floating_chat_fastapi
from floating_selector_tool import mount_floating_selector
from scene_learning.ai_feedback_button_manager import mount_ai_feedback_button_manager

# 导入 AI 内容生成触发器（公共模块）
from utils.ai_generation_trigger import trigger_ai_generation_for_today
from utils.auth_helper import get_current_user_id, require_login, get_jwt_token
from utils.escape_utils import escape_html
from utils.wordbook_manager import (
    get_available_wordbooks,
    get_current_wordbook,
    set_current_wordbook,
    load_wordbook_to_database,
    render_wordbook_selector
)
# 共享导航组件
from utils.sidebar_nav import render_sidebar_nav

# ========== 页面配置 ==========
st.set_page_config(
    page_title="模块化学习",
    page_icon=":material/my_location:",
    layout="wide"
)

# ========== 自定义CSS样式 - 沉浸式深色主题 ==========
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600&family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --bg-dark: #030712;
        --panel-dark: rgba(15, 23, 42, 0.92);
        --panel-soft: rgba(30, 41, 59, 0.85);
        --accent: #8B5CF6;
        --accent-strong: #6366F1;
        --accent-soft: rgba(99, 102, 241, 0.35);
        --success: #22D3EE;
        --text-primary: #F8FAFC;
        --text-secondary: #94A3B8;
    }

    html, body {
        background: var(--bg-dark) !important;
        color: var(--text-primary);
    }

    .stApp {
        position: relative;
        min-height: 100vh;
        isolation: isolate;
        background:
            radial-gradient(28% 32% at 20% 18%, rgba(99,102,241,0.26), transparent 55%),
            radial-gradient(22% 28% at 78% 12%, rgba(34,211,238,0.22), transparent 60%),
            radial-gradient(35% 40% at 50% 72%, rgba(15,23,42,0.4), transparent 65%),
            linear-gradient(145deg, #050915 0%, #0b1626 52%, #050915 100%);
        background-attachment: fixed;
        color: var(--text-primary);
        font-family: 'Inter', sans-serif;
    }

    .stApp::before {
        content: '';
        position: fixed;
        inset: 0;
        pointer-events: none;
        background:
            radial-gradient(40% 45% at 15% 30%, rgba(94,234,212,0.1), transparent 55%),
            radial-gradient(30% 35% at 85% 24%, rgba(139,92,246,0.12), transparent 52%);
        mix-blend-mode: screen;
        opacity: 0.85;
        z-index: 0;
    }

    /* 覆盖 Streamlit header 区域为透明，让底层渐变背景显示 */
    header[data-testid="stHeader"] {
        background: transparent !important;
        background-color: transparent !important;
    }

    /* 侧边栏展开按钮图标颜色 - 改为白色以适应深色主题 */
    [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {
        color: white !important;
    }

    /* 修复 expander 标题背景（展开或折叠时都保持透明） */
    .stExpander summary {
        background-color: transparent !important;
        border: 1px solid rgba(56, 189, 248, 0.3) !important;
        border-left: 3px solid rgba(94, 234, 212, 0.65) !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
        transition: all 0.3s ease !important;
    }

    .stExpander summary:hover {
        background-color: transparent !important;
        border-color: rgba(94, 234, 212, 0.55) !important;
        border-left-color: rgba(59, 130, 246, 0.75) !important;
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.35) !important;
    }

    .stExpander summary:focus-visible,
    .stExpander summary:active {
        background-color: transparent !important;
        border-color: rgba(59, 130, 246, 0.65) !important;
        border-left-color: rgba(94, 234, 212, 0.85) !important;
    }

    /* Expander 展开后 details 容器左边框 — 显式定义（原 Streamlit 默认值） */
    .stExpander details {
        border: 1px solid rgba(49, 51, 63, 0.2) !important;
    }

    /* Expander 标题与内容之间的分隔线 — 显式定义（原 Streamlit 默认值） */
    .stExpander [data-testid="stExpanderDetails"] {
        border-top: 1px solid rgba(49, 51, 63, 0.2) !important;
    }

    /* <hr> 分割线颜色 — 显式定义（原 Streamlit 默认值） */
    .stMarkdown hr {
        border-color: rgba(49, 51, 63, 0.2) !important;
    }


    .main .block-container {
        padding: 0 2rem 4rem;
        max-width: 1200px;
    }

    .hero {
        display: grid;
        grid-template-columns: minmax(320px, 2.1fr) minmax(240px, 1fr);
        gap: 32px;
        background: linear-gradient(145deg, rgba(31,41,55,0.95), rgba(15,23,42,0.95));
        border-radius: 28px;
        padding: 48px;
        border: 1px solid rgba(148, 163, 184, 0.25);
        box-shadow: 0 35px 70px rgba(2, 6, 23, 0.6);
        margin: 32px 0 24px;
        position: relative;
        overflow: hidden;
    }

    .hero::after {
        content: '';
        position: absolute;
        inset: 0;
        background: radial-gradient(circle at 80% 20%, rgba(56,189,248,0.2), transparent 45%);
        pointer-events: none;
    }

    .hero-content {
        position: relative;
        z-index: 2;
        max-width: 560px;
    }

    .hero-label {
        font-size: 13px;
        letter-spacing: 3px;
        text-transform: uppercase;
        color: var(--text-secondary);
    }

    .hero h1 {
        font-size: 42px;
        font-weight: 700;
        margin: 12px 0;
        color: white;
        display: inline-flex;
        align-items: center;
        gap: 12px;
    }

    .hero-desc {
        font-size: 16px;
        color: var(--text-secondary);
        max-width: 420px;
        line-height: 1.6;
    }

    .hero-flow {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 24px;
    }

    .hero-cta {
        position: relative;
        z-index: 2;
        border-radius: 28px;
        padding: 42px 32px;
        border: 1px solid rgba(94, 234, 212, 0.35);
        background: linear-gradient(150deg, rgba(3, 7, 18, 0.95), rgba(7, 18, 36, 0.85));
        box-shadow: 0 40px 90px rgba(2, 6, 23, 0.7);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        cursor: default;
        transition: transform 0.35s ease, box-shadow 0.35s ease, border-color 0.35s ease;
        overflow: hidden;
        isolation: isolate;
        min-height: 100%;
    }

    .hero-cta::before {
        content: '';
        position: absolute;
        width: 160%;
        height: 160%;
        top: -30%;
        left: -30%;
        background: conic-gradient(from 90deg,
                    rgba(94,234,212,0.3),
                    rgba(59,130,246,0.5),
                    rgba(147,51,234,0.35),
                    rgba(236,72,153,0.25),
                    rgba(94,234,212,0.3));
        filter: blur(65px);
        opacity: 0.9;
        animation: heroCtaHalo 16s linear infinite;
        pointer-events: none;
        z-index: 0;
    }

    .hero-cta::after {
        content: '';
        position: absolute;
        inset: 2px;
        border-radius: 26px;
        border: 1px solid rgba(255,255,255,0.04);
        background:
            radial-gradient(circle at 25% 25%, rgba(94,234,212,0.15), transparent 55%),
            radial-gradient(circle at 75% 15%, rgba(59,130,246,0.18), transparent 50%),
            linear-gradient(160deg, rgba(2,9,23,0.92), rgba(2,6,19,0.85));
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
        pointer-events: none;
        z-index: 1;
    }

    .hero-cta[data-enabled="true"] {
        cursor: pointer;
    }

    .hero-cta[data-enabled="true"]:hover {
        transform: translateY(-6px) scale(1.01);
        box-shadow: 0 55px 95px rgba(2, 6, 23, 0.8);
        border-color: rgba(94, 234, 212, 0.55);
    }

    .hero-cta[data-enabled="true"]:active {
        transform: translateY(-2px) scale(0.995);
    }

    .hero-cta[data-enabled="false"] {
        opacity: 0.65;
        filter: grayscale(0.25);
        cursor: not-allowed;
        box-shadow: none;
    }

    .hero-cta-main {
        font-size: 26px;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: 0.08em;
        position: relative;
        z-index: 2;
        text-shadow: 0 0 22px rgba(94, 234, 212, 0.7);
        display: inline-flex;
        align-items: center;
        gap: 10px;
        animation: heroCtaPulse 4s ease-in-out infinite;
        white-space: nowrap;
    }

    .hero-cta-main::after {
        content: '';
        position: absolute;
        left: 50%;
        bottom: -16px;
        width: 78px;
        height: 2px;
        border-radius: 999px;
        transform: translateX(-50%);
        background: linear-gradient(90deg, transparent, rgba(94,234,212,0.85), transparent);
        opacity: 0.8;
    }

    @keyframes heroCtaHalo {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    @keyframes heroCtaPulse {
        0%, 100% { text-shadow: 0 0 14px rgba(94, 234, 212, 0.35); letter-spacing: 0.07em; }
        50% { text-shadow: 0 0 34px rgba(59, 130, 246, 0.65); letter-spacing: 0.1em; }
    }


    .module-pill {
        background: rgba(99,102,241,0.2);
        border: 1px solid rgba(99,102,241,0.4);
        border-radius: 999px;
        padding: 6px 14px;
        font-size: 13px;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: white;
    }

    .module-pill.pill-empty {
        border-style: dashed;
        color: var(--text-secondary);
        background: transparent;
    }

    /* Hero 设置按钮锚点 - 在标题下方 */
    #hero-settings-anchor {
        margin: 12px 0 20px;
        position: relative;
        z-index: 10;
    }

    /* Hero 内嵌设置按钮 */
    .st-key-hero-settings-btn {
        width: auto !important;
    }

    .st-key-hero-settings-btn > div {
        width: auto !important;
    }

    .st-key-hero-settings-btn [data-testid="stPopoverButton"] {
        background: rgba(15, 23, 42, 0.85) !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(148, 163, 184, 0.35) !important;
        border-radius: 14px !important;
        padding: 10px 16px !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        transition: all 0.25s ease;
    }

    .st-key-hero-settings-btn [data-testid="stPopoverButton"]:hover {
        border-color: rgba(94, 234, 212, 0.6) !important;
        background: rgba(15, 23, 42, 0.95) !important;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(94, 234, 212, 0.2);
        transform: translateY(-2px);
    }

    .st-key-hero-settings-btn [data-testid="stMarkdownContainer"] p {
        font-size: 13px !important;
        font-weight: 500;
        color: #E2E8F0 !important;
        margin: 0 !important;
        white-space: nowrap;
    }

    .hero-visual {
        position: relative;
        z-index: 2;
        background: rgba(2,6,23,0.45);
        border-radius: 24px;
        padding: 24px;
        border: 1px solid rgba(148, 163, 184, 0.15);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
    }

    .hero-module-card {
        display: flex;
        gap: 14px;
        align-items: center;
        padding: 14px 18px;
        border-radius: 18px;
        border: 1px solid rgba(99,102,241,0.15);
        background: rgba(15,23,42,0.9);
        margin-bottom: 12px;
        box-shadow: 0 10px 25px rgba(2,6,23,0.45);
    }

    .hero-module-icon {
        width: 52px;
        height: 52px;
        border-radius: 16px;
        background: rgba(99,102,241,0.15);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 22px;
    }

    .hero-module-card span {
        color: var(--text-secondary);
        font-size: 13px;
    }

    .stat-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 16px;
        margin-bottom: 32px;
    }

    .stat-card {
        background: rgba(15,23,42,0.85);
        border-radius: 20px;
        padding: 20px;
        border: 1px solid rgba(148,163,184,0.2);
        box-shadow: 0 15px 35px rgba(2,6,23,0.45);
    }

    .stat-card h3 {
        margin: 8px 0 4px;
        font-size: 28px;
        color: white;
    }

    .stat-card span {
        color: var(--text-secondary);
        font-size: 13px;
        letter-spacing: 0.5px;
    }

    .section-heading {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        margin-bottom: 18px;
    }

    .section-heading h3 {
        margin: 4px 0;
        font-size: 26px;
        color: white;
    }

    .section-heading p {
        margin: 0;
        color: var(--text-secondary);
    }

    .section-chip {
        padding: 6px 16px;
        border-radius: 999px;
        border: 1px solid rgba(148,163,184,0.4);
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: var(--text-secondary);
    }

    .section-note {
        color: var(--text-secondary);
        margin-bottom: 12px;
        font-size: 14px;
    }

    .eyebrow {
        font-size: 12px;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: var(--text-secondary);
    }

    .insight-card {
        background: rgba(2,6,23,0.55);
        border-radius: 20px;
        border: 1px solid rgba(148,163,184,0.25);
        padding: 20px;
        box-shadow: 0 20px 40px rgba(2,6,23,0.5);
    }

    .insight-card h4 {
        margin: 6px 0 10px;
        color: white;
    }

    .insight-card p {
        margin: 0;
        color: var(--text-secondary);
        line-height: 1.5;
    }

    .insight-card ul {
        margin: 16px 0 0;
        padding-left: 18px;
        color: var(--text-primary);
        font-size: 14px;
    }

    .insight-card li {
        margin-bottom: 6px;
        color: var(--text-secondary);
    }

    .module-card {
        position: relative;
        background: linear-gradient(150deg, rgba(255,255,255,0.02), rgba(2,6,23,0.92));
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 20px;
        padding: 18px;
        margin-bottom: 16px;
        display: flex;
        gap: 16px;
        align-items: center;
        box-shadow: 0 20px 40px rgba(2, 6, 23, 0.45);
        transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
        overflow: hidden;
    }

    .module-card[data-module] {
        --accent-rgb: 99, 102, 241;
        --accent-color: #6366F1;
        background: linear-gradient(135deg, rgba(var(--accent-rgb), 0.12), rgba(7, 12, 27, 0.95));
        border-color: rgba(var(--accent-rgb), 0.5);
    }

    .module-card[data-module]::before {
        content: '';
        position: absolute;
        inset: 0;
        background:
            radial-gradient(120% 90% at 0% 0%, rgba(var(--accent-rgb), 0.18), transparent 45%),
            radial-gradient(75% 65% at 100% 20%, rgba(255,255,255,0.06), transparent 42%);
        opacity: 0.9;
        pointer-events: none;
    }

    .module-card[data-module]::after {
        content: '';
        position: absolute;
        inset: 1px;
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.04);
        pointer-events: none;
    }

    .module-card.is-available:hover {
        transform: translateY(-4px);
        border-color: rgba(var(--accent-rgb), 0.6);
        box-shadow: 0 32px 70px rgba(var(--accent-rgb), 0.18), 0 25px 50px rgba(2,6,23,0.5);
        background: linear-gradient(135deg, rgba(var(--accent-rgb), 0.16), rgba(3,7,18,0.96));
    }

    .module-icon {
        position: relative;
        z-index: 1;
        width: 56px;
        height: 56px;
        border-radius: 18px;
        background: rgba(var(--accent-rgb, 99, 102, 241), 0.16);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 26px;
        color: #f8fafc;
        box-shadow: 0 10px 24px rgba(var(--accent-rgb, 99, 102, 241), 0.25), inset 0 1px 0 rgba(255,255,255,0.08);
    }

    .module-meta {
        position: relative;
        z-index: 1;
        flex: 1;
    }

    .module-meta-top {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 6px;
        flex-wrap: wrap;
    }

    .module-chip-soft {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(var(--accent-rgb, 99, 102, 241), 0.14);
        color: #e0f2fe;
        border: 1px solid rgba(var(--accent-rgb, 99, 102, 241), 0.32);
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .module-meta h4 {
        margin: 0;
        font-size: 18px;
        color: #f8fafc;
        letter-spacing: 0.02em;
        text-shadow: 0 1px 1px rgba(0,0,0,0.4);
    }

    .module-meta p {
        margin: 0;
        color: var(--text-secondary);
        font-size: 14px;
        line-height: 1.55;
    }

    .selected-card {
        background: linear-gradient(140deg, rgba(var(--accent-rgb, 99, 102, 241), 0.24), rgba(9,12,26,0.96));
        border: 1px solid rgba(var(--accent-rgb, 99, 102, 241), 0.7);
        position: relative;
        box-shadow: 0 28px 65px rgba(var(--accent-rgb, 99, 102, 241), 0.18), 0 20px 45px rgba(2,6,23,0.55);
    }

    .number-badge {
        position: relative;
        z-index: 1;
        width: 32px;
        height: 32px;
        background: rgba(var(--accent-rgb, 94, 234, 212), 0.26);
        color: white;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        margin-right: 8px;
        border: 1px solid rgba(var(--accent-rgb, 94, 234, 212), 0.5);
        box-shadow: 0 8px 18px rgba(var(--accent-rgb, 94, 234, 212), 0.25), inset 0 1px 0 rgba(255,255,255,0.08);
    }

    .empty-state {
        background: rgba(15,23,42,0.8);
        border: 1px dashed rgba(148,163,184,0.35);
        border-radius: 18px;
        padding: 32px;
        text-align: center;
        color: var(--text-secondary);
    }

    .flow-panel {
        background: rgba(15,23,42,0.9);
        border-radius: 24px;
        padding: 28px;
        border: 1px solid rgba(148,163,184,0.25);
        margin-top: 16px;
        box-shadow: 0 30px 60px rgba(2,6,23,0.55);
    }

    .flow-timeline {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        justify-content: center;
        align-items: center;
        margin-top: 16px;
    }

    .timeline-step {
        background: rgba(79,70,229,0.18);
        border-radius: 18px;
        padding: 16px;
        width: 160px;
        text-align: center;
        border: 1px solid rgba(124,58,237,0.4);
        position: relative;
    }

    .timeline-step h5 {
        margin: 8px 0 0;
        color: white;
    }

    .timeline-index {
        position: absolute;
        top: -10px;
        right: -10px;
        width: 32px;
        height: 32px;
        background: rgba(15,23,42,0.9);
        border: 1px solid rgba(124,58,237,0.6);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
    }

    .timeline-arrow {
        color: var(--text-secondary);
        font-size: 20px;
    }

    .cta-panel {
        background: linear-gradient(120deg, rgba(59,130,246,0.35), rgba(16,185,129,0.3));
        border-radius: 28px;
        padding: 36px;
        border: 1px solid rgba(148,163,184,0.25);
        margin: 40px 0 16px;
        box-shadow: 0 40px 70px rgba(2, 6, 23, 0.55);
        text-align: center;
    }

    .cta-panel h3 {
        margin: 0;
        color: white;
        font-size: 24px;
    }

    .cta-panel p {
        margin: 8px 0 0;
        color: var(--text-secondary);
    }

    .divider {
        width: 100%;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(148,163,184,0.5), transparent);
        margin: 32px 0;
    }

    .stButton > button {
        width: 100%;
        background: linear-gradient(120deg, #8B5CF6, #6366F1);
        border: none;
        color: white;
        font-weight: 600;
        padding: 14px 24px;
        border-radius: 14px;
        box-shadow: 0 20px 40px rgba(79,70,229,0.35);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 30px 50px rgba(79,70,229,0.45);
    }

    .stButton > button[disabled] {
        opacity: 0.5;
        box-shadow: none;
    }

    [class*="st-key-start_learning_btn"] {
        display: none !important;
    }

    /* 隐藏导航按钮（由悬浮按钮触发，使用 CSS 预先隐藏避免闪烁） */
    [class*="st-key-hidden_prev_button_modular"],
    [class*="st-key-hidden_next_button_modular"] {
        display: none !important;
    }

    /* Hero右侧按钮容器 */
    .hero-action-container {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: stretch;
        padding: 32px 24px;
        gap: 20px;
        background: linear-gradient(145deg, rgba(16, 185, 129, 0.05), rgba(6, 182, 212, 0.05));
        border-radius: 24px;
        border: 1px solid rgba(16, 185, 129, 0.2);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
        min-height: 100%;
    }

    /* 操作按钮特殊样式 - 使用属性选择器定位 */
    /* 定位help属性包含"上移"、"下移"、"移除"的按钮 */
    .stButton:has(> button[title*="上移"]),
    .stButton:has(> button[title*="下移"]),
    .stButton:has(> button[title*="移除"]) {
        width: auto !important;
        display: inline-block !important;
    }

    button[title="上移"],
    button[title="下移"],
    button[title="移除"],
    .stButton > button[title="上移"],
    .stButton > button[title="下移"],
    .stButton > button[title="移除"] {
        width: 42px !important;
        height: 42px !important;
        min-width: 42px !important;
        padding: 8px !important;
        background: rgba(99, 102, 241, 0.2) !important;
        color: #CBD5E1 !important;
        font-size: 18px !important;
        font-weight: normal !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
        border: 1px solid rgba(99, 102, 241, 0.4) !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.2s ease !important;
        line-height: 1 !important;
    }

    button[title="上移"]:hover,
    button[title="下移"]:hover,
    button[title="移除"]:hover,
    .stButton > button[title="上移"]:hover,
    .stButton > button[title="下移"]:hover,
    .stButton > button[title="移除"]:hover {
        background: rgba(139, 92, 246, 0.3) !important;
        border-color: rgba(139, 92, 246, 0.6) !important;
        color: #FFFFFF !important;
        transform: scale(1.05) !important;
        box-shadow: 0 4px 8px rgba(139, 92, 246, 0.2) !important;
    }

    /* Tertiary按钮样式 - 使用key选择器精准定位上移/下移/移除按钮 */
    [class*="st-key-up_"] button[data-testid="stBaseButton-tertiary"],
    [class*="st-key-down_"] button[data-testid="stBaseButton-tertiary"],
    [class*="st-key-del_"] button[data-testid="stBaseButton-tertiary"] {
        width: 42px !important;
        height: 42px !important;
        min-width: 42px !important;
        padding: 8px !important;
        background: transparent !important;
        color: #E2E8F0 !important;
        font-size: 18px !important;
        border-radius: 10px !important;
        border: 1px solid rgba(148, 163, 184, 0.3) !important;
        transition: all 0.2s ease !important;
    }

    [class*="st-key-up_"] button[data-testid="stBaseButton-tertiary"]:hover,
    [class*="st-key-down_"] button[data-testid="stBaseButton-tertiary"]:hover,
    [class*="st-key-del_"] button[data-testid="stBaseButton-tertiary"]:hover {
        background: rgba(139, 92, 246, 0.2) !important;
        border-color: rgba(139, 92, 246, 0.5) !important;
        color: #FFFFFF !important;
        transform: scale(1.05) !important;
    }

    /* Slider 颜色强化（暗底下更显眼） */
    [data-testid="stPopoverBody"] .stSlider > div > div > div {
        background: rgba(255, 255, 255, 0.12) !important; /* 灰白轨道 */
        height: 6px !important;
        border-radius: 999px !important;
    }

    [data-testid="stPopoverBody"] .stSlider > div > div > div > div {
        background: linear-gradient(120deg, #22d3ee, #6366f1) !important; /* 亮色进度条 */
        box-shadow: 0 8px 18px rgba(34, 211, 238, 0.25) !important;
        height: 6px !important;
        border-radius: 999px !important;
    }

    /* 进度点和数值气泡 */
    [data-testid="stPopoverBody"] .stSlider [data-testid="stSliderThumbValue"] {
        color: #0b1626 !important;
        font-weight: 700 !important;
        background: #f8fafc !important;
        border: 1px solid rgba(148,163,184,0.45) !important;
        border-radius: 10px !important;
        padding: 3px 8px !important;
        box-shadow: 0 10px 20px rgba(0,0,0,0.25) !important;
    }

    [data-testid="stPopoverBody"] .stSlider [data-testid="stWidgetLabel"] p {
        color: var(--text-secondary) !important;
    }

    .stAlert {
        background: rgba(15,23,42,0.85) !important;
        border: 1px solid rgba(248,250,252,0.1) !important;
        border-radius: 16px !important;
        color: var(--text-secondary) !important;
    }
    .stAlert p {
        color: #e2e8f0 !important;
    }

    /* ========== AI互动模块 ========== */
    /* 句子/释义卡片 */
    .english-sentence {
        background: linear-gradient(135deg, rgba(59,130,246,0.12), rgba(45,212,191,0.14), rgba(15,23,42,0.92));
        border: 1px solid rgba(94,234,212,0.35);
        border-radius: 16px;
        padding: 18px 20px;
        color: #e2e8f0;
        font-size: 18px;
        line-height: 1.75;
        box-shadow: 0 18px 45px rgba(2,6,23,0.45);
        margin: 14px 0 10px 0;
        backdrop-filter: blur(6px);
    }

    .english-sentence strong {
        color: #f8fafc;
    }

    /* 高亮单词样式（AI互动场景） */
    .highlight-word {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
        color: #ffffff;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 700;
        box-shadow: 0 2px 8px rgba(255, 107, 107, 0.4);
        text-shadow: 0 1px 2px rgba(0,0,0,0.35);
    }

    /* 问题提示块 */
    .question-prompt {
        background: radial-gradient(circle at 20% 20%, rgba(94,234,212,0.16), transparent 60%),
                    linear-gradient(145deg, rgba(99,102,241,0.24), rgba(14,165,233,0.2));
        color: #f8fafc;
        border: 1px solid rgba(94,234,212,0.35);
        border-radius: 14px;
        padding: 14px 18px;
        font-weight: 600;
        box-shadow: 0 16px 34px rgba(2,6,23,0.42);
        margin: 10px 0 12px 0;
    }

    /* 输入框样式（AI互动场景常用的 text_input） */
    div[data-testid="stTextInput"] > label + div input {
        background: rgba(15,23,42,0.8);
        border: 1px solid rgba(148,163,184,0.35);
        color: #e2e8f0;
        padding: 12px 14px;
        border-radius: 12px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
        caret-color: #22d3ee;
    }

    div[data-testid="stTextInput"] > label + div input:focus {
        outline: none;
        border-color: rgba(94,234,212,0.7);
        box-shadow: 0 0 0 1px rgba(94,234,212,0.55);
    }

    /* 多行输入框样式（text_area） */
    div[data-testid="stTextArea"] > label + div textarea {
        background: rgba(15,23,42,0.8);
        border: 1px solid rgba(148,163,184,0.35);
        color: #e2e8f0;
        padding: 12px 14px;
        border-radius: 12px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
        caret-color: #22d3ee;
        min-height: 120px;
        line-height: 1.6;
        resize: vertical;
    }

    div[data-testid="stTextArea"] > label + div textarea:focus {
        outline: none;
        border-color: rgba(94,234,212,0.7);
        box-shadow: 0 0 0 1px rgba(94,234,212,0.55);
    }

    /* AI反馈按钮样式 */
    .ai-feedback-button {
        background: linear-gradient(118deg, #1dd3b0 0%, #32b5ff 55%, #8091ff 100%) !important;
        border: 1px solid rgba(99,102,241,0.65) !important;
        color: #0b1220 !important;
        border-radius: 14px !important;
        padding: 10px 14px !important;
        font-weight: 700 !important;
        letter-spacing: 0.01em;
        box-shadow: 0 16px 36px rgba(50, 181, 255, 0.32) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease !important;
    }

    .ai-feedback-button:not(:disabled):hover {
        transform: translateY(-2px);
        box-shadow: 0 22px 46px rgba(29, 211, 176, 0.34), 0 12px 30px rgba(79, 70, 229, 0.24) !important;
    }

    .ai-feedback-button:not(:disabled):active {
        transform: translateY(-1px);
    }

    .ai-feedback-button:disabled {
        background: linear-gradient(118deg, #cbd5e1 0%, #94a3b8 100%) !important;
        border-color: rgba(148,163,184,0.6) !important;
        color: #0f172a !important;
        box-shadow: none !important;
        opacity: 0.7 !important;
    }

    /* 换一题按钮 - 柔和冷色调（次要操作） */
    [class*="st-key-refresh_question_btn"] button[data-testid="stBaseButton-secondary"] {
        background: linear-gradient(135deg, #27323b 0%, #31404c 100%) !important;
        border: 1px solid rgba(145, 158, 173, 0.22) !important;
        color: #efe7dc !important;
        border-radius: 14px !important;
        padding: 10px 16px !important;
        font-size: 15px !important;
        font-weight: 500 !important;
        box-shadow: 0 4px 12px rgba(5, 8, 12, 0.32) !important;
        transition: background 0.2s ease, box-shadow 0.2s ease !important;
        width: auto !important;
        min-width: 156px !important;
    }

    [class*="st-key-refresh_question_btn"] button[data-testid="stBaseButton-secondary"]:hover:not(:disabled) {
        background: linear-gradient(135deg, #2e3a44 0%, #384956 100%) !important;
        box-shadow: 0 6px 16px rgba(5, 8, 12, 0.38) !important;
    }

    [class*="st-key-refresh_question_btn"] button[data-testid="stBaseButton-secondary"]:active:not(:disabled) {
        background: linear-gradient(135deg, #242d35 0%, #2d3b46 100%) !important;
    }

    /* Agent 工具条文案 */
    .agent-toolbar-note {
        padding: 10px 12px;
        border-radius: 12px;
        background: rgba(15,23,42,0.75);
        border: 1px solid rgba(148,163,184,0.25);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
        color: var(--text-secondary);
        font-size: 13px;
        line-height: 1.5;
        margin-bottom: 4px;
    }

    .agent-toolbar-note .title {
        color: #e2e8f0;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        font-size: 11px;
    }

    @media (max-width: 900px) {
        .hero {
            padding: 32px;
            grid-template-columns: 1fr;
        }

        .hero-cta {
            order: 2;
        }

        .hero h1 {
            font-size: 34px;
        }

        .module-card {
            flex-direction: column;
            align-items: flex-start;
        }

        .module-icon {
            width: 48px;
            height: 48px;
        }
    }

    /* ========== Popover 设置面板样式 ========== */
    /* Popover 触发按钮美化 */
    [data-testid="stPopoverButton"] {
        width: 100%;
        position: relative;
        background: linear-gradient(125deg, rgba(99, 102, 241, 0.18), rgba(34, 211, 238, 0.16), rgba(12, 18, 34, 0.92));
        border: 1px solid rgba(148, 163, 184, 0.35);
        border-radius: 18px !important;
        padding: 14px 16px !important;
        box-shadow: 0 18px 42px rgba(2, 6, 23, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.05);
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 14px;
        color: #e2e8f0;
        text-align: left;
        overflow: hidden;
        isolation: isolate;
        transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
    }

    [data-testid="stPopoverButton"]::before {
        content: '';
        position: absolute;
        inset: 0;
        background: radial-gradient(75% 75% at 20% 20%, rgba(59, 130, 246, 0.25), transparent 55%),
                    radial-gradient(90% 90% at 90% 20%, rgba(34, 211, 238, 0.2), transparent 50%);
        opacity: 0.95;
        pointer-events: none;
        z-index: 0;
    }

    [data-testid="stPopoverButton"]::after {
        content: '';
        position: absolute;
        inset: 1px;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.04);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
        pointer-events: none;
    }

    [data-testid="stPopoverButton"]:hover {
        transform: translateY(-2px);
        border-color: rgba(94, 234, 212, 0.45);
        box-shadow: 0 24px 54px rgba(8, 47, 73, 0.45), 0 10px 30px rgba(99, 102, 241, 0.3);
    }

    [data-testid="stPopoverButton"]:focus-visible {
        outline: none;
        border-color: rgba(94,234,212,0.65);
        box-shadow: 0 0 0 2px rgba(94,234,212,0.35), 0 14px 34px rgba(99,102,241,0.28);
    }

    [data-testid="stPopoverButton"]:active {
        transform: translateY(-1px);
    }

    [data-testid="stPopoverButton"] span[data-testid="stIconMaterial"] {
        width: 38px;
        height: 38px;
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.35), rgba(59, 130, 246, 0.28));
        color: #f8fafc;
        box-shadow: 0 8px 16px rgba(59, 130, 246, 0.3), inset 0 1px 0 rgba(255,255,255,0.08);
        z-index: 1;
    }

    [data-testid="stPopoverButton"] div[data-testid="stMarkdownContainer"] p {
        margin: 0;
        color: #e2e8f0;
        line-height: 1.4;
        font-weight: 700;
        white-space: pre-line;
    }

    [data-testid="stPopoverButton"] div[data-testid="stMarkdownContainer"] p::first-line {
        color: #f8fafc;
        letter-spacing: 0.02em;
        font-size: 15px;
    }

    [data-testid="stPopoverButton"] > div:last-of-type {
        width: 38px;
        height: 38px;
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(15,23,42,0.65);
        border: 1px solid rgba(148,163,184,0.35);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
        color: #cbd5e1;
        z-index: 1;
    }

    [data-testid="stPopoverButton"] > div:last-of-type svg {
        color: inherit;
        opacity: 0.92;
    }

    /* Popover 外层容器（毛玻璃 + 霓虹描边） */
    [data-testid="stPopoverBody"] {
        position: relative;
        background:
            radial-gradient(110% 90% at 14% 18%, rgba(34, 211, 238, 0.2), transparent 48%),
            radial-gradient(90% 85% at 86% 12%, rgba(139, 92, 246, 0.22), transparent 46%),
            linear-gradient(170deg, rgba(6, 12, 24, 0.98), rgba(2, 6, 19, 0.96)),
            #050915 !important;
        background-color: #050915 !important;
        border-radius: 18px !important;
        border: 2px solid rgba(148, 163, 184, 0.35) !important;
        box-shadow: 0 30px 70px rgba(0, 0, 0, 0.6), 0 14px 32px rgba(59, 130, 246, 0.22) !important;
        overflow: auto !important;
        backdrop-filter: blur(14px) saturate(130%) !important;
        color: var(--text-primary) !important;
        padding: 12px 16px 18px !important;
        box-sizing: border-box !important;
        min-width: 380px;
    }

    [data-testid="stPopoverBody"]::before {
        content: '';
        position: absolute;
        inset: 10px;
        border-radius: 12px;
        border: none;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
        pointer-events: none;
    }

    /* 去掉 Streamlit 默认白底 */
    [data-testid="stPopoverBody"] > div[class*="st-c6"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    /* 更彻底地移除 BaseWeb/Streamlit 注入的白底 */
    [data-testid="stPopoverBody"] .st-bc,
    [data-testid="stPopoverBody"] .st-bw,
    [data-testid="stPopoverBody"] .st-dm,
    [data-testid="stPopoverBody"] .st-dl,
    [data-testid="stPopoverBody"] .st-dq {
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
    }

    /* 覆盖可能变动的 st-b* 类（BaseWeb 版本迭代时的白底） */
    [data-testid="stPopoverBody"] [class^="st-b"],
    [data-testid="stPopoverBody"] [class*=" st-b"] {
        background: transparent !important;
        box-shadow: none !important;
        border: none !important;
    }

    /* 兜底：所有直接子层的 div 去掉背景，防止刷新后出现白块 */
    [data-testid="stPopoverBody"] > div,
    [data-testid="stPopoverBody"] > div > div {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    [data-testid="stPopoverBody"] .stVerticalBlock {
        background: transparent !important;
    }

    [data-testid="stPopoverBody"] .st-bs {
        background: transparent !important;
    }

    /* 修复 Popover 内 tertiary 按钮 hover 时文字变红的问题 */
    [data-testid="stPopoverBody"] [data-testid="stBaseButton-tertiary"]:hover,
    [data-testid="stPopoverBody"] [data-testid="stBaseButton-tertiary"]:focus-visible {
        color: var(--success) !important;  /* 使用青色代替红色 */
    }

    [data-testid="stPopoverBody"] [data-testid="stBaseButton-tertiary"]:hover p,
    [data-testid="stPopoverBody"] [data-testid="stBaseButton-tertiary"]:focus-visible p {
        color: var(--success) !important;
    }

    [data-testid="stPopoverBody"]::-webkit-scrollbar {
        width: 8px;
    }

    [data-testid="stPopoverBody"]::-webkit-scrollbar-thumb {
        background: rgba(148, 163, 184, 0.3);
        border-radius: 999px;
    }

    [data-testid="stPopoverBody"]::-webkit-scrollbar-track {
        background: transparent;
    }

    .popover-summary-card {
        background: linear-gradient(125deg, rgba(94, 234, 212, 0.14), rgba(99, 102, 241, 0.16), rgba(12, 18, 34, 0.92));
        border: 1px solid rgba(148, 163, 184, 0.32);
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 12px 26px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06);
        margin-bottom: 10px;
    }

    .popover-summary-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(148,163,184,0.38);
        color: #e2e8f0;
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .popover-summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 14px;
        margin-top: 14px;
    }

    .popover-summary-stat {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .popover-summary-stat .label {
        color: #9fb2c7;
        font-size: 12px;
        letter-spacing: 0.02em;
    }

    .popover-summary-stat .value {
        color: #f8fafc;
        font-size: 21px;
        font-weight: 700;
        text-shadow: 0 3px 10px rgba(59,130,246,0.35);
    }

    .popover-summary-hint {
        margin-top: 10px;
        font-size: 12px;
        color: #a5b4c7;
    }

    /* 自定义 Popover 触发按钮区域 */
    .popover-trigger-area {
        display: flex;
        justify-content: center;
        margin: -8px 0 24px;
    }

    /* Popover 内的 section 分隔 */
    .popover-section {
        padding: 16px 18px 12px;
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 14px;
        background: linear-gradient(135deg, rgba(255,255,255,0.015), rgba(99,102,241,0.05));
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
        margin-bottom: 12px;
    }

    .popover-section:last-child {
        border-bottom: none;
    }

    .popover-section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 10px;
    }

    .popover-section-icon {
        width: 34px;
        height: 34px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        color: #fff;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.22), rgba(34, 211, 238, 0.16));
        border: 1px solid rgba(99, 102, 241, 0.28);
        box-shadow: 0 6px 14px rgba(0,0,0,0.35);
    }

    .popover-section-title {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
    }

    .popover-section-desc {
        font-size: 12px;
        color: var(--text-secondary);
        margin: 0;
    }

    /* Popover 内的模块卡片（紧凑版） */
    .popover-module-card {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: linear-gradient(140deg, rgba(15, 23, 42, 0.9), rgba(18, 29, 54, 0.88));
        margin-bottom: 10px;
        transition: all 0.2s ease;
        position: relative;
        overflow: hidden;
        box-shadow: 0 12px 28px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.05);
    }

    .popover-module-card::after {
        content: '';
        position: absolute;
        inset: 1px;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.02);
        pointer-events: none;
    }

    .popover-module-card:hover {
        border-color: rgba(99, 102, 241, 0.4);
        background: linear-gradient(140deg, rgba(99, 102, 241, 0.16), rgba(15, 23, 42, 0.9));
        transform: translateY(-2px);
        box-shadow: 0 16px 36px rgba(59,130,246,0.22);
    }

    .popover-module-icon {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
        flex-shrink: 0;
        position: relative;
        color: #f8fafc;
        text-shadow: 0 1px 2px rgba(0,0,0,0.45);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 10px 18px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.08);
        overflow: hidden;
    }

    .popover-module-icon::after {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: inherit;
        background:
            radial-gradient(120% 90% at 20% 15%, rgba(255,255,255,0.12), transparent 55%),
            radial-gradient(80% 70% at 80% 20%, rgba(255,255,255,0.06), transparent 55%);
        pointer-events: none;
        mix-blend-mode: screen;
    }

    .popover-module-info {
        flex: 1;
        min-width: 0;
    }

    .popover-module-name {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .popover-module-desc {
        font-size: 11px;
        color: var(--text-secondary);
        margin: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* 已选流程的迷你预览 */
    .popover-flow-preview {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 12px;
        background: linear-gradient(125deg, rgba(3, 7, 18, 0.75), rgba(15, 23, 42, 0.85));
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.14);
        min-height: 44px;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
    }

    .popover-flow-item {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(59, 130, 246, 0.16));
        border: 1px solid rgba(99, 102, 241, 0.38);
        color: var(--text-primary);
        box-shadow: 0 6px 12px rgba(0,0,0,0.25);
    }

    .popover-flow-arrow {
        color: var(--text-secondary);
        font-size: 10px;
    }

    .popover-empty-hint {
        color: var(--text-secondary);
        font-size: 12px;
        font-style: italic;
    }

    /* 数量徽章 */
    .popover-count-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 22px;
        height: 22px;
        padding: 0 7px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
        background: rgba(34, 211, 238, 0.2);
        color: var(--success);
        border: 1px solid rgba(34, 211, 238, 0.32);
        box-shadow: 0 8px 14px rgba(34,211,238,0.18);
    }

    /* Popover 内部按钮强化（仅限添加模块的按钮） */
    div[data-testid="stPopover"] [class*="st-key-add_"] button {
        width: 100% !important;
        border-radius: 12px !important;
        background: linear-gradient(120deg, rgba(99, 102, 241, 0.28), rgba(59, 130, 246, 0.32)) !important;
        border: 1px solid rgba(99, 102, 241, 0.6) !important;
        color: #f8fafc !important;
        font-weight: 700 !important;
        box-shadow: 0 14px 28px rgba(99, 102, 241, 0.24) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease !important;
    }

    div[data-testid="stPopover"] [class*="st-key-add_"] button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 18px 36px rgba(94, 234, 212, 0.16), 0 10px 28px rgba(99, 102, 241, 0.24) !important;
        border-color: rgba(94, 234, 212, 0.6) !important;
    }

    div[data-testid="stPopover"] [class*="st-key-add_"] button:active {
        transform: translateY(-1px) !important;
    }

    /* 已选流程的行样式 */
    div[data-testid="stPopoverBody"] .stHorizontalBlock {
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid rgba(148,163,184,0.22);
        background: linear-gradient(125deg, rgba(12,18,34,0.92), rgba(6,12,24,0.92));
        box-shadow: 0 12px 28px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.04);
        margin-bottom: 10px;
        align-items: center !important;  /* 覆盖 Streamlit 默认的 stretch */
    }

    /* 关键修复：让每个 stColumn 在父容器中垂直居中，而不是拉伸 */
    div[data-testid="stPopoverBody"] .stHorizontalBlock .stColumn {
        align-self: center !important;
    }

    /* stVerticalBlock 高度自适应 */
    div[data-testid="stPopoverBody"] .stHorizontalBlock .stVerticalBlock {
        height: auto !important;
    }

    div[data-testid="stPopoverBody"] .stHorizontalBlock:last-of-type {
        margin-bottom: 0;
    }

    /* 行内文字对齐 & 提升对比度 */
    div[data-testid="stPopoverBody"] .stColumn p {
        margin: 0;
        color: #e2e8f0;
        font-weight: 600;
        letter-spacing: 0.01em;
    }

    /* 侧边栏用户卡片样式（Minimal Flat 风格） */
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(148, 163, 184, 0.25) !important;
        border-radius: 12px !important;
    }
    /* 卡片内文字颜色 */
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] p {
        color: #94a3b8 !important;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] a {
        color: #94a3b8 !important;
        text-decoration: none !important;
    }
    /* 侧边栏内的 secondary 按钮（Minimal Flat 风格） */
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(0, 0, 0, 0.25) !important;
        border-radius: 12px !important;
        color: #000000 !important;
        padding: 4px 12px !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:focus {
        box-shadow: none !important;
        outline: none !important;
    }
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] span,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] div {
        color: #000000 !important;
    }
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
        background: rgba(0, 0, 0, 0.08) !important;
        border-color: rgba(0, 0, 0, 0.4) !important;
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏 <hr> 颜色 — JS 监听主题变化，即时适配深色/浅色模式
components.html("""
<script>
(function() {
    let D;
    try {
        D = (window.parent && window.parent !== window) ? window.parent.document : document;
    } catch(e) { return; }

    function updateSidebarHr() {
        var sb = D.querySelector('[data-testid="stSidebar"]');
        if (!sb) return;
        const bg = getComputedStyle(sb).backgroundColor;
        const m = bg.match(/\\d+/g);
        if (!m) return;
        const lum = (0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]) / 255;
        const color = lum < 0.5 ? 'rgba(250,250,250,0.2)' : '#d3d2ca';
        sb.querySelectorAll('.stMarkdown hr').forEach(function(el) {
            el.style.setProperty('border-color', color, 'important');
            el.style.setProperty('border-width', '1px', 'important');
        });
    }

    updateSidebarHr();
    // 主题切换：body style 属性变化
    new MutationObserver(updateSidebarHr).observe(D.body, { attributes: true, attributeFilter: ['style'] });
    // DOM 变化：侧边栏出现、hr 插入（debounce 避免高频调用）
    var t;
    new MutationObserver(function() { clearTimeout(t); t = setTimeout(updateSidebarHr, 100); }).observe(D.body, { childList: true, subtree: true });
})();
</script>
""", height=0)

# ========== 初始化状态 ==========
# 学习模式：'single' 或 'batch'
if 'learning_mode' not in st.session_state:
    st.session_state.learning_mode = 'batch'

# 批量学习的单词数量（1-10）
if 'batch_size' not in st.session_state:
    st.session_state.batch_size = 5

# 可用的学习模块定义
AVAILABLE_MODULES = [
    {
        'id': 'read_three_times',
        'name': '朗读练习',
        'description': '智能语音播放，加深记忆印象',
        'icon': '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/></svg>',
        # 青蓝霓虹：和页面主色的蓝绿系更统一
        'color': '#22d3ee'
    },
    {
        'id': 'view_details',
        'name': '词汇详解',
        'description': '深度解析词义、用法与例句',
        'icon': '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/></svg>',
        # 薄荷青绿：偏学习/理解感，比较柔和
        'color': '#22c55e'
    },
    {
        'id': 'self_rating',
        'name': '记忆评估',
        'description': '智能间隔复习系统',
        'icon': '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 18V5"/><path d="M15 13a4.17 4.17 0 0 1-3-4 4.17 4.17 0 0 1-3 4"/><path d="M17.598 6.5A3 3 0 1 0 12 5a3 3 0 1 0-5.598 1.5"/><path d="M17.997 5.125a4 4 0 0 1 2.526 5.77"/><path d="M18 18a4 4 0 0 0 2-7.464"/><path d="M19.967 17.483A4 4 0 1 1 12 18a4 4 0 1 1-7.967-.517"/><path d="M6 18a4 4 0 0 1-2-7.464"/><path d="M6.003 5.125a4 4 0 0 0-2.526 5.77"/></svg>',
        # 琥珀橙：很适合「进度 / 评价」这种感觉
        'color': '#fbbf24'
    },
    {
        'id': 'agent_learning',
        'name': 'AI互动',
        'description': '场景对话与智能练习',
        'icon': '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>',
        # 电光紫：和整体紫色主调很搭，也容易联想到「AI」
        'color': '#a855f7'
    }
]

MODULE_BADGES = {
    'read_three_times': '节奏&发音',
    'view_details': '拆解&例句',
    'self_rating': '记忆追踪',
    'agent_learning': 'AI互动'
}


def get_module_info(module_id):
    """根据模块ID获取模块信息。"""
    return next((m for m in AVAILABLE_MODULES if m['id'] == module_id), None)


def hex_to_rgba(hex_color, alpha):
    """将 #RRGGBB 颜色转换为 rgba，用于渐变强调。"""
    if not hex_color:
        return f"rgba(99, 102, 241, {alpha})"
    value = hex_color.lstrip('#')
    if len(value) != 6:
        return f"rgba(99, 102, 241, {alpha})"
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def hex_to_rgb(hex_color):
    """将 #RRGGBB 颜色转换为 r,g,b 字符串，便于在 CSS 中复用。"""
    if not hex_color:
        return "99, 102, 241"
    value = hex_color.lstrip('#')
    if len(value) != 6:
        return "99, 102, 241"
    r = int(value[0:2], 16)
    g = int(value[2:4], 16)
    b = int(value[4:6], 16)
    return f"{r}, {g}, {b}"

# 用户选择的模块（默认选择三个）
if 'selected_modules' not in st.session_state:
    st.session_state.selected_modules = ['view_details', 'read_three_times', 'agent_learning']

# 模块顺序（默认顺序：词汇详解 -> 朗读练习 -> AI互动）
if 'module_order' not in st.session_state:
    st.session_state.module_order = ['view_details', 'read_three_times', 'agent_learning']

# 学习状态
if 'learning_started' not in st.session_state:
    st.session_state.learning_started = False

# ========== FastAPI和OpenAI配置 ==========
fastapi_url = os.getenv("FASTAPI_URL")
# 强制登录检查
require_login()
user_id = get_current_user_id()  # 获取当前登录用户ID

# 检测用户变更，清理缓存
if 'current_user_id' not in st.session_state:
    st.session_state.current_user_id = user_id
elif st.session_state.current_user_id != user_id:
    # 用户已变更，清理所有用户相关的缓存
    st.session_state.current_user_id = user_id
    st.session_state.chat_session_id = uuid.uuid4().hex
    if 'previous_session_id' in st.session_state:
        st.session_state.previous_session_id = st.session_state.chat_session_id
    if 'ai_content_checked' in st.session_state:
        st.session_state.ai_content_checked = False
    # 清理学习计划数据（防御性编程，防止跨用户数据泄露）
    st.session_state.learning_plan = []
    st.session_state.loop_learning_plan = []
    st.session_state.current_index = 0
    st.session_state.loop_current_index = 0
    # 清理所有题目相关的缓存数据（防止跨用户数据污染和索引越界）
    keys_to_delete = [k for k in st.session_state.keys()
                      if k.startswith(('question_type_', 'random_sentence_',
                                       'random_sentence_meaning_', 'random_translation_',
                                       'random_fill_blank_', 'current_word_data_',
                                       'answer_'))]
    for key in keys_to_delete:
        del st.session_state[key]
    # 清理单词书选择（防止跨用户继承）
    # 使用 set_current_wordbook(None) 走完整的清理路径
    # 这会同时重置 learning_started，防止 book_name=None 时加载全库单词
    set_current_wordbook(None)

    # 清理单词书选择器状态（防止沿用上个用户的选项）
    if 'wordbook_category_selector' in st.session_state:
        del st.session_state['wordbook_category_selector']
    if 'wordbook_book_selector' in st.session_state:
        del st.session_state['wordbook_book_selector']
    if '_skip_db_restore' in st.session_state:
        del st.session_state['_skip_db_restore']

# 检查FastAPI服务器状态
fastapi_status = "🟢 运行中"
try:
    response = requests.get(f"{fastapi_url}/health", timeout=2)
    if response.status_code == 200:
        fastapi_status = "🟢 运行中"
    else:
        fastapi_status = "🔴 异常"
except:
    fastapi_status = "🔴 未启动"


# 🔐 为 <audio> TTS GET 请求写入 HttpOnly cookie（避免 JWT 出现在 URL 参数中）
# 前端会用 JS fetch 携带 Authorization header 调用 FastAPI 的 /api/tts/auth/cookie，
# 由后端下发 HttpOnly cookie，之后 <audio src=".../api/tts/word/..."> 会自动携带 cookie。
try:
    if user_id and fastapi_status.startswith("🟢"):
        jwt_token_for_tts_cookie = get_jwt_token(user_id)
        if jwt_token_for_tts_cookie and st.session_state.get("_tts_cookie_token") != jwt_token_for_tts_cookie:
            st.session_state["_tts_cookie_token"] = jwt_token_for_tts_cookie

            cookie_api_url = f"{fastapi_url}/api/tts/auth/cookie"
            cookie_api_url_js = json.dumps(cookie_api_url).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
            token_js = json.dumps(jwt_token_for_tts_cookie).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

            components.html(
                f"""
                <script>
                (async () => {{
                    try {{
                        const apiUrl = {cookie_api_url_js};
                        const token = {token_js};
                        await fetch(apiUrl, {{
                            method: "POST",
                            headers: {{
                                "Authorization": "Bearer " + token,
                            }},
                            credentials: "include",
                        }});
                    }} catch (e) {{
                        console.warn("[TTS cookie] set cookie failed:", e);
                    }}
                }})();
                </script>
                """,
                height=0,
            )
except Exception:
    pass


# AI聊天相关状态（必须在侧边栏之前初始化）
if 'chat_session_id' not in st.session_state:
    st.session_state.chat_session_id = uuid.uuid4().hex

# ========== 早期初始化 FSRS 系统（侧边栏需要使用）==========
sys.path.insert(0, os.path.join(project_root, 'fsrs_demo'))
from fsrs_postgresql_demo import FSRSPostgreSQLSystem

# 🚀 全局单例：所有用户共享同一个连接池（减少 DB 连接数）
@st.cache_resource(show_spinner=False)
def get_fsrs_system():
    """
    使用 st.cache_resource 缓存 FSRS 系统实例
    - 所有 users/sessions/reruns 共享同一个连接池
    - psycopg_pool.ConnectionPool 是线程安全的
    - 数据隔离通过 user_id 参数在 SQL 层面实现
    """
    return FSRSPostgreSQLSystem()

if 'fsrs_system' not in st.session_state:
    st.session_state.fsrs_system = get_fsrs_system()

# 🔧 中断 widget clean-up 过程，保留 pronunciation 状态（Streamlit 官方推荐方案）
# 参考：https://docs.streamlit.io/develop/concepts/architecture/widget-behavior#interrupting-the-widget-clean-up-process
# 当切换页面时，widget 的 session_state 会被清理，通过重新赋值可以中断这个过程
if 'pronunciation' in st.session_state:
    st.session_state.pronunciation = st.session_state.pronunciation

# 从数据库加载用户的发音偏好（实现跨设备同步）
if user_id:
    # 检查是否需要从数据库加载（首次访问、用户切换、或 pronunciation 不存在）
    if ('_pronunciation_loaded_for_user' not in st.session_state 
        or st.session_state._pronunciation_loaded_for_user != user_id
        or 'pronunciation' not in st.session_state):
        db_pronunciation = st.session_state.fsrs_system.get_pronunciation(user_id)
        st.session_state.pronunciation = db_pronunciation
        st.session_state._pronunciation_loaded_for_user = user_id

# ========== 侧边栏 ==========
with st.sidebar:
    # ========== 自定义导航菜单 ==========
    render_sidebar_nav()
    
    # ========== 登录状态显示（Minimal Flat 风格） ==========
    if st.user.is_logged_in:
        with st.container(border=True):
            st.markdown(f":material/person: {st.user.email}")
            if st.button("退出登录", key="sidebar_logout", icon=":material/logout:"):
                st.logout()
    else:
        if st.button("登录", icon=":material/login:"):
            st.login("auth0")
    st.markdown("---")

    # ========== 单词书选择 ==========
    st.markdown("### :material/menu_book: 单词书")
    if render_wordbook_selector(user_id, st.session_state.fsrs_system):
        st.rerun()

    # ========== 退出沉浸式学习 ==========
    if st.session_state.get('learning_started', False):
        if st.button("退出沉浸式学习", key="exit_immersive_learning", use_container_width=True, icon=":material/logout:"):
            st.session_state.learning_started = False
            st.session_state.learning_plan = []
            st.session_state.batch_index = 0
            st.session_state.module_index = 0
            st.session_state.word_index_in_batch = 0
            # 清理所有题目相关的缓存数据（防止重新开始学习时复用旧数据）
            keys_to_delete = [k for k in st.session_state.keys()
                              if k.startswith(('question_type_', 'random_sentence_',
                                               'random_sentence_meaning_', 'random_translation_',
                                               'random_fill_blank_', 'current_word_data_',
                                               'answer_'))]
            for key in keys_to_delete:
                del st.session_state[key]
            st.rerun()

    st.markdown("---")

    # ========== AI对话历史选择（置顶） ==========
    if fastapi_status == "🟢 运行中":
        try:
            # 使用 JWT 认证调用 FastAPI
            jwt_token = get_jwt_token(user_id)
            response = requests.get(
                f"{fastapi_url}/api/sessions",
                headers={"Authorization": f"Bearer {jwt_token}"},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    available_sessions = data.get('sessions', [])
                    st.markdown("### :material/smart_toy: AI对话")

                    # 新建对话按钮
                    if st.button("新建对话", use_container_width=True, icon=":material/add:"):
                        st.session_state.chat_session_id = uuid.uuid4().hex
                        st.session_state.previous_session_id = st.session_state.chat_session_id
                        st.rerun()

                    # 创建选择框选项 - 显示时间和消息预览
                    def format_session_option(s):
                        last_time = s.get('last_message_time', '')
                        preview = s.get('last_message_preview', '')

                        # 格式化时间
                        time_str = "未知时间"
                        if last_time:
                            from datetime import datetime
                            try:
                                dt_utc = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
                                dt_local = dt_utc.astimezone()
                                time_str = dt_local.strftime("%m-%d %H:%M")
                            except:
                                time_str = last_time[:16] if len(last_time) > 16 else last_time

                        # 组合时间和预览
                        if preview:
                            # 截取前20个字符，避免太长
                            preview_text = preview[:20] + "..." if len(preview) > 20 else preview
                            return f"{time_str} - {preview_text}"
                        else:
                            return time_str

                    # 找到当前session_id在列表中的位置
                    current_session_id = st.session_state.chat_session_id
                    session_id_in_list = False
                    current_index_in_available = 0

                    for idx, session in enumerate(available_sessions):
                        if session['session_id'] == current_session_id:
                            current_index_in_available = idx
                            session_id_in_list = True
                            break

                    # 构建选项列表
                    if not session_id_in_list:
                        display_sessions = [{"session_id": current_session_id, "last_message_time": None, "is_placeholder": True}] + available_sessions
                        session_options = ["未选择历史对话"] + [format_session_option(s) for s in available_sessions]
                        current_index = 0
                    else:
                        display_sessions = available_sessions
                        session_options = [format_session_option(s) for s in available_sessions]
                        current_index = current_index_in_available

                    # 存储到 session_state
                    st.session_state._display_sessions = display_sessions

                    def on_session_change():
                        selected_index = st.session_state.session_selector_index
                        display_sessions = st.session_state.get('_display_sessions', [])
                        if not display_sessions or selected_index >= len(display_sessions):
                            return

                        selected_session = display_sessions[selected_index]
                        if selected_session.get('is_placeholder'):
                            return

                        new_session_id = selected_session['session_id']
                        if new_session_id != st.session_state.chat_session_id:
                            st.session_state.chat_session_id = new_session_id
                            st.session_state.previous_session_id = new_session_id
                            st.session_state._session_changed = True  # 设置标志
                            st.session_state._auto_open_dialog = True  # 🔥 自动打开对话框标志

                    # 历史对话选择框
                    selected_index = st.selectbox(
                        "历史对话选择",
                        options=list(range(len(session_options))),
                        format_func=lambda i: session_options[i],
                        index=current_index,
                        key="session_selector_index",
                        on_change=on_session_change
                    )

                    # 刷新历史对话列表按钮
                    if st.button("刷新历史对话", use_container_width=True, icon=":material/refresh:"):
                        st.rerun()

                    # 检查是否需要重新渲染
                    if st.session_state.get('_session_changed'):
                        st.session_state._session_changed = False
                        st.rerun()
        except Exception as e:
            st.error(f"加载对话历史失败: {str(e)}", icon=":material/error:")

    st.markdown("---")

    # ========== 发音选择（放在侧边栏最下面） ==========
    # 发音选择回调 - 保存到数据库实现跨设备同步
    def on_pronunciation_change():
        """发音选择变更时保存到数据库"""
        if user_id:
            st.session_state.fsrs_system.set_pronunciation(
                user_id, st.session_state.pronunciation
            )
    
    # 发音选择 - 使用 key="pronunciation" 让 radio 自动管理状态
    # 重要：必须使用与 app.py 相同的 key，确保 widget 状态在页面切换时不被清理
    st.radio(
        "选择发音",
        options=["us", "uk"],
        format_func=lambda x: "🇺🇸 美式发音" if x == "us" else "🇬🇧 英式发音",
        key="pronunciation",
        on_change=on_pronunciation_change  # 保存到数据库
    )

    # ========== 清理 TTS 缓存按钮 ==========
    st.markdown("---")
    if st.button("清理语音缓存", key="clear_tts_cache", use_container_width=True, icon=":material/delete:"):
        # 通过 JavaScript 清理 localStorage 中的 TTS 缓存
        components.html("""
        <script>
        (function() {
            try {
                const storage = window.parent.localStorage;
                const keys = Object.keys(storage).filter(k => k.startsWith('tts_cache_v2_'));
                const count = keys.length;
                keys.forEach(k => storage.removeItem(k));
                console.log('[TTS Cache] 已清理 ' + count + ' 条缓存');
                // 显示提示（使用 Streamlit 的 toast 机制不可用，改用 alert）
                if (count > 0) {
                    alert('✅ 已清理 ' + count + ' 条语音缓存');
                } else {
                    alert('ℹ️ 没有语音缓存需要清理');
                }
            } catch (e) {
                console.error('[TTS Cache] 清理失败:', e);
                alert('❌ 清理失败: ' + e.message);
            }
        })();
        </script>
        """, height=0)
    st.caption("清理浏览器中缓存的语音数据")

# ========== 主界面 ==========
# ========== 配置界面（仅在未开始学习时显示） ==========
if not st.session_state.learning_started:
    # 清理沉浸式学习遗留的悬浮按钮
    components.html("""
    <script>
    (function() {
        try {
            const D = window.parent ? window.parent.document : document;
            const prevBtn = D.getElementById('floating-prev-button');
            const nextBtn = D.getElementById('floating-next-button');
            if (prevBtn) { prevBtn.remove(); console.log('[Cleanup] 已移除上一个按钮'); }
            if (nextBtn) { nextBtn.remove(); console.log('[Cleanup] 已移除下一个按钮'); }
        } catch (e) {
            console.log('[Cleanup] 清理失败:', e.message);
        }
    })();
    </script>
    """, height=0)

    selected_flow = [module for module in (get_module_info(mid) for mid in st.session_state.module_order) if module]

    hero_badges = (
        " ".join([
            f"<span class='module-pill' style='background: {hex_to_rgba(module['color'], 0.18)}; border-color: {hex_to_rgba(module['color'], 0.55)}; box-shadow: 0 0 0 1px {hex_to_rgba(module['color'], 0.25)};'>{module['icon']} {module['name']}</span>"
            for module in selected_flow[:4]
        ]) if selected_flow else "<span class='module-pill pill-empty'>添加模块，打造专属学习路径</span>"
    )

    active_module_count = len(selected_flow)
    current_book = get_current_wordbook()
    has_wordbook = current_book is not None

    # 需要同时满足：1) 选择了学习模块 2) 选择了单词书
    hero_cta_enabled = active_module_count > 0 and has_wordbook

    if not has_wordbook:
        hero_cta_main = '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/></svg> 请先从左侧选择单词书'
    elif active_module_count == 0:
        hero_cta_main = '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 19-7-7 7-7"/><path d="M19 12H5"/></svg> 请先从设置添加学习模块'
    else:
        hero_cta_main = '<svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09"/><path d="M9 12a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.4 22.4 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 .05 5 .05"/></svg> 开启沉浸式学习'

    hero_html = f"""
    <div class="hero" id="hero-main">
        <div class="hero-content">
            <span class="hero-label">UltraThink · 模块实验室</span>
            <h1>Agent 模块化学习系统</h1>
            <div id="hero-settings-anchor"></div>
            <div class="hero-flow">
                {hero_badges}
            </div>
        </div>
        <div class="hero-cta" id="hero-cta-action" data-enabled="{str(hero_cta_enabled).lower()}">
            <div class="hero-cta-main">{hero_cta_main}</div>
        </div>
    </div>
    """

    st.markdown(hero_html, unsafe_allow_html=True)

    hidden_button_placeholder = st.empty()

    if hero_cta_enabled:
        if hidden_button_placeholder.button(
            "开启沉浸式学习",
            key="start_learning_btn",
            use_container_width=True,
            icon=":material/rocket_launch:"
        ):
            st.session_state.learning_started = True
            st.balloons()
            st.rerun()

    # 使用动态时间戳强制每次 rerun 都重新执行 JavaScript
    # 修复 bug: 静态 srcdoc 内容导致浏览器不重新执行 iframe 中的 JS
    _hero_cta_ts = str(time.time())
    components.html(
        """
        <script>
        // Force re-execution: """ + _hero_cta_ts + """
        (function() {
            const parentWin = window.parent || window;
            const bindHeroCta = () => {
                const doc = parentWin.document;
                const hero = doc.getElementById('hero-cta-action');
                if (!hero) return;
                const buttons = Array.from(doc.querySelectorAll('button'));
                const target = buttons.find(btn => btn.innerText && btn.innerText.includes('开启沉浸式学习'));
                // 如果找不到目标按钮，移除旧绑定，等待下一次扫描
                if (!target) {
                    if (hero.__heroCtaHandler) {
                        hero.removeEventListener('click', hero.__heroCtaHandler);
                        hero.__heroCtaHandler = null;
                        hero.__heroCtaTarget = null;
                    }
                    return;
                }

                // 强制每次都重新绑定事件监听器
                // 修复 bug: DOM 更新（如 load_wordbook_to_database 进度条）会破坏浏览器内部监听器状态
                // 即使 target 相同，也需要 remove + add 来确保监听器正常工作
                if (hero.__heroCtaHandler) {
                    hero.removeEventListener('click', hero.__heroCtaHandler);
                }

                hero.__heroCtaTarget = target;
                hero.__heroCtaHandler = (evt) => {
                    if (hero.getAttribute('data-enabled') !== 'true') return;
                    evt.preventDefault();
                    evt.stopPropagation();
                    // 如果目标已被销毁，先重新绑定再尝试立即点击新的目标
                    if (!target || !target.isConnected) {
                        hero.__heroCtaTarget = null;
                        hero.__heroCtaHandler = null;
                        setTimeout(() => {
                            bindHeroCta();
                            const freshButtons = Array.from(doc.querySelectorAll('button'));
                            const freshTarget = freshButtons.find(btn => btn.innerText && btn.innerText.includes('开启沉浸式学习'));
                            if (freshTarget && freshTarget.isConnected) {
                                freshTarget.click();
                            }
                        }, 20);
                        return;
                    }
                    target.click();
                };
                hero.addEventListener('click', hero.__heroCtaHandler);

                const wrapper = target.closest('div[data-testid="stButton"]');
                if (wrapper) {
                    wrapper.style.display = 'none';
                }
                const container = wrapper ? wrapper.closest('div[data-testid="element-container"]') : null;
                if (container) {
                    container.style.display = 'none';
                }
            };

            const scheduleBind = () => {
                setTimeout(bindHeroCta, 50);
                setTimeout(bindHeroCta, 250);
                setTimeout(bindHeroCta, 600);
            };

            if (!parentWin.__heroCtaBinderRegistered) {
                parentWin.__heroCtaBinderRegistered = true;
                parentWin.addEventListener('resize', () => setTimeout(bindHeroCta, 200));
            }

            if (['complete', 'interactive'].includes(parentWin.document.readyState)) {
                scheduleBind();
            } else {
                parentWin.document.addEventListener('DOMContentLoaded', scheduleBind, { once: true });
            }

            scheduleBind();

            // ========== 将设置按钮移动到 Hero 内部 ==========
            const moveSettingsBtn = () => {
                const doc = parentWin.document;
                const hero = doc.getElementById('hero-main');
                const anchor = doc.getElementById('hero-settings-anchor');
                const settingsContainer = doc.querySelector('.st-key-hero-settings-btn');

                if (!hero || !anchor || !settingsContainer) return;

                // 如果已经在 hero 内部，跳过
                if (settingsContainer.parentElement === anchor || hero.contains(settingsContainer)) return;

                // 移动到锚点内
                anchor.appendChild(settingsContainer);
            };

            const scheduleMove = () => {
                setTimeout(moveSettingsBtn, 100);
                setTimeout(moveSettingsBtn, 300);
                setTimeout(moveSettingsBtn, 700);
            };

            if (['complete', 'interactive'].includes(parentWin.document.readyState)) {
                scheduleMove();
            } else {
                parentWin.document.addEventListener('DOMContentLoaded', scheduleMove, { once: true });
            }

            scheduleMove();

            // ========== 强制让设置 Popover 出现在按钮下方 ==========
            const repositionSettingsPopover = () => {
                const doc = parentWin.document;
                const btn = doc.querySelector('.st-key-hero-settings-btn [data-testid="stPopoverButton"]');
                const pop = doc.querySelector('[data-testid="stPopoverBody"]');
                if (!btn || !pop) return;
                const rect = btn.getBoundingClientRect();
                const vw = parentWin.innerWidth || doc.documentElement.clientWidth;
                const vh = parentWin.innerHeight || doc.documentElement.clientHeight;
                const desiredWidth = Math.max(rect.width, 420);
                const width = Math.min(desiredWidth, vw - 24);
                const left = Math.min(rect.left, vw - width - 12);
                const top = rect.bottom + 12;
                const maxHeight = Math.max(280, vh - top - 20);

                pop.style.position = 'fixed';
                pop.style.left = `${left}px`;
                pop.style.top = `${top}px`;
                pop.style.transform = 'none';
                pop.style.width = `${width}px`;
                pop.style.maxWidth = '92vw';
                pop.style.maxHeight = `${maxHeight}px`;
                pop.style.overflow = 'auto';
                pop.style.zIndex = 9999;
            };

            const attachPopoverReposition = () => {
                const doc = parentWin.document;
                const btn = doc.querySelector('.st-key-hero-settings-btn [data-testid="stPopoverButton"]');
                if (!btn) return;
                if (btn.__popoverRepositionBound) return;
                btn.__popoverRepositionBound = true;
                btn.addEventListener('click', () => {
                    setTimeout(repositionSettingsPopover, 30);
                    setTimeout(repositionSettingsPopover, 120);
                    setTimeout(repositionSettingsPopover, 260);
                });
            };

            const schedulePopoverHook = () => {
                setTimeout(attachPopoverReposition, 80);
                setTimeout(attachPopoverReposition, 300);
                setTimeout(attachPopoverReposition, 700);
            };

            if (['complete', 'interactive'].includes(parentWin.document.readyState)) {
                schedulePopoverHook();
            } else {
                parentWin.document.addEventListener('DOMContentLoaded', schedulePopoverHook, { once: true });
            }

            schedulePopoverHook();
        })();
        </script>
        """,
        height=0,
        width=0
    )

    # ========== Popover 设置面板（内嵌于 Hero 右上角） ==========
    module_count = len(selected_flow)
    # 简化标签，适合右上角显示
    popover_label = "设置"

    # 使用带 key 的 container，便于 CSS 定位到 hero 内部
    with st.container(key="hero-settings-btn"):
        with st.popover(popover_label, icon=":material/tune:"):
            # ========== STEP 01: 参数校准 ==========
            st.markdown("""
            <div class="popover-section">
                <div class="popover-section-header">
                    <div class="popover-section-icon" style="background: rgba(99, 102, 241, 0.2);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 5H3"/><path d="M12 19H3"/><path d="M14 3v4"/><path d="M16 17v4"/><path d="M21 12h-9"/><path d="M21 19h-5"/><path d="M21 5h-7"/><path d="M8 10v4"/><path d="M8 12H3"/></svg></div>
                    <div>
                        <p class="popover-section-title">STEP 01 · 参数校准</p>
                        <p class="popover-section-desc">设置每个模块处理的词量</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            batch_size = st.slider(
                "每模块词量",
                min_value=1,
                max_value=10,
                value=st.session_state.batch_size,
                key="batch_slider",
                help="设置每个模块的学习单词数量"
            )
            st.session_state.batch_size = batch_size
            st.session_state.learning_mode = 'batch'

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

            # ========== STEP 02: 模块编排 ==========
            st.markdown("""
            <div class="popover-section">
                <div class="popover-section-header">
                    <div class="popover-section-icon" style="background: rgba(34, 211, 238, 0.2);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15.39 4.39a1 1 0 0 0 1.68-.474 2.5 2.5 0 1 1 3.014 3.015 1 1 0 0 0-.474 1.68l1.683 1.682a2.414 2.414 0 0 1 0 3.414L19.61 15.39a1 1 0 0 1-1.68-.474 2.5 2.5 0 1 0-3.014 3.015 1 1 0 0 1 .474 1.68l-1.683 1.682a2.414 2.414 0 0 1-3.414 0L8.61 19.61a1 1 0 0 0-1.68.474 2.5 2.5 0 1 1-3.014-3.015 1 1 0 0 0 .474-1.68l-1.683-1.682a2.414 2.414 0 0 1 0-3.414L4.39 8.61a1 1 0 0 1 1.68.474 2.5 2.5 0 1 0 3.014-3.015 1 1 0 0 1-.474-1.68l1.683-1.682a2.414 2.414 0 0 1 3.414 0z"/></svg></div>
                    <div>
                        <p class="popover-section-title">STEP 02 · 模块编排</p>
                        <p class="popover-section-desc">选择学习模块，设计专属流程</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 可选模块列表
            st.markdown("<p style='font-size: 12px; color: #94A3B8; margin: 8px 0;'>点击添加模块到流程：</p>", unsafe_allow_html=True)

            for module in AVAILABLE_MODULES:
                accent_fill = hex_to_rgba(module['color'], 0.18)
                module_html = f"""
                <div class="popover-module-card">
                    <div class="popover-module-icon" style="background: {accent_fill};">{module['icon']}</div>
                    <div class="popover-module-info">
                        <p class="popover-module-name">{module['name']}</p>
                        <p class="popover-module-desc">{module['description']}</p>
                    </div>
                </div>
                """
                st.markdown(module_html, unsafe_allow_html=True)

                if st.button(
                    f"+ 添加 {module['name']}",
                    key=f"add_{module['id']}",
                    use_container_width=True,
                    type="tertiary"
                ):
                    st.session_state.module_order.append(module['id'])
                    if module['id'] not in st.session_state.selected_modules:
                        st.session_state.selected_modules.append(module['id'])
                    st.rerun()

            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

            # ========== STEP 03: 已选流程预览 ==========
            st.markdown("""
            <div class="popover-section">
                <div class="popover-section-header">
                    <div class="popover-section-icon" style="background: rgba(139, 92, 246, 0.2);"><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/></svg></div>
                    <div>
                        <p class="popover-section-title">STEP 03 · 当前流程</p>
                        <p class="popover-section-desc">调整顺序或移除模块</p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.session_state.module_order:
                # 显示已选模块的紧凑预览
                flow_items = []
                for idx, module_id in enumerate(st.session_state.module_order):
                    module_info = get_module_info(module_id)
                    if module_info:
                        flow_items.append(f"<span class='popover-flow-item'>{module_info['icon']} {module_info['name']}</span>")

                flow_preview_html = "<div class='popover-flow-preview'>" + "<span class='popover-flow-arrow'>→</span>".join(flow_items) + "</div>"
                st.markdown(flow_preview_html, unsafe_allow_html=True)

                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

                # 模块管理（移动/删除）
                for idx, module_id in enumerate(st.session_state.module_order):
                    module_info = get_module_info(module_id)
                    if not module_info:
                        continue

                    cols = st.columns([1, 3, 1, 1, 1], vertical_alignment="center")
                    with cols[0]:
                        st.markdown(f"<span class='popover-count-badge'>{idx + 1}</span>", unsafe_allow_html=True)
                    with cols[1]:
                        st.markdown(f"<span style='font-size: 13px;'>{module_info['icon']} {module_info['name']}</span>", unsafe_allow_html=True)
                    with cols[2]:
                        if idx > 0 and st.button("⬆", key=f"up_{idx}_{module_id}", help="上移", type="tertiary"):
                            st.session_state.module_order[idx], st.session_state.module_order[idx-1] = (
                                st.session_state.module_order[idx-1],
                                st.session_state.module_order[idx]
                            )
                            st.rerun()
                    with cols[3]:
                        if idx < len(st.session_state.module_order) - 1 and st.button("⬇", key=f"down_{idx}_{module_id}", help="下移", type="tertiary"):
                            st.session_state.module_order[idx], st.session_state.module_order[idx+1] = (
                                st.session_state.module_order[idx+1],
                                st.session_state.module_order[idx]
                            )
                            st.rerun()
                    with cols[4]:
                        if st.button("", key=f"del_{idx}_{module_id}", help="移除", type="tertiary", icon=":material/delete:"):
                            st.session_state.module_order.pop(idx)
                            if module_id not in st.session_state.module_order and module_id in st.session_state.selected_modules:
                                st.session_state.selected_modules.remove(module_id)
                            st.rerun()
            else:
                st.markdown("<div class='popover-flow-preview'><span class='popover-empty-hint'>还没有选择模块，从上方添加吧</span></div>", unsafe_allow_html=True)

            # 底部提示
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            if module_count > 0:
                st.success(f"已配置 {module_count} 个模块，每模块 {st.session_state.batch_size} 词，点击外部关闭此面板")
            else:
                st.info("请至少添加一个模块才能开始学习")

# ========== 导入模块化学习组件 ==========
from modular_learning_modules import (
    render_read_module,
    render_view_details_module,
    render_self_rating_module,
    render_agent_module
)

# ========== 批量学习状态变量 ==========
# 注意：FSRS 系统已在侧边栏之前早期初始化（第 1682-1686 行）
if 'batch_index' not in st.session_state:
    st.session_state.batch_index = 0

if 'module_index' not in st.session_state:
    st.session_state.module_index = 0

if 'word_index_in_batch' not in st.session_state:
    st.session_state.word_index_in_batch = 0

if 'learning_plan' not in st.session_state:
    st.session_state.learning_plan = []

if 'pronunciation' not in st.session_state:
    st.session_state.pronunciation = 'us'  # 默认美式发音

# 滚动计数器（用于触发滚动到页面顶部）
if 'scroll_counter' not in st.session_state:
    st.session_state.scroll_counter = 0

# AI内容检查标志（只在首次加载或刷新时检查）
if 'ai_content_checked' not in st.session_state:
    st.session_state.ai_content_checked = False

# 为今天的学习计划生成AI内容（只在首次加载或刷新时检查）
if not st.session_state.ai_content_checked:
    trigger_ai_generation_for_today()
    st.session_state.ai_content_checked = True

# 🔧 检查是否需要触发 AI 生成（由"下一个"按钮的 callback 设置）
# 这样耗时操作在主脚本中执行，不阻塞 callback，避免白屏
if st.session_state.get('need_trigger_ai_generation', False):
    st.session_state.need_trigger_ai_generation = False  # 重置标记
    # from_callback=True 跳过 st.rerun()，避免页面闪烁
    trigger_ai_generation_for_today(from_callback=True)

# ========== 辅助函数 ==========
def load_learning_plan():
    """加载今日学习计划"""
    try:
        system = st.session_state.fsrs_system

        # 获取当前选择的单词书
        current_book = get_current_wordbook()
        book_name = current_book['name'] if current_book else None

        # 获取需要复习的单词（按单词书过滤）
        due_words = system.get_due_words(user_id=user_id, book_name=book_name)

        # 获取新单词（至少30个，按单词书过滤）
        new_words = system.get_new_words(user_id=user_id, limit=30, book_name=book_name)

        # 合并学习计划
        learning_plan = due_words + new_words

        return learning_plan
    except Exception as e:
        st.error(f"""
        加载学习计划失败

        错误类型: {type(e).__name__}
        错误信息: {e}

        请检查数据库连接是否正常
        """)
        return []

def _mark_scroll_if_view_details():
    """仅在当前模块为词汇详解时，标记需要滚动到顶部。"""
    module_order = st.session_state.get('module_order') or []
    idx = st.session_state.get('module_index', 0)
    if 0 <= idx < len(module_order) and module_order[idx] == 'view_details':
        st.session_state.scroll_counter += 1

def go_next_word_or_module():
    """进入下一个单词或模块（批量模式）"""
    # 🔧 在 AI 互动模块点击"下一个"时，设置标记触发 AI 内容生成
    # 不在 callback 中执行耗时操作，避免白屏
    current_module = st.session_state.module_order[st.session_state.module_index]
    if current_module == 'agent_learning':
        # 只设置标记，实际触发在主脚本中执行（避免 callback 阻塞 UI）
        st.session_state.need_trigger_ai_generation = True

    _mark_scroll_if_view_details()
    st.session_state.word_index_in_batch += 1

    # 检查是否完成当前模块的批量学习
    if st.session_state.word_index_in_batch >= st.session_state.batch_size:
        # 重置单词索引，进入下一个模块
        st.session_state.word_index_in_batch = 0
        st.session_state.module_index += 1

        # 检查是否完成所有模块
        if st.session_state.module_index >= len(st.session_state.module_order):
            # 重置模块索引，进入下一批次
            st.session_state.module_index = 0
            st.session_state.batch_index += 1

            # 检查是否完成所有批次（无限循环）
            total_words = len(st.session_state.learning_plan)
            if st.session_state.batch_index * st.session_state.batch_size >= total_words:
                st.session_state.batch_index = 0  # 回到第一批次，无限循环
                st.balloons()
                st.success("恭喜完成一轮学习！现在开始新一轮循环...", icon=":material/celebration:")

def go_previous_word_or_module():
    """返回上一个单词或模块（批量模式）"""
    _mark_scroll_if_view_details()
    # 如果当前单词不是第一个，返回上一个单词
    if st.session_state.word_index_in_batch > 0:
        st.session_state.word_index_in_batch -= 1
    else:
        # 如果是当前模块的第一个单词，返回上一个模块的最后一个单词
        if st.session_state.module_index > 0:
            st.session_state.module_index -= 1
            st.session_state.word_index_in_batch = st.session_state.batch_size - 1
        else:
            # 如果是第一个模块，返回上一批次的最后一个模块的最后一个单词
            if st.session_state.batch_index > 0:
                st.session_state.batch_index -= 1
                st.session_state.module_index = len(st.session_state.module_order) - 1
                st.session_state.word_index_in_batch = st.session_state.batch_size - 1
              
def refresh_agent_question(current_idx):
    """刷新当前AI互动题目（重置随机题目相关的session_state key）"""
    key_patterns = [
        f"question_type_{current_idx}",
        f"random_sentence_{current_idx}",
        f"random_sentence_meaning_{current_idx}",
        f"random_translation_{current_idx}",
        f"random_fill_blank_{current_idx}",
        f"current_word_data_{current_idx}",
        f"answer_{current_idx}_",
        f"answer_sentence_{current_idx}_",
        f"answer_translation_{current_idx}_",
        f"answer_fill_blank_{current_idx}_",
        f"answer_visual_connection_{current_idx}"
    ]

    keys_to_delete = []

    for key in list(st.session_state.keys()):
        for pattern in key_patterns:
            if key == pattern or key.startswith(pattern):
                keys_to_delete.append(key)
                break

    for key in keys_to_delete:
        st.session_state.pop(key, None)

# ========== 学习界面 ==========
if st.session_state.learning_started:
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # 加载学习计划（如果还没加载）
    if not st.session_state.learning_plan:
        with st.spinner("正在加载今日学习计划..."):
            st.session_state.learning_plan = load_learning_plan()

    learning_plan = st.session_state.learning_plan

    if not learning_plan:
        st.warning("今天没有学习计划或数据加载失败", icon=":material/menu_book:")
        st.info("请检查数据库连接，或稍后重试", icon=":material/lightbulb:")
        if st.button("重新加载", icon=":material/refresh:"):
            st.session_state.learning_plan = []
            st.rerun()
        st.stop()

    # 计算当前单词索引
    actual_word_index = (
        st.session_state.batch_index * st.session_state.batch_size +
        st.session_state.word_index_in_batch
    )

    # 检查索引是否超出范围（无限循环时重置）
    if actual_word_index >= len(learning_plan):
        st.session_state.batch_index = 0
        st.session_state.module_index = 0
        st.session_state.word_index_in_batch = 0
        actual_word_index = 0

    word_info = learning_plan[actual_word_index]
    current_module_id = st.session_state.module_order[st.session_state.module_index]
    current_module_info = get_module_info(current_module_id)
    badge_hint = MODULE_BADGES.get(current_module_id, '模块')
    module_accent_bg = hex_to_rgba(current_module_info['color'], 0.18)
    module_accent_soft = hex_to_rgba(current_module_info['color'], 0.06)
    module_accent_border = hex_to_rgba(current_module_info['color'], 0.65)
    module_accent_shadow = hex_to_rgba(current_module_info['color'], 0.22)

    # 显示当前进度
    total_batches = (len(learning_plan) + st.session_state.batch_size - 1) // st.session_state.batch_size
    total_modules = len(st.session_state.module_order)

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(8,15,30,0.94), rgba(4,10,24,0.96));
        border-radius: 20px;
        padding: 26px 24px;
        margin: 24px 0;
        border: 1px solid rgba(255,255,255,0.06);
        box-shadow: 0 24px 60px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.04), 0 28px 65px {module_accent_shadow};
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(10px) saturate(120%);
    ">
        <div style="position:absolute; inset:0; background: radial-gradient(80% 80% at 12% 0%, {module_accent_bg}, transparent 52%), radial-gradient(50% 50% at 86% 10%, {module_accent_soft}, transparent 45%), linear-gradient(120deg, rgba(59,130,246,0.08), rgba(16,185,129,0.05)); opacity:0.9;"></div>
        <div style="position:absolute; inset:1px; border-radius: 18px; border: 1px solid rgba(255,255,255,0.05); pointer-events:none;"></div>
        <div style="position: relative; z-index: 1; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
            <div>
                <div style="display:flex; align-items:center; gap:12px; margin-bottom:6px;">
                    <span style="padding: 6px 12px; border-radius: 999px; border: 1px solid {module_accent_border}; font-size: 12px; letter-spacing: 0.08em; color: #e0f2fe; background: rgba(255,255,255,0.06); box-shadow: 0 0 0 1px rgba(255,255,255,0.04);">{badge_hint}</span>
                    <span style="color: {current_module_info.get('color', '#ffffff')}; font-size: 22px; opacity: 0.95;">{current_module_info['icon']}</span>
                </div>
                <h3 style="margin: 0 0 8px 0; color: #e5e7eb; font-size: 28px; letter-spacing: 0.03em; text-shadow: 0 2px 6px rgba(0,0,0,0.45);">
                    {current_module_info['name']}
                </h3>
                <p style="margin: 0; color: #cbd5e1; font-size: 14px;">
                    {current_module_info['description']}
                </p>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 14px; color: #cbd5e1; margin-bottom: 4px;">
                    批次 {st.session_state.batch_index + 1}/{total_batches} ·
                    模块 {st.session_state.module_index + 1}/{total_modules} ·
                    单词 {st.session_state.word_index_in_batch + 1}/{st.session_state.batch_size}
                </div>
                <div style="font-size: 22px; font-weight: 700; color: #f8fafc; text-shadow: 0 4px 10px rgba(0,0,0,0.35);">
                    {escape_html(word_info['word'])}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 生成唯一ID（用于避免组件冲突）
    # 🔧 包含 pronunciation，确保切换发音时强制重新渲染音频组件
    unique_id = f"batch{st.session_state.batch_index}_mod{st.session_state.module_index}_word{st.session_state.word_index_in_batch}_{st.session_state.pronunciation}"

    # 渲染对应模块
    st.markdown("---")

    if current_module_id == 'read_three_times':
        render_read_module(
            word_info=word_info,
            unique_id=unique_id,
            repeat_count=3,  # 可以改为可配置
            pronunciation=st.session_state.pronunciation,
            user_id=user_id,
            fastapi_url=fastapi_url
        )

    elif current_module_id == 'view_details':
        render_view_details_module(
            word_info=word_info,
            unique_id=unique_id,
            pronunciation=st.session_state.pronunciation,
            user_id=user_id,
            fastapi_url=fastapi_url
        )

    elif current_module_id == 'self_rating':
        render_self_rating_module(
            word_info=word_info,
            current_index=actual_word_index,
            fsrs_system=st.session_state.fsrs_system,
            unique_id=unique_id,
            pronunciation=st.session_state.pronunciation,
            user_id=user_id,
            fastapi_url=fastapi_url
        )

    elif current_module_id == 'agent_learning':
        # 清空按钮配置（避免累积导致警告）
        import time
        print(f"[fsrs_modular_learning] 🧹 清空 ai_button_configs，时间: {time.time():.3f}")
        st.session_state.ai_button_configs = []

        # 轻量工具条：左侧提示，右侧“换一题”，与内容融为一行
        tool_cols = st.columns([7, 3])
        with tool_cols[0]:
            st.markdown("""
            <div class="agent-toolbar-note">
                <div class="title">互动工具</div>
                <div>题目不合适？一键换一题试试。</div>
            </div>
            """, unsafe_allow_html=True)
        with tool_cols[1]:
            st.button(
                "换一题",
                icon=":material/refresh:",
                on_click=refresh_agent_question,
                args=(actual_word_index,),
                use_container_width=True,
                type="secondary",
                key="refresh_question_btn",
                help="重新随机生成一道题目"
            )

        render_agent_module(
            word_info=word_info,
            current_index=actual_word_index
        )


    # 导航按钮
    st.markdown("---")

    # 自定义按钮样式
    st.markdown("""
    <style>
    /* 下一个按钮样式 - 排除评分按钮和换一题按钮 */
    div[data-testid="stHorizontalBlock"]:not(:has([class*="st-key-rating_"])):not(:has([class*="st-key-refresh_question_btn"])) button {
        height: 64px !important;
        font-size: 19px !important;
        font-weight: 600 !important;
        border-radius: 16px !important;
        border: none !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        background: linear-gradient(135deg, #22d3ee 0%, #38bdf8 45%, #f59e0b 100%) !important;
        color: #0b1220 !important;
        text-shadow: 0 1px 0 rgba(255,255,255,0.25) !important;
    }

    div[data-testid="stHorizontalBlock"]:not(:has([class*="st-key-rating_"])):not(:has([class*="st-key-refresh_question_btn"])) button:hover:not(:disabled) {
        transform: translateY(-3px) !important;
        box-shadow: 0 10px 30px rgba(34, 211, 238, 0.35), 0 14px 32px rgba(0,0,0,0.35) !important;
    }

    div[data-testid="stHorizontalBlock"]:not(:has([class*="st-key-rating_"])):not(:has([class*="st-key-refresh_question_btn"])) button:active:not(:disabled) {
        transform: translateY(-1px) !important;
    }

    div[data-testid="stHorizontalBlock"]:not(:has([class*="st-key-rating_"])):not(:has([class*="st-key-refresh_question_btn"])) button:disabled {
        background: linear-gradient(135deg, #e5e7eb 0%, #d1d5db 100%) !important;
        opacity: 0.4 !important;
        cursor: not-allowed !important;
        box-shadow: none !important;
    }

    /* ========== 评分按钮样式（统一紫蓝青渐变风格） ========== */
    [class*="st-key-rating_"] button {
        height: 64px !important;
        font-size: 17px !important;
        font-weight: 600 !important;
        border-radius: 16px !important;
        border: none !important;
        color: #ffffff !important;
        text-shadow: 0 1px 2px rgba(0,0,0,0.2) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    [class*="st-key-rating_"] button:hover:not(:disabled) {
        transform: translateY(-3px) !important;
    }

    [class*="st-key-rating_"] button:active:not(:disabled) {
        transform: translateY(-1px) !important;
    }

    /* 忘记按钮 - 深琥珀（柔和版，适配暗色背景） */
    [class*="st-key-rating_1"] button {
        background: linear-gradient(135deg, #6f4a2d 0%, #885a33 100%) !important;
        color: #f6efe6 !important;
        box-shadow: 0 4px 14px rgba(111, 74, 45, 0.28) !important;
    }
    [class*="st-key-rating_1"] button:hover:not(:disabled) {
        box-shadow: 0 8px 22px rgba(111, 74, 45, 0.45) !important;
    }

    /* 困难按钮 - 中琥珀（柔和版） */
    [class*="st-key-rating_2"] button {
        background: linear-gradient(135deg, #885a33 0%, #a06a3a 100%) !important;
        color: #f8f1e8 !important;
        box-shadow: 0 4px 14px rgba(136, 90, 51, 0.28) !important;
    }
    [class*="st-key-rating_2"] button:hover:not(:disabled) {
        box-shadow: 0 8px 22px rgba(136, 90, 51, 0.45) !important;
    }

    /* 记得按钮 - 浅琥珀（柔和版） */
    [class*="st-key-rating_3"] button {
        background: linear-gradient(135deg, #a06a3a 0%, #b98245 100%) !important;
        color: #3a2412 !important;
        box-shadow: 0 4px 14px rgba(160, 106, 58, 0.26) !important;
    }
    [class*="st-key-rating_3"] button:hover:not(:disabled) {
        box-shadow: 0 8px 22px rgba(160, 106, 58, 0.42) !important;
    }

    /* 简单按钮 - 亮琥珀（柔和版） */
    [class*="st-key-rating_4"] button {
        background: linear-gradient(135deg, #b98245 0%, #d1a05c 100%) !important;
        color: #3a2412 !important;
        box-shadow: 0 4px 14px rgba(185, 130, 69, 0.26) !important;
    }
    [class*="st-key-rating_4"] button:hover:not(:disabled) {
        box-shadow: 0 8px 22px rgba(185, 130, 69, 0.42) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 只在非朗读模块、非词汇详解、非AI互动模块、非记忆评估模块显示"下一个"按钮（这些模块都用悬浮按钮）
    if current_module_id not in ['read_three_times', 'view_details', 'agent_learning', 'self_rating']:
        st.button(
            "下一个",
            on_click=go_next_word_or_module,
            use_container_width=True,
            type="primary",
            icon=":material/chevron_right:",
            help=f"进入下一个单词或模块"
        )

    # ========== 隐藏的导航按钮（用于悬浮按钮触发） ==========
    # 判断是否是第一个或最后一个单词
    is_first = (st.session_state.batch_index == 0 and
                st.session_state.module_index == 0 and
                st.session_state.word_index_in_batch == 0)

    is_last = False
    if st.session_state.learning_plan:
        total_words = len(st.session_state.learning_plan)
        total_batches = (total_words + st.session_state.batch_size - 1) // st.session_state.batch_size
        is_last = (st.session_state.batch_index >= total_batches - 1 and
                   st.session_state.module_index >= len(st.session_state.module_order) - 1 and
                   st.session_state.word_index_in_batch >= st.session_state.batch_size - 1)

    # 创建隐藏的按钮（使用 JavaScript 在客户端隐藏）
    col_left, col_middle, col_right = st.columns([1, 2, 1])

    with col_left:
        # 隐藏的"上一个"按钮
        st.button(
            "上一个",
            on_click=go_previous_word_or_module,
            icon=":material/chevron_left:",
            key="hidden_prev_button_modular",
            disabled=is_first,
            use_container_width=True
        )

    with col_right:
        # 隐藏的"下一个"按钮
        st.button(
            "下一个",
            on_click=go_next_word_or_module,
            icon=":material/chevron_right:",
            key="hidden_next_button_modular",
            disabled=is_last,
            use_container_width=True
        )

    # 使用 JavaScript 强制隐藏这些按钮
    components.html("""
    <script>
    (function() {
        // 获取父页面document
        let W = window;
        let D = document;

        try {
            if (window.parent && window.parent !== window) {
                W = window.parent;
                D = W.document;
            }
        } catch (e) {
            return;
        }

        // 查找并隐藏包含"上一个"和"下一个"文本的按钮（非悬浮按钮）
        function hideNavigationButtons() {
            const buttons = D.querySelectorAll('button');
            buttons.forEach((btn) => {
                const text = btn.textContent || '';
                // 只隐藏包含箭头的按钮（悬浮按钮在div中，不是button元素）
                if (text.includes('上一个') || text.includes('下一个')) {
                    // 找到按钮的父容器（stColumn）
                    let parent = btn.closest('[data-testid="stColumn"]');
                    if (parent) {
                        parent.style.display = 'none';
                        parent.style.visibility = 'hidden';
                        parent.style.height = '0';
                    }
                }
            });
        }

        // 立即执行一次
        hideNavigationButtons();

        // 监听 DOM 变化（防止 Streamlit 重新渲染后按钮又出现）
        const observer = new MutationObserver(() => {
            hideNavigationButtons();
        });

        observer.observe(D.body, {
            childList: true,
            subtree: true
        });
    })();
    </script>
    """, height=0)

    # ========== 悬浮导航按钮（左下角 + 右下角） ==========
    # 注入悬浮按钮HTML和CSS
    st.markdown("""
    <style>
    /* 悬浮按钮基础样式 */
    .floating-nav-button {
        position: fixed;
        bottom: 92px;
        z-index: 998;   /* 低于聊天图标(999) */
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        min-width: 180px;
        width: 180px;
        padding: 12px 16px;
        background: linear-gradient(145deg, rgba(8,15,30,0.9), rgba(12,18,36,0.9));
        color: #e2e8f0;
        border-radius: 16px;
        border: 1px solid rgba(94,234,212,0.4);
        box-shadow: 0 16px 42px rgba(0,0,0,0.45), 0 0 0 1px rgba(255,255,255,0.05), 0 12px 34px rgba(59,130,246,0.16);
        cursor: pointer;
        font-size: 16px;
        font-weight: 700;
        letter-spacing: 0.02em;
        user-select: none;
        backdrop-filter: blur(12px) saturate(130%);
        transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease, background 0.25s ease;
        isolation: isolate;
        overflow: hidden;
        box-sizing: border-box;
    }

    .floating-nav-button::after {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: 16px;
        background: linear-gradient(145deg, rgba(56,189,248,0.18), rgba(16,185,129,0.18), rgba(236,72,153,0.16));
        opacity: 0;
        transition: opacity 0.25s ease;
        z-index: 0;
    }

    .floating-nav-button:hover {
        transform: translateY(-3px) scale(1.01);
        box-shadow: 0 20px 50px rgba(45, 212, 191, 0.25), 0 18px 38px rgba(59,130,246,0.2), 0 16px 34px rgba(0,0,0,0.55);
        border-color: rgba(94, 234, 212, 0.65);
        background: linear-gradient(135deg, rgba(59,130,246,0.14), rgba(34,211,238,0.12), rgba(8,47,73,0.92));
    }

    .floating-nav-button:hover::after {
        opacity: 1;
    }

    .floating-nav-button:active {
        transform: translateY(-1px);
    }

    .floating-icon {
        width: 40px;
        height: 40px;
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(56,189,248,0.3), rgba(59,130,246,0.25));
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        color: #f8fafc;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
        z-index: 1;
    }

    .floating-copy {
        display: flex;
        flex-direction: column;
        gap: 0;
        z-index: 1;
    }

    .floating-title {
        color: #f8fafc;
        font-size: 16px;
        line-height: 1.2;
    }

    /* 上一个按钮（左下角，需要适应侧边栏） */
    #floating-prev-button {
        left: 24px;  /* 初始位置，JavaScript会根据侧边栏状态调整 */
    }

    /* 下一个按钮（右下角） */
    #floating-next-button {
        right: 24px;
    }

    @media (max-width: 900px) {
        .floating-nav-button {
            min-width: 0;
            width: auto;
            padding: 12px 14px;
            gap: 8px;
            bottom: 86px;
        }

    }
    </style>
    """, unsafe_allow_html=True)

    # 注入JavaScript（动态创建悬浮按钮、处理点击事件和侧边栏自适应）
    components.html(f"""
    <script>
    (function() {{
        console.log('[FloatingNav] 🔄 JavaScript开始执行');

        // 获取父页面document
        let W = window;
        let D = document;
        let PARENT_OK = false;

        try {{
            if (window.parent && window.parent !== window) {{
                void window.parent.document;
                W = window.parent;
                D = W.document;
                PARENT_OK = true;
                console.log('[FloatingNav] ✅ 成功访问父页面document');
            }}
        }} catch (e) {{
            console.log('[FloatingNav] ❌ 无法访问父页面: ' + e.message);
            return;
        }}

        if (!PARENT_OK) return;

        // ========== 0. 创建/更新悬浮按钮（插入到父页面body） ==========
        const IS_FIRST_WORD = {str(is_first).lower()};
        const IS_LAST_WORD = {str(is_last).lower()};

        const buildButtonContent = (isPrev) => (
            '<span class="floating-icon">' + (isPrev ? '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>' : '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>') + '</span>' +
            '<span class="floating-copy">' +
                '<span class="floating-title">' + (isPrev ? '上一个' : '下一个') + '</span>' +
            '</span>'
        );

        // 统一处理：如需存在则创建或重绘内容，避免复用旧页面残留的简易版本
        function ensureNavButton(id, isPrev, shouldExist) {{
            let btn = D.getElementById(id);
            if (!shouldExist) {{
                if (btn) {{
                    btn.remove();
                    console.log('[FloatingNav] 🗑️ 已移除按钮:', id);
                }}
                return null;
            }}

            if (!btn) {{
                btn = D.createElement('div');
                btn.id = id;
                D.body.appendChild(btn);
                console.log('[FloatingNav] ✅ 按钮已创建:', id);
            }}

            // 重置样式与内容，确保跨页面一致
            btn.className = 'floating-nav-button';
            btn.innerHTML = buildButtonContent(isPrev);
            return btn;
        }}

        const prevBtn = ensureNavButton('floating-prev-button', true, !IS_FIRST_WORD);
        const nextBtn = ensureNavButton('floating-next-button', false, !IS_LAST_WORD);

        // ========== 1. 侧边栏自适应位置调整 ==========
        const SIDEBAR_WIDTH = 256;
        const MARGIN = 24;

        function updatePrevButtonPosition() {{
            const sidebar = D.querySelector('[data-testid="stSidebar"]');
            if (!sidebar) {{
                console.log('[FloatingNav] ⚠️ 未找到侧边栏元素');
                return;
            }}

            const isExpanded = sidebar.getAttribute('aria-expanded') === 'true';
            const newLeft = isExpanded ? (SIDEBAR_WIDTH + MARGIN) + 'px' : MARGIN + 'px';

            const prevBtn = D.getElementById('floating-prev-button');
            if (prevBtn) {{
                prevBtn.style.left = newLeft;
                console.log('[FloatingNav] 📍 更新上一个按钮位置: ' + newLeft);
            }}
        }}

        // 监听侧边栏状态变化
        const sidebar = D.querySelector('[data-testid="stSidebar"]');
        if (sidebar) {{
            const sidebarObserver = new MutationObserver((mutations) => {{
                mutations.forEach((mutation) => {{
                    if (mutation.type === 'attributes' && mutation.attributeName === 'aria-expanded') {{
                        console.log('[FloatingNav] 🔄 检测到侧边栏状态变化');
                        updatePrevButtonPosition();
                    }}
                }});
            }});

            sidebarObserver.observe(sidebar, {{
                attributes: true,
                attributeFilter: ['aria-expanded']
            }});

            // 初始化位置
            updatePrevButtonPosition();
            console.log('[FloatingNav] ✅ 侧边栏监听器已安装');
        }}

        // ========== 2. 点击事件处理 ==========
        if (prevBtn) {{
            prevBtn.onclick = function() {{
                console.log('[FloatingNav] 🖱️ 上一个按钮被点击');

                // 查找隐藏的Streamlit按钮并触发点击
                const buttons = D.querySelectorAll('button');
                for (let btn of buttons) {{
                    if (btn.textContent && btn.textContent.includes('上一个')) {{
                        console.log('[FloatingNav] ✅ 找到隐藏按钮，触发点击');
                        btn.click();
                        break;
                    }}
                }}
            }};
            console.log('[FloatingNav] ✅ 上一个按钮事件已绑定');
        }}

        if (nextBtn) {{
            nextBtn.onclick = function() {{
                console.log('[FloatingNav] 🖱️ 下一个按钮被点击');

                // 查找隐藏的Streamlit按钮并触发点击
                const buttons = D.querySelectorAll('button');
                for (let btn of buttons) {{
                    if (btn.textContent && btn.textContent.includes('下一个')) {{
                        console.log('[FloatingNav] ✅ 找到隐藏按钮，触发点击');
                        btn.click();
                        break;
                    }}
                }}
            }};
            console.log('[FloatingNav] ✅ 下一个按钮事件已绑定');
        }}

        console.log('[FloatingNav] 🎉 初始化完成');
    }})();
    </script>
    """, height=0)

# ========== 文本选择播放、翻译和AI聊天组件 ==========
# TTS 配置（如果有 API Key）
# TTS 组件（使用后端代理，不再需要前端 API Key）
channel = "tts-modular-learning-channel"
iframe_height = 0

# 获取 JWT token（用于 Selector 和 Player 组件）
jwt_token = get_jwt_token(user_id)

# 渲染文本选择监听器（提供播放和翻译按钮）
mount_floating_selector(
    channel=channel,
    debug=True,  # 🔍 临时开启诊断
    height=iframe_height,
    show_status=False,
    jwt_token=jwt_token,
    fastapi_url=fastapi_url,
    pronunciation=st.session_state.pronunciation  # 传递发音偏好
)

# 渲染 TTS 播放器（使用后端 TTS API）
render_player(
    api_url=f"{fastapi_url}/api/tts",
    jwt_token=jwt_token,
    cache_size=15,
    channel=channel,
    height=iframe_height,
    enable_postmessage=True,
    show_demo_content=False,
    pronunciation=st.session_state.pronunciation  # 传递发音偏好
)

# 翻译选择器（无条件渲染，避免组件不重新挂载导致事件监听器丢失）
mount_translate_selector(
    channel="translate-chat-modular",
    debug=False,
    height=0
)

# AI聊天组件（只有 FastAPI 服务器运行中才渲染）
if fastapi_status == "🟢 运行中":
    # 🤖 AI反馈按钮管理器（在页面底部挂载，读取 session_state 中的按钮配置）
    mount_ai_feedback_button_manager(
        channel="translate-chat",
        debug=True,  # 🔍 临时开启诊断
        height=0
    )

    # AI聊天对话框（FastAPI版本）
    # 🔥 检查是否需要自动打开对话框
    auto_open = st.session_state.get('_auto_open_dialog', False)

    # 签发 JWT（每次 rerun 重新签发，1小时过期）
    jwt_token = get_jwt_token(user_id)
    render_floating_chat_fastapi(
        jwt_token=jwt_token,
        session_id=st.session_state.chat_session_id,
        api_url=f"{fastapi_url}/api/chat",
        height=0,
        debug=True,  # 🔍 临时开启调试模式，定位 iOS 对话框问题后改回 False
        auto_open_dialog=auto_open
    )

    # 清除自动打开标志
    if auto_open:
        st.session_state._auto_open_dialog = False

# ========== 滚动到顶部功能 ==========
# 在点击上一个/下一个后自动滚动到页面顶部
if st.session_state.scroll_counter > 0:
    components.html(f"""
        <script>
        const stMain = window.parent.document.querySelector('[data-testid="stMain"]');
        if (stMain) {{
            stMain.scrollTo({{
                top: 0,
                behavior: 'smooth'
            }});
            console.log('✅ 滚动到顶部 - 第{st.session_state.scroll_counter}次');
        }}
        </script>
    """, height=0)
