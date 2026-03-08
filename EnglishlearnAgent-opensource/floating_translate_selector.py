"""
全页翻译选择工具
================

功能：在Streamlit父页面上监听文本选择，点击翻译按钮后发送到聊天对话框

技术原理：
- 参考 floating_selector_tool.py 的实现（TTS选择器）
- 在父页面document上注入事件监听器和悬浮翻译按钮
- 通过postMessage将翻译请求发送给聊天对话框
- 单词：发送 "{word}是什么意思，美国人口语中一般什么时候会使用{word}？"
- 多词：发送 "{text}仅翻译为中文（用自然口语表达）"
"""

import streamlit.components.v1 as components


def mount_translate_selector(channel: str = "translate-chat", debug: bool = False, height: int = 0):
    """
    在父页面挂载全页选中监听 + 悬浮翻译按钮

    参数：
        channel: 通道名称，用于与聊天组件配对
        debug: 是否开启调试模式（在console输出详细日志）
        height: iframe高度（px），设置为0完全隐藏（默认0）

    工作原理：
        1. iframe访问 window.parent.document（需要allow-same-origin）
        2. 在父页面document添加mouseup监听器
        3. 在父页面body注入悬浮翻译按钮
        4. 监听父页面的getSelection()
        5. 点击翻译按钮后，通过postMessage发送到聊天组件
    """

    debug_code = """
        function debugLog(msg) {
            console.log(`[Translate-Selector][${CHANNEL}] ${msg}`);
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
    <div id="status" style="display:none;">Translate Selector Ready</div>

    <script>
    (function() {{
        const CHANNEL = {channel!r};
        {debug_code}

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
            }}
        }} catch (e) {{
            debugLog("❌ 无法访问父页面document: " + e.message);
        }}

        if (!PARENT_OK) {{
            debugLog("无法访问父页面，终止");
            return;
        }}

        // 🍎 iOS 设备检测（在 IIFE 顶层定义，供整个脚本使用）
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
                      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

        // ========== 1.5 AbortController 管理事件监听器 ==========
        // ✅ 关键修复：避免旧 iframe 的 unload 清理“误伤”新实例
        // 原因：Streamlit rerun 期间，新 iframe 可能先执行并把全局 controller 覆盖，
        //      旧 iframe 后触发 cleanupParentElements() 时如果再去 abort 全局 controller，
        //      就会把新实例的监听器也 abort 掉，导致按钮“消失”。

        const SAFE_CHANNEL = CHANNEL.replace(/[^a-zA-Z0-9]/g, '_');
        const REGISTRY_KEY = "__stx_translate_selector_registry";
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

        // 创建新的 AbortController（本地变量 + 注册到 registry）
        const controller = new AbortController();
        W[REGISTRY_KEY][SAFE_CHANNEL] = {{ id: INSTANCE_ID, controller }};
        const listenerSignal = controller.signal;
        debugLog("✅ AbortController 已创建 (instance=" + INSTANCE_ID + ")");

        // ========== 2. 在父页面注入CSS样式 ==========
        const CSS_ID = "__stx_translate_css_" + CHANNEL.replace(/[^a-zA-Z0-9]/g, '_');
        let styleEl = D.getElementById(CSS_ID);
        if (!styleEl) {{
            styleEl = D.createElement("style");
            styleEl.id = CSS_ID;
            styleEl.textContent = `
                            #__stx_translate_popup_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}} {{
                                position: absolute;
                                display: none;
                                z-index: 2147483647;
                                background: transparent;
                                transition: opacity 0.2s ease;
                            }}
                            #__stx_translate_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}} {{
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
                            #__stx_translate_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}::after {{
                                content: '';
                                position: absolute;
                                top: 0; left: -100%; width: 50%; height: 100%;
                                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent);
                                transform: skewX(-20deg);
                                transition: 0.6s ease;
                            }}
                            #__stx_translate_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}:hover {{
                                background: rgba(203, 120, 92, 1);
                                box-shadow: 0 6px 20px rgba(203, 120, 92, 0.4);
                            }}
                            #__stx_translate_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}:hover::after {{
                                left: 150%;
                            }}
                            #__stx_translate_btn_${{CHANNEL.replace(/[^a-zA-Z0-9]/g, '_')}}:active {{
                                transform: scale(0.95);
                            }}
                        `;
            D.head.appendChild(styleEl);
            debugLog("✅ CSS样式已注入父页面");
        }}
        // 标记归属，避免旧实例 cleanup 误删
        try {{
            styleEl.dataset.stxOwner = INSTANCE_ID;
        }} catch (e) {{}}

        // ========== 3. 在父页面创建悬浮翻译按钮 ==========
        const POPUP_ID = "__stx_translate_popup_" + CHANNEL.replace(/[^a-zA-Z0-9]/g, '_');
        const BTN_ID = "__stx_translate_btn_" + CHANNEL.replace(/[^a-zA-Z0-9]/g, '_');

        // ========== SVG 图标（液态玻璃方案 E） ==========
        const SVG_TRANSLATE = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg>';

        let popup = D.getElementById(POPUP_ID);
        if (!popup) {{
            popup = D.createElement("div");
            popup.id = POPUP_ID;
            popup.innerHTML = `<button id="${{BTN_ID}}">${{SVG_TRANSLATE}} 翻译</button>`;
            D.body.appendChild(popup);
            debugLog("✅ 悬浮翻译按钮已注入父页面body");
        }}
        // 标记归属（旧实例 cleanup 不会误删）
        try {{
            popup.dataset.stxOwner = INSTANCE_ID;
        }} catch (e) {{}}

        // 自愈：如果 button 意外缺失，重新生成
        let btn = D.getElementById(BTN_ID);
        if (!btn) {{
            popup.innerHTML = `<button id="${{BTN_ID}}">${{SVG_TRANSLATE}} 翻译</button>`;
            btn = D.getElementById(BTN_ID);
        }}
        if (!btn) {{
            debugLog("❌ 未找到翻译按钮元素，终止初始化");
            return;
        }}


// ========== 4. 判断是单词还是多词 ==========
        function countWords(text) {{
            // 移除前后空格，按空格分割
            const trimmed = text.trim();
            if (!trimmed) return 0;

            // 按空格、标点符号分割
            const words = trimmed.split(/[\\s,;.!?]+/).filter(w => w.length > 0);
            return words.length;
        }}

        function buildTranslateMessage(text) {{
            const wordCount = countWords(text);
            const cleanText = text.trim();

            if (wordCount === 1) {{
                // 单词：询问意思和使用场景
                return `${{cleanText}}是什么意思，美国人口语中一般什么时候会使用${{cleanText}}？`;
            }} else {{
                // 多词：仅翻译为中文（用自然口语表达）
                return `仅翻译为中文（用自然口语表达）：${{cleanText}}`;
            }}
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

            // 检测选择来自父页面还是iframe
            const isParentSelection = sel === (W.getSelection && W.getSelection());
            const scrollX = isParentSelection ? W.scrollX : window.scrollX;
            const scrollY = isParentSelection ? W.scrollY : window.scrollY;

            // 计算实际位置
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

            const popupWidth = 120;
            const popupHeight = 50;

            let left, top;
            if (isIOS) {{
                // 🍎 iOS: 固定在右侧边，Y坐标跟随选中文本中心（避免与系统菜单冲突）
                left = W.innerWidth - popupWidth - 16;  // 距离右边 16px
                top = Math.max(60, Math.min(
                    selectionRect.top + selectionRect.height / 2 - popupHeight / 2 - 160,
                    W.innerHeight - popupHeight - 16
                ));
                debugLog(`🍎 [iOS] 右侧边定位: left=${{left}}px, top=${{top}}px`);
            }} else {{
                // ✨ 其他设备：翻译按钮放在选中文本的右下方（避免与TTS按钮重叠）
                left = Math.min(
                    selectionRect.right + 8,
                    W.innerWidth - popupWidth - 8
                );
                top = Math.min(selectionRect.bottom + 8, W.innerHeight - popupHeight - 8);
                debugLog(`✅ 最终按钮位置: left=${{left}}px, top=${{top}}px (selectionRect.top=${{selectionRect.top}}, selectionRect.right=${{selectionRect.right}})`);
            }}

            popup.style.left = left + "px";
            popup.style.top = top + "px";
            popup.style.display = "block";
            popup.style.opacity = "1";
        }}

        function updateSelection() {{
            const sel = W.getSelection();
            if (sel && sel.rangeCount > 0) {{
                const text = sel.toString().trim();
                if (text && text.length > 0) {{
                    selectedText = text;
                    debugLog(`选中文本: "${{text}}" (词数: ${{countWords(text)}})`);
                    showFloatingButton(sel);
                }} else {{
                    hidePopup();
                }}
            }} else {{
                hidePopup();
            }}
        }}

        function hidePopup() {{
            popup.style.display = "none";
            selectedText = "";
        }}

        // ========== 6. 添加事件监听器 ==========
        // 🔧 iOS Safari 兼容：使用 selectionchange 事件（mouseup 在 iOS 文本选择后不触发）
        D.addEventListener('selectionchange', () => {{
            // selectionchange 会频繁触发，使用防抖
            clearTimeout(W.__stx_translate_debounce);
            W.__stx_translate_debounce = setTimeout(updateSelection, 100);
        }}, {{ signal: listenerSignal }});
        
        // 保留 mouseup 用于桌面浏览器的快速响应
        D.addEventListener('mouseup', (e) => {{
            // 延迟执行，确保selection已更新
            setTimeout(() => {{
                // 检查点击是否在按钮上
                if (e.target === btn || btn.contains(e.target)) {{
                    return; // 不隐藏popup
                }}
                updateSelection();
            }}, 10);
        }}, {{ signal: listenerSignal }});

        // 按下ESC键隐藏popup
        D.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') {{
                hidePopup();
            }}
        }}, {{ signal: listenerSignal }});

        // 🔥 滚动时隐藏按钮并广播消息给其他组件
        D.addEventListener('scroll', () => {{
            if (popup.style.display === 'block') {{
                // position: absolute + 文档坐标不需要更新位置
                // 但可以选择在滚动时隐藏按钮
                popup.style.display = 'none';
                debugLog(`📜 滚动时隐藏翻译按钮`);
            }}

            // 🔥 广播滚动事件给所有iframe（包括播放按钮组件）
            try {{
                const msg = {{
                    type: 'PARENT_SCROLL_EVENT',
                    scrollY: W.scrollY,
                    scrollX: W.scrollX,
                    timestamp: Date.now()
                }};
                W.postMessage(msg, '*');
                // debugLog(`📡 已广播滚动事件: scrollY=${{W.scrollY}}`);  // 暂时注释，减少日志输出
            }} catch(e) {{
                debugLog(`❌ 广播滚动事件失败: ${{e.message}}`);
            }}
        }}, {{ capture: true, signal: listenerSignal }});

        // ========== 7. 监听AI busy状态（禁用翻译按钮）==========
        let isAIBusy = false;

        // 🔥 辅助函数：更新按钮状态
        function updateButtonState(busy) {{
            isAIBusy = busy;
            if (busy) {{
                btn.disabled = true;
                btn.style.opacity = '0.5';
                btn.style.cursor = 'not-allowed';
                btn.title = '⏳ AI正在回复中，请稍候...';
            }} else {{
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.style.cursor = 'pointer';
                btn.title = '点击翻译选中的文本';
            }}
        }}

        W.addEventListener('message', (event) => {{
            // 监听来自聊天组件的busy状态广播
            if (event.data && event.data.type === 'AI_BUSY_STATUS') {{
                debugLog(`🔔 收到busy状态更新: ${{event.data.busy}}`);
                updateButtonState(event.data.busy);
            }}
        }}, {{ signal: listenerSignal }});

        // 🔥 初始化时检查输入框状态（防止组件重新渲染后状态丢失）
        setTimeout(() => {{
            try {{
                const chatInput = D.getElementById('__stx_chat_input_fastapi');
                if (chatInput && chatInput.disabled) {{
                    debugLog("🔍 检测到AI正在回复中，禁用翻译按钮");
                    updateButtonState(true);
                }} else {{
                    debugLog("🔍 AI未回复，翻译按钮可用");
                }}
            }} catch(e) {{
                debugLog(`检查输入框状态失败: ${{e.message}}`);
            }}
        }}, 200);  // 延迟200ms确保聊天组件已初始化

        // ========== 8. 翻译按钮点击事件 ==========
        btn.addEventListener('click', () => {{
            // 🔥 检查AI是否正忙
            if (isAIBusy) {{
                debugLog("⏳ AI正在回复中，忽略点击");
                return;
            }}

            if (!selectedText) {{
                debugLog("没有选中文本");
                return;
            }}

            const message = buildTranslateMessage(selectedText);
            debugLog(`发送翻译请求: "${{message}}"`);

            // 🔑 通过postMessage发送到聊天组件
            W.postMessage({{
                type: 'TRANSLATE_REQUEST',
                channel: CHANNEL,
                text: selectedText,
                message: message,
                timestamp: Date.now()
            }}, '*');

            hidePopup();
        }}, {{ signal: listenerSignal }});

        // ========== 9. 初始化完成 ==========
        debugLog("🎉 翻译选择器初始化完成");

        // ========== 10. 页面卸载时清理父页面元素 ==========
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

                // 清理悬浮翻译按钮（仅当 owner 匹配）
                const parentPopup = D.getElementById(POPUP_ID);
                if (parentPopup && parentPopup.dataset && parentPopup.dataset.stxOwner === INSTANCE_ID) {{
                    parentPopup.remove();
                    debugLog('✅ 已清理父页面的翻译按钮');
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

    components.html(html_code, height=height)
