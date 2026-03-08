#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模块化学习组件库
=================

为 Agent 模块化学习系统提供独立的学习模块函数。
每个函数负责渲染一个特定的学习模块。

包含模块：
1. render_read_module - 朗读练习（自动播放N次）
2. render_view_details_module - 词汇详解（完整信息展示）
3. render_self_rating_module - 记忆评估（FSRS评分）
4. render_agent_module - AI互动（场景学习）
"""

import os
import sys
import time
import base64
import requests
import streamlit as st
import streamlit.components.v1 as components
from decimal import Decimal

# 导入场景渲染器
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, 'scene_learning'))
from scene_learning.interactive_scene_renderer import render_scene_with_toggle

# 服务费率（从环境变量读取，默认 30%）
SERVICE_FEE_RATE = Decimal(os.getenv("SERVICE_FEE_RATE", "0.30"))


# ========== 模块1：朗读练习 ==========
def render_read_module(word_info, unique_id, repeat_count=3, pronunciation='us', user_id=None, fastapi_url=None):
    """
    朗读练习模块

    功能：
    - 显示单词标题 + 音频播放器
    - 显示中文释义（始终展开）
    - 自动播放音频 N 次
    - 播放完成后自动触发"下一个"按钮

    参数：
        word_info: 单词信息字典
        unique_id: 唯一ID（用于避免组件冲突）
        repeat_count: 朗读次数（默认3次）
        pronunciation: 发音类型 ('us' 或 'uk')
        user_id: 用户ID（用于 OpenAI TTS 认证）
        fastapi_url: FastAPI 服务器地址
    """
    word_value = word_info['word']
    translation = word_info.get('translation', '')

    # ========== 异步「重新生成」任务进度（跨单词可见） ==========
    if user_id:
        _ensure_regen_state(user_id, fastapi_url)
        render_regen_task_center()


    # 检查本地音频缓存（使用项目目录下的 audio 文件夹，与 fsrs_loop.py 一致）
    audio_dir = os.path.join(project_root, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    # 清理特殊字符（与 batch_download_tts.py 保持一致）
    safe_word = word_value.lower().replace("/", "_")
    possible_files = [
        os.path.join(audio_dir, f"{safe_word}_{pronunciation}_openai.mp3")
    ]

    cached_file = None
    for file_path in possible_files:
        if os.path.exists(file_path):
            cached_file = file_path
            break

    # 生成音频源
    has_cache = False
    if cached_file:
        with open(cached_file, 'rb') as audio_file:
            audio_bytes = audio_file.read()
            audio_base64 = base64.b64encode(audio_bytes).decode()
        audio_source = f"data:audio/mp3;base64,{audio_base64}"
        has_cache = True
    else:
        # 使用 OpenAI TTS GET URL（通过 Cookie 认证，点击播放时才请求）
        if user_id:
            from urllib.parse import quote
            word_encoded = quote(word_value, safe='')
            audio_source = f"{fastapi_url}/api/tts/word/{word_encoded}/{pronunciation}"
        else:
            # 未登录时无音频
            audio_source = ""

    online_hint = "" if has_cache else '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg> 在线音频'

    # 单词卡片 HTML
    # 🔧 iOS Safari 兼容：不再创建 <audio> 元素，改为 slot，由 JS 将全局复用的 audio 元素挂载进来
    word_id = f"word-{word_value.lower().replace(' ', '-')}"
    word_audio_html = f"""
    <style>
        .word-container-{unique_id} {{
            text-align: center;
            margin-bottom: 10px;
            padding: 10px 20px;
        }}
        .audio-container-{unique_id} {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-top: 12px;
        }}
        #fsrs_read_unlock_btn {{
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
            transition: all 0.2s ease;
        }}
        #fsrs_read_unlock_btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5);
        }}
        #fsrs_read_unlock_btn:active {{
            transform: translateY(0);
        }}
    </style>
    <div id="{word_id}" class="word-container-{unique_id}">
        <div class="word-title" style="margin-bottom: 12px; font-size: 48px; font-weight: 800; color: #e2e8f0; text-shadow: 0 3px 10px rgba(0,0,0,0.35); letter-spacing: 0.01em;">{word_value}</div>
        <div id="fsrs_read_audio_slot" class="audio-container-{unique_id}">
            <!-- 全局复用的 audio 元素会被 JS 挂载到这里 -->
            <span style="color: #a5b4fc; font-size: 0.78em; font-style: italic;">{online_hint}</span>
        </div>
    </div>
    """
    st.markdown(word_audio_html, unsafe_allow_html=True)

    # 传统单词书的中文释义（始终展开显示）
    if translation:
        translations = translation.split('\n')
        translation_items = ""
        for trans in translations:
            if trans.strip():
                translation_items += f"<div style='margin: 8px 0; font-size: 16px; color: #e2e8f0; line-height: 1.55;'>• {trans.strip()}</div>"

        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(76,29,149,0.25), rgba(14,116,144,0.28), rgba(14,165,233,0.18));
            border: 1px solid rgba(125,211,252,0.32);
            border-left: 4px solid #5eead4;
            padding: 24px 28px;
            margin: 20px auto;
            max-width: 900px;
            border-radius: 16px;
            box-shadow: 0 18px 38px rgba(0,0,0,0.35);
            backdrop-filter: blur(8px);
        ">
            <h4 style="margin: 0 0 16px 0; color: #e0f2fe; font-size: 20px; font-weight: 700;"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg> 中文释义</h4>
            {translation_items}
        </div>
        """, unsafe_allow_html=True)

    # ========== iOS Safari 兼容：全局复用 audio 元素 ==========
    # 核心原理（WebKit 官方推荐）：
    # 1. 自动播放授权是 per-element 的
    # 2. 复用同一个 audio 元素，只换 src，授权不会丢失
    # 3. 把 audio 元素放在 parent document body 下，Streamlit rerun 时不会被销毁
    components.html(f"""
    <script>
    (function() {{
        console.log('[AutoPlay] 🔄 开始自动播放逻辑（iOS 兼容版）');

        const parentDoc = window.parent.document;

        // ========== 固定 ID：确保 audio 元素跨单词复用 ==========
        const AUDIO_ID = 'fsrs_read_audio_el';       // 全局唯一的 audio 元素
        const HOST_ID = 'fsrs_read_audio_host';      // 放在 body 下的隐藏容器（Streamlit 管不到）
        const SLOT_ID = 'fsrs_read_audio_slot';      // 每个单词卡片里的挂载点

        const audioSrc = '{audio_source}';
        const maxPlays = {repeat_count};
        const session = '{unique_id}';  // 用于防止旧事件串台

        // ========== 1. 创建/获取 host 容器（Streamlit rerun 时不会被销毁） ==========
        let host = parentDoc.getElementById(HOST_ID);
        if (!host) {{
            host = parentDoc.createElement('div');
            host.id = HOST_ID;
            host.style.cssText = 'position: fixed; left: -9999px; top: 0; pointer-events: none;';
            parentDoc.body.appendChild(host);
            console.log('[AutoPlay] 📦 创建 host 容器');
        }}

        // ========== 2. 创建/获取全局复用的 audio 元素 ==========
        let audio = parentDoc.getElementById(AUDIO_ID);
        if (!audio) {{
            audio = parentDoc.createElement('audio');
            audio.id = AUDIO_ID;
            audio.controls = true;
            audio.preload = 'auto';
            audio.style.cssText = 'min-width: 250px;';
            host.appendChild(audio);
            console.log('[AutoPlay] 🎵 创建全局 audio 元素');
        }}

        // ========== 3. 把 audio 元素挂载到当前单词卡片的 slot ==========
        const slot = parentDoc.getElementById(SLOT_ID);
        if (slot) {{
            // 插入到 slot 的最前面（在提示文字之前）
            if (audio.parentElement !== slot) {{
                slot.insertBefore(audio, slot.firstChild);
                console.log('[AutoPlay] 📍 audio 元素已挂载到 slot');
            }}
        }} else {{
            console.warn('[AutoPlay] ⚠️ 找不到 slot');
        }}

        // ========== 4. 重置状态 + 换源（元素实例不变，授权保留） ==========
        audio.pause();
        audio.currentTime = 0;
        audio.dataset.fsrsSession = session;
        audio.src = audioSrc;

        let playCount = 0;
        let started = false;

        // ========== 5. 关键：触发 rerun 之前把 audio 移回 host ==========
        function parkAudioToHost() {{
            if (audio.parentElement !== host) {{
                host.appendChild(audio);
                console.log('[AutoPlay] 🏠 audio 已移回 host（避免被 Streamlit 销毁）');
            }}
        }}

        // ========== 6. 查找并点击"下一个"按钮 ==========
        function clickNext() {{
            // 优先查找 hidden_next_button_modular
            const nextBtn =
                parentDoc.querySelector('[class*="st-key-hidden_next_button_modular"] button') ||
                Array.from(parentDoc.querySelectorAll('button')).find(
                    b => b.textContent && b.textContent.includes('下一个')
                );

            if (nextBtn) {{
                console.log('[AutoPlay] 🖱️ 找到下一个按钮，准备点击');
                nextBtn.click();
                console.log('[AutoPlay] ✅ 已触发点击');
            }} else {{
                console.warn('[AutoPlay] ⚠️ 未找到下一个按钮');
            }}
        }}

        // ========== 7. 安全播放（捕获 NotAllowedError） ==========
        async function safePlay() {{
            try {{
                await audio.play();
                console.log('[AutoPlay] ✅ 播放成功');
                // 移除解锁按钮（如果存在）
                const unlockBtn = parentDoc.getElementById('fsrs_read_unlock_btn');
                if (unlockBtn) unlockBtn.remove();
                return true;
            }} catch (err) {{
                console.warn('[AutoPlay] ⚠️ 播放被阻止:', err.message);
                ensureUnlockButton();
                return false;
            }}
        }}

        // ========== 8. iOS 解锁按钮（仅在自动播放被阻止时显示） ==========
        function ensureUnlockButton() {{
            const slot = parentDoc.getElementById(SLOT_ID);
            if (!slot) return;

            let btn = parentDoc.getElementById('fsrs_read_unlock_btn');
            if (!btn) {{
                btn = parentDoc.createElement('button');
                btn.id = 'fsrs_read_unlock_btn';
                btn.textContent = '▶️ 点击继续朗读';
                btn.onclick = async () => {{
                    const ok = await safePlay();
                    if (ok) btn.remove();
                }};
                slot.appendChild(btn);
                console.log('[AutoPlay] 🔓 已添加解锁按钮');
            }}
        }}

        // ========== 9. 首次启动（只执行一次） ==========
        async function startOnce() {{
            if (started) return;
            started = true;
            await safePlay();
        }}

        // ========== 10. 播放结束事件（使用 onended 覆盖，避免多次 addEventListener 堆叠） ==========
        audio.onended = async () => {{
            // 防止旧 session 的事件串台
            if (audio.dataset.fsrsSession !== session) return;

            playCount++;
            console.log('[AutoPlay] 🎵 播放完成，当前次数: ' + playCount + '/' + maxPlays);

            if (playCount < maxPlays) {{
                console.log('[AutoPlay] ▶️ 准备播放第 ' + (playCount + 1) + ' 次');
                await safePlay();
            }} else {{
                console.log('[AutoPlay] ✅ 播放完成' + maxPlays + '次，准备进入下一个单词');
                parkAudioToHost();  // 关键：先移回 host
                clickNext();        // 再触发 rerun
            }}
        }};

        // ========== 11. 音频加载完成后启动 ==========
        audio.oncanplay = async () => {{
            if (audio.dataset.fsrsSession !== session) return;
            audio.oncanplay = null;  // 只触发一次
            await startOnce();
        }};

        // ========== 12. iOS Safari 需要显式 load() ==========
        console.log('[AutoPlay] 📱 readyState:', audio.readyState, '，调用 load()');
        audio.load();

        // 如果已经 ready，也启动一次（加保险）
        if (audio.readyState >= 3) {{
            startOnce();
        }}
    }})();
    </script>
    """, height=0)


