"""
充值中心页面

注意：此页面使用独立登录检查，不调用 require_login()
原因：允许未完成 onboarding 的用户访问，以便充值

[修改 - 余额制改造 2026-01-20]
- 移除订阅检查，所有用户都能看到充值功能
- 移除订阅入口，只保留充值功能
"""
import os
import sys
import streamlit as st
import requests

# 修复模块导入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.auth_helper import get_current_user_id, get_jwt_token
from utils.sidebar_nav import render_sidebar_nav

st.set_page_config(
    page_title="价格与充值",
    page_icon=":material/credit_card:",
    layout="centered"
)

# ========== 侧边栏导航 ==========
with st.sidebar:
    render_sidebar_nav()

# ========== 独立登录检查（不含 onboarding）==========
if not st.user.is_logged_in:
    st.title(":material/lock: 请先登录")
    st.markdown("请登录后访问充值页面。")
    if st.button("登录", type="primary", icon=":material/key:"):
        st.login("auth0")
    st.stop()

user_id = get_current_user_id()

# FastAPI 配置
fastapi_url = os.getenv("FASTAPI_URL")
jwt_token = get_jwt_token(user_id)
headers = {"Authorization": f"Bearer {jwt_token}"}

# 检查 URL 参数
query_params = st.query_params
if query_params.get("success") == "true" or query_params.get("topup_success") == "true":
    st.success("充值成功！感谢支持！")
    st.balloons()
elif query_params.get("canceled") == "true" or query_params.get("topup_canceled") == "true":
    st.warning("支付已取消")

st.title(":material/credit_card: 充值中心")

# ========== 产品与服务说明 ==========
with st.expander("产品与服务详情", expanded=False, icon=":material/list_alt:"):
    st.markdown("""
    | 功能                         | 功能说明                                                              |
    | -------------------------- | ----------------------------------------------------------------- |
    | 语域解码（Register Decoding）    | Sensally Agent 会对每个词/表达给出清晰的"语境边界"：什么时候用、什么时候不该用、母语者更常用的默认说法是什么、用错可能带来什么效果差异。所有讲解与例句都会结合你的兴趣、英语水平、知识点掌握情况等进行定制，你的学习材料会围绕你的兴趣持续生成与展开。 |
    | 探索式反馈             | Sensally Agent 不用"对/错/得分"来审判，而是告诉你：你的表达是否能被理解、母语者更常用哪种说法，以及为什么那样更自然。它把"错"当作探索的起点，并会结合你的兴趣与水平等个性化信息，给出更贴合你的反馈与示例。 |
    | 深度定制教练              | Sensally Agent 更像一个全程陪伴的私人教练：每次对话都基于你的画像定制，不需要你自己决定学什么、怎么学。它会持续围绕你的兴趣与能力状态，安排内容、练习与节奏，让学习过程更省心、更连续。 |
    | 生成学习内容                     | Sensally Agent 会自动为你生成学习内容（例如语域解码、语境画面、词义联结/词源联结等），并根据你的兴趣、水平与薄弱点调整呈现方式与难度，让"教材"真正因人而异、因兴趣而生。 |
    | 内容随时可调                     | 如果你对 Sensally Agent 的讲解方式或者生成的例句、学习材料有任何不满意，都可以随时提出修改要求。它会根据你的反馈调整呈现方式，直到你满意为止——你不需要被动接受任何不适合自己的内容。 |
    | 设计互动练习                     | Sensally Agent 会按你的情况设计互动练习（如填空、翻译、情境选择等），并把题目场景尽量放在你熟悉、感兴趣的语境里，同时根据你的能力与薄弱点动态调节题型与难度。 |
    | 单词循环朗读                     | 你可以选择"循环朗读"模式，Sensally Agent 会自动循环播放单词发音，你不需要手动点击，可以边听边跟读、边做笔记，让耳朵先熟悉发音和节奏，听完后自动进入下一个单词。 |
    | 自评速刷                         | 你可以选择"自评速刷"模式，快速过一遍单词：看到单词后用"忘记/困难/记得/简单"四个按钮评估自己的记忆程度，Sensally Agent 会根据你的评分自动调整这个单词的下次复习时间。 |
    | 多样互动题型                     | Sensally Agent 提供多种互动练习方式：单词释义选择、句意理解、中译英、填空补全、视觉联想等。题型会根据你的薄弱点和学习阶段动态调整，让练习更有针对性、也不容易枯燥。 |
    | 内化评估                | 你在练习时，Sensally Agent 会根据你的真实作答表现判断掌握情况，并在不打断你学习节奏的前提下"静默更新你的学习情况"。它像一个只对你负责的老师，持续记录并更新你的学习情况与状态，不会忘记、也不会错过关键变化。 |
    | 个性化复习安排            | Sensally Agent 会为"每个人的每个单词"建立独立记忆卡片与个性化复习曲线，并根据你的实际表现更新下次复习时间，把复习节奏精确到"人"和"词"。整体体验像专属老师一样持续跟踪与安排。 |
    | 精细技能追踪                     | Sensally Agent 不只给一个"总水平"，还会追踪到更细的子技能（如时态、搭配、连贯等）的掌握度，并提供置信度；这些评估会随着你的练习与对话持续渐进更新。 |
    | 错误画像记录与针对性强化               | Sensally Agent 会记录你的错误画像（例如错误类型、典型错误形式、常见混淆点等），并在后续学习中自动触发更有针对性的提醒与强化训练，帮助你更快补齐薄弱环节。 |
    | 能力进步驱动难度提升               | Sensally Agent 会持续分析你的能力进步，当你稳定提升后，学习内容与练习难度会自然上调；整个过程自动发生，你无需额外设置或手动"升难度"。 |
    | 个性化输入信息注入     | Sensally Agent 在每次"学/练"时都会综合注入与你最相关的信息：核心兴趣、CEFR 水平、技能掌握度、错误画像、反馈偏好、活动偏好等，用这些信息来定制内容与练习形式，确保学习始终围绕你的兴趣与当前需要展开。 |
    | 长期记忆组织               | Sensally Agent 的长期记忆会按语义/情景/程序等维度组织，用来记住如何更好地帮助你学习：你的薄弱点、学习习惯、兴趣偏好、词汇偏好、常见句子问题等。它会持续更新这些信息，形成稳定而不断进化的"专属教学档案"。 |
    | 语义检索：对话时动态注入最相关记忆          | Sensally Agent 每次对话都会做语义检索，只把与当下话题最相关的记忆注入进来（例如与你正在学的内容相关的薄弱点与偏好），同时稳定使用你的核心兴趣与英语水平来控制场景与难度，让它始终"记得你是谁、也知道你此刻最需要什么"。 |
    | 多义词"核心画面"联结         | Sensally Agent 会用一个"核心意象/画面"把多义词的多个含义串起来，从核心意象推导不同义项，帮助你形成结构化记忆，做到"记一个等于记十个"。相关例子也会尽量贴合你的兴趣与熟悉场景。 |
    | 交互方式自适应                    | Sensally Agent 会根据你的学习风格、策略与偏好调整交互方式：比如更偏提示还是直接纠正、你更喜欢角色扮演还是刷题、节奏快慢与讲解粒度等，确保学习体验更顺手、更符合你的习惯。 |
    | 隐私保护下的个性化        | Sensally Agent 不依赖大数据推荐，而是依靠 LLM 的理解能力做个性化；只分析你一个人的信息。它不会保留原始学习行为数据（会提取关键信息写入长期记忆后丢弃原始内容），并尽量避免形成信息茧房式的限制。 |
    """)

