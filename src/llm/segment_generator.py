# -*- coding: utf-8 -*-
"""
Segment Script Generator（保持接口不变：可直接替换）

注意：本文件只负责“分段组装 + 逐段调用 LLM”。
你项目里如果已经有自己的 LLMClient，请保持 generate(system,user,temperature) 接口一致即可。

支持三类可调参数（全部为可选覆盖，不影响旧调用）：
- humor_level: 0-3
- brief_density: short/long
- persona_preset: 使用 prompts.py 内置预设（balanced/warm/spicy）
- persona: 自定义 HostPersona（优先级最高）
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from typing import List, Optional, Protocol, Dict

from src.llm.templates.prompts import (
    ShowConfig,
    NewsItem,
    HostPersona,
    PRESET_PERSONAS,
    SYSTEM_PROMPT,
    spell_out_acronyms,
    build_opening_prompt,
    build_history_prompt,
    build_brief_news_prompt,
    build_deep_dive_prompt,
    build_outro_prompt,
)


# =========================
# 0) 口播润色 Prompt（内部常量）
# =========================

POLISH_PROMPT = r"""
你现在要做的是：把下面这段播客初稿，润色成"更适合 TTS 口播"的最终稿。

核心原则：为耳朵写，让 TTS 读起来自然、有停顿、像真人播音。

必须遵守的规则：
1) 保留事实：不增删关键事实、数字、来源；不杜撰"某机构数据显示"。
2) 口播化：
   - 短句为主，一句一个意思；长句拆成两句。
   - 减少书面连接词（"因此/综上/鉴于"等），改用口语（"所以/那么/这样一来"）。
   - 一口气别太长：大部分句子不超过 25 个字。
3) 停顿自然（TTS 友好）：
   - 主动使用句号分思路、逗号做短停顿。
   - 必要时用破折号/省略号做语气停顿（但别滥用）。
   - 避免一逗到底；该断句就断句。
4) 去模板痕迹：
   - 删掉"为什么这阵子突然重要了？"这类设问模板。
   - 若要解释"为什么现在被讨论"，必须先写清对比背景（例如"之前是…现在变成…"），否则改为陈述句或删除。
   - 禁止无对比背景却写"突然重要/突然火/这阵子突然/一下子变得/最近才重要"。
   - 避免在一串内容里机械重复"先/然后/接着/最后"这类连接词，改成更自然的短句或停顿。
5) 机构简称硬禁用：
   - 不得出现任何机构简称/缩写（例：中消协/工信部/发改委/证监会/央行/文旅部/住建部/卫健委/市监局/网信办等）。
   - 知道全称就写全称（例如"中消协"必须写"中国消费者协会"）。
   - 不确定全称就用中性指代（"相关部门/消费者组织/行业协会/平台方/监管部门"），绝不猜测。
6) 口头禅与称呼：
   - 把"我把它翻译成一句话/你可以这么理解/所以呢/简单说/翻译一下"等减少到"整段最多1次"，能不用就不用，用时要非常自然。
   - 避免频繁直接说"那跟你有什么关系呢"，更自然地改成"这和很多人/普通人/大家有什么关系"这类说法。
   - 优先用“大家/普通人/很多人/消费者”等集合称呼，而不是反复直接用“你”。
   - 避免生硬的"第一条/第二条/第三条"枚举，可以改成"还有一件事/再看一条消息"等更口语的过渡。
7) 段落角色一致：
   - 开场段不要抢先总结整期节目，不说"以上就是今天的快讯/内容"。
   - 快讯段的结尾不要假装节目结束，可以轻轻预告后面的慢放一条或收尾。
   - 深度段可以接着快讯的语气，但结尾要像把这一条讲完，而不是结束整期节目。
8) 最终只输出润色后的正文，不输出任何自检过程、说明、标注。