# ========== 辅助函数：重新生成 AI 内容 ==========
def _call_regenerate_api(word: str, content_type: str, user_id: str, feedback: str = None, current_content: str = None):
    """
    纯 API 调用函数（不包含 UI 逻辑）
    
    返回：
        (response, error_message) - response 对象或 None，error_message 或 None
    """
    from utils.auth_helper import get_jwt_token
    
    API_BASE_URL = os.getenv("FASTAPI_URL")
    
    try:
        jwt_token = get_jwt_token(user_id)
        response = requests.post(
            f"{API_BASE_URL}/api/ai/regenerate",
            json={
                "word": word, 
                "content_type": content_type,
                "feedback": feedback if feedback and feedback.strip() else None,
                "current_content": current_content
            },
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=1980  # 33分钟，大于计费预留过期(32分钟)
        )
        return response, None
    except requests.exceptions.Timeout:
        return None, "请求超时，请稍后重试"
    except Exception as e:
        return None, f"网络错误：{e}"




# ========== 重新生成任务（异步轮询 + 跨单词进度提示）==========
# 目标：
# 1) 用户在单词 A 点“重新生成”，切到单词 B 时仍能看到 A 的生成进度
# 2) 生成完成后回到 A 能直接看到新内容（不需要整页刷新）
#
# 方案：
# - 前端点击“重新生成”时，不再同步等待 /api/ai/regenerate 返回（避免被切词打断）
# - 改为调用 /api/ai/regenerate_task（快速返回 task_id）
# - 用 st.fragment(run_every=...) 做轻量轮询，展示任务状态，并在完成后把内容写回 st.session_state.learning_plan

_REGEN_TASKS_KEY = "ml_regen_tasks"          # task_id -> task dict
_REGEN_INDEX_KEY = "ml_regen_task_index"    # f"{word}::{content_type}" -> task_id
_REGEN_META_KEY = "ml_regen_meta"           # {"user_id":..., "base_url":...}


def _normalize_base_url(fastapi_url: str) -> str:
    base = fastapi_url or os.getenv("FASTAPI_URL")
    return base.rstrip("/")


def _regen_task_key(word: str, content_type: str) -> str:
    return f"{word}::{content_type}"


def _ensure_regen_state(user_id: str, fastapi_url: str) -> None:
    if _REGEN_TASKS_KEY not in st.session_state:
        st.session_state[_REGEN_TASKS_KEY] = {}
    if _REGEN_INDEX_KEY not in st.session_state:
        st.session_state[_REGEN_INDEX_KEY] = {}
    st.session_state[_REGEN_META_KEY] = {
        "user_id": user_id,
        "base_url": _normalize_base_url(fastapi_url),
    }


def _register_regen_task(task_id: str, word: str, content_type: str) -> None:
    tasks = st.session_state.get(_REGEN_TASKS_KEY, {})
    index = st.session_state.get(_REGEN_INDEX_KEY, {})

    tasks[task_id] = {
        "task_id": task_id,
        "word": word,
        "content_type": content_type,
        "status": "queued",
        "created_at": time.time(),
        "updated_at": time.time(),
        "applied": False,
        "notified": False,
        "error": None,
        "cost_usd": None,
        "content": None,
    }
    index[_regen_task_key(word, content_type)] = task_id

    st.session_state[_REGEN_TASKS_KEY] = tasks
    st.session_state[_REGEN_INDEX_KEY] = index