with st.expander("价格与计费说明", expanded=False, icon=":material/payments:"):
    st.markdown("""
    ### :material/bar_chart: 我们使用的 AI 模型及官方定价
    
    我们使用 **OpenAI** 最先进的 AI 模型为您提供服务：
    
    #### 文本生成模型
    | 模型 | 输入价格 | 缓存输入价格 | 输出价格 |
    |------|----------|--------------|----------|
    | **GPT-5.4** | \$2.50/百万tokens | \$0.25/百万tokens | \$15.00/百万tokens |
    
    #### 语音合成模型 (TTS)
    | 模型 | 定价 |
    |------|------|
    | GPT-4o-mini-TTS | 输入 \$0.60/百万tokens，\$0.015/分钟 |
    
    """)

with st.expander("服务费说明（重要）", expanded=True, icon=":material/warning:"):
    st.warning("""
:material/campaign: 服务费收取说明

我们会按照 LLM 官方（官网/官方账单）调用成本进行结算，并在此基础上按比例收取一定的服务费，用于覆盖平台运营与服务成本。

利润率承诺：在覆盖各项成本后，我们的综合利润率不超过 5%，如有超过会返还账户余额。

服务费机制：服务费会在每次调用的官方成本基础上按比例加收，该比例会根据实际运营成本动态调整，但最高不超过 30%。

由于服务器、支付渠道、安全与合规等成本会随时间波动，因此服务费具体比例无法固定保证，以实际结算为准。

:material/check_circle: 服务费主要用于支付以下费用：

:material/dns: 服务器与带宽等运营成本

:material/credit_card: 支付渠道手续费/佣金

:material/security: 安全、风控与认证服务

:material/build: 技术维护、升级与稳定性保障

:material/support_agent: 客户支持与服务响应

:material/attach_money: 计费示例

假设您本次使用产生 \$1.00 的官方 LLM 成本：

示例 A：当期服务费比例为 20%（示例比例，仅用于演示）

项目	金额
官方 LLM 成本	\$1.00
服务费（20%）	\$0.20
实际扣费	\$1.20

示例 B：服务费比例上限为 30%（最大情况）

项目	金额
官方 LLM 成本	\$1.00
服务费（≤30%）	≤\$0.30
实际扣费	≤\$1.30

:material/receipt: 计费方式

预扣款机制：每次调用前，系统会预估最大成本并冻结相应额度

实际结算：调用完成后按实际用量结算，超出部分冻结额度会立即退回

精确计费：使用 picoUSD（10⁻¹² USD）精度计算，确保计费公平准确

:material/lightbulb: 提示：您只需为实际产生的官方 LLM 用量及对应服务费付费，不收取月费；服务费比例会随成本变化动态调整，但不超过 30%，并在账单中清晰展示。
    """)
    
    st.info("**提示**：我们的定价模式确保您只为实际使用的 AI 资源付费，没有月费或隐藏费用。", icon=":material/lightbulb:")