下面是初稿：
""".strip()


# =========================
# 1) LLM Client 接口
# =========================

class LLMClient(Protocol):
    def generate(self, *, system: str, user: str, temperature: float = 0.7) -> str:
        ...


class MockLLMClient:
    """开发时占位：不调用模型，仅回显 user prompt。"""
    def generate(self, *, system: str, user: str, temperature: float = 0.7) -> str:
        return (
            "【Mock 输出】\n"
            "（这里应替换为真实 L L M 输出）\n\n"
            f"--- user prompt ---\n{user}\n"
        )


# =========================
# 1) 段落定义
# =========================

@dataclass
class Segment:
    segment_id: str
    title: str
    prompt: str
    temperature: float = 0.7


# =========================
# 2) 内部工具：文本规范化
# =========================

def _normalize_text(text: str) -> str:
    """
    内部后处理：规范化机构简称为全称或中性指代。
    先处理英文缩写，再处理中文机构简称。
    """
    if not text:
        return text
    
    # 1) 先调用 spell_out_acronyms 处理英文缩写
    result = spell_out_acronyms(text)
    
    # 2) 机构简称替换表（扩展版）
    replacements = {
        # 中央部委
        "中消协": "中国消费者协会",
        "工信部": "工业和信息化部",
        "发改委": "国家发展和改革委员会",
        "证监会": "中国证券监督管理委员会",
        "银保监会": "中国银行保险监督管理委员会",
        "央行": "中国人民银行",
        "文旅部": "文化和旅游部",
        "住建部": "住房和城乡建设部",
        "商务部": "商务部",
        "教育部": "教育部",
        "财政部": "财政部",
        "交通部": "交通运输部",
        "农业部": "农业农村部",
        "环保部": "生态环境部",
        "卫健委": "国家卫生健康委员会",
        "市监局": "市场监督管理局",
        "网信办": "国家互联网信息办公室",
        "人社部": "人力资源和社会保障部",
        "自然资源部": "自然资源部",
        "应急部": "应急管理部",
        "科技部": "科学技术部",
        "公安部": "公安部",
        "民政部": "民政部",
        "司法部": "司法部",
        "外交部": "外交部",
        "国防部": "国防部",
        "退役军人部": "退役军人事务部",
        # 其他常见简称
        "国资委": "国务院国有资产监督管理委员会",
        "税务总局": "国家税务总局",
        "海关总署": "海关总署",
        "广电总局": "国家广播电视总局",
        "体育总局": "国家体育总局",
        "统计局": "国家统计局",
        "知识产权局": "国家知识产权局",
        "药监局": "国家药品监督管理局",
        "林草局": "国家林业和草原局",
        "邮政局": "国家邮政局",
        "文物局": "国家文物局",
        "中科院": "中国科学院",
        "社科院": "中国社会科学院",
        "工程院": "中国工程院",
    }
    
    # 3) 执行替换
    for abbr, full in replacements.items():
        result = result.replace(abbr, full)
    
    return result


# =========================
# 3) 生成器
# =========================

class SegmentScriptGenerator:
    def __init__(
        self,
        llm: LLMClient,
        config: Optional[ShowConfig] = None,
    ) -> None:
        self.llm = llm
        self.config = config or ShowConfig()

    def _config_with_overrides(
        self,
        *,
        humor_level: Optional[int] = None,
        brief_density: Optional[str] = None,
        persona_preset: Optional[str] = None,
        persona: Optional[HostPersona] = None,
    ) -> ShowConfig:
        cfg = self.config

        if humor_level is not None:
            cfg = replace(cfg, humor_level=int(humor_level))

        if brief_density is not None:
            bd = str(brief_density).lower().strip()
            if bd not in ("short", "long"):
                bd = cfg.brief_density
            cfg = replace(cfg, brief_density=bd)

        if persona is not None:
            cfg = replace(cfg, persona=persona)

        if persona_preset is not None:
            pp = str(persona_preset).strip()
            if pp and pp in PRESET_PERSONAS:
                cfg = replace(cfg, persona_preset=pp, persona=None)
            elif pp:
                cfg = replace(cfg, persona_preset=cfg.persona_preset)

        return cfg

    def build_segments(
        self,
        *,
        cfg: ShowConfig,
        date_line: str,
        weekday_line: Optional[str],
        lunar_line: Optional[str],
        tease_points: List[str],
        history_event: str,
        news_items: List[NewsItem],
        deep_topic: str,
        deep_facts: str,
        outro_hint: str,
        cta_hint: Optional[str] = None,
    ) -> List[Segment]:
        segs: List[Segment] = []

        segs.append(
            Segment(
                segment_id="opening",
                title="开机自检（开场）",
                prompt=build_opening_prompt(cfg, date_line, lunar_line, weekday_line, tease_points),
                temperature=0.6,
            )
        )

        segs.append(
            Segment(
                segment_id="history",
                title="时间倒带（历史上的今天）",
                prompt=build_history_prompt(cfg, history_event),
                temperature=0.7,
            )
        )

        segs.append(
            Segment(
                segment_id="briefs",
                title="快进快讯（资讯串讲）",
                prompt=build_brief_news_prompt(cfg, news_items),
                temperature=0.6,
            )
        )

        segs.append(
            Segment(
                segment_id="deep_dive",
                title="慢放一条（深度拆解）",
                prompt=build_deep_dive_prompt(cfg, deep_topic, deep_facts),
                temperature=0.7,
            )
        )

        segs.append(
            Segment(
                segment_id="outro",
                title="关机前一句（收尾）",
                prompt=build_outro_prompt(cfg, outro_hint, cta_hint=cta_hint),
                temperature=0.6,
            )
        )

        return segs

    def render(
        self,
        *,
        date_line: str,
        weekday_line: Optional[str] = None,
        lunar_line: Optional[str] = None,
        tease_points: Optional[List[str]] = None,
        history_event: str,
        news_items: List[NewsItem],
        deep_topic: str,
        deep_facts: str,
        outro_hint: str = "明天我们再展开",
        cta_hint: Optional[str] = "喜欢这种A I切片的话，点个关注，就当给我充电。",
        # 旋钮：可按每一期覆盖（不影响旧调用）
        humor_level: Optional[int] = None,
        brief_density: Optional[str] = None,
        persona_preset: Optional[str] = None,
        persona: Optional[HostPersona] = None,
    ) -> Dict[str, str]:
        """
        返回：
          {
            "full_script": "...",
            "opening": "...",
            ...
          }
        """
        cfg = self._config_with_overrides(
            humor_level=humor_level,
            brief_density=brief_density,
            persona_preset=persona_preset,
            persona=persona,
        )

        # 如果未提供 tease_points，就从 news_items 标题里取前 6 条做信息地图
        if not tease_points:
            tease_points = [it.title.strip() for it in news_items[:6]]

        segments = self.build_segments(
            cfg=cfg,
            date_line=date_line,
            weekday_line=weekday_line,
            lunar_line=lunar_line,
            tease_points=tease_points,
            history_event=history_event,
            news_items=news_items,
            deep_topic=deep_topic,
            deep_facts=deep_facts,
            outro_hint=outro_hint,
            cta_hint=cta_hint,
        )

        outputs: Dict[str, str] = {}
        parts: List[str] = []

        for seg in segments:
            # 第一次调用：生成初稿
            draft = self.llm.generate(
                system=SYSTEM_PROMPT,
                user=seg.prompt,
                temperature=seg.temperature,
            ).strip()
            
            # 第二次调用：口播润色
            # 温度降低到0.4，使语言更稳定、更像播音稿
            polished = self.llm.generate(
                system=SYSTEM_PROMPT,
                user=f"{POLISH_PROMPT}\n\n{draft}",
                temperature=0.4,
            ).strip()
            
            # 内部后处理：规范化机构简称
            final_text = _normalize_text(polished)
            
            outputs[seg.segment_id] = final_text
            parts.append(final_text)

        outputs["full_script"] = "\n\n".join([p for p in parts if p])
        return outputs


# =========================
# 3) Demo 数据（保留）
# =========================

def demo_inputs() -> Dict:
    news_items = [
        NewsItem(
            title="智能眼镜首次纳入国补",
            facts="首批625亿国补资金下达，明年补贴范围扩大到智能眼镜等。",
            context="对消费者来说，可能意味着入手门槛下降；对品牌来说，是一波抢位战。",
        ),
        NewsItem(
            title="宇树科技线下首店北京开业",
            facts="线下门店集中展示四足机器狗与人形机器人等产品。",
            context="机器人从展会走进商场，是‘能看见的商业化’。",
        ),
        NewsItem(
            title="必胜客开始卖烤串做夜宵",
            facts="部分门店新增夜宵时段与烤串菜单，价格贴近连锁烧烤。",
            context="餐饮巨头在用‘第二曲线’对抗存量竞争。",
        ),
        NewsItem(
            title="国产载人飞艇拿到生产许可证",
            facts="祥云A700取得全国首张国产载人飞艇生产许可证。",
            context="低空经济从概念走向交付，接下来拼的是场景。",
        ),
    ]

    return dict(
        date_line="2026年1月4日",
        weekday_line="星期日",
        lunar_line=None,
        tease_points=[
            "国补把智能眼镜也算进来了",
            "机器人开店，离日常更近一步",
            "必胜客卖烤串，夜宵开始内卷",
            "飞艇拿到准生证，低空要进城",
        ],
        history_event="在1996年的12月31日，波音与麦道宣布合并，这被很多人视作行业格局的一次改写，也给后来的文化磨合埋下伏笔。",
        news_items=news_items,
        deep_topic="载人飞艇为什么突然火了",
        deep_facts=(
            "素材要点：取得生产许可证；可载10人，航时可达10小时；"
            "优势是低空慢速、短距起降；安全依赖材料、冗余与试飞验证；"
            "主要场景包括低空观光、城市安保与巡检、应急通信与物资投送。"
        ),
        outro_hint="明天我们再展开",
        cta_hint="如果你觉得有用，点个关注，咱们每天一起把信息切一下。",
    )


# =========================
# 4) CLI（保留）
# =========================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="运行 demo（使用 MockLLM）")
    parser.add_argument("--humor", type=int, default=None, help="幽默度 0-3（覆盖 config）")
    parser.add_argument("--density", type=str, default=None, help="快讯密度 short/long（覆盖 config）")
    parser.add_argument(
        "--persona",
        type=str,
        default=None,
        help=f"主持人个性预设（覆盖 config）。可选：{', '.join(PRESET_PERSONAS.keys())}",
    )
    args = parser.parse_args()

    if args.demo:
        llm = MockLLMClient()
        gen = SegmentScriptGenerator(llm=llm, config=ShowConfig())
        out = gen.render(**demo_inputs(), humor_level=args.humor, brief_density=args.density, persona_preset=args.persona)
        print(out["full_script"])
        return

    print("请在你的工程中引入 SegmentScriptGenerator，并传入真实的 LLMClient。")


if __name__ == "__main__":
    main()