def _get_latest_regen_task(word: str, content_type: str) -> dict:
    index = st.session_state.get(_REGEN_INDEX_KEY, {})
    tasks = st.session_state.get(_REGEN_TASKS_KEY, {})
    task_id = index.get(_regen_task_key(word, content_type))
    return tasks.get(task_id) if task_id else None


def _update_learning_plan_word(word: str, content_type: str, content: str) -> None:
    if not content:
        return
    field = "ai_explanation" if content_type == "ai_explanation" else "scene_content"
    plan = st.session_state.get("learning_plan", [])
    for item in plan:
        if item.get("word") == word:
            item[field] = content
            break
    st.session_state["learning_plan"] = plan  # 写回，确保引用一致


def _start_regenerate_task_api(
    base_url: str,
    word: str,
    content_type: str,
    user_id: str,
    feedback: str = None,
    current_content: str = None,
):
    """启动后台任务：POST /api/ai/regenerate_task"""
    from utils.auth_helper import get_jwt_token

    try:
        jwt_token = get_jwt_token(user_id)
        response = requests.post(
            f"{base_url}/api/ai/regenerate_task",
            json={
                "word": word,
                "content_type": content_type,
                "feedback": feedback if feedback and feedback.strip() else None,
                "current_content": current_content,
            },
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=30,  # 这里只需要拿到 task_id，必须短超时
        )
        return response, None
    except requests.exceptions.Timeout:
        return None, "请求超时，请稍后重试"
    except Exception as e:
        return None, f"网络错误：{e}"


def _get_regenerate_task_status_api(base_url: str, task_id: str, user_id: str):
    """查询任务状态：GET /api/ai/regenerate_task/{task_id}"""
    from utils.auth_helper import get_jwt_token

    try:
        jwt_token = get_jwt_token(user_id)
        response = requests.get(
            f"{base_url}/api/ai/regenerate_task/{task_id}",
            headers={"Authorization": f"Bearer {jwt_token}"},
            timeout=15,
        )
        return response, None
    except requests.exceptions.Timeout:
        return None, "请求超时，请稍后重试"
    except Exception as e:
        return None, f"网络错误：{e}"


@st.fragment(run_every=2)
def render_regen_task_center():
    """后台任务中心：轮询任务状态 + 展示进度（跨单词可见）"""
    meta = st.session_state.get(_REGEN_META_KEY, {})
    user_id = meta.get("user_id")
    base_url = meta.get("base_url")
    tasks = st.session_state.get(_REGEN_TASKS_KEY, {})

    if not user_id or not base_url or not tasks:
        return

    # 1) 轮询更新（仅更新未完成的任务）
    for task_id, t in list(tasks.items()):
        if t.get("status") in ("succeeded", "failed"):
            continue

        resp, err = _get_regenerate_task_status_api(base_url, task_id, user_id)
        if err:
            # 网络波动不直接置失败，只记录
            t["error"] = err
            t["updated_at"] = time.time()
            tasks[task_id] = t
            continue

        if resp is None:
            continue

        if resp.status_code == 200:
            data = resp.json()
            t["status"] = data.get("status", t.get("status"))
            t["error"] = data.get("error")
            t["cost_usd"] = data.get("cost_usd")
            if t["status"] == "succeeded":
                t["content"] = data.get("content")
            t["updated_at"] = time.time()
            tasks[task_id] = t
        elif resp.status_code == 404:
            t["status"] = "failed"
            t["error"] = "任务不存在或已过期"
            t["updated_at"] = time.time()
            tasks[task_id] = t
        elif resp.status_code in (401, 403):
            t["status"] = "failed"
            t["error"] = "登录状态失效或无权访问任务"
            t["updated_at"] = time.time()
            tasks[task_id] = t
        else:
            t["error"] = f"状态查询失败：HTTP {resp.status_code}"
            t["updated_at"] = time.time()
            tasks[task_id] = t

    # 2) 将完成的内容写回 learning_plan（只做一次）
    # ⚠️ 注意：Streamlit 不会因为后台任务完成而自动 rerun 其它区域。
    # 所以这里在“任务完成且内容写回”时，触发一次 full-app rerun，让当前页面内容立刻更新。
    should_rerun_app = False

    index = st.session_state.get(_REGEN_INDEX_KEY, {})

    for task_id, t in list(tasks.items()):
        word = t.get("word")
        ctype = t.get("content_type")

        # 2.1 写回内容（仅“最新任务”生效，避免旧任务覆盖新结果）
        if t.get("status") == "succeeded" and not t.get("applied"):
            latest_id = index.get(_regen_task_key(word, ctype))
            if latest_id == task_id:
                if t.get("content"):
                    _update_learning_plan_word(word, ctype, t.get("content"))
                    should_rerun_app = True
            # 无论是否 latest，都标记已处理，避免重复 apply
            t["applied"] = True
            tasks[task_id] = t

        # 2.2 完成提示（成功/失败只提示一次）
        if t.get("status") in ("succeeded", "failed") and not t.get("notified"):
            label = "语域解码" if ctype == "ai_explanation" else "语境画面"
            if t.get("status") == "succeeded":
                st.toast(f"{word} 的{label}已生成完成", icon=":material/check_circle:", duration="long")
            else:
                st.toast(f"{word} 的{label}生成失败：{t.get('error') or '未知错误'}", icon=":material/error:", duration="long")
            t["notified"] = True
            tasks[task_id] = t
            # 让“生成中提示”及时消失/展示失败信息
            should_rerun_app = True

    st.session_state[_REGEN_TASKS_KEY] = tasks

    # 3) 展示任务进度（进行中 + 最近完成）
    running = [t for t in tasks.values() if t.get("status") in ("queued", "running")]
    finished = [t for t in tasks.values() if t.get("status") in ("succeeded", "failed")]

    if not running and not finished:
        return

    with st.expander("AI 内容后台生成进度", icon=":material/extension:", expanded=bool(running)):
        if running:
            st.markdown("**进行中**")
            for t in running:
                label = "语域解码" if t.get("content_type") == "ai_explanation" else "语境画面"
                st.write(f":material/hourglass_empty: {t.get('word')} - {label}：{t.get('status')}")
        if finished:
            st.markdown("**最近完成**")
            # 只展示最近 6 条，避免列表无限增长
            for t in finished[-6:]:
                label = "语域解码" if t.get("content_type") == "ai_explanation" else "语境画面"
                icon = ":material/check_circle:" if t.get("status") == "succeeded" else ":material/error:"
                extra = ""
                if t.get("cost_usd"):
                    try:
                        raw_cost = Decimal(str(t.get("cost_usd")).replace("$", ""))
                        total_cost = raw_cost * (Decimal("1") + SERVICE_FEE_RATE)
                        extra = f"（{total_cost:.6f}）"
                    except Exception:
                        extra = f"（{t.get('cost_usd')}）"
                st.write(f"{icon} {t.get('word')} - {label}：{t.get('status')} {extra}")

    # 4) 如果有任务刚完成/写回，则触发一次全局 rerun，让页面其它区域立刻拿到新内容
    if should_rerun_app:
        st.rerun(scope="app")

