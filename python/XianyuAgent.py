import re
from typing import List, Dict, Optional
from openai import OpenAI
from loguru import logger


class XianyuReplyBot:
    def __init__(self, config: dict, prompt_overrides: dict):
        self.config = config
        self.client = OpenAI(
            api_key=config.get("API_KEY"),
            base_url=config.get("MODEL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
        self._init_system_prompts(prompt_overrides)
        self._init_agents()
        self.router = IntentRouter(self.agents['classify'])
        self.last_intent = None

    def _init_agents(self):
        """初始化各领域Agent"""
        model_name = self.config.get("MODEL_NAME", "qwen-max")
        self.agents = {
            'classify': ClassifyAgent(self.client, self.classify_prompt, self._safe_filter, model_name),
            'price': PriceAgent(self.client, self.price_prompt, self._safe_filter, model_name),
            'tech': TechAgent(self.client, self.tech_prompt, self._safe_filter, model_name),
            'default': DefaultAgent(self.client, self.default_prompt, self._safe_filter, model_name),
        }

    def _init_system_prompts(self, prompt_overrides: dict):
        """初始化各Agent专用提示词，从 prompt_overrides（数据库加载）获取"""
        if prompt_overrides is None:
            raise RuntimeError("prompt_overrides 不能为 None，请通过 config_manager.get_all_prompts() 传入提示词")
        self.classify_prompt = prompt_overrides.get("classify_prompt", "")
        self.price_prompt = prompt_overrides.get("price_prompt", "")
        self.tech_prompt = prompt_overrides.get("tech_prompt", "")
        self.default_prompt = prompt_overrides.get("default_prompt", "")
        logger.info("已从配置数据库加载所有提示词")

    def _safe_filter(self, text: str) -> str:
        """安全过滤模块"""
        blocked_phrases = ["微信", "QQ", "支付宝", "银行卡", "线下"]
        return "[安全提醒]请通过平台沟通" if any(p in text for p in blocked_phrases) else text

    def format_history(self, context: List[Dict]) -> str:
        """格式化对话历史，返回完整的对话记录"""
        user_assistant_msgs = [msg for msg in context if msg['role'] in ['user', 'assistant']]
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in user_assistant_msgs])

    def generate_reply(self, user_msg: str, item_desc: str, context: List[Dict], knowledge: Optional[List[Dict]] = None) -> str:
        """生成回复主流程"""
        formatted_context = self.format_history(context)

        if knowledge:
            kb_lines = "\n".join([f"Q: {k.get('question','')}\nA: {k.get('answer','')}" for k in knowledge])
            formatted_context = f"【相关知识库】\n{kb_lines}\n\n【对话历史】\n{formatted_context}"

        detected_intent = self.router.detect(user_msg, item_desc, formatted_context)

        internal_intents = {'classify'}

        if detected_intent == 'no_reply':
            logger.info('意图识别完成: no_reply - 无需回复')
            self.last_intent = 'no_reply'
            return "-"
        elif detected_intent in self.agents and detected_intent not in internal_intents:
            agent = self.agents[detected_intent]
            logger.info(f'意图识别完成: {detected_intent}')
            self.last_intent = detected_intent
        else:
            agent = self.agents['default']
            logger.info('意图识别完成: default')
            self.last_intent = 'default'

        bargain_count = self._extract_bargain_count(context)
        logger.info(f'议价次数: {bargain_count}')

        return agent.generate(
            user_msg=user_msg,
            item_desc=item_desc,
            context=formatted_context,
            bargain_count=bargain_count
        )

    def _extract_bargain_count(self, context: List[Dict]) -> int:
        for msg in context:
            if msg['role'] == 'system' and '议价次数' in msg['content']:
                try:
                    match = re.search(r'议价次数[:：]\s*(\d+)', msg['content'])
                    if match:
                        return int(match.group(1))
                except Exception:
                    pass
        return 0

    def reload_prompts(self, prompt_overrides: dict = None):
        """重新加载所有提示词"""
        logger.info("正在重新加载提示词...")
        self._init_system_prompts(prompt_overrides)
        self._init_agents()
        logger.info("提示词重新加载完成")


class IntentRouter:
    """意图路由决策器"""

    def __init__(self, classify_agent):
        self.rules = {
            'tech': {
                'keywords': ['参数', '规格', '型号', '连接', '对比'],
                'patterns': [r'和.+比']
            },
            'price': {
                'keywords': ['便宜', '价', '砍价', '少点'],
                'patterns': [r'\d+元', r'能少\d+']
            }
        }
        self.classify_agent = classify_agent

    def detect(self, user_msg: str, item_desc, context) -> str:
        """三级路由策略（技术优先）"""
        text_clean = re.sub(r'[^\w\u4e00-\u9fa5]', '', user_msg)

        if any(kw in text_clean for kw in self.rules['tech']['keywords']):
            return 'tech'

        for pattern in self.rules['tech']['patterns']:
            if re.search(pattern, text_clean):
                return 'tech'

        for intent in ['price']:
            if any(kw in text_clean for kw in self.rules[intent]['keywords']):
                return intent
            for pattern in self.rules[intent]['patterns']:
                if re.search(pattern, text_clean):
                    return intent

        return self.classify_agent.generate(
            user_msg=user_msg,
            item_desc=item_desc,
            context=context
        )


class BaseAgent:
    """Agent基类"""

    def __init__(self, client, system_prompt, safety_filter, model_name: str = "qwen-max"):
        self.client = client
        self.system_prompt = system_prompt
        self.safety_filter = safety_filter
        self.model_name = model_name

    def generate(self, user_msg: str, item_desc: str, context: str, bargain_count: int = 0) -> str:
        messages = self._build_messages(user_msg, item_desc, context)
        response = self._call_llm(messages)
        return self.safety_filter(response)

    def _build_messages(self, user_msg: str, item_desc: str, context: str) -> List[Dict]:
        return [
            {"role": "system", "content": f"【商品信息】{item_desc}\n【你与客户对话历史】{context}\n{self.system_prompt}"},
            {"role": "user", "content": user_msg}
        ]

    def _call_llm(self, messages: List[Dict], temperature: float = 0.4) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=500,
            top_p=0.8
        )
        return response.choices[0].message.content


class PriceAgent(BaseAgent):
    """议价处理Agent"""

    def generate(self, user_msg: str, item_desc: str, context: str, bargain_count: int = 0) -> str:
        dynamic_temp = self._calc_temperature(bargain_count)
        messages = self._build_messages(user_msg, item_desc, context)
        messages[0]['content'] += f"\n▲当前议价轮次：{bargain_count}"
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=dynamic_temp,
            max_tokens=500,
            top_p=0.8
        )
        return self.safety_filter(response.choices[0].message.content)

    def _calc_temperature(self, bargain_count: int) -> float:
        return min(0.3 + bargain_count * 0.15, 0.9)


class TechAgent(BaseAgent):
    """技术咨询Agent"""

    def generate(self, user_msg: str, item_desc: str, context: str, bargain_count: int = 0) -> str:
        messages = self._build_messages(user_msg, item_desc, context)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.4,
            max_tokens=500,
            top_p=0.8,
            extra_body={"enable_search": True}
        )
        return self.safety_filter(response.choices[0].message.content)


class ClassifyAgent(BaseAgent):
    """意图识别Agent"""

    def generate(self, **args) -> str:
        return super().generate(**args)


class DefaultAgent(BaseAgent):
    """默认处理Agent"""

    def _call_llm(self, messages: List[Dict], *args) -> str:
        return super()._call_llm(messages, temperature=0.7)
