"""
选择文本播放器 V2 - 支持postMessage
=====================================

功能：接收来自floating_selector_tool的选中文本，并自动播放

技术原理（基于Streamlit源代码分析）：
- Streamlit使用srcdoc创建iframe（streamlit/elements/iframe.py:182）
- srcdoc iframe继承父页面的源（同源）
- sandbox包含allow-same-origin（streamlit/static/static/js/index.6xX1278W.js:452）
- 因此可以与其他同源iframe通过postMessage通信

新增功能：
- 监听postMessage消息
- 发送PLAYER_READY握手消息
- 接收SELECTION消息并自动播放

基于：selection_player_component.py（保持所有原有功能不变）
"""

import streamlit.components.v1 as components


def get_player_html(
    api_url: str,
    jwt_token: str,
    cache_size: int = 15,
    channel: str = "gpt-4o-mini-tts",
    enable_postmessage: bool = True,
    show_demo_content: bool = True,
    pronunciation: str = "us"
) -> str:
    """
    生成支持postMessage的TTS播放器HTML

    参数：
        api_url: 后端 TTS API 地址（如 http://localhost:8000/api/tts）
        jwt_token: JWT 认证令牌
        cache_size: LRU缓存大小
        channel: postMessage通道名称（用于多组件隔离）
        enable_postmessage: 是否启用postMessage接收功能
        show_demo_content: 是否显示使用说明和示例文章（默认True）
        pronunciation: 发音偏好 'us'（美式）或 'uk'（英式），默认 'us'
    """

    # postMessage接收器代码
    postmessage_code = f"""
        // ========== postMessage 通信系统 ==========
        const CHANNEL = {channel!r};
        console.log(`[TTS Player V2] 通道: ${{CHANNEL}}`);

        // 步骤1：发送READY消息告诉selector工具"播放器已就绪"
        // 🔥 使用心跳重试机制：每500ms重发一次，持续5秒
        let readyHeartbeatCount = 0;
        const MAX_HEARTBEAT_COUNT = 10;  // 5秒 = 10次 × 500ms

        function sendPlayerReady() {{
            try {{
                if (window.parent && window.parent !== window) {{
                    window.parent.postMessage({{
                        type: "PLAYER_READY",
                        channel: CHANNEL,
                        timestamp: Date.now(),
                        heartbeat: readyHeartbeatCount
                    }}, "*");
                    console.log(`[TTS Player][${{CHANNEL}}] ✅ 已发送PLAYER_READY消息 (心跳 #${{readyHeartbeatCount}})`);
                }}
            }} catch (e) {{
                console.warn("[TTS Player] ⚠️ 无法发送PLAYER_READY:", e.message);
            }}
        }}

        // 立即发送第一次
        sendPlayerReady();

        // 启动心跳定时器
        const readyHeartbeatTimer = setInterval(() => {{
            readyHeartbeatCount++;
            if (readyHeartbeatCount >= MAX_HEARTBEAT_COUNT) {{
                clearInterval(readyHeartbeatTimer);
                console.log(`[TTS Player][${{CHANNEL}}] 🛑 PLAYER_READY心跳已停止（达到最大次数）`);
                return;
            }}
            sendPlayerReady();
        }}, 500);

        // 步骤2：监听SELECTION消息和ACK消息
        window.addEventListener("message", (evt) => {{
            try {{
                const data = evt.data || {{}};

                // 🔥 收到 ACK 后停止心跳
                if (data.type === "PLAYER_READY_ACK" && data.channel === CHANNEL) {{
                    clearInterval(readyHeartbeatTimer);
                    console.log(`[TTS Player][${{CHANNEL}}] ✅ 收到ACK，停止心跳`);
                    return;
                }}

                // ✨ 处理缓存检查请求
                if (data.type === "CHECK_CACHE" && data.channel === CHANNEL) {{
                    const text = data.text;
                    const cached = getCachedAudio(text);
                    const hasCached = !!cached;

                    // 回复缓存状态
                    window.parent.postMessage({{
                        type: 'CACHE_STATUS',
                        channel: CHANNEL,
                        text: text,
                        cached: hasCached,
                        timestamp: Date.now()
                    }}, '*');

                    console.log(`[TTS Player] 📤 回复缓存状态: ${{hasCached ? '已缓存' : '未缓存'}}`);
                    return;
                }}

                // 只处理匹配通道的SELECTION消息
                if (data.type === "SELECTION" && data.channel === CHANNEL) {{
                    const text = (data.text || "").trim();
                    console.log(`[TTS Player][${{CHANNEL}}] 📨 收到选中文本(${{text.length}}字符):`, text.substring(0, 50) + "...");

                    if (!text) {{
                        console.warn("[TTS Player] ⚠️ 收到空文本，忽略");
                        return;
                    }}

                    // 设置选中文本
                    selectedText = text;

                    // 如果有位置信息，更新selectionRect（用于定位播放按钮）
                    if (data.rect) {{
                        selectionRect = data.rect;
                        console.log("[TTS Player] 📍 收到选区位置信息");
                    }}

                    // ✨ 新增：检测缓存并更新按钮样式
                    const cached = getCachedAudio(text);
                    if (cached) {{
                        playBtn.className = 'play-btn cached';
                        btnIcon.innerHTML = SVG_ZAP;
                        btnText.textContent = '播放（已缓存）';
                        console.log('[TTS Player] ⚡ 检测到缓存（postMessage）');
                    }} else {{
                        playBtn.className = 'play-btn';
                        btnIcon.innerHTML = SVG_VOLUME;
                        btnText.textContent = '播放选中内容';
                        console.log('[TTS Player] 📝 未缓存（postMessage）');
                    }}

                    // 短暂显示播放按钮（让用户看到"已缓存"指示器）
                    popup.style.display = 'block';
                    popup.style.left = '50%';
                    popup.style.top = '20px';
                    popup.style.transform = 'translateX(-50%)';

                    // 延迟自动播放，让用户看到缓存状态
                    setTimeout(() => {{
                        console.log("[TTS Player] 🎵 自动触发播放");
                        playBtn.click();
                    }}, 800);  // 显示800ms后自动播放
                }}
            }} catch (e) {{
                console.error("[TTS Player] ❌ 处理消息失败:", e);
            }}
        }});

        console.log(`[TTS Player][${{CHANNEL}}] 🎧 postMessage监听器已安装`);

        // ========== 状态通知函数（通知父页面播放器状态）==========
        function notifyParentStatus(status, data = {{}}) {{
            try {{
                if (window.parent && window.parent !== window) {{
                    window.parent.postMessage({{
                        type: 'PLAYER_STATUS',
                        channel: CHANNEL,
                        status: status,
                        timestamp: Date.now(),
                        ...data
                    }}, '*');
                    console.log(`[TTS Player] 📤 状态通知: ${{status}}`);
                }}
            }} catch (e) {{
                console.warn('[TTS Player] ⚠️ 状态通知失败:', e.message);
            }}
        }}
    """ if enable_postmessage else "console.log('[TTS Player V2] postMessage功能已禁用');"

    html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
            background: {('linear-gradient(135deg, #667eea 0%, #764ba2 100%)' if show_demo_content else 'transparent')};
            padding: {('20px' if show_demo_content else '0')};
            min-height: {('100vh' if show_demo_content else 'auto')};
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: {('white' if show_demo_content else 'transparent')};
            border-radius: {('16px' if show_demo_content else '0')};
            box-shadow: {('0 20px 60px rgba(0,0,0,0.3)' if show_demo_content else 'none')};
            padding: {('30px' if show_demo_content else '0')};
        }}

        h2 {{
            color: #667eea;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 24px;
        }}

        .badge {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}

        .content-area {{
            font-size: 18px;
            line-height: 1.8;
            color: #333;
            padding: 25px;
            background: linear-gradient(to bottom, #f8f9fa, #ffffff);
            border-radius: 12px;
            margin: 20px 0;
            user-select: text;
            cursor: text;
            border: 2px solid #e9ecef;
        }}

        .content-area h3 {{
            color: #764ba2;
            margin-bottom: 15px;
            font-size: 20px;
        }}

        .content-area p {{
            margin-bottom: 15px;
            text-align: justify;
        }}

        .content-area strong {{
            color: #667eea;
            font-weight: 600;
        }}

        /* 播放按钮悬浮窗 */
        .play-popup {{
            position: absolute;
            display: none;
            background: transparent;
            z-index: 1000;
            animation: popupFadeIn 0.2s ease;
        }}

        @keyframes popupFadeIn {{
            from {{
                opacity: 0;
                transform: translateY(-10px) scale(0.95);
            }}
            to {{
                opacity: 1;
                transform: translateY(0) scale(1);
            }}
        }}

        .play-btn {{
            background: rgba(203, 120, 92, 0.85);
            color: #fff;
            border: 1px solid rgba(255, 255, 255, 0.3);
            padding: 10px 18px;
            border-radius: 9999px;
            cursor: pointer;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.4s cubic-bezier(0.25, 1, 0.5, 1);
            font-family: 'Space Grotesk', sans-serif;
            font-size: 14px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 16px rgba(203, 120, 92, 0.3);
        }}

        .play-btn::after {{
            content: '';
            position: absolute;
            top: 0; left: -100%; width: 50%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent);
            transform: skewX(-20deg);
            transition: 0.6s ease;
        }}

        .play-btn:hover {{
            background: rgba(203, 120, 92, 1);
            box-shadow: 0 6px 20px rgba(203, 120, 92, 0.4);
        }}

        .play-btn:hover::after {{
            left: 150%;
        }}

        .play-btn:active {{
            transform: scale(0.95);
        }}

        .play-btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }}

        .play-btn.cached {{
            background: rgba(14, 165, 233, 0.85);
            color: #fff;
            border-color: rgba(14, 165, 233, 0.3);
        }}

        .play-btn.processing {{
            background: rgba(203, 120, 92, 0.85);
            color: #fff;
            cursor: wait;
            border: 1px solid rgba(203, 120, 92, 0.4);
            animation: liquidBreathe 2s ease-in-out infinite;
        }}

        .play-btn.subscription-required {{
            background: rgba(251, 191, 36, 0.15);
            color: #b8860b;
            border-color: rgba(251, 191, 36, 0.3);
            cursor: pointer;
        }}

        .play-btn.subscription-required:hover {{
            background: rgba(251, 191, 36, 0.25);
        }}

        /* [新增 - 余额制改造 2026-01-20] 余额不足样式 */
        .play-btn.credit-required {{
            background: rgba(251, 191, 36, 0.15);
            color: #b8860b;
            border-color: rgba(251, 191, 36, 0.3);
            cursor: pointer;
        }}

        .play-btn.credit-required:hover {{
            background: rgba(251, 191, 36, 0.25);
        }}

        @keyframes liquidBreathe {{
            0%, 100% {{ box-shadow: 0 0 0 0 rgba(203, 120, 92, 0.1); border-color: rgba(203, 120, 92, 0.4); }}
            50% {{ box-shadow: 0 0 12px 4px rgba(203, 120, 92, 0.15); border-color: rgba(203, 120, 92, 0.7); }}
        }}

        /* 音频控制器 - 液态玻璃面板 */
        .audio-controls {{
            position: fixed;
            top: 80px;
            left: 20px;
            background: rgba(255, 255, 255, 0.5);
            backdrop-filter: blur(24px) saturate(150%);
            -webkit-backdrop-filter: blur(24px) saturate(150%);
            border: 1px solid rgba(255, 255, 255, 0.8);
            border-radius: 1.25rem;
            box-shadow: 0 16px 40px rgba(61, 58, 42, 0.08), inset 0 0 0 1px rgba(255, 255, 255, 0.5);
            padding: 0;
            width: 320px;
            z-index: 10001;
            display: none;
            animation: slideInFromLeft 0.3s ease-out;
            color: #3d3a2a;
            overflow: hidden;
        }}

        .audio-controls::before {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(-45deg, #fdfdf8, #f8ebe6, #eef2f6, #fdfdf8);
            z-index: 0;
        }}

        .audio-controls::after {{
            content: '';
            position: absolute;
            width: 160px; height: 160px;
            background: rgba(203, 120, 92, 0.25);
            border-radius: 50%;
            filter: blur(40px);
            top: -40px; left: -20px;
            z-index: 0;
        }}

        .audio-controls.active {{
            display: block;
        }}

        @keyframes slideInFromLeft {{
            from {{
                opacity: 0;
                transform: translateX(-20px);
            }}
            to {{
                opacity: 1;
                transform: translateX(0);
            }}
        }}

        .controls-header {{
            position: relative;
            z-index: 1;
            background: linear-gradient(180deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0) 100%);
            color: #3d3a2a;
            padding: 16px 20px;
            border-radius: 1.25rem 1.25rem 0 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.6);
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: move;
            user-select: none;
        }}

        .controls-title {{
            font-weight: 600;
            font-size: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
            text-shadow: 0 1px 2px rgba(255,255,255,0.8);
        }}

        .recording-dot {{
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #cb785c;
            border-radius: 50%;
            box-shadow: 0 0 8px rgba(203, 120, 92, 0.8);
            animation: pulse-dot 2s infinite;
        }}

        @keyframes pulse-dot {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.5; transform: scale(0.8); }}
        }}

        .close-controls {{
            background: rgba(255, 255, 255, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.8);
            border-radius: 50%;
            width: 28px;
            height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #3d3a2a;
            cursor: pointer;
            font-size: 16px;
            line-height: 1;
            transition: all 0.2s;
        }}

        .close-controls:hover {{
            background: rgba(255, 255, 255, 0.9);
            transform: rotate(90deg);
        }}

        .controls-body {{
            padding: 20px;
            position: relative;
            z-index: 1;
        }}

        .progress-container {{
            margin-bottom: 12px;
        }}

        .progress-bar {{
            width: 100%;
            height: 8px;
            border-radius: 4px;
            outline: none;
            -webkit-appearance: none;
            appearance: none;
            background: rgba(0, 0, 0, 0.05);
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
            cursor: pointer;
            overflow: hidden;
            position: relative;
        }}

        .progress-bar::-webkit-slider-runnable-track {{
            height: 8px;
            border-radius: 4px;
        }}

        .progress-bar::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #cb785c;
            border: 3px solid #fff;
            box-shadow: 0 2px 6px rgba(203, 120, 92, 0.5), -400px 0 0 392px rgba(203, 120, 92, 0.7);
            margin-top: -4px;
            cursor: pointer;
            transition: transform 0.1s;
        }}

        .progress-bar::-webkit-slider-thumb:hover {{
            transform: scale(1.2);
        }}

        .progress-bar::-moz-range-thumb {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #cb785c;
            cursor: pointer;
            border: 3px solid #fff;
            box-shadow: 0 2px 6px rgba(203, 120, 92, 0.5);
        }}

        .time-display {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            font-family: 'Space Mono', monospace;
            color: #555;
            margin-top: 8px;
            font-weight: 500;
        }}

        .control-buttons {{
            display: flex;
            gap: 12px;
            align-items: center;
            margin-top: 16px;
        }}

        .control-btn {{
            flex: 1;
            display: flex;
            gap: 8px;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.4);
            color: #3d3a2a;
            border: 1px solid rgba(255, 255, 255, 0.7);
            border-radius: 9999px;
            padding: 10px 18px;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.25, 1, 0.5, 1);
        }}

        .control-btn:hover {{
            background: rgba(255, 255, 255, 0.7);
            box-shadow: 0 4px 12px rgba(61, 58, 42, 0.05);
            transform: translateY(-1px);
        }}

        .control-btn:active {{
            transform: scale(0.96);
        }}

        .speed-control {{
            background: rgba(255, 255, 255, 0.4);
            border: 1px solid rgba(255, 255, 255, 0.7);
            border-radius: 9999px;
            padding: 10px 18px;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 14px;
            font-weight: 600;
            color: #3d3a2a;
            cursor: pointer;
            outline: none;
            -webkit-appearance: none;
            appearance: none;
            text-align: center;
            transition: all 0.3s cubic-bezier(0.25, 1, 0.5, 1);
        }}

        .speed-control:hover {{
            background: rgba(255, 255, 255, 0.7);
            box-shadow: 0 4px 12px rgba(61, 58, 42, 0.05);
        }}

        .speed-control:focus {{
            box-shadow: 0 0 0 3px rgba(203, 120, 92, 0.15);
        }}

        /* 加载动画 */
        .loading {{
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}

        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}

        /* 状态指示器 */
        .status {{
            padding: 12px 16px;
            border-radius: 8px;
            margin-top: 15px;
            font-size: 14px;
            animation: statusFadeIn 0.3s ease;
        }}

        @keyframes statusFadeIn {{
            from {{ opacity: 0; transform: translateY(-10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .status.info {{
            background: #e3f2fd;
            color: #1976d2;
            border-left: 4px solid #1976d2;
        }}

        .status.success {{
            background: #e8f5e9;
            color: #388e3c;
            border-left: 4px solid #388e3c;
        }}

        .status.error {{
            background: #ffebee;
            color: #d32f2f;
            border-left: 4px solid #d32f2f;
        }}

        .highlight {{
            background: linear-gradient(120deg, #fff9c4 0%, #fff59d 100%);
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
        }}

        .info-box {{
            background: #f0f4ff;
            border: 2px solid #667eea;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        }}

        .info-box strong {{
            color: #667eea;
        }}

        .info-box ol {{
            margin: 8px 0 0 20px;
            line-height: 1.8;
        }}

        .info-box li {{
            margin-bottom: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        {('<h2><span>🎙️</span><span>TTS播放器</span><span class="badge">V2 - postMessage</span></h2>' if show_demo_content else '')}

        {('<div class="info-box"><strong>💡 使用方法：</strong><ol><li>在下方内容区域<strong>选择任意文本</strong></li><li>松开鼠标后会弹出<strong>"🎵 播放选中内容"</strong>按钮</li><li>点击按钮即可朗读选中的文本</li><li>✨ 也可以通过外部选择工具发送文本（postMessage）</li></ol></div>' if show_demo_content else '')}

        {('<div class="content-area"><h3>📖 示例文章：科技与创新</h3>' if show_demo_content else '<div class="content-area" style="display:none;"><h3>📖 示例文章：科技与创新</h3>')}

            <p>
                <strong>Technology</strong> is best when it brings people together.
                The advance of technology is based on making it fit in so that you
                don't really even notice it, so it's part of everyday life. We are
                stuck with technology when what we really want is just stuff that works.
            </p>

            <p>
                <strong>Innovation</strong> distinguishes between a leader and a follower.
                The only way to discover the limits of the possible is to go beyond
                them into the impossible. Innovation is the ability to see change as
                an opportunity, not a threat. It's not about ideas, it's about making
                ideas happen.
            </p>

            <p>
                <strong>Artificial Intelligence</strong> is transforming our world in
                unprecedented ways. From healthcare to education, from transportation
                to entertainment, AI is reshaping every aspect of our daily lives.
                The question is not whether AI will change our future, but how we will
                guide that change to benefit humanity.
            </p>

            <p>
                <strong>The Future of Learning:</strong> Education is no longer confined
                to classrooms. With digital tools and online platforms, knowledge is
                accessible to anyone, anywhere, at any time. This democratization of
                education empowers individuals to pursue their passions and develop
                new skills throughout their lives.
            </p>

            <p>
                Remember: <span class="highlight">The best way to predict the future
                is to invent it.</span> So let's build a future we're proud of, one
                innovation at a time. Success is not final, failure is not fatal: it
                is the courage to continue that counts.
            </p>
        </div>

        <div id="status-message"></div>
    </div>

    <!-- 播放按钮悬浮窗 -->
    <div class="play-popup" id="playPopup">
        <button class="play-btn" id="playBtn">
            <span id="btnIcon"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg></span>
            <span id="btnText">播放选中内容</span>
        </button>
    </div>

    <!-- 音频控制器 - 完整版 -->
    <div class="audio-controls" id="audioControls">
        <div class="controls-header">
            <span class="controls-title"><span class="recording-dot"></span> 音频播放中</span>
            <button class="close-controls" id="closeControls"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></button>
        </div>
        <div class="controls-body">
            <div class="progress-container">
                <input type="range" id="progressBar" class="progress-bar" min="0" max="100" value="0" step="0.1">
                <div class="time-display">
                    <span id="currentTime">0:00</span>
                    <span id="totalTime">0:00</span>
                </div>
            </div>
            <div class="control-buttons">
                <button id="playPauseBtn" class="control-btn"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/></svg> 暂停</button>
                <select id="speedControl" class="speed-control">
                    <option value="0.5">0.5x</option>
                    <option value="0.75">0.75x</option>
                    <option value="1" selected>1x</option>
                    <option value="1.25">1.25x</option>
                    <option value="1.5">1.5x</option>
                    <option value="2">2x</option>
                </select>
            </div>
        </div>
    </div>

    <audio id="audioPlayer"></audio>

    <script>
        // 🔥 脚本开始执行标记
        console.log('[Selection Player V2] 🚀 脚本开始执行');

        // ========== 全局变量 ==========
        const API_URL = {api_url!r};
        const JWT_TOKEN = {jwt_token!r};
        const CACHE_PREFIX = 'tts_cache_v2_';
        const MAX_CACHE_SIZE = {cache_size};
        const PRONUNCIATION = {pronunciation!r};  // 从 Python 传入的发音偏好
        const VOICE = PRONUNCIATION === "uk" ? "fable" : "alloy";  // uk=fable(英式), us=alloy(美式)

        // ========== SVG 图标常量（液态玻璃方案 E） ==========
        const SVG_VOLUME = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>';
        const SVG_ZAP = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>';
        const SVG_DOLLAR = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 18V6"/></svg>';
        const SVG_PAUSE = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/></svg>';
        const SVG_PLAY = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>';

        let selectedText = "";
        let selectionRect = null;

        const popup = document.getElementById('playPopup');
        const playBtn = document.getElementById('playBtn');
        const btnIcon = document.getElementById('btnIcon');
        const btnText = document.getElementById('btnText');
        const audioPlayer = document.getElementById('audioPlayer');
        const audioControls = document.getElementById('audioControls');
        const playPauseBtn = document.getElementById('playPauseBtn');
        const speedControl = document.getElementById('speedControl');
        const progressBar = document.getElementById('progressBar');
        const currentTimeDisplay = document.getElementById('currentTime');
        const totalTimeDisplay = document.getElementById('totalTime');
        const closeControls = document.getElementById('closeControls');
        const statusMessage = document.getElementById('status-message');

        // 拖动功能变量
        let isDragging = false;
        let dragStartX = 0;
        let dragStartY = 0;
        let controlsStartX = 0;
        let controlsStartY = 0;
        let isProcessing = false;

        console.log('[TTS Player V2] 开始初始化...');
        console.log('[TTS Player V2] 🎛️ 控制器元素:', audioControls ? '✅ 存在' : '❌ 不存在');
        console.log('[TTS Player V2] 📊 控制器初始display:', audioControls ? window.getComputedStyle(audioControls).display : 'N/A');
        console.log('[TTS Player V2] 🎮 playPauseBtn:', playPauseBtn ? '✅ 存在' : '❌ 不存在');
        console.log('[TTS Player V2] ⚡ speedControl:', speedControl ? '✅ 存在' : '❌ 不存在');
        console.log('[TTS Player V2] 📏 progressBar:', progressBar ? '✅ 存在' : '❌ 不存在');

        // ========== AbortController 管理父页面事件监听器 ==========
        // 🔧 清理旧的事件监听器（如果存在）
        try {{
            if (window.parent && window.parent !== window && window.parent.__stx_tts_player_abort_controller) {{
                window.parent.__stx_tts_player_abort_controller.abort();
                console.log('[TTS Player V2] 🧹 已清理旧的父页面事件监听器');
            }}
        }} catch (e) {{
            console.warn('[TTS Player V2] ⚠️ 无法清理旧监听器:', e.message);
        }}

        // 创建新的 AbortController 并存储在父页面
        let parentListenerSignal = null;
        try {{
            if (window.parent && window.parent !== window) {{
                window.parent.__stx_tts_player_abort_controller = new AbortController();
                parentListenerSignal = window.parent.__stx_tts_player_abort_controller.signal;
                console.log('[TTS Player V2] ✅ 父页面 AbortController 已创建');
            }}
        }} catch (e) {{
            console.warn('[TTS Player V2] ⚠️ 无法创建父页面 AbortController:', e.message);
        }}

        // ========== LRU缓存管理 ==========
        // ✨ 使用父页面的 localStorage（与 floating_selector_tool 共享）
        function getStorage() {{
            try {{
                if (window.parent && window.parent !== window) {{
                    // 测试是否真的能访问
                    void window.parent.localStorage.length;
                    console.log('[Cache] ✅ 使用父页面localStorage');
                    return window.parent.localStorage;
                }}
            }} catch (e) {{
                console.warn('[Cache] ⚠️ 无法访问父页面localStorage，使用iframe本地存储:', e.message);
            }}
            console.log('[Cache] ⚠️ 降级使用iframe localStorage');
            return localStorage;
        }}

        function getCacheKey(text, voice) {{
            // 使用base64编码文本作为key，确保唯一性
            return CACHE_PREFIX + btoa(encodeURIComponent(text.substring(0, 100) + '|' + voice)).substring(0, 50);
        }}

        function getCachedAudio(text) {{
            const key = getCacheKey(text, VOICE);
            try {{
                const storage = getStorage();
                const cached = storage.getItem(key);
                if (cached) {{
                    const data = JSON.parse(cached);
                    // 更新最后使用时间（LRU）
                    data.lastUsed = Date.now();
                    storage.setItem(key, JSON.stringify(data));
                    console.log('[Cache] ✅ 缓存命中');
                    return data.audioData;
                }}
            }} catch (e) {{
                console.warn('[Cache] 读取缓存失败:', e);
            }}
            return null;
        }}

        function setCachedAudio(text, audioData) {{
            const key = getCacheKey(text, VOICE);
            const data = {{
                audioData: audioData,
                lastUsed: Date.now(),
                createdAt: Date.now(),
                textLength: text.length
            }};

            try {{
                const storage = getStorage();
                console.log('[Cache] 📍 存储位置:', storage === window.parent.localStorage ? '父页面localStorage' : 'iframe localStorage');
                console.log('[Cache] 🔑 缓存key:', key.substring(0, 30) + '...');
                storage.setItem(key, JSON.stringify(data));
                console.log('[Cache] ✅ 已缓存音频');
                enforceStorageLimit();
            }} catch (e) {{
                console.warn('[Cache] ⚠️ 存储失败，尝试清理:', e.message);
                cleanOldestCache();
                try {{
                    const storage = getStorage();
                    storage.setItem(key, JSON.stringify(data));
                    console.log('[Cache] ✅ 清理后缓存成功');
                }} catch (e2) {{
                    console.error('[Cache] ❌ 最终缓存失败:', e2);
                }}
            }}
        }}

        function enforceStorageLimit() {{
            const storage = getStorage();
            const keys = Object.keys(storage).filter(k => k.startsWith(CACHE_PREFIX));
            if (keys.length <= MAX_CACHE_SIZE) return;

            console.log(`[Cache] 清理缓存：当前${{keys.length}}项，限制${{MAX_CACHE_SIZE}}项`);

            const entries = keys.map(key => {{
                try {{
                    const data = JSON.parse(storage.getItem(key));
                    return {{ key, lastUsed: data.lastUsed || 0 }};
                }} catch {{
                    return {{ key, lastUsed: 0 }};
                }}
            }});

            entries.sort((a, b) => a.lastUsed - b.lastUsed);
            const toRemove = entries.slice(0, entries.length - MAX_CACHE_SIZE);
            toRemove.forEach(entry => {{
                storage.removeItem(entry.key);
            }});
            console.log(`[Cache] ✅ 已清理${{toRemove.length}}项旧缓存`);
        }}

        function cleanOldestCache() {{
            const storage = getStorage();
            const keys = Object.keys(storage).filter(k => k.startsWith(CACHE_PREFIX));
            if (keys.length === 0) {{
                console.warn('[Cache] 无缓存可清理');
                return;
            }}

            let oldestKey = keys[0];
            let oldestTime = Infinity;

            keys.forEach(key => {{
                try {{
                    const data = JSON.parse(storage.getItem(key));
                    if (data.lastUsed < oldestTime) {{
                        oldestTime = data.lastUsed;
                        oldestKey = key;
                    }}
                }} catch {{
                    // 损坏的缓存，优先删除
                    storage.removeItem(key);
                }}
            }});

            storage.removeItem(oldestKey);
            console.log('[Cache] ✅ 已清理最旧缓存');
        }}

        // ========== 文本选择监听（iframe内部） ==========
        document.addEventListener('mouseup', (e) => {{
            setTimeout(() => {{
                const sel = window.getSelection();
                const text = sel ? sel.toString().trim() : "";

                if (text && sel.rangeCount > 0 && !isProcessing) {{
                    selectedText = text;
                    const range = sel.getRangeAt(0);
                    const rect = range.getBoundingClientRect();

                    // 🔥 保存文档坐标（加上滚动偏移）
                    selectionRect = {{
                        left: rect.left + window.scrollX,
                        top: rect.top + window.scrollY,
                        width: rect.width,
                        height: rect.height,
                        bottom: rect.bottom + window.scrollY
                    }};

                    // 定位悬浮按钮（使用文档坐标）
                    const popupWidth = 200;
                    const left = Math.max(10, selectionRect.left + selectionRect.width / 2 - popupWidth / 2);
                    const top = Math.max(10, selectionRect.top - 60);

                    popup.style.left = left + 'px';
                    popup.style.top = top + 'px';
                    popup.style.display = 'block';

                    // 检查缓存并更新按钮样式
                    const cached = getCachedAudio(text);
                    if (cached) {{
                        playBtn.className = 'play-btn cached';
                        btnIcon.innerHTML = SVG_ZAP;
                        btnText.textContent = '播放（已缓存）';
                        console.log('[Selection] ⚡ 检测到缓存');
                    }} else {{
                        playBtn.className = 'play-btn';
                        btnIcon.innerHTML = SVG_VOLUME;
                        btnText.textContent = '播放选中内容';
                    }}

                    console.log(`[Selection] 选中文本(${{text.length}}字符): ${{text.substring(0, 30)}}...`);
                }} else if (text.length === 0) {{
                    popup.style.display = 'none';
                }}
            }}, 10);
        }});

        // 点击其他地方隐藏悬浮按钮
        document.addEventListener('mousedown', (e) => {{
            if (!popup.contains(e.target) && !audioControls.contains(e.target)) {{
                popup.style.display = 'none';
            }}
        }});

        // 🔥 滚动时隐藏播放按钮（position: absolute + 文档坐标不需要更新位置）
        // ⚠️ 播放按钮在iframe内部，监听iframe内部滚动
        window.addEventListener('scroll', () => {{
            if (popup.style.display === 'block') {{
                popup.style.display = 'none';
                console.log(`[Scroll] 📜 iframe内部滚动，隐藏播放按钮`);
            }}
        }}, true);

        // 🔥 监听父页面滚动事件（通过postMessage）
        window.addEventListener('message', (event) => {{
            // 🔥 调试：打印所有收到的消息
            console.log(`[PostMessage Debug] 收到消息:`, event.data);

            if (event.data && event.data.type === 'PARENT_SCROLL_EVENT') {{
                console.log(`[Scroll] ✅ 确认是滚动事件，popup display: ${{popup.style.display}}`);
                if (popup.style.display === 'block') {{
                    popup.style.display = 'none';
                    console.log(`[Scroll] 📜 收到父页面滚动消息，隐藏播放按钮`);
                }} else {{
                    console.log(`[Scroll] ⚠️ popup已经隐藏，display=${{popup.style.display}}`);
                }}
            }}
        }});

        console.log(`[Selection Player] ✅ postMessage监听器已安装`);

        // ========== 播放控制器辅助函数 ==========

        // 格式化时间（秒 -> 分:秒）
        function formatTime(seconds) {{
            if (isNaN(seconds)) return '0:00';
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${{mins}}:${{secs.toString().padStart(2, '0')}}`;
        }}

        // 更新进度条
        function updateProgress() {{
            if (audioPlayer.duration) {{
                const progress = (audioPlayer.currentTime / audioPlayer.duration) * 100;
                progressBar.value = progress;
                progressBar.style.setProperty('--progress', `${{progress}}%`);
                currentTimeDisplay.textContent = formatTime(audioPlayer.currentTime);
                totalTimeDisplay.textContent = formatTime(audioPlayer.duration);
            }}
        }}

        // 显示播放控制器（注入到父页面）
        function showAudioControls() {{
            console.log('[Controls] 🎛️ 显示控制器被调用');

            // 尝试在父页面显示控制器
            try {{
                if (window.parent && window.parent !== window) {{
                    // 检查父页面是否已有控制器
                    let parentControls = window.parent.document.getElementById('tts-parent-controls');

                    // ✨ 如果旧控制器存在，先删除（解决rerun后控制器失效的问题）
                    if (parentControls) {{
                        console.log('[Controls] 🗑️ 删除旧控制器（准备重建）');
                        window.parent.document.body.removeChild(parentControls);
                    }}

                    // 创建新控制器
                    console.log('[Controls] 📦 在父页面创建新控制器');
                    parentControls = audioControls.cloneNode(true);
                    parentControls.id = 'tts-parent-controls';
                    window.parent.document.body.appendChild(parentControls);

                    // 绑定父页面控制器的事件
                    setupParentControls(parentControls);

                    // ✨ 重置控制器状态（每次播放新内容）
                    const pPlayPauseBtn = parentControls.querySelector('#playPauseBtn');
                    const pSpeedControl = parentControls.querySelector('#speedControl');
                    const pProgressBar = parentControls.querySelector('#progressBar');

                    if (pPlayPauseBtn) {{
                        pPlayPauseBtn.innerHTML = SVG_PAUSE + ' 暂停';  // 重置为暂停状态
                    }}

                    if (pSpeedControl) {{
                        pSpeedControl.value = '1';  // 重置速度为1x
                        audioPlayer.playbackRate = 1.0;  // 同时重置audio元素的速度
                        console.log('[Controls] 🔄 速度已重置为1x');
                    }}

                    if (pProgressBar) {{
                        pProgressBar.value = 0;  // 重置进度条
                        pProgressBar.style.setProperty('--progress', '0%');
                    }}

                    // 显示父页面的控制器
                    parentControls.classList.add('active');
                    parentControls.style.display = 'block';

                    // 定位父页面控制器
                    if (selectionRect) {{
                        const controlsWidth = 320;
                        let left = selectionRect.left + (selectionRect.width / 2) - (controlsWidth / 2);
                        let top = selectionRect.bottom + 10;
                        left = Math.max(10, Math.min(left, window.parent.innerWidth - controlsWidth - 10));
                        top = Math.max(10, top);
                        parentControls.style.left = left + 'px';
                        parentControls.style.top = top + 'px';
                    }} else {{
                        parentControls.style.left = '20px';
                        parentControls.style.top = '80px';
                    }}

                    console.log('[Controls] ✅ 父页面控制器已显示');
                    return;
                }}
            }} catch (e) {{
                console.warn('[Controls] ⚠️ 无法访问父页面，使用iframe内控制器:', e.message);
            }}

            // 降级：在iframe内显示
            audioControls.classList.add('active');
            console.log('[Controls] ✅ iframe内控制器已显示，display:', window.getComputedStyle(audioControls).display);

            if (selectionRect) {{
                const controlsWidth = 320;
                const controlsHeight = audioControls.offsetHeight || 200;
                let left = selectionRect.left + (selectionRect.width / 2) - (controlsWidth / 2);
                let top = selectionRect.bottom + 10;
                left = Math.max(10, Math.min(left, window.innerWidth - controlsWidth - 10));
                top = Math.max(10, Math.min(top, window.innerHeight - controlsHeight - 10));
                audioControls.style.left = (left + window.scrollX) + 'px';
                audioControls.style.top = (top + window.scrollY) + 'px';
            }} else {{
                audioControls.style.left = '20px';
                audioControls.style.top = '80px';
            }}
        }}

        // 为父页面控制器设置事件监听
        function setupParentControls(parentControls) {{
            const pPlayPauseBtn = parentControls.querySelector('#playPauseBtn');
            const pSpeedControl = parentControls.querySelector('#speedControl');
            const pProgressBar = parentControls.querySelector('#progressBar');
            const pCloseControls = parentControls.querySelector('#closeControls');
            const pControlsHeader = parentControls.querySelector('.controls-header');

            // 播放/暂停
            if (pPlayPauseBtn) {{
                pPlayPauseBtn.addEventListener('click', () => {{
                    if (audioPlayer.paused) {{
                        audioPlayer.play();
                        pPlayPauseBtn.innerHTML = SVG_PAUSE + ' 暂停';
                    }} else {{
                        audioPlayer.pause();
                        pPlayPauseBtn.innerHTML = SVG_PLAY + ' 播放';
                    }}
                }});
            }}

            // 速度控制
            if (pSpeedControl) {{
                pSpeedControl.addEventListener('change', () => {{
                    audioPlayer.playbackRate = parseFloat(pSpeedControl.value);
                }});
            }}

            // 进度条
            if (pProgressBar) {{
                pProgressBar.addEventListener('input', () => {{
                    if (audioPlayer.duration) {{
                        audioPlayer.currentTime = (pProgressBar.value / 100) * audioPlayer.duration;
                    }}
                }});

                // 同步进度
                audioPlayer.addEventListener('timeupdate', () => {{
                    if (audioPlayer.duration) {{
                        const progress = (audioPlayer.currentTime / audioPlayer.duration) * 100;
                        pProgressBar.value = progress;
                        pProgressBar.style.setProperty('--progress', `${{progress}}%`);
                        const pCurrentTime = parentControls.querySelector('#currentTime');
                        const pTotalTime = parentControls.querySelector('#totalTime');
                        if (pCurrentTime) pCurrentTime.textContent = formatTime(audioPlayer.currentTime);
                        if (pTotalTime) pTotalTime.textContent = formatTime(audioPlayer.duration);
                    }}
                }});
            }}

            // 关闭按钮
            if (pCloseControls) {{
                pCloseControls.addEventListener('click', () => {{
                    parentControls.classList.remove('active');
                    parentControls.style.display = 'none';
                    audioPlayer.pause();
                    audioPlayer.currentTime = 0;
                }});
            }}

            // ✨ 音频播放结束时更新父页面控制器
            audioPlayer.addEventListener('ended', () => {{
                if (pPlayPauseBtn) {{
                    pPlayPauseBtn.innerHTML = SVG_PLAY + ' 播放';
                }}
                if (pProgressBar) {{
                    pProgressBar.value = 0;
                    pProgressBar.style.setProperty('--progress', '0%');
                }}
                console.log('[Controls] ✅ 父页面控制器已更新（播放完成）');
            }});

            // 拖动功能
            if (pControlsHeader) {{
                let pIsDragging = false;
                let pDragStartX = 0, pDragStartY = 0;
                let pControlsStartX = 0, pControlsStartY = 0;

                pControlsHeader.addEventListener('mousedown', (e) => {{
                    if (e.target !== pCloseControls && !pCloseControls.contains(e.target)) {{
                        pIsDragging = true;
                        pDragStartX = e.clientX;
                        pDragStartY = e.clientY;
                        const rect = parentControls.getBoundingClientRect();
                        pControlsStartX = rect.left;
                        pControlsStartY = rect.top;
                        pControlsHeader.style.cursor = 'grabbing';
                        e.preventDefault();
                    }}
                }});

                // 🔧 添加 AbortController signal 防止监听器累积
                const dragOptions = parentListenerSignal ? {{ signal: parentListenerSignal }} : {{}};

                window.parent.document.addEventListener('mousemove', (e) => {{
                    if (pIsDragging) {{
                        const deltaX = e.clientX - pDragStartX;
                        const deltaY = e.clientY - pDragStartY;
                        let newX = pControlsStartX + deltaX;
                        let newY = pControlsStartY + deltaY;
                        const maxX = window.parent.innerWidth - parentControls.offsetWidth;
                        const maxY = window.parent.innerHeight - parentControls.offsetHeight;
                        newX = Math.max(0, Math.min(newX, maxX));
                        newY = Math.max(0, Math.min(newY, maxY));
                        parentControls.style.left = newX + 'px';
                        parentControls.style.top = newY + 'px';
                    }}
                }}, dragOptions);

                window.parent.document.addEventListener('mouseup', () => {{
                    if (pIsDragging) {{
                        pIsDragging = false;
                        pControlsHeader.style.cursor = 'move';
                    }}
                }}, dragOptions);
            }}

            console.log('[Controls] ✅ 父页面控制器事件已绑定');
        }}

        // 隐藏播放控制器
        function hideAudioControls() {{
            audioControls.classList.remove('active');
            audioPlayer.pause();
            audioPlayer.currentTime = 0;
            playPauseBtn.innerHTML = SVG_PAUSE + ' 暂停';
        }}

        // ========== TTS播放功能 ==========
        async function playText(text) {{
            if (!text) {{
                console.warn('[TTS] ⚠️ 文本为空');
                return;
            }}

            popup.style.display = 'none';
            isProcessing = true;

            // 显示加载状态
            playBtn.disabled = true;
            playBtn.className = 'play-btn processing';
            playBtn.innerHTML = '<div class="loading"></div><span>加载中...</span>';

            try {{
                console.log(`[TTS] 🎵 开始播放: ${{text.substring(0, 50)}}... (${{text.length}}字符)`);

                // 检查缓存
                let audioData = getCachedAudio(text);

                if (!audioData) {{
                    // ========== 智能音频策略：单个单词4o-mini，多个单词使用OpenAI ==========
                    console.log('\\n' + '='.repeat(80));
                    console.log('[TTS DEBUG] 🎬 开始音频生成流程');
                    console.log('[TTS DEBUG] 📝 原始文本:', `"${{text}}"`);

                    // 判断是否为单个单词
                    const cleanedText = text.trim().replace(/[.,!?;:'"()\\[\\]{{}}]+/g, '');
                    const words = cleanedText.split(/\\s+/);
                    const isSingleWord = words.length === 1;

                    console.log('[TTS DEBUG] 🧹 清理后文本:', `"${{cleanedText}}"`);
                    console.log('[TTS DEBUG] 📊 单词分析:', `${{words.length}} 个单词 [${{words.join(', ')}}]`);
                    console.log('[TTS DEBUG] 🎯 策略选择:', isSingleWord ? '✅ 4o-mini（单词）' : '✅ OpenAI TTS（多词）');
                    console.log('='.repeat(80) + '\\n');

                    let audioBlob = null;
                    let usedSource = '';

                    if (isSingleWord) {{
                        // ========== 单个单词：使用 OpenAI TTS ==========
                        const word = words[0];
                        console.log(`[TTS DEBUG] 🎯 单个单词模式: "${{word}}"`);
                        showStatus(`正在生成语音...`, 'info');

                        // ✨ 通知父页面：开始生成
                        if (typeof notifyParentStatus !== 'undefined') {{
                            notifyParentStatus('GENERATING', {{ text: word, strategy: 'openai' }});
                        }}

                        console.log('[TTS DEBUG] 🌐 调用后端 TTS API...');
                        const response = await fetch(API_URL, {{
                            method: 'POST',
                            headers: {{
                                'Authorization': `Bearer ${{JWT_TOKEN}}`,
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{
                                text: word,
                                model: 'gpt-4o-mini-tts',
                                voice: VOICE
                            }})
                        }});

                        if (!response.ok) {{
                            const errorText = await response.text();
                            throw new Error(`TTS API 错误 ${{response.status}}: ${{errorText}}`);
                        }}

                        audioBlob = await response.blob();
                        usedSource = '后端 TTS (单词)';
                        console.log(`[TTS DEBUG] ✅ 后端 TTS 成功！音频大小: ${{(audioBlob.size / 1024).toFixed(2)}} KB`);
                        showStatus('✅ 语音生成成功', 'success');

                    }} else {{
                        // ========== 多个单词：使用后端 TTS API ==========
                        console.log('┌─────────────────────────────────────────────────────┐');
                        console.log('│ 🔤 多个单词模式：使用后端 TTS API                   │');
                        console.log('└─────────────────────────────────────────────────────┘');
                        const multiWordStartTime = performance.now();
                        console.log(`[TTS DEBUG] 📡 调用后端 TTS API（多词）...`);
                        console.log(`[TTS DEBUG] 📝 文本长度: ${{text.length}} 字符`);
                        showStatus('正在生成语音...', 'info');

                        // ✨ 通知父页面：开始生成
                        if (typeof notifyParentStatus !== 'undefined') {{
                            notifyParentStatus('GENERATING', {{ text: text.substring(0, 50), strategy: 'backend' }});
                        }}

                        const response = await fetch(API_URL, {{
                            method: 'POST',
                            headers: {{
                                'Authorization': `Bearer ${{JWT_TOKEN}}`,
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{
                                text: text,
                                model: 'tts-1',
                                voice: VOICE
                            }})
                        }});

                        console.log(`[TTS DEBUG] 📡 API响应状态: ${{response.status}}`);

                        if (!response.ok) {{
                            const errorText = await response.text();
                            console.log(`[TTS DEBUG] ❌ API错误响应: ${{errorText}}`);
                            throw new Error(`TTS API 错误 ${{response.status}}: ${{errorText}}`);
                        }}

                        audioBlob = await response.blob();
                        usedSource = '后端 TTS (多词)';
                        const multiWordTime = (performance.now() - multiWordStartTime).toFixed(0);
                        console.log(`[TTS DEBUG] ✅ 后端 TTS 成功！音频大小: ${{(audioBlob.size / 1024).toFixed(2)}} KB`);
                        console.log(`[TTS DEBUG] ⏱️  总耗时: ${{multiWordTime}}ms\\n`);
                    }}

                    // ========== 统一处理：将 audioBlob 转换为 base64 并缓存 ==========
                    if (!audioBlob) {{
                        console.log('[TTS DEBUG] ❌ 所有音频源均失败');
                        throw new Error('所有音频源均失败');
                    }}

                    console.log('┌═════════════════════════════════════════════════════┐');
                    console.log(`│ 🎉 最终音频源: ${{usedSource.padEnd(35)}} │`);
                    console.log('└═════════════════════════════════════════════════════┘');
                    console.log(`[TTS DEBUG] 💾 转换音频为 base64 并缓存...`);

                    // 转换为base64存储
                    const reader = new FileReader();
                    audioData = await new Promise((resolve, reject) => {{
                        reader.onload = () => resolve(reader.result);
                        reader.onerror = reject;
                        reader.readAsDataURL(audioBlob);
                    }});

                    setCachedAudio(text, audioData);
                    console.log(`[TTS DEBUG] ✅ 音频已缓存到 localStorage`);
                    console.log('='.repeat(80) + '\\n');
                    showStatus('✅ 语音已生成并缓存', 'success');

                    // ✨ 通知父页面：生成完成，开始播放
                    if (typeof notifyParentStatus !== 'undefined') {{
                        notifyParentStatus('PLAYING', {{ cached: false, text: text }});
                    }}
                }} else {{
                    console.log('[TTS] ✅ 使用缓存音频');
                    showStatus('✅ 使用缓存音频', 'success');

                    // ✨ 通知父页面：使用缓存播放
                    if (typeof notifyParentStatus !== 'undefined') {{
                        notifyParentStatus('PLAYING', {{ cached: true, text: text }});
                    }}
                }}

                // 播放音频
                audioPlayer.src = audioData;
                audioPlayer.playbackRate = parseFloat(speedControl.value);

                // ✨ 等待音频元数据加载完成
                await new Promise((resolve) => {{
                    audioPlayer.addEventListener('loadedmetadata', function onLoaded() {{
                        audioPlayer.removeEventListener('loadedmetadata', onLoaded);
                        console.log('[TTS] ✅ 音频元数据已加载，时长:', formatTime(audioPlayer.duration));
                        resolve();
                    }});
                }});

                await audioPlayer.play();
                console.log('[TTS] ▶️ 开始播放');

                // 显示控制器
                showAudioControls();
                playPauseBtn.innerHTML = SVG_PAUSE + ' 暂停';

            }} catch (error) {{
                console.error('[TTS] ❌ 播放失败:', error);

                // [修改 - 余额制改造 2026-01-20] 检测 402 余额不足或 403 错误
                const isCreditError = error.message.includes('402') || error.message.includes('403');

                if (isCreditError) {{
                    // 设置按钮为充值状态
                    playBtn.disabled = false;
                    playBtn.className = 'play-btn credit-required';
                    playBtn.innerHTML = '<span>' + SVG_DOLLAR + '</span><span>请充值</span>';
                    console.log('[TTS] 💰 余额不足，请充值后使用');

                    // 通知父页面
                    if (typeof notifyParentStatus !== 'undefined') {{
                        notifyParentStatus('CREDIT_REQUIRED', {{ message: '余额不足，请充值' }});
                    }}

                    // 标记为余额错误，阻止 finally 恢复按钮
                    window._creditError = true;
                }} else {{
                    showStatus(`❌ 播放失败: ${{error.message}}`, 'error');
                    window._creditError = false;
                }}
                // [已注释 - 余额制改造] 原订阅检查逻辑
                // const isSubscriptionError = error.message.includes('403');
                // if (isSubscriptionError) {{
                //     playBtn.className = 'play-btn subscription-required';
                //     playBtn.innerHTML = '<span>🔒</span><span>需要会员解锁</span>';
                //     notifyParentStatus('SUBSCRIPTION_REQUIRED', {{ message: '需要会员解锁' }});
                //     window._subscriptionError = true;
                // }}
            }} finally {{
                // 只有非余额错误时才恢复按钮
                if (!window._creditError) {{
                    playBtn.disabled = false;
                    playBtn.className = 'play-btn';
                    // 恢复按钮结构（因为loading时innerHTML被替换了）
                    playBtn.innerHTML = '<span id="btnIcon">' + SVG_VOLUME + '</span><span id="btnText">播放选中内容</span>';
                }}
                setTimeout(() => {{ isProcessing = false; }}, 500);
            }}
        }}

        function showStatus(message, type) {{
            statusMessage.className = `status ${{type}}`;
            statusMessage.textContent = message;
            setTimeout(() => {{
                statusMessage.textContent = '';
                statusMessage.className = '';
            }}, 3000);
        }}

        // ========== 音频控制事件 ==========
        playBtn.addEventListener('click', () => {{
            if (selectedText) {{
                playText(selectedText);
            }} else {{
                console.warn('[TTS] ⚠️ 未选中文本');
            }}
        }});

        // 播放/暂停按钮
        playPauseBtn.addEventListener('click', () => {{
            if (audioPlayer.paused) {{
                audioPlayer.play();
                playPauseBtn.innerHTML = SVG_PAUSE + ' 暂停';
                console.log('[Audio] ▶️ 继续播放');
            }} else {{
                audioPlayer.pause();
                playPauseBtn.innerHTML = SVG_PLAY + ' 播放';
                console.log('[Audio] ⏸️ 已暂停');
            }}
        }});

        // 进度条拖动
        progressBar.addEventListener('input', () => {{
            if (audioPlayer.duration) {{
                const seekTime = (progressBar.value / 100) * audioPlayer.duration;
                audioPlayer.currentTime = seekTime;
                console.log(`[Audio] ⏩ 跳转到: ${{formatTime(seekTime)}}`);
            }}
        }});

        // 播放速度控制
        speedControl.addEventListener('change', () => {{
            audioPlayer.playbackRate = parseFloat(speedControl.value);
            console.log(`[Audio] ⚡ 播放速度: ${{speedControl.value}}x`);
        }});

        // 关闭控制器按钮
        closeControls.addEventListener('click', () => {{
            hideAudioControls();
            console.log('[Audio] ❌ 关闭控制器');
        }});

        // 音频播放时更新进度条
        audioPlayer.addEventListener('timeupdate', updateProgress);

        // 音频播放结束时
        audioPlayer.addEventListener('ended', () => {{
            playPauseBtn.innerHTML = SVG_PLAY + ' 播放';
            progressBar.value = 0;
            progressBar.style.setProperty('--progress', '0%');
            console.log('[Audio] ✅ 播放完成');

            // ✨ 通知父页面：播放完成
            if (typeof notifyParentStatus !== 'undefined') {{
                notifyParentStatus('COMPLETED');
            }}

            // 不自动关闭，保持控制器显示
        }});

        // 音频加载完成时更新总时长
        audioPlayer.addEventListener('loadedmetadata', () => {{
            totalTimeDisplay.textContent = formatTime(audioPlayer.duration);
            console.log(`[Audio] ⏱️ 时长: ${{formatTime(audioPlayer.duration)}}`);
        }});

        audioPlayer.addEventListener('error', (e) => {{
            console.error('[Audio] ❌ 播放错误:', e);
            showStatus('❌ 音频播放错误', 'error');
            hideAudioControls();
        }});

        // ========== 拖动功能 ==========

        // 获取控制器头部元素
        const controlsHeader = audioControls.querySelector('.controls-header');

        // 鼠标按下开始拖动
        controlsHeader.addEventListener('mousedown', (e) => {{
            // 不要在点击关闭按钮时触发拖动
            if (e.target !== closeControls && !closeControls.contains(e.target)) {{
                isDragging = true;
                dragStartX = e.clientX;
                dragStartY = e.clientY;
                const rect = audioControls.getBoundingClientRect();
                controlsStartX = rect.left;
                controlsStartY = rect.top;
                controlsHeader.style.cursor = 'grabbing';
                e.preventDefault();
                console.log('[Drag] 🖱️ 开始拖动');
            }}
        }});

        // 鼠标移动时更新位置
        document.addEventListener('mousemove', (e) => {{
            if (isDragging) {{
                const deltaX = e.clientX - dragStartX;
                const deltaY = e.clientY - dragStartY;
                let newX = controlsStartX + deltaX;
                let newY = controlsStartY + deltaY;

                // 边界限制
                const maxX = window.innerWidth - audioControls.offsetWidth;
                const maxY = window.innerHeight - audioControls.offsetHeight;
                newX = Math.max(0, Math.min(newX, maxX));
                newY = Math.max(0, Math.min(newY, maxY));

                audioControls.style.left = newX + 'px';
                audioControls.style.top = newY + 'px';
            }}
        }});

        // 鼠标松开停止拖动
        document.addEventListener('mouseup', () => {{
            if (isDragging) {{
                isDragging = false;
                controlsHeader.style.cursor = 'move';
                console.log('[Drag] ✅ 拖动完成');
            }}
        }});

        // ========== 父页面CSS注入 ==========
        (function injectParentCSS() {{
            try {{
                if (window.parent && window.parent !== window) {{
                    // 检查是否已注入CSS
                    if (window.parent.document.getElementById('tts-parent-css')) {{
                        return;
                    }}

                    const style = window.parent.document.createElement('style');
                    style.id = 'tts-parent-css';
                    style.textContent = `
                        #tts-parent-controls {{
                            position: fixed;
                            top: 80px;
                            left: 20px;
                            background: rgba(255, 255, 255, 0.5);
                            backdrop-filter: blur(24px) saturate(150%);
                            -webkit-backdrop-filter: blur(24px) saturate(150%);
                            border: 1px solid rgba(255, 255, 255, 0.8);
                            border-radius: 1.25rem;
                            box-shadow: 0 16px 40px rgba(61, 58, 42, 0.08), inset 0 0 0 1px rgba(255, 255, 255, 0.5);
                            padding: 0;
                            width: 320px;
                            z-index: 99999;
                            display: none;
                            animation: slideInFromLeft 0.3s ease-out;
                            color: #3d3a2a;
                            overflow: hidden;
                        }}

                        #tts-parent-controls::before {{
                            content: '';
                            position: absolute;
                            inset: 0;
                            background: linear-gradient(-45deg, #fdfdf8, #f8ebe6, #eef2f6, #fdfdf8);
                            z-index: 0;
                        }}

                        #tts-parent-controls::after {{
                            content: '';
                            position: absolute;
                            width: 160px; height: 160px;
                            background: rgba(203, 120, 92, 0.25);
                            border-radius: 50%;
                            filter: blur(40px);
                            top: -40px; left: -20px;
                            z-index: 0;
                        }}

                        @keyframes slideInFromLeft {{
                            from {{ opacity: 0; transform: translateX(-20px); }}
                            to {{ opacity: 1; transform: translateX(0); }}
                        }}

                        #tts-parent-controls .controls-header {{
                            position: relative;
                            z-index: 1;
                            background: linear-gradient(180deg, rgba(255,255,255,0.4) 0%, rgba(255,255,255,0) 100%);
                            color: #3d3a2a;
                            padding: 16px 20px;
                            border-radius: 1.25rem 1.25rem 0 0;
                            border-bottom: 1px solid rgba(255, 255, 255, 0.6);
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            cursor: move;
                            user-select: none;
                        }}

                        #tts-parent-controls .controls-title {{
                            font-weight: 600;
                            font-size: 15px;
                            display: flex;
                            align-items: center;
                            gap: 8px;
                            text-shadow: 0 1px 2px rgba(255,255,255,0.8);
                        }}

                        #tts-parent-controls .recording-dot {{
                            display: inline-block;
                            width: 8px;
                            height: 8px;
                            background: #cb785c;
                            border-radius: 50%;
                            box-shadow: 0 0 8px rgba(203, 120, 92, 0.8);
                            animation: pulse-dot 2s infinite;
                        }}

                        @keyframes pulse-dot {{
                            0%, 100% {{ opacity: 1; transform: scale(1); }}
                            50% {{ opacity: 0.5; transform: scale(0.8); }}
                        }}

                        #tts-parent-controls .close-controls {{
                            background: rgba(255, 255, 255, 0.4);
                            border: 1px solid rgba(255, 255, 255, 0.8);
                            border-radius: 50%;
                            width: 28px;
                            height: 28px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: #3d3a2a;
                            cursor: pointer;
                            font-size: 16px;
                            line-height: 1;
                            transition: all 0.2s;
                        }}

                        #tts-parent-controls .close-controls:hover {{
                            background: rgba(255, 255, 255, 0.9);
                            transform: rotate(90deg);
                        }}

                        #tts-parent-controls .controls-body {{
                            padding: 20px;
                            position: relative;
                            z-index: 1;
                        }}

                        #tts-parent-controls .progress-container {{
                            margin-bottom: 12px;
                        }}

                        #tts-parent-controls .progress-bar {{
                            width: 100%;
                            height: 8px;
                            border-radius: 4px;
                            outline: none;
                            -webkit-appearance: none;
                            appearance: none;
                            background: rgba(0, 0, 0, 0.05);
                            box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
                            cursor: pointer;
                            overflow: hidden;
                            position: relative;
                        }}

                        #tts-parent-controls .progress-bar::-webkit-slider-runnable-track {{
                            height: 8px;
                            border-radius: 4px;
                        }}

                        #tts-parent-controls .progress-bar::-webkit-slider-thumb {{
                            -webkit-appearance: none;
                            width: 16px;
                            height: 16px;
                            border-radius: 50%;
                            background: #cb785c;
                            border: 3px solid #fff;
                            box-shadow: 0 2px 6px rgba(203, 120, 92, 0.5), -400px 0 0 392px rgba(203, 120, 92, 0.7);
                            margin-top: -4px;
                            cursor: pointer;
                            transition: transform 0.1s;
                        }}

                        #tts-parent-controls .progress-bar::-webkit-slider-thumb:hover {{
                            transform: scale(1.2);
                        }}

                        #tts-parent-controls .progress-bar::-moz-range-thumb {{
                            width: 16px;
                            height: 16px;
                            border-radius: 50%;
                            background: #cb785c;
                            cursor: pointer;
                            border: 3px solid #fff;
                            box-shadow: 0 2px 6px rgba(203, 120, 92, 0.5);
                        }}

                        #tts-parent-controls .time-display {{
                            display: flex;
                            justify-content: space-between;
                            font-size: 12px;
                            font-family: 'Space Mono', monospace;
                            color: #555;
                            margin-top: 8px;
                            font-weight: 500;
                        }}

                        #tts-parent-controls .control-buttons {{
                            display: flex;
                            gap: 12px;
                            align-items: center;
                            margin-top: 16px;
                        }}

                        #tts-parent-controls .control-btn {{
                            flex: 1;
                            display: flex;
                            gap: 8px;
                            align-items: center;
                            justify-content: center;
                            background: rgba(255, 255, 255, 0.4);
                            color: #3d3a2a;
                            border: 1px solid rgba(255, 255, 255, 0.7);
                            border-radius: 9999px;
                            padding: 10px 18px;
                            font-family: 'Space Grotesk', sans-serif;
                            font-size: 14px;
                            font-weight: 600;
                            cursor: pointer;
                            transition: all 0.3s cubic-bezier(0.25, 1, 0.5, 1);
                        }}

                        #tts-parent-controls .control-btn:hover {{
                            background: rgba(255, 255, 255, 0.7);
                            box-shadow: 0 4px 12px rgba(61, 58, 42, 0.05);
                            transform: translateY(-1px);
                        }}

                        #tts-parent-controls .control-btn:active {{
                            transform: scale(0.96);
                        }}

                        #tts-parent-controls .speed-control {{
                            background: rgba(255, 255, 255, 0.4);
                            border: 1px solid rgba(255, 255, 255, 0.7);
                            border-radius: 9999px;
                            padding: 10px 18px;
                            font-family: 'Space Grotesk', sans-serif;
                            font-size: 14px;
                            font-weight: 600;
                            color: #3d3a2a;
                            cursor: pointer;
                            outline: none;
                            -webkit-appearance: none;
                            appearance: none;
                            text-align: center;
                            transition: all 0.3s cubic-bezier(0.25, 1, 0.5, 1);
                        }}

                        #tts-parent-controls .speed-control:hover {{
                            background: rgba(255, 255, 255, 0.7);
                            box-shadow: 0 4px 12px rgba(61, 58, 42, 0.05);
                        }}

                        #tts-parent-controls .speed-control:focus {{
                            box-shadow: 0 0 0 3px rgba(203, 120, 92, 0.15);
                        }}
                    `;

                    window.parent.document.head.appendChild(style);
                    console.log('[TTS Player V2] ✅ 父页面CSS已注入');
                }}
            }} catch (e) {{
                console.warn('[TTS Player V2] ⚠️ 无法注入父页面CSS:', e.message);
            }}
        }})();

        // ========== postMessage通信（仅在启用时）==========
        {postmessage_code}

        console.log('[TTS Player V2] ✅ 初始化完成');

        // ========== 页面卸载时清理父页面元素 ==========
        function cleanupParentControls() {{
            try {{
                // 🔧 清理事件监听器
                if (window.parent && window.parent !== window && window.parent.__stx_tts_player_abort_controller) {{
                    window.parent.__stx_tts_player_abort_controller.abort();
                    console.log('[TTS Player V2] 🧹 已清理父页面事件监听器');
                }}

                if (window.parent && window.parent !== window && window.parent.document) {{
                    // 清理父页面的播放控制器
                    const parentControls = window.parent.document.getElementById('tts-parent-controls');
                    if (parentControls && parentControls.parentNode) {{
                        parentControls.parentNode.removeChild(parentControls);
                        console.log('[TTS Player V2] ✅ 已清理父页面的播放控制器');
                    }}

                    // 清理父页面的CSS样式
                    const parentCSS = window.parent.document.getElementById('tts-parent-css');
                    if (parentCSS && parentCSS.parentNode) {{
                        parentCSS.parentNode.removeChild(parentCSS);
                        console.log('[TTS Player V2] ✅ 已清理父页面的CSS样式');
                    }}
                }}
            }} catch (e) {{
                // 忽略跨域或其他错误
                console.warn('[TTS Player V2] 清理失败:', e.message);
            }}
        }}

        // 监听页面卸载事件
        // 🍎 iOS 设备检测（包括 iPadOS 13+ 伪装成 Mac 的情况）
        // 🍎 iOS Safari 修复：pagehide 在多页面应用首次加载时误触发，使用 visibilitychange + 延迟双重检查
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) ||
                      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

        if (isIOS) {{
            // iOS: 使用 visibilitychange 代替 pagehide，并添加延迟检查
            document.addEventListener('visibilitychange', () => {{
                if (document.visibilityState === 'hidden') {{
                    // 延迟100ms后再次检查，避免首次加载时的误触发
                    setTimeout(() => {{
                        if (document.visibilityState === 'hidden') {{
                            cleanupParentControls();
                        }} else {{
                            console.log('[TTS Player V2] 🍎 [iOS] 页面重新可见，跳过清理');
                        }}
                    }}, 100);
                }}
            }});
            console.log('[TTS Player V2] ✅ 已注册页面卸载清理监听器（iOS 优化模式）');
        }} else {{
            // 非iOS: 保持原有行为
            window.addEventListener('pagehide', cleanupParentControls);
            window.addEventListener('beforeunload', cleanupParentControls);
            console.log('[TTS Player V2] ✅ 已注册页面卸载清理监听器');
        }}
    </script>
</body>
</html>
"""

    return html_code


def render_player(
    api_url: str,
    jwt_token: str,
    cache_size: int = 15,
    channel: str = "tts-bridge-001",
    height: int = 750,
    enable_postmessage: bool = True,
    show_demo_content: bool = True,
    pronunciation: str = "us"
):
    """
    渲染支持postMessage的TTS播放器

    参数：
        api_url: 后端 TTS API 地址（如 http://localhost:8000/api/tts）
        jwt_token: JWT 认证令牌
        cache_size: 缓存大小（LRU）
        channel: postMessage通道名称
        height: 组件高度（像素）
        enable_postmessage: 是否启用postMessage接收
        show_demo_content: 是否显示使用说明和示例文章（默认True）
        pronunciation: 发音偏好 'us'（美式）或 'uk'（英式），默认 'us'
    """
    html_code = get_player_html(api_url, jwt_token, cache_size, channel, enable_postmessage, show_demo_content, pronunciation)
    components.html(html_code, height=height, scrolling=True)


if __name__ == "__main__":
    import os
    import streamlit as st

    st.set_page_config(page_title="TTS播放器 V2 测试", layout="wide")
    st.title("🎙️ TTS播放器 V2 - 后端代理版本")

    st.warning("⚠️ 此测试页面需要 FastAPI 后端服务运行在 localhost:8000")

    # 配置后端 API 地址
    api_url = st.text_input("后端 TTS API 地址", value="http://localhost:8000/api/tts")
    jwt_token = st.text_input("JWT Token", type="password", help="从主应用获取的 JWT 令牌")

    if not jwt_token:
        st.error("❌ 请输入 JWT Token（需要先登录主应用获取）")
        st.stop()

    st.markdown("""
    ### ✨ 新功能

    - ✅ 后端代理模式：API Key 不再暴露给前端
    - ✅ 支持接收postMessage消息（来自floating_selector_tool）
    - ✅ 自动与悬浮选择工具配对（通过channel）
    - ✅ 保持所有原有功能（iframe内选择、LRU缓存等）

    ### 🔐 安全改进

    - API Key 存储在服务器端，前端无法访问
    - 所有 TTS 请求通过后端代理，需要 JWT 认证
    - 订阅检查在后端完成，防止绕过
    """)

    st.markdown("---")

    render_player(
        api_url=api_url,
        jwt_token=jwt_token,
        channel="test-v2",
        cache_size=15,
        enable_postmessage=True,
        height=750
    )

    st.info("💡 在上方组件内选择文本测试播放功能")