# ========== 模块2：词汇详解 ==========
def render_view_details_module(word_info, unique_id, pronunciation='us', user_id=None, fastapi_url=None):
    """
    词汇详解模块

    功能：
    - 显示单词 + 音频播放器
    - 显示音标
    - 显示完整详情（无需评分）：
      - 英文定义 (definition)
      - AI学习内容 (ai_explanation) - 默认展开
      - 场景画面 (scene_content) - 默认展开
      - 中文释义 (translation) - 默认折叠
      - TED视频实例 (ted_videos)
      - 状态信息 (state, retrievability)

    参数：
        word_info: 单词信息字典
        unique_id: 唯一ID
        pronunciation: 发音类型 ('us' 或 'uk')
        user_id: 用户ID（用于 OpenAI TTS 认证）
        fastapi_url: FastAPI 服务器地址
    """
    word_value = word_info['word']

    # 🔧 清理朗读练习模块的全局 audio 元素（避免显示两个播放器）
    components.html("""
    <script>
    (function() {
        const parentDoc = window.parent.document;
        const audio = parentDoc.getElementById('fsrs_read_audio_el');
        const host = parentDoc.getElementById('fsrs_read_audio_host');
        if (audio && host && audio.parentElement !== host) {
            audio.pause();
            host.appendChild(audio);
            console.log('[ViewDetails] 🧹 已将朗读练习的 audio 移回 host');
        }
    })();
    </script>
    """, height=0)

    # ========== 异步「重新生成」任务进度（跨单词可见） ==========
    # 让轮询 fragment 在「词汇详解」模块也始终挂载，否则任务状态不会更新
    if user_id:
        _ensure_regen_state(user_id, fastapi_url)
        render_regen_task_center()


    # 检查本地音频缓存（使用项目目录下的 audio 文件夹，与 fsrs_loop.py 一致）
    audio_dir = os.path.join(project_root, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    # 清理特殊字符（与 batch_download_tts.py 保持一致）
    safe_word = word_value.lower().replace("/", "_")
    possible_files = [
        os.path.join(audio_dir, f"{safe_word}_{pronunciation}_openai.mp3")
    ]

    cached_file = None
    for file_path in possible_files:
        if os.path.exists(file_path):
            cached_file = file_path
            break

    # 生成音频源
    has_cache = False
    if cached_file:
        with open(cached_file, 'rb') as audio_file:
            audio_bytes = audio_file.read()
            audio_base64 = base64.b64encode(audio_bytes).decode()
        audio_source = f"data:audio/mp3;base64,{audio_base64}"
        has_cache = True
    else:
        # 使用 OpenAI TTS GET URL（通过 Cookie 认证，点击播放时才请求）
        if user_id:
            from urllib.parse import quote
            word_encoded = quote(word_value, safe='')
            audio_source = f"{fastapi_url}/api/tts/word/{word_encoded}/{pronunciation}"
        else:
            # 未登录时无音频
            audio_source = ""

    online_hint = "" if has_cache else '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg> 在线音频'

    # 单词卡片 HTML
    word_id = f"word-{word_value.lower().replace(' ', '-')}"
    word_audio_html = f"""
    <style>
        .word-container-{unique_id} {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .audio-container-{unique_id} {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-top: 16px;
        }}
    </style>
    <div id="{word_id}" class="word-container-{unique_id}">
        <div class="word-title" style="font-size: 48px; font-weight: 800; color: #e2e8f0; text-shadow: 0 3px 10px rgba(0,0,0,0.35); letter-spacing: 0.01em;">{word_value}</div>
        <div class="audio-container-{unique_id}">
            <audio controls preload="none" key="{unique_id}">
                <source src="{audio_source}" type="audio/mp3">
            </audio>
            <span style="color: #a5b4fc; font-size: 0.78em; font-style: italic;">{online_hint}</span>
        </div>
    </div>
    """
    st.markdown(word_audio_html, unsafe_allow_html=True)

    # 音标（使用 lipis/flag-icons 开源 SVG 国旗替代 emoji，MIT 协议）
    # 来源：https://github.com/lipis/flag-icons
    _flag_us = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480" width="20" height="15" style="vertical-align:-2px;border-radius:2px"><path fill="#bd3d44" d="M0 0h640v480H0"/><path stroke="#fff" stroke-width="37" d="M0 55.3h640M0 129h640M0 203h640M0 277h640M0 351h640M0 425h640"/><path fill="#192f5d" d="M0 0h364.8v258.5H0"/><marker id="us-a" markerHeight="30" markerWidth="30"><path fill="#fff" d="m14 0 9 27L0 10h28L5 27z"/></marker><path fill="none" marker-mid="url(#us-a)" d="m0 0 16 11h61 61 61 61 60L47 37h61 61 60 61L16 63h61 61 61 61 60L47 89h61 61 60 61L16 115h61 61 61 61 60L47 141h61 61 60 61L16 166h61 61 61 61 60L47 192h61 61 60 61L16 218h61 61 61 61 60z"/></svg>'
    _flag_uk = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480" width="20" height="15" style="vertical-align:-2px;border-radius:2px"><path fill="#012169" d="M0 0h640v480H0z"/><path fill="#FFF" d="m75 0 244 181L562 0h78v62L400 241l240 178v61h-80L320 301 81 480H0v-60l239-178L0 64V0z"/><path fill="#C8102E" d="m424 281 216 159v40L369 281zm-184 20 6 35L54 480H0zM640 0v3L391 191l2-44L590 0zM0 0l239 176h-60L0 42z"/><path fill="#FFF" d="M241 0v480h160V0zM0 160v160h640V160z"/><path fill="#C8102E" d="M0 193v96h640v-96zM273 0v480h96V0z"/></svg>'
    usphone = word_info.get('usphone', '')
    ukphone = word_info.get('ukphone', '')
    if usphone or ukphone:
        phonetic_parts = []
        if usphone:
            phonetic_parts.append(f'{_flag_us} /{usphone}/')
        if ukphone:
            phonetic_parts.append(f'{_flag_uk} /{ukphone}/')

        st.markdown(f'<div style="font-size: 24px; color: #cbd5e1; text-align: center; margin-bottom: 30px; letter-spacing: 0.01em;"><strong>{" &middot; ".join(phonetic_parts)}</strong></div>', unsafe_allow_html=True)

    # 英文定义
    definition = word_info.get('definition', '')
    if definition:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, rgba(10,18,36,0.95), rgba(5,14,28,0.94)); color: #e2e8f0; line-height:1.7; border: 1px solid rgba(148,163,184,0.35); border-left: 4px solid #38bdf8; padding: 20px; margin: 20px 0; border-radius: 12px; box-shadow: 0 16px 30px rgba(3,7,18,0.45);">
            <h4 style="margin: 0 0 10px 0; color: #bae6fd;"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -3px; margin-right: 4px;"><path d="M12 7v14"/><path d="M16 12h2"/><path d="M16 8h2"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/><path d="M6 12h2"/><path d="M6 8h2"/></svg> English Definition</h4>
            {definition.replace(chr(10), '<br>')}
        </div>
        """, unsafe_allow_html=True)

    # AI学习内容 或 中文释义（折叠显示）
    ai_explanation = word_info.get('ai_explanation', '')
    scene_content = word_info.get('scene_content', '')
    translation = word_info.get('translation', '')

    # ========== 内嵌式「重新生成」按钮的全局样式 ==========
    if user_id and (ai_explanation or scene_content):
        st.markdown(
            """
            <style>
                /* 隐藏用于 JS 触发的内部按钮 */
                div[class*="st-key-mlm_open_regen_"] {
                    display: none !important;
                }

                /* 注入到 expander summary 的动作按钮样式 */
                button.mlm-expander-action-btn {
                    position: absolute;
                    right: 0.65rem;
                    top: 50%;
                    transform: translateY(-50%);
                    display: inline-flex;
                    align-items: center;
                    gap: 0.35rem;
                    padding: 0.2rem 0.55rem;
                    border-radius: 999px;
                    border: 1px solid rgba(148, 163, 184, 0.35);
                    background: rgba(15, 23, 42, 0.55);
                    color: #e2e8f0;
                    font-size: 12px;
                    line-height: 1;
                    cursor: pointer;
                    white-space: nowrap;
                    box-shadow: 0 10px 22px rgba(2, 6, 23, 0.35);
                    backdrop-filter: blur(8px);
                    z-index: 3;
                }
                button.mlm-expander-action-btn:hover {
                    border-color: rgba(56, 189, 248, 0.6);
                    background: rgba(56, 189, 248, 0.16);
                }

                /* 表单提交按钮样式 - 与输入框颜色一致 */
                button[data-testid="stBaseButton-secondaryFormSubmit"] {
                    background: rgba(15, 23, 42, 0.8) !important;
                    color: rgb(226, 232, 240) !important;
                    border: 1px solid rgba(148, 163, 184, 0.35) !important;
                }
                button[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
                    background: rgba(56, 189, 248, 0.16) !important;
                    border-color: rgba(56, 189, 248, 0.6) !important;
                }

                /* 输入框 Placeholder 颜色 - 与输入文字同色系，50%透明度 */
                div[data-testid="stTextArea"] textarea::placeholder {
                    color: rgba(226, 232, 240, 0.5) !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

    def _inject_regen_button_into_expander_header(*, container_key: str, open_btn_key: str, tooltip: str) -> None:
        """将「重新生成」按钮注入到 expander 标题栏右侧"""
        import json
        components.html(
            f"""
            <script>
            (function() {{
                const DOC = window.parent.document;
                const marker = 'data-mlm-action';
                const tooltip = {json.dumps(tooltip)};
                let attempts = 0;
                const maxAttempts = 25;

                const tryInject = () => {{
                    attempts += 1;
                    const container = DOC.querySelector('.st-key-{container_key}');
                    if (!container) {{ if (attempts < maxAttempts) setTimeout(tryInject, 60); return; }}
                    const details = container.querySelector('details');
                    if (!details) {{ if (attempts < maxAttempts) setTimeout(tryInject, 60); return; }}
                    const summary = details.querySelector('summary');
                    if (!summary) {{ if (attempts < maxAttempts) setTimeout(tryInject, 60); return; }}
                    
                    // 清理：移除整个文档中所有相同 open_btn_key 的旧按钮（防止重复）
                    DOC.querySelectorAll('button[' + marker + '="{open_btn_key}"]').forEach(b => b.remove());
                    // 清理：移除当前 summary 中所有残留按钮（防止错位按钮）
                    summary.querySelectorAll('button.mlm-expander-action-btn').forEach(b => b.remove());

                    summary.style.position = 'relative';
                    summary.style.paddingRight = '6.4rem';

                    const btn = DOC.createElement('button');
                    btn.type = 'button';
                    btn.className = 'mlm-expander-action-btn';
                    btn.setAttribute(marker, '{open_btn_key}');
                    btn.title = tooltip;
                    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg> 重新生成';

                    btn.addEventListener('click', (e) => {{
                        e.preventDefault();
                        e.stopPropagation();
                        details.open = true;
                        const hidden = container.querySelector('[class*="st-key-{open_btn_key}"] button');
                        if (hidden) hidden.click();
                    }});
                    summary.appendChild(btn);
                }};
                tryInject();
            }})();
            </script>
            """,
            height=0,
            width=0,
        )

    # ========== 语域解码（带内嵌重新生成按钮）==========
    if ai_explanation:
        @st.fragment
        def _ai_explanation_fragment():
            container_key = f"mlm_exp_ai_{unique_id}"
            open_btn_key = f"mlm_open_regen_ai_{unique_id}"
            open_state_key = f"mlm_regen_open_ai_{unique_id}"

            with st.container(key=container_key):
                # 隐藏的触发按钮
                if user_id and st.button("open", key=open_btn_key):
                    st.session_state[open_state_key] = True

                with st.expander("语域解码 · 元思维", icon=":material/psychology:", expanded=True):
                    # 内嵌反馈 UI（点击标题栏按钮后显示）
                    if user_id and st.session_state.get(open_state_key, False):
                        st.markdown(
                            """<div style="background: rgba(15,23,42,0.55); border: 1px solid rgba(148,163,184,0.28); border-left: 4px solid rgba(34,211,238,0.9); border-radius: 12px; padding: 14px 16px; margin: 12px 0 18px 0;">
                                <div style="font-weight: 700; color: #e2e8f0; margin-bottom: 6px;"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg> 重新生成 · 语域解码</div>
                                <div style="color: #94a3b8; font-size: 12px;">可输入反馈来定向微调，例如：更口语 / 更短 / 多举例</div>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        if st.button("取消", key=f"mlm_cancel_ai_{unique_id}", type="tertiary", icon=":material/close:"):
                            st.session_state[open_state_key] = False
                            st.rerun()

                        if st.session_state.get(open_state_key, False):
                            status_ph = st.empty()
                            with st.form(key=f"mlm_form_ai_{unique_id}"):
                                fb = st.text_area("反馈建议（可选）", placeholder="例如：希望用更简单的语言解释", key=f"mlm_fb_ai_{unique_id}", height=80, max_chars=1500)
                                submitted = st.form_submit_button("重新生成", use_container_width=True, icon=":material/auto_awesome:")
                            if submitted:
                                # 启动后台任务：快速返回 task_id（避免切换单词导致结果丢失）
                                base_url = _normalize_base_url(fastapi_url)
                                with status_ph, st.spinner(":material/autorenew: 已提交后台生成任务..."):
                                    response, error = _start_regenerate_task_api(
                                        base_url=base_url,
                                        word=word_info["word"],
                                        content_type="ai_explanation",
                                        user_id=user_id,
                                        feedback=fb,
                                        current_content=word_info.get("ai_explanation", ""),
                                    )
                                if error:
                                    status_ph.error(f"{error}", icon=":material/error:")
                                elif response and response.status_code in (200, 202):
                                    result = response.json()
                                    if result.get("success") and result.get("task_id"):
                                        task_id = result["task_id"]
                                        _register_regen_task(task_id, word_info["word"], "ai_explanation")
                                        status_ph.success("已加入后台生成队列（可先学习下一个词）", icon=":material/check_circle:")
                                        st.session_state[open_state_key] = False
                                        st.rerun()
                                    else:
                                        status_ph.error(f"{result.get('error', '启动任务失败')}", icon=":material/error:")
                                elif response and response.status_code == 402:
                                    status_ph.error("额度不足", icon=":material/error:")
                                else:
                                    # 尝试获取后端返回的详细错误信息
                                    try:
                                        error_detail = response.json().get("detail", "请求失败")
                                    except Exception:
                                        error_detail = "请求失败"
                                    status_ph.error(f"{error_detail}", icon=":material/error:")

                    # 内容展示
                    # 该内容的后台生成状态（跨单词轮询更新）
                    task = _get_latest_regen_task(word_info["word"], "ai_explanation")
                    if task and task.get("status") in ("queued", "running"):
                        st.info("语域解码正在后台生成中… 你可以先学习下一个词，完成后会自动更新。", icon=":material/hourglass_empty:")
                    elif task and task.get("status") == "failed":
                        st.warning(f"上次重新生成失败：{task.get('error') or '未知错误'}", icon=":material/warning:")

                    current_ai = word_info.get("ai_explanation", "")
                    if current_ai:
                        st.markdown(f"""
                        <div style="background: linear-gradient(135deg, rgba(22,38,71,0.92), rgba(17,24,39,0.9)); color: #e5e7eb; line-height:1.7; border: 1px solid rgba(56,189,248,0.35); border-left: 4px solid #22d3ee; padding: 20px; margin: 20px 0; border-radius: 12px; box-shadow: 0 18px 44px rgba(2,6,23,0.5); backdrop-filter: blur(8px);">
                            {current_ai.replace(chr(10), '<br>')}
                        </div>
                        """, unsafe_allow_html=True)

                # 注入标题栏按钮
                if user_id:
                    _inject_regen_button_into_expander_header(container_key=container_key, open_btn_key=open_btn_key, tooltip="重新生成「语域解码」")

        _ai_explanation_fragment()

    # ========== 语境画面（带内嵌重新生成按钮）==========
    if scene_content:
        @st.fragment
        def _scene_content_fragment():
            container_key = f"mlm_exp_scene_{unique_id}"
            open_btn_key = f"mlm_open_regen_scene_{unique_id}"
            open_state_key = f"mlm_regen_open_scene_{unique_id}"

            with st.container(key=container_key):
                if user_id and st.button("open", key=open_btn_key):
                    st.session_state[open_state_key] = True

                with st.expander("语境画面 · 场景记忆", icon=":material/movie:", expanded=True):
                    if user_id and st.session_state.get(open_state_key, False):
                        st.markdown(
                            """<div style="background: rgba(15,23,42,0.55); border: 1px solid rgba(148,163,184,0.28); border-left: 4px solid rgba(165,180,252,0.95); border-radius: 12px; padding: 14px 16px; margin: 12px 0 18px 0;">
                                <div style="font-weight: 700; color: #e2e8f0; margin-bottom: 6px;"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg> 重新生成 · 语境画面</div>
                                <div style="color: #94a3b8; font-size: 12px;">可输入反馈来控制画面感：更具体 / 更荒诞 / 更生活化</div>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        if st.button("取消", key=f"mlm_cancel_scene_{unique_id}", type="tertiary", icon=":material/close:"):
                            st.session_state[open_state_key] = False
                            st.rerun()

                        if st.session_state.get(open_state_key, False):
                            status_ph = st.empty()
                            with st.form(key=f"mlm_form_scene_{unique_id}"):
                                fb = st.text_area("反馈建议（可选）", placeholder="例如：场景换成咖啡店", key=f"mlm_fb_scene_{unique_id}", height=80, max_chars=1500)
                                submitted = st.form_submit_button("重新生成", use_container_width=True, icon=":material/auto_awesome:")
                            if submitted:
                                # 启动后台任务：快速返回 task_id（避免切换单词导致结果丢失）
                                base_url = _normalize_base_url(fastapi_url)
                                with status_ph, st.spinner(":material/autorenew: 已提交后台生成任务..."):
                                    response, error = _start_regenerate_task_api(
                                        base_url=base_url,
                                        word=word_info["word"],
                                        content_type="scene_content",
                                        user_id=user_id,
                                        feedback=fb,
                                        current_content=word_info.get("scene_content", ""),
                                    )
                                if error:
                                    status_ph.error(f"{error}", icon=":material/error:")
                                elif response and response.status_code in (200, 202):
                                    result = response.json()
                                    if result.get("success") and result.get("task_id"):
                                        task_id = result["task_id"]
                                        _register_regen_task(task_id, word_info["word"], "scene_content")
                                        status_ph.success("已加入后台生成队列（可先学习下一个词）", icon=":material/check_circle:")
                                        st.session_state[open_state_key] = False
                                        st.rerun()
                                    else:
                                        status_ph.error(f"{result.get('error', '启动任务失败')}", icon=":material/error:")
                                elif response and response.status_code == 402:
                                    status_ph.error("额度不足", icon=":material/error:")
                                else:
                                    # 尝试获取后端返回的详细错误信息
                                    try:
                                        error_detail = response.json().get("detail", "请求失败")
                                    except Exception:
                                        error_detail = "请求失败"
                                    status_ph.error(f"{error_detail}", icon=":material/error:")

                    # 该内容的后台生成状态（跨单词轮询更新）
                    task = _get_latest_regen_task(word_info["word"], "scene_content")
                    if task and task.get("status") in ("queued", "running"):
                        st.info("语境画面正在后台生成中… 你可以先学习下一个词，完成后会自动更新。", icon=":material/hourglass_empty:")
                    elif task and task.get("status") == "failed":
                        st.warning(f"上次重新生成失败：{task.get('error') or '未知错误'}", icon=":material/warning:")

                    current_scene = word_info.get("scene_content", "")
                    if current_scene:
                        st.markdown(f"""
                        <div style="background: linear-gradient(140deg, rgba(9,14,26,0.95), rgba(5,24,36,0.94)); color: #e5e7eb; line-height:1.7; border: 1px solid rgba(129,140,248,0.35); border-left: 4px solid #a5b4fc; padding: 20px; margin: 20px 0; border-radius: 12px; box-shadow: 0 18px 44px rgba(0,0,0,0.45); backdrop-filter: blur(8px);">
                            {current_scene.replace(chr(10), '<br>')}
                        </div>
                        """, unsafe_allow_html=True)

                if user_id:
                    _inject_regen_button_into_expander_header(container_key=container_key, open_btn_key=open_btn_key, tooltip="重新生成「语境画面」")

        _scene_content_fragment()

    # ========== 已注释：底部「重新生成 AI 内容」区域 ==========
    # if user_id and (ai_explanation or scene_content):
    #     
    #     @st.fragment
    #     def _regen_fragment():
    #         with st.expander("🔧 不满意？重新生成 AI 内容", expanded=False):
    #             st.caption("💡 可以输入反馈建议，指导 AI 重新生成更符合您需求的内容")
    #             
    #             st.markdown("""
    #             <style>
    #                 textarea::placeholder { color: #94a3b8 !important; opacity: 1 !important; }
    #                 div[data-testid="stTextArea"] > label { color: #94a3b8 !important; }
    #             </style>
    #             """, unsafe_allow_html=True)
    #             
    #             feedback = st.text_area(
    #                 "反馈建议（可选）",
    #                 placeholder="例如：\n• 希望用更简单的语言解释\n• 多举一些生活中的例子\n• 关联我喜欢的电影/游戏",
    #                 key=f"feedback_{unique_id}",
    #                 height=100
    #             )
    #             
    #             col1, col2 = st.columns(2)
    #             clicked_type = None
    #             
    #             with col1:
    #                 if ai_explanation:
    #                     if st.button("🔄 重新生成「语域解码」", key=f"regen_ai_{unique_id}", use_container_width=True):
    #                         clicked_type = "ai_explanation"
    #                 else:
    #                     st.info("暂无语域解码内容")
    #                 placeholder_ai = st.empty()
    #             
    #             with col2:
    #                 if scene_content:
    #                     if st.button("🔄 重新生成「语境画面」", key=f"regen_scene_{unique_id}", use_container_width=True):
    #                         clicked_type = "scene_content"
    #                 else:
    #                     st.info("暂无语境画面内容")
    #                 placeholder_scene = st.empty()
    #             
    #             if clicked_type:
    #                 content_name = "语域解码" if clicked_type == "ai_explanation" else "语境画面"
    #                 current = ai_explanation if clicked_type == "ai_explanation" else scene_content
    #                 active_placeholder = placeholder_ai if clicked_type == "ai_explanation" else placeholder_scene
    #                 
    #                 with active_placeholder:
    #                     with st.spinner(f"正在重新生成「{content_name}」...（约需 5-15 秒）"):
    #                         response, error = _call_regenerate_api(word_info['word'], clicked_type, user_id, feedback, current)
    #                 
    #                 if error:
    #                     active_placeholder.error(f"❌ {error}")
    #                 elif response.status_code == 200:
    #                     result = response.json()
    #                     if result.get("success"):
    #                         active_placeholder.success(f"✅ 重新生成成功！费用：{result.get('cost_usd', 'N/A')}")
    #                         new_content = result.get("content")
    #                         if new_content and "learning_plan" in st.session_state:
    #                             for item in st.session_state.learning_plan:
    #                                 if item.get("word") == word_info["word"]:
    #                                     item[clicked_type] = new_content
    #                                     break
    #                         st.rerun()
    #                     else:
    #                         active_placeholder.error(f"❌ {result.get('error', '未知错误')}")
    #                 elif response.status_code == 402:
    #                     active_placeholder.error("❌ 额度不足，请充值后再试")
    #                 else:
    #                     active_placeholder.error(f"❌ 请求失败：HTTP {response.status_code}")
    #     
    #     _regen_fragment()

    # 传统单词书的中文释义（默认折叠）
    if translation:
        with st.expander("传统单词书中的中文释义", icon=":material/translate:", expanded=False):
            translations = translation.split('\n')
            for trans in translations:
                if trans.strip():
                    st.success(trans.strip())

    # TED视频实例
    ted_videos = word_info.get('ted_videos', [])
    if ted_videos and isinstance(ted_videos, list):
        st.markdown('<strong><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px"><path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.934a.5.5 0 0 0-.777-.416L16 11"/><rect x="2" y="6" width="14" height="12" rx="2"/></svg> TED 视频实例</strong>', unsafe_allow_html=True)
        for video in ted_videos[:5]:
            timestamp = video.get('timestamp', '')
            text = video.get('text', '')
            jump_link = video.get('jump_link', '')

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(59,130,246,0.16), rgba(56,189,248,0.12), rgba(236,72,153,0.14)); color: #e2e8f0; border-radius: 12px; padding: 16px 16px 12px; margin: 10px 0; border: 1px solid rgba(148,163,184,0.4); box-shadow: 0 12px 24px rgba(0,0,0,0.3); display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center;">
                <div style="line-height: 1.5;">
                    <strong style="color:#bfdbfe;"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> {timestamp}</strong><br>
                    {text}
                </div>
                <a href="{jump_link}" target="_blank" style="text-decoration: none; color: #0c4a6e; font-weight: 700; background: linear-gradient(120deg, #5eead4, #38bdf8); padding: 10px 14px; border-radius: 10px; box-shadow: 0 10px 20px rgba(56,189,248,0.25);">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><polygon points="6 3 20 12 6 21 6 3"/></svg> 观看
                </a>
            </div>
            """, unsafe_allow_html=True)

    # 状态信息
    st.markdown("---")
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        st.info(f"当前状态：{word_info['state']}", icon=":material/bar_chart:")
    with col_info2:
        st.info(f"记忆概率：{word_info['retrievability']:.1%}", icon=":material/psychology:")


# ========== 模块3：记忆评估 ==========
def render_self_rating_module(word_info, current_index, fsrs_system, unique_id, pronunciation='us', user_id: str = None, fastapi_url=None):
    """
    记忆评估模块

    功能：
    - 未评分时：只显示4个评分按钮（1️⃣忘记, 2️⃣困难, 3️⃣记得, 4️⃣简单）
    - 评分后：显示完整详情（同view_details模块）
    - 调用FSRS算法更新单词状态

    参数：
        word_info: 单词信息字典
        current_index: 当前单词索引（用于tracking评分状态）
        fsrs_system: FSRS系统实例
        unique_id: 唯一ID
        pronunciation: 发音类型 ('us' 或 'uk')
        user_id: 用户ID（必填）
        fastapi_url: FastAPI 服务器地址
    """
    # 强制要求 user_id
    if not user_id:
        raise ValueError("render_self_rating_module 需要 user_id 参数")

    word_value = word_info['word']

    # 🔧 清理朗读练习模块的全局 audio 元素（避免显示两个播放器）
    components.html("""
    <script>
    (function() {
        const parentDoc = window.parent.document;
        const audio = parentDoc.getElementById('fsrs_read_audio_el');
        const host = parentDoc.getElementById('fsrs_read_audio_host');
        if (audio && host && audio.parentElement !== host) {
            audio.pause();
            host.appendChild(audio);
            console.log('[SelfRating] 🧹 已将朗读练习的 audio 移回 host');
        }
    })();
    </script>
    """, height=0)

    # ========== 异步「重新生成」任务进度（跨单词可见） ==========
    # 记忆评估模块也可能展示「语域解码/语境画面」，需要同样的后台任务轮询
    _ensure_regen_state(user_id, fastapi_url)
    render_regen_task_center()


    # 检查本地音频缓存（使用项目目录下的 audio 文件夹，与 fsrs_loop.py 一致）
    audio_dir = os.path.join(project_root, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    # 清理特殊字符（与 batch_download_tts.py 保持一致）
    safe_word = word_value.lower().replace("/", "_")
    possible_files = [
        os.path.join(audio_dir, f"{safe_word}_{pronunciation}_openai.mp3")
    ]

    cached_file = None
    for file_path in possible_files:
        if os.path.exists(file_path):
            cached_file = file_path
            break

    # 生成音频源
    has_cache = False
    if cached_file:
        with open(cached_file, 'rb') as audio_file:
            audio_bytes = audio_file.read()
            audio_base64 = base64.b64encode(audio_bytes).decode()
        audio_source = f"data:audio/mp3;base64,{audio_base64}"
        has_cache = True
    else:
        # 使用 OpenAI TTS GET URL（通过 Cookie 认证，点击播放时才请求）
        if user_id:
            from urllib.parse import quote
            word_encoded = quote(word_value, safe='')
            audio_source = f"{fastapi_url}/api/tts/word/{word_encoded}/{pronunciation}"
        else:
            # 未登录时无音频
            audio_source = ""

    online_hint = "" if has_cache else '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg> 在线音频'

    # 单词卡片 HTML
    word_id = f"word-{word_value.lower().replace(' ', '-')}"
    word_audio_html = f"""
    <style>
        .word-container-{unique_id} {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .audio-container-{unique_id} {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-top: 16px;
        }}
    </style>
    <div id="{word_id}" class="word-container-{unique_id}">
        <div class="word-title" style="font-size: 48px; font-weight: 800; color: #e2e8f0; text-shadow: 0 3px 10px rgba(0,0,0,0.35); letter-spacing: 0.01em;">{word_value}</div>
        <div class="audio-container-{unique_id}">
            <audio controls preload="none" key="{unique_id}">
                <source src="{audio_source}" type="audio/mp3">
            </audio>
            <span style="color: #a5b4fc; font-size: 0.78em; font-style: italic;">{online_hint}</span>
        </div>
    </div>
    """
    st.markdown(word_audio_html, unsafe_allow_html=True)

    # 音标（使用 lipis/flag-icons 开源 SVG 国旗替代 emoji，MIT 协议）
    # 来源：https://github.com/lipis/flag-icons
    _flag_us = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480" width="20" height="15" style="vertical-align:-2px;border-radius:2px"><path fill="#bd3d44" d="M0 0h640v480H0"/><path stroke="#fff" stroke-width="37" d="M0 55.3h640M0 129h640M0 203h640M0 277h640M0 351h640M0 425h640"/><path fill="#192f5d" d="M0 0h364.8v258.5H0"/><marker id="us-a" markerHeight="30" markerWidth="30"><path fill="#fff" d="m14 0 9 27L0 10h28L5 27z"/></marker><path fill="none" marker-mid="url(#us-a)" d="m0 0 16 11h61 61 61 61 60L47 37h61 61 60 61L16 63h61 61 61 61 60L47 89h61 61 60 61L16 115h61 61 61 61 60L47 141h61 61 60 61L16 166h61 61 61 61 60L47 192h61 61 60 61L16 218h61 61 61 61 60z"/></svg>'
    _flag_uk = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480" width="20" height="15" style="vertical-align:-2px;border-radius:2px"><path fill="#012169" d="M0 0h640v480H0z"/><path fill="#FFF" d="m75 0 244 181L562 0h78v62L400 241l240 178v61h-80L320 301 81 480H0v-60l239-178L0 64V0z"/><path fill="#C8102E" d="m424 281 216 159v40L369 281zm-184 20 6 35L54 480H0zM640 0v3L391 191l2-44L590 0zM0 0l239 176h-60L0 42z"/><path fill="#FFF" d="M241 0v480h160V0zM0 160v160h640V160z"/><path fill="#C8102E" d="M0 193v96h640v-96zM273 0v480h96V0z"/></svg>'
    usphone = word_info.get('usphone', '')
    ukphone = word_info.get('ukphone', '')
    if usphone or ukphone:
        phonetic_parts = []
        if usphone:
            phonetic_parts.append(f'{_flag_us} /{usphone}/')
        if ukphone:
            phonetic_parts.append(f'{_flag_uk} /{ukphone}/')

        st.markdown(f'<div style="font-size: 24px; color: #cbd5e1; text-align: center; margin-bottom: 30px; letter-spacing: 0.01em;"><strong>{" &middot; ".join(phonetic_parts)}</strong></div>', unsafe_allow_html=True)

    # 检查当前单词是否已评分
    rated_key = f'rated_{current_index}'
    is_rated = st.session_state.get(rated_key, False)

    # 评分提交函数
    def submit_rating(rating):
        """提交FSRS评分"""
        import time

        # 计算学习时长（如果有start_time）
        duration = 0
        if 'rating_start_time' in st.session_state:
            duration_seconds = time.time() - st.session_state.rating_start_time
            if 0 < duration_seconds < 3600:  # 有效时长：0-1小时
                duration = int(duration_seconds * 1000)

        # 调用FSRS系统记录评分
        try:
            fsrs_system.review_word(
                word=word_info['word'],
                rating=rating,
                user_id=user_id,
                review_duration_ms=duration
            )
        except Exception as e:
            st.error(f"评分失败: {e}", icon=":material/error:")

        # 标记为已评分
        st.session_state[rated_key] = True

    # 评分按钮（只在未评分时显示）
    if not is_rated:
        # 开始计时
        if 'rating_start_time' not in st.session_state:
            import time
            st.session_state.rating_start_time = time.time()

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("忘记", key=f"rating_1_{unique_id}", use_container_width=True, icon=":material/close:"):
                submit_rating(1)
                st.rerun()

        with col2:
            if st.button("困难", key=f"rating_2_{unique_id}", use_container_width=True, icon=":material/help:"):
                submit_rating(2)
                st.rerun()

        with col3:
            if st.button("记得", key=f"rating_3_{unique_id}", use_container_width=True, icon=":material/check:"):
                submit_rating(3)
                st.rerun()

        with col4:
            if st.button("简单", key=f"rating_4_{unique_id}", use_container_width=True, icon=":material/done_all:"):
                submit_rating(4)
                st.rerun()

    # 评分后显示详细内容（与view_details模块相同）
    if is_rated:
        # 英文定义
        definition = word_info.get('definition', '')
        if definition:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(10,18,36,0.95), rgba(5,14,28,0.94)); color: #e2e8f0; line-height:1.7; border: 1px solid rgba(148,163,184,0.35); border-left: 4px solid #38bdf8; padding: 20px; margin: 20px 0; border-radius: 12px; box-shadow: 0 16px 30px rgba(3,7,18,0.45);">
                <h4 style="margin: 0 0 10px 0; color: #bae6fd;"><svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -3px; margin-right: 4px;"><path d="M12 7v14"/><path d="M16 12h2"/><path d="M16 8h2"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/><path d="M6 12h2"/><path d="M6 8h2"/></svg> English Definition</h4>
                {definition.replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)

        # AI学习内容
        ai_explanation = word_info.get('ai_explanation', '')
        scene_content = word_info.get('scene_content', '')
        translation = word_info.get('translation', '')

        if ai_explanation:
            with st.expander("🧠 语域解码 · 元思维", expanded=True):
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(22,38,71,0.92), rgba(17,24,39,0.9)); color: #e5e7eb; line-height:1.7; border: 1px solid rgba(56,189,248,0.35); border-left: 4px solid #22d3ee; padding: 20px; margin: 20px 0; border-radius: 12px; box-shadow: 0 18px 44px rgba(2,6,23,0.5); backdrop-filter: blur(8px);">
                    {ai_explanation.replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)

        if scene_content:
            with st.expander("🎬 语境画面 · 场景记忆", expanded=True):
                st.markdown(f"""
                <div style="background: linear-gradient(140deg, rgba(9,14,26,0.95), rgba(5,24,36,0.94)); color: #e5e7eb; line-height:1.7; border: 1px solid rgba(129,140,248,0.35); border-left: 4px solid #a5b4fc; padding: 20px; margin: 20px 0; border-radius: 12px; box-shadow: 0 18px 44px rgba(0,0,0,0.45); backdrop-filter: blur(8px);">
                    {scene_content.replace(chr(10), '<br>')}
                </div>
                """, unsafe_allow_html=True)

        if translation:
            with st.expander("传统单词书中的中文释义", icon=":material/translate:", expanded=False):
                translations = translation.split('\n')
                for trans in translations:
                    if trans.strip():
                        st.success(trans.strip())

        # TED视频实例
        ted_videos = word_info.get('ted_videos', [])
        if ted_videos and isinstance(ted_videos, list):
            st.markdown('<strong><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px"><path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.934a.5.5 0 0 0-.777-.416L16 11"/><rect x="2" y="6" width="14" height="12" rx="2"/></svg> TED 视频实例</strong>', unsafe_allow_html=True)
            for video in ted_videos[:5]:
                timestamp = video.get('timestamp', '')
                text = video.get('text', '')
                jump_link = video.get('jump_link', '')

                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(59,130,246,0.16), rgba(56,189,248,0.12), rgba(236,72,153,0.14)); color: #e2e8f0; border-radius: 12px; padding: 16px 16px 12px; margin: 10px 0; border: 1px solid rgba(148,163,184,0.4); box-shadow: 0 12px 24px rgba(0,0,0,0.3); display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center;">
                    <div style="line-height: 1.5;">
                        <strong style="color:#bfdbfe;"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> {timestamp}</strong><br>
                        {text}
                    </div>
                    <a href="{jump_link}" target="_blank" style="text-decoration: none; color: #0c4a6e; font-weight: 700; background: linear-gradient(120deg, #5eead4, #38bdf8); padding: 10px 14px; border-radius: 10px; box-shadow: 0 10px 20px rgba(56,189,248,0.25);">
                        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px"><polygon points="6 3 20 12 6 21 6 3"/></svg> 观看
                    </a>
                </div>
                """, unsafe_allow_html=True)

        # 状态信息
        st.markdown("---")
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.info(f"当前状态：{word_info['state']}", icon=":material/bar_chart:")
        with col_info2:
            st.info(f"记忆概率：{word_info['retrievability']:.1%}", icon=":material/psychology:")


# ========== 模块4：AI互动 ==========
def render_agent_module(word_info, current_index):
    """
    AI互动模块（场景学习）

    功能：
    - 调用现有的 render_scene_with_toggle 函数
    - 显示交互式场景学习内容
    - 随机生成题目（单词意思/句子意思/中译英/填空/视觉连接）

    参数：
        word_info: 单词信息字典
        current_index: 当前单词索引
    """
    import time
    print(f"[render_agent_module] 🚀 开始渲染，时间: {time.time():.3f}, word_index: {current_index}")
    
    scene_content = word_info.get('scene_content', '')
    target_word = word_info.get('word', '')
    exchange = word_info.get('exchange', '')
    translation = word_info.get('translation', '')

    # 存储当前单词信息到session_state（供visual_connection_renderer使用）
    current_word_data_key = f"current_word_data_{current_index}"
    if current_word_data_key not in st.session_state:
        st.session_state[current_word_data_key] = {
            'word': target_word,
            'translation': translation
        }

    # 直接调用现有的场景渲染器
    render_scene_with_toggle(scene_content, target_word, current_index, exchange)
    
    print(f"[render_agent_module] ✅ 渲染完成，时间: {time.time():.3f}")
