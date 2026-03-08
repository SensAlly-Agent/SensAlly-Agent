"""
全页悬浮选择工具
================

功能：在Streamlit父页面上监听文本选择，并通过postMessage发送给播放器iframe

技术原理：
- 利用Streamlit iframe的 allow-same-origin 特性
- iframe可以访问 window.parent.document（因为srcdoc同源）
- 在父页面document上注入事件监听器和悬浮按钮
- 通过postMessage将选中文本发送给播放器组件

源代码证据：
- streamlit/static/static/js/index.6xX1278W.js:452
  DEFAULT_IFRAME_SANDBOX_POLICY 包含 "allow-same-origin"
"""

import os
import streamlit.components.v1 as components


def mount_floating_selector(channel: str = "tts-bridge-001", debug: bool = False, height: int = 80, show_status: bool = True, jwt_token: str = "", fastapi_url: str = None, pronunciation: str = "us"):
    """
    在父页面挂载全页选中监听 + 悬浮发送按钮

    参数：
        channel: 通道名称，用于与播放器组件配对（多组件隔离）
        debug: 是否开启调试模式（在console输出详细日志）
        height: iframe高度（px），设置为0或1可完全隐藏（默认80）
        show_status: 是否显示状态信息（默认True，设为False完全隐藏）
        jwt_token: JWT 认证令牌（用于非会员点击时跳转支付页面）
        fastapi_url: FastAPI 服务器地址
        pronunciation: 发音偏好 'us'（美式）或 'uk'（英式），默认 'us'

    工作原理：
        1. iframe访问 window.parent（基础API）
        2. 检测是否能访问 window.parent.document（需要allow-same-origin）
        3. 在父页面document添加mouseup监听器
        4. 在父页面body注入悬浮按钮
        5. 监听父页面的getSelection()
        6. 通过postMessage发送选中文本
    """
    # 环境变量 fallback
    if fastapi_url is None:
        fastapi_url = os.getenv("FASTAPI_URL")

    debug_code = """
        function debugLog(msg) {
            console.log(`[floating-selector][${CHANNEL}] ${msg}`);
        }
    """ if debug else """
        function debugLog(msg) { /* no-op */ }
    """

    html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
    <div id="status" style="padding:10px;background:#e8f5e9;border-radius:8px;font-family:sans-serif;display:{('block' if show_status else 'none')};">
        <div id="status-text">🔄 正在初始化全页选择监听器...</div>
    </div>

    <script>
    (function() {{
        const CHANNEL = {channel!r};
        const JWT_TOKEN = {jwt_token!r};
        const FASTAPI_URL = {fastapi_url!r};
        {debug_code}

        const statusDiv = document.getElementById('status-text');

        // ========== 1. 获取父窗口/文档 ==========
        let W = window;
        let D = document;
        let PARENT_OK = false;

        try {{
            if (window.parent && window.parent !== window) {{
                // 尝试访问父页面document（需要allow-same-origin权限）
                void window.parent.document;
                W = window.parent;
                D = W.document;
                PARENT_OK = true;
                debugLog("✅ 成功访问父页面document");
                statusDiv.innerHTML = "✅ 已激活全页选择监听（监听整个Streamlit页面）";
                statusDiv.parentElement.style.background = "#c8e6c9";
            }}
        }} catch (e) {{
            debugLog("❌ 无法访问父页面document: " + e.message);
            statusDiv.innerHTML = "⚠️ 降级模式：仅监听iframe内部（无法访问父页面）<br><small>错误: " + e.message + "</small>";
            statusDiv.parentElement.style.background = "#ffecb3";
        }}

        if (!PARENT_OK) {{
            debugLog("降级到iframe内部监听模式");
            // 无法访问父页面时，终止后续操作
            return;
        }}

        // 🍎 iOS 设备检测（在 IIFE 顶层定义，供整个脚本使用）
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
                      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

        // ========== 1.5 AbortController 管理事件监听器 ==========
        // ✅ 关键修复：避免旧 iframe 的 unload 清理“误伤”新实例（Streamlit rerun 时常见）
        const SAFE_CHANNEL = CHANNEL.replace(/[^a-zA-Z0-9]/g, '_');
        const REGISTRY_KEY = "__stx_fsel_registry";
        const INSTANCE_ID = Date.now().toString(36) + Math.random().toString(36).slice(2);

        if (!W[REGISTRY_KEY]) {{
            W[REGISTRY_KEY] = {{}};
        }}

        // 🔧 清理同 channel 的旧实例监听器（如果存在）
        const prev = W[REGISTRY_KEY][SAFE_CHANNEL];
        if (prev && prev.controller) {{
            try {{
                prev.controller.abort();
                debugLog("🧹 已清理旧实例事件监听器（同channel）");
            }} catch (e) {{
                debugLog("🧹 清理旧实例失败: " + e.message);
            }}
        }}

        // 创建新的 AbortController（本地变量 + 注册到 registry explain）
        const controller = new AbortController();
        W[REGISTRY_KEY][SAFE_CHANNEL] = {{ id: INSTANCE_ID, controller }};
        const listenerSignal = controller.signal;
        debugLog("✅ AbortController 已创建 (instance=" + INSTANCE_ID + ")");

        // ========== 2. 在父页面注入CSS样式 ==========
        const CSS_ID = "__stx_fsel_css_" + CHANNEL.replace(/[^a-zA-Z0-9]/g, '_');
        let styleEl = D.getElementById(CSS_ID);
        if (!styleEl) {{
            styleEl = D.createElement("style");
            styleEl.id = CSS_ID;
            styleEl.textContent = `
                            #__stx_fsel_popup_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}} {{
                                position: absolute;
                                display: none;
                                z-index: 2147483647;
                                background: transparent;
                                transition: opacity 0.2s ease;
                            }}
                            #__stx_fsel_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}} {{
                                display: flex;
                                gap: 8px;
                                align-items: center;
                                padding: 10px 18px;
                                border: 1px solid rgba(255, 255, 255, 0.3);
                                cursor: pointer;
                                border-radius: 9999px;
                                font-weight: 600;
                                background: rgba(203, 120, 92, 0.85);
                                color: #fff;
                                box-shadow: 0 4px 16px rgba(203, 120, 92, 0.3);
                                font-family: 'Space Grotesk', sans-serif;
                                font-size: 14px;
                                position: relative;
                                overflow: hidden;
                                transition: all 0.4s cubic-bezier(0.25, 1, 0.5, 1);
                            }}
                            #__stx_fsel_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}::after {{
                                content: '';
                                position: absolute;
                                top: 0; left: -100%; width: 50%; height: 100%;
                                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent);
                                transform: skewX(-20deg);
                                transition: 0.6s ease;
                            }}
                            #__stx_fsel_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}:hover {{
                                background: rgba(203, 120, 92, 1);
                                box-shadow: 0 6px 20px rgba(203, 120, 92, 0.4);
                            }}
                            #__stx_fsel_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}:hover::after {{
                                left: 150%;
                            }}
                            #__stx_fsel_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}:active {{
                                transform: scale(0.95);
                            }}
                            #__stx_fsel_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}.processing {{
                                cursor: wait;
                                background: rgba(203, 120, 92, 0.85);
                                color: #fff;
                                border: 1px solid rgba(203, 120, 92, 0.4);
                                animation: liquidBreathe 2s ease-in-out infinite;
                            }}
                            #__stx_fsel_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}.playing {{
                                background: rgba(203, 120, 92, 0.85);
                                color: #fff;
                                border: 1px solid rgba(203, 120, 92, 0.3);
                                animation: liquidBreathe 2s ease-in-out infinite;
                            }}
                            #__stx_fsel_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}.cached {{
                                background: rgba(14, 165, 233, 0.85);
                                color: #fff;
                                border-color: rgba(14, 165, 233, 0.3);
                            }}
                            #__stx_fsel_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}.subscription-required {{
                                background: rgba(251, 191, 36, 0.15);
                                color: #b8860b;
                                border-color: rgba(251, 191, 36, 0.3);
                                cursor: pointer;
                            }}
                            /* [新增 - 余额制改造 2026-01-20] 余额不足样式 */
                            #__stx_fsel_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}.credit-required {{
                                background: rgba(251, 191, 36, 0.85);
                                color: #ffffff;
                                border-color: rgba(251, 191, 36, 0.3);
                                cursor: pointer;
                            }}
                            @keyframes liquidBreathe {{
                                0%, 100% {{ box-shadow: 0 0 0 0 rgba(203, 120, 92, 0.1); border-color: rgba(203, 120, 92, 0.4); }}
                                50% {{ box-shadow: 0 0 12px 4px rgba(203, 120, 92, 0.15); border-color: rgba(203, 120, 92, 0.7); }}
                            }}
                            @keyframes spin {{ 100% {{ transform: rotate(360deg); }} }}
                        `;
            D.head.appendChild(styleEl);
            debugLog("✅ CSS样式已注入父页面");
        }}
        // 标记归属，避免旧实例 cleanup 误删
        try {{
            styleEl.dataset.stxOwner = INSTANCE_ID;
        }} catch (e) {{}}

        // ========== 3. 在父页面创建悬浮按钮 ==========
        const POPUP_ID = "__stx_fsel_popup_" + CHANNEL.replace(/[^a-zA-Z0-9]/g, '_');
        const BTN_ID = "__stx_fsel_btn_" + CHANNEL.replace(/[^a-zA-Z0-9]/g, '_');

        // ========== SVG 图标常量（液态玻璃方案 E） ==========
        const SVG_VOLUME = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>';
        const SVG_ZAP = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>';
        const SVG_VOLUME1 = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>';
        const SVG_LOADER = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation: spin 2s linear infinite;"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>';
        const SVG_DOLLAR = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 18V6"/></svg>';
        const SVG_X = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';

        let popup = D.getElementById(POPUP_ID);
        if (!popup) {{
            popup = D.createElement("div");
            popup.id = POPUP_ID;
            popup.innerHTML = `<button id="${{BTN_ID}}">${{SVG_VOLUME}} 播放</button>`;
            D.body.appendChild(popup);
            debugLog("✅ 悬浮按钮已注入父页面body");
        }}
        // 标记归属（旧实例 cleanup 不会误删）
        try {{
            popup.dataset.stxOwner = INSTANCE_ID;
        }} catch (e) {{}}

        // 自愈：如果 button 意外缺失，重新生成
        let btn = D.getElementById(BTN_ID);
        if (!btn) {{
            popup.innerHTML = `<button id="${{BTN_ID}}">${{SVG_VOLUME}} 播放</button>`;
            btn = D.getElementById(BTN_ID);
        }}
        if (!btn) {{
            debugLog("❌ 未找到播放按钮元素，终止初始化");
            return;
        }}

// ========== 4. 缓存检测函数 ==========
        const CACHE_PREFIX = "tts_audio_";
        const PRONUNCIATION = {pronunciation!r};  // 从 Python 传入的发音偏好
        const VOICE = PRONUNCIATION === "uk" ? "fable" : "alloy";  // uk=fable(英式), us=alloy(美式)

        function getCacheKey(text, voice) {{
            return CACHE_PREFIX + btoa(encodeURIComponent(text.substring(0, 100) + '|' + voice)).substring(0, 50);
        }}

        // ✨ 使用 postMessage 询问播放器是否有缓存
        const cacheStatusCache = {{}}; // 本地缓存询问结果

        function checkCacheViaPostMessage(text) {{
            const key = getCacheKey(text, VOICE);

            // 检查本地缓存的询问结果
            if (cacheStatusCache[key] !== undefined) {{
                debugLog(`📋 使用缓存的询问结果: ${{cacheStatusCache[key] ? '已缓存' : '未缓存'}}`);
                return cacheStatusCache[key];
            }}

            // 通过 postMessage 询问播放器
            if (playerWin) {{
                playerWin.postMessage({{
                    type: 'CHECK_CACHE',
                    channel: CHANNEL,
                    text: text,
                    timestamp: Date.now()
                }}, playerOrigin || '*');
                debugLog('📤 已发送缓存检查请求');
            }}

            return false; // 默认未缓存
        }}

        function getCachedAudio(text) {{
            return checkCacheViaPostMessage(text);
        }}

        // ========== 5. 监听父页面的文本选择 ==========
        let selectedText = "";
        let selectionRect = null;

        function showFloatingButton(sel) {{
            const range = sel.getRangeAt(0);
            let rect = range.getBoundingClientRect();

            debugLog(`📍 原始range位置: left=${{rect.left}}, top=${{rect.top}}, width=${{rect.width}}, height=${{rect.height}}`);

            // ✨ 检测是否在input/textarea中（这些元素的range.getBoundingClientRect返回全0）
            let targetElement = null;
            let isInputOrTextarea = false;
            let inputElement = null;
            try {{
                const container = range.commonAncestorContainer;
                targetElement = container.nodeType === 3 ? container.parentNode : container;

                debugLog(`🔍 检测到容器元素: ${{targetElement ? targetElement.tagName : 'null'}} (nodeType: ${{container.nodeType}})`);

                // 🔍 向上查找父元素链，检查是否在input/textarea中
                let element = targetElement;
                let depth = 0;
                debugLog(`🔍 开始遍历父元素链...`);
                while (element && element !== W.document.body) {{
                    debugLog(`  层级${{depth}}: ${{element.tagName}} (class: ${{element.className || 'none'}})`);
                    if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {{
                        inputElement = element;
                        isInputOrTextarea = true;
                        debugLog(`🎯 在父元素链中找到${{element.tagName}}`);
                        break;
                    }}
                    element = element.parentElement;
                    depth++;
                    if (depth > 10) {{
                        debugLog(`⚠️ 遍历深度超过10层，停止查找`);
                        break;
                    }}
                }}

                // 🔍 如果父元素链中没找到，尝试在容器内部查找子元素
                if (!isInputOrTextarea && targetElement) {{
                    debugLog(`🔍 在容器内部查找INPUT/TEXTAREA子元素...`);
                    const foundInput = targetElement.querySelector('input, textarea');
                    if (foundInput) {{
                        inputElement = foundInput;
                        isInputOrTextarea = true;
                        debugLog(`🎯 在容器内部找到${{foundInput.tagName}}`);
                    }} else {{
                        debugLog(`❌ 容器内部也没有找到INPUT/TEXTAREA`);
                    }}
                }}

                // 如果在input或textarea中，使用元素本身的位置
                if (isInputOrTextarea && inputElement) {{
                    const oldRect = rect;
                    rect = inputElement.getBoundingClientRect();
                    debugLog(`⚠️ 检测到${{inputElement.tagName}}，替换位置:`);
                    debugLog(`   旧位置: left=${{oldRect.left}}, top=${{oldRect.top}}`);
                    debugLog(`   新位置: left=${{rect.left}}, top=${{rect.top}}, width=${{rect.width}}, height=${{rect.height}}`);
                }}
            }} catch (e) {{
                debugLog(`❌ 检测input/textarea失败: ${{e.message}}`);
            }}

            // ✨ 检测选择来自父页面还是iframe
            const isParentSelection = sel === (W.getSelection && W.getSelection());
            const scrollX = isParentSelection ? W.scrollX : window.scrollX;
            const scrollY = isParentSelection ? W.scrollY : window.scrollY;
            const innerWidth = isParentSelection ? W.innerWidth : window.innerWidth;

            // ✨ 如果是iframe内部的选择，需要转换为父页面坐标
            let actualLeft = rect.left + scrollX;
            let actualTop = rect.top + scrollY;

            if (!isParentSelection) {{
                // iframe内部选择，需要加上iframe相对于父页面的偏移
                const iframeRect = window.frameElement.getBoundingClientRect();
                actualLeft += iframeRect.left + W.scrollX;
                actualTop += iframeRect.top + W.scrollY;
            }}

            selectionRect = {{
                left: actualLeft,
                top: actualTop,
                right: actualLeft + rect.width,
                bottom: actualTop + rect.height,
                width: rect.width,
                height: rect.height
            }};

            const popupWidth = 220;
            const popupHeight = 60;

            let left, top;
            if (isIOS) {{
                // 🍎 iOS: 固定在右侧边偏左，Y坐标跟随选中文本中心（避免与系统菜单和翻译按钮冲突）
                left = W.innerWidth - popupWidth - 144;  // 距离右边 144px（给翻译按钮留出空间）
                top = Math.max(60, Math.min(
                    selectionRect.top + selectionRect.height / 2 - popupHeight / 2 - 160,
                    W.innerHeight - popupHeight - 16
                ));
                debugLog(`🍎 [iOS] 播放按钮右侧边定位: left=${{left}}px, top=${{top}}px`);
            }} else {{
                // 其他设备：放在选中文本下方居中
                left = Math.max(8, Math.min(
                    selectionRect.left + selectionRect.width / 2 - popupWidth / 2,
                    W.innerWidth - popupWidth - 8
                ));
                top = Math.min(selectionRect.bottom + 8, W.innerHeight - popupHeight - 8);
                debugLog(`✅ 最终按钮位置: left=${{left}}px, top=${{top}}px (selectionRect.top=${{selectionRect.top}}, selectionRect.left=${{selectionRect.left}})`);
            }}

            popup.style.left = left + "px";
            popup.style.top = top + "px";
            popup.style.display = "block";
            popup.style.opacity = "1";
        }}

        function updateSelection() {{
            // ✨ 尝试从父页面和iframe内部获取选择
            let sel = W.getSelection && W.getSelection();
            let selectedFromParent = sel && sel.toString().trim();

            // 如果父页面没有选择，尝试从iframe内部获取
            if (!selectedFromParent) {{
                sel = window.getSelection && window.getSelection();
            }}

            selectedText = sel ? (sel.toString() || "").trim() : "";

            if (selectedText && sel && sel.rangeCount > 0) {{
                showFloatingButton(sel);

                // ✨ 检测缓存状态并更新按钮样式
                const cached = getCachedAudio(selectedText);
                if (cached) {{
                    btn.className = btn.id + ' cached';
                    btn.innerHTML = SVG_ZAP + ' 播放（已缓存）';
                    debugLog(`⚡ 检测到缓存`);
                }} else {{
                    btn.className = btn.id;
                    btn.innerHTML = SVG_VOLUME + ' 播放';
                    debugLog(`📝 未缓存`);
                }}

                debugLog(`选中文本: "${{selectedText.substring(0, 50)}}..." (来源: ${{selectedFromParent ? '父页面' : 'iframe内部'}})`);
            }} else {{
                // 🔧 iOS Safari 修复：如果正在生成音频，不隐藏 popup
                // iOS Safari 特有行为：触摸按钮会清除选择，但我们需要保持 popup 显示状态
                if (isGeneratingAudio) {{
                    debugLog(`🔒 选择为空但正在生成音频，保持popup显示`);
                }} else {{
                    debugLog(`选择为空，隐藏popup`);
                    popup.style.display = "none";
                }}
            }}
        }}

        // 在父页面document添加事件监听器
        // 🔧 iOS Safari 兼容：使用 selectionchange 事件（mouseup 在 iOS 文本选择后不触发）
        D.addEventListener("selectionchange", () => {{
            // selectionchange 会频繁触发，使用防抖
            clearTimeout(W.__stx_fsel_debounce);
            W.__stx_fsel_debounce = setTimeout(updateSelection, 100);
        }}, {{ signal: listenerSignal }});
        
        // 保留 mouseup 用于桌面浏览器的快速响应
        D.addEventListener("mouseup", () => {{
            setTimeout(updateSelection, 10);
        }}, {{ signal: listenerSignal }});

        D.addEventListener("keyup", (e) => {{
            if (e.key === "Escape") {{
                popup.style.display = "none";
            }}
        }}, {{ signal: listenerSignal }});

        D.addEventListener("mousedown", (e) => {{
            if (!popup.contains(e.target)) {{
                popup.style.display = "none";
            }}
        }}, {{ signal: listenerSignal }});

        // ✨ 同时在iframe内部添加监听器（监听iframe内部的文本选择）
        document.addEventListener("mouseup", () => {{
            setTimeout(updateSelection, 10);
        }}, {{ signal: listenerSignal }});

        document.addEventListener("keyup", (e) => {{
            if (e.key === "Escape") {{
                popup.style.display = "none";
            }}
        }}, {{ signal: listenerSignal }});

        // 🔥 滚动时隐藏按钮（除非正在生成音频）
        D.addEventListener("scroll", () => {{
            if (popup.style.display === "block") {{
                if (!isGeneratingAudio) {{
                    popup.style.display = "none";
                    debugLog("📜 滚动时隐藏播放按钮");
                }} else {{
                    debugLog("⏳ 音频生成中，保持播放按钮显示");
                }}
            }}
        }}, {{ capture: true, signal: listenerSignal }});

        debugLog("✅ 事件监听器已安装到父页面");

        // ========== 5. 与播放器iframe建立postMessage通信 ==========
        let playerWin = null;
        let playerOrigin = "*";
        let playerConnected = false;  // ✨ 防止重复显示连接消息
        let isGeneratingAudio = false;  // 🔥 追踪音频生成状态

        // 监听播放器消息（READY + STATUS + AUDIO_GENERATING）
        W.addEventListener("message", (evt) => {{
            try {{
                const data = evt.data || {{}};

                // 播放器就绪消息
                if (data.type === "PLAYER_READY" && data.channel === CHANNEL) {{
                    playerWin = evt.source;
                    playerOrigin = evt.origin;
                    debugLog(`✅ 播放器已就绪，origin=${{playerOrigin}}，心跳#${{data.heartbeat || 0}}`);

                    // ✨ 只在首次连接时显示消息和发送ACK
                    if (!playerConnected) {{
                        statusDiv.innerHTML += "<br>✅ 播放器已连接";
                        playerConnected = true;

                        // 🔥 发送ACK通知播放器停止心跳
                        try {{
                            playerWin.postMessage({{
                                type: "PLAYER_READY_ACK",
                                channel: CHANNEL,
                                timestamp: Date.now()
                            }}, playerOrigin);
                            debugLog(`📤 已发送ACK给播放器`);
                        }} catch (e) {{
                            debugLog(`❌ 发送ACK失败: ${{e.message}}`);
                        }}
                    }}
                }}

                // 🔥 音频生成状态消息（监听播放器状态）
                if (data.type === "PLAYER_STATUS" && data.channel === CHANNEL) {{
                    if (data.status === 'GENERATING') {{
                        isGeneratingAudio = true;
                        debugLog(`🎵 音频生成中...`);
                    }} else if (data.status === 'PLAYING') {{
                        isGeneratingAudio = false;
                        debugLog(`🎵 音频生成完成，开始播放`);
                    }}
                }}

                // ✨ 缓存状态响应消息
                if (data.type === "CACHE_STATUS" && data.channel === CHANNEL) {{
                    const key = getCacheKey(data.text, VOICE);
                    cacheStatusCache[key] = data.cached;
                    debugLog(`📨 收到缓存状态: ${{data.cached ? '已缓存' : '未缓存'}}`);

                    // 更新当前显示的按钮
                    if (selectedText === data.text && popup.style.display === "block") {{
                        if (data.cached) {{
                            btn.className = btn.id + ' cached';
                            btn.innerHTML = SVG_ZAP + ' 播放（已缓存）';
                        }} else {{
                            btn.className = btn.id;
                            btn.innerHTML = SVG_VOLUME + ' 播放';
                        }}
                    }}
                }}

                // ✨ 播放器状态更新消息
                if (data.type === "PLAYER_STATUS" && data.channel === CHANNEL) {{
                    debugLog(`📨 收到状态: ${{data.status}}`);

                    // ✨ 如果是 PLAYING 状态，更新缓存状态（新生成的会被缓存）
                    // 🔧 使用消息中的 text 而不是 selectedText，避免 selectedText 被清空的问题
                    if (data.status === "PLAYING" && !data.cached && data.text) {{
                        const key = getCacheKey(data.text, VOICE);
                        cacheStatusCache[key] = true;  // 新生成的内容已被缓存
                        debugLog('✨ 更新缓存状态：新内容已缓存');
                    }}

                    // 更新按钮状态
                    if (popup.style.display === "block") {{
                        if (data.status === "GENERATING") {{
                            btn.className = btn.id + ' processing';
                            btn.innerHTML = SVG_LOADER + ' 生成中...';
                        }} else if (data.status === "PLAYING") {{
                            btn.className = btn.id + ' playing';
                            if (data.cached) {{
                                btn.innerHTML = SVG_ZAP + ' 缓存播放中...';
                            }} else {{
                                btn.innerHTML = SVG_VOLUME1 + ' 播放中...';
                            }}

                            // 播放开始后3秒自动隐藏按钮
                            setTimeout(() => {{
                                popup.style.display = "none";
                                btn.className = btn.id;
                            }}, 3000);
                        }} else if (data.status === "COMPLETED") {{
                            // 播放完成，隐藏按钮
                            popup.style.display = "none";
                            btn.className = btn.id;
                        }} else if (data.status === "CREDIT_REQUIRED" || data.status === "SUBSCRIPTION_REQUIRED") {{
                            // [修改 - 余额制改造 2026-01-20] 余额不足（滚动时隐藏，与翻译按钮保持一致）
                            isGeneratingAudio = false;  // 重置状态，允许滚动时隐藏
                            btn.className = btn.id + ' credit-required';
                            btn.innerHTML = SVG_DOLLAR + ' 请充值';
                            debugLog('💰 余额不足，请充值');
                            // [已注释 - 余额制改造] 原订阅检查逻辑
                            // btn.className = btn.id + ' subscription-required';
                            // btn.innerHTML = '🔒 需要会员解锁';
                            // debugLog('🔒 TTS 功能需要会员订阅');
                        }}
                    }}
                }}
            }} catch (e) {{
                debugLog("处理消息失败: " + e.message);
            }}
        }}, {{ signal: listenerSignal }});

        // ========== 6. 点击按钮发送选中文本 ==========
        btn.addEventListener("click", async () => {{
            // 💰 [修改 - 余额制改造 2026-01-20] 检测是否是"请充值"状态，直接跳转充值页面
            if (btn.classList.contains('credit-required') || btn.classList.contains('subscription-required')) {{
                debugLog("💰 检测到需要充值状态，跳转充值页面");
                window.open('/pricing', '_blank');
                popup.style.display = "none";
                return;
            }}

            if (!selectedText) {{
                debugLog("⚠️ 没有选中文本");
                return;
            }}

            if (!playerWin) {{
                alert("⚠️ 播放器未就绪\\n\\n请确认播放器组件已加载。");
                debugLog("❌ playerWin为空，无法发送消息");
                return;
            }}

            // 🔧 iOS Safari 修复：立即设置 isGeneratingAudio，防止触摸清除选择时隐藏 popup
            // iOS Safari 特有行为：触摸任何元素会立即清除文本选择，触发 selectionchange
            isGeneratingAudio = true;
            debugLog("🔒 已设置 isGeneratingAudio=true（iOS Safari 兼容）");

            try {{
                const message = {{
                    type: "SELECTION",
                    channel: CHANNEL,
                    text: selectedText,
                    rect: selectionRect,
                    timestamp: Date.now()
                }};

                playerWin.postMessage(message, playerOrigin || "*");
                debugLog(`✅ 已发送消息: ${{selectedText.substring(0, 50)}}...`);

                // 保持按钮可见，状态将由播放器的 postMessage 更新
                // 不再清空 selectedText，这样用户可以看到实时状态
            }} catch (e) {{
                alert("发送失败: " + e.message);
                debugLog("❌ postMessage失败: " + e.message);
                isGeneratingAudio = false;  // 🔧 重置状态
                btn.className = btn.id;
                btn.innerHTML = SVG_X + ' 发送失败';
                setTimeout(() => {{
                    btn.innerHTML = SVG_VOLUME + ' 播放';
                    popup.style.display = "none";
                }}, 2000);
            }}
        }}, {{ signal: listenerSignal }});

        debugLog("🎉 全页选择监听器初始化完成");

        // ========== 7. 页面卸载时清理父页面元素 ==========
        function cleanupParentElements() {{
            try {{
                // ✅ 只清理当前 iframe 实例自己的监听器
                controller.abort();
                debugLog('🧹 已清理本实例事件监听器');

                // ✅ 只有“仍然是最新实例”时，才移除 DOM（避免误删新实例）
                const reg = W[REGISTRY_KEY] && W[REGISTRY_KEY][SAFE_CHANNEL];
                if (!reg || reg.id !== INSTANCE_ID) {{
                    debugLog('🧹 跳过 DOM 清理：已存在更新实例');
                    return;
                }}

                // 解除注册（防止内存泄露）
                try {{
                    delete W[REGISTRY_KEY][SAFE_CHANNEL];
                }} catch (e) {{}}

                // 清理悬浮按钮（仅当 owner 匹配）
                const parentPopup = D.getElementById(POPUP_ID);
                if (parentPopup && parentPopup.dataset && parentPopup.dataset.stxOwner === INSTANCE_ID) {{
                    parentPopup.remove();
                    debugLog('✅ 已清理父页面的播放按钮');
                }}

                // 清理CSS样式（仅当 owner 匹配）
                const parentCSS = D.getElementById(CSS_ID);
                if (parentCSS && parentCSS.dataset && parentCSS.dataset.stxOwner === INSTANCE_ID) {{
                    parentCSS.remove();
                    debugLog('✅ 已清理父页面的CSS样式');
                }}
            }} catch (e) {{
                debugLog('清理失败: ' + e.message);
            }}
        }}

        // 监听页面卸载事件
        // 🍎 iOS Safari 修复：pagehide 事件在多页面应用首次加载时可能误触发
        // 导致组件初始化后立即被清理，悬浮按钮无法显示
        // 解决方案：iOS 上使用 visibilitychange + 延迟双重检查（复用上方已定义的 isIOS 变量）
        if (isIOS) {{
            // iOS: 使用 visibilitychange 代替 pagehide，并添加延迟检查
            D.addEventListener('visibilitychange', () => {{
                if (D.visibilityState === 'hidden') {{
                    // 延迟100ms后再次检查，避免首次加载时的误触发
                    setTimeout(() => {{
                        if (D.visibilityState === 'hidden') {{
                            cleanupParentElements();
                        }} else {{
                            debugLog('🍎 [iOS] 页面重新可见，跳过清理');
                        }}
                    }}, 100);
                }}
            }});
            debugLog('✅ 已注册页面卸载清理监听器（iOS 优化模式）');
        }} else {{
            // 非iOS: 保持原有行为
            window.addEventListener('pagehide', cleanupParentElements);
            window.addEventListener('beforeunload', cleanupParentElements);
            debugLog('✅ 已注册页面卸载清理监听器');
        }}
    }})();
    </script>
</body>
</html>
"""

    components.html(html_code, height=height, scrolling=False)


if __name__ == "__main__":
    import streamlit as st

    st.set_page_config(page_title="悬浮选择工具测试", layout="wide")
    st.title("🎯 悬浮选择工具测试")

    st.markdown("""
    ### 测试说明

    这个组件会在Streamlit父页面上安装文本选择监听器。

    **技术验证：**
    - ✅ iframe访问 `window.parent.document`（需要`allow-same-origin`）
    - ✅ 在父页面添加事件监听器
    - ✅ 在父页面body注入悬浮按钮
    """)

    mount_floating_selector(channel="test-001", debug=True)

    st.markdown("---")
    st.markdown("""
    ### 测试内容

    **请选择下方任意文本**，松开鼠标后会弹出"🔊 播放"按钮。

    > Technology is best when it brings people together. The advance of technology is based on making it fit in so that you don't really even notice it, so it's part of everyday life.

    Innovation distinguishes between a leader and a follower. The only way to discover the limits of the possible is to go beyond them into the impossible.
    """)