st.divider()

# 获取账单状态
billing_status = {"success": False}
try:
    response = requests.get(f"{fastapi_url}/api/billing/status", headers=headers, timeout=5)
    if response.status_code == 200:
        billing_status = response.json()
except Exception as e:
    st.error(f"无法获取账单状态: {e}")

# ========== 额度余额显示（所有用户都显示）==========
credits = billing_status.get("credits", {})
available_usd = credits.get("available_usd", "0.000000")
held_usd = credits.get("held_usd", "0.000000")
total_spent_usd = credits.get("total_spent_usd", "0.000000")

st.subheader(":material/account_balance_wallet: 当前余额")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("可用余额", f"${available_usd[:8]}")
with col2:
    st.metric("预扣款", f"${held_usd[:8]}")
with col3:
    st.metric("已消费", f"${total_spent_usd[:8]}")

st.divider()

# ========== 充值功能（所有用户都显示）==========
st.subheader(":material/credit_card: 额度充值")

topup_amount = st.selectbox(
    "选择充值金额",
    options=[5, 10, 20, 50],
    format_func=lambda x: f"${x}",
    index=1,
)

# 预获取充值 URL（带金额参数的缓存）
# 🔒 安全修复：移除下划线前缀，确保 user_id 和 user_email 参与缓存 key
@st.cache_data(ttl=300, show_spinner="正在获取支付链接...")  # 缓存5分钟
def get_topup_checkout_url(user_id: str, user_email: str, amount: int):
    """获取充值 Stripe Checkout URL
    
    缓存 key = hash(user_id, user_email, amount)
    每个用户的每个金额都有独立缓存，避免跨用户泄漏
    """
    try:
        response = requests.post(
            f"{fastapi_url}/api/billing/topup/create_checkout",
            headers={"Authorization": f"Bearer {get_jwt_token(user_id)}"},
            json={"amount_usd": amount, "email": user_email},
            timeout=10
        )
        data = response.json()
        if data.get("success"):
            return data["url"]
        return None
    except Exception:
        return None

topup_url = get_topup_checkout_url(user_id, getattr(st.user, "email", None), topup_amount)

if topup_url:
    st.link_button(f"立即充值 ${topup_amount}", topup_url, type="primary", use_container_width=True, icon=":material/credit_card:")
else:
    st.error("无法创建支付链接，请稍后重试")

st.info("如需使用微信支付或其他方式充值，请联系客服：support@sensally.com", icon=":material/chat:")

st.divider()

# ========== 管理账单 ==========
if st.button("管理账单", use_container_width=True, icon=":material/receipt_long:"):
    try:
        response = requests.post(
            f"{fastapi_url}/api/billing/portal",
            headers=headers,
            json={"return_url": os.getenv("PUBLIC_APP_URL", "http://localhost:8501") + "/pricing"},
            timeout=10
        )
        data = response.json()
        if data.get("success"):
            st.markdown(f"[点击此处管理账单]({data['url']})")
        else:
            st.error(data.get("error", "创建门户失败"))
    except Exception as e:
        st.error(f"请求失败: {e}")

st.divider()

# 返回主页
if st.button("返回主页", use_container_width=True, icon=":material/home:"):
    st.switch_page("app.py")

st.caption("支付由 Stripe 安全处理，我们不存储您的支付信息。如有疑问，请联系客服。")