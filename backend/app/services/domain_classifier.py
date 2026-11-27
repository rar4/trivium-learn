import json
import logging
import re
from typing import Dict, Any
from app.services.llm_gateway import LLMGateway
from json_repair import repair_json

logger = logging.getLogger(__name__)

class DomainClassifier:
    """
    Classificador Universal de Domínios e Orquestrador Epistemológico (Padrão NotebookLM / Perplexity):
    Infere a natureza ontológica e pedagógica de qualquer assunto humano a partir de primeiros princípios,
    gerando o contrato de persona, tom de voz, métricas de evidência e arquétipos visuais.
    """

    DEFAULT_PROFILE: Dict[str, Any] = {
        "dynamic_domain_name": "Conhecimento Prático e Fundamentos Aplicados",
        "persona_title": "Mentor Especialista e Comunicador Apaixonado",
        "tone_of_voice": "Tom conversacional, cativante, empático e cristalino. Fala diretamente com o aluno ('você'), usa metáforas visuais do dia a dia, zero burocracia acadêmica e explica a intuição física como um mentor amigo apaixonado pela matéria.",
        "evaluation_rubric_core": "Avalie a compreensão intuitiva dos mecanismos fundamentais e a capacidade de raciocínio prático diante de situações reais.",
        "visual_archetype": "Diagramas esquemáticos clássicos, instrumentos de precisão, mapas conceituais e ferramentas emblemáticas da disciplina",
        "case_study_format": "História real ou dilema prático que ilustra de forma fascinante o conceito em ação no cotidiano."
    }

    # Domain persona switching: 'auto' lets the AI infer one from the topic;
    # the other presets force a distinct pedagogical voice across the course.
    PERSONAS: Dict[str, Dict[str, Any]] = {
        "auto": {
            "label_en": "Auto (domain AI)", "label_pt": "Automática (IA do domínio)",
            "persona_title": None, "tone_of_voice": None,
        },
        "practitioner": {
            "label_en": "Practical Mentor", "label_pt": "Mentor Prático",
            "persona_title": "The Practitioner — a battle-tested specialist who teaches the move that actually works",
            "tone_of_voice": "Direct, hands-on and outcome-driven. Explain the exact working procedure, the trade-off and the common failure, then hand the learner a reusable checklist. Concrete numbers and real workflows over theory.",
        },
        "socratic": {
            "label_en": "Socratic Philosopher", "label_pt": "Filósofo Socrático",
            "persona_title": "The Socratic Guide — a question-driven philosopher who makes the learner discover the answer",
            "tone_of_voice": "Pose sharp questions before giving definitions, expose contradictions in intuitive answers, and guide the reader to the insight themselves. Calm, curious and relentlessly precise.",
        },
        "storyteller": {
            "label_en": "Storytelling Essayist", "label_pt": "Ensaísta Narrador",
            "persona_title": "The Storytelling Essayist — a vivid narrator who turns every concept into a memorable scene",
            "tone_of_voice": "Narrative, cinematic and sensory. Open with a concrete scene or true anecdote, weave the concept through it, and close with a surprising human angle. Avoid dry bullet-point exposition.",
        },
        "rigorist": {
            "label_en": "Rigorous Scientist", "label_pt": "Cientista Rigoroso",
            "persona_title": "The Rigorous Scientist — an evidence-first researcher who separates fact from plausible story",
            "tone_of_voice": "Precise, evidence-led and skeptical. Define terms exactly, cite the verified source for each claim, show the experiment or data behind it, and flag uncertainty explicitly.",
        },
    }

    @classmethod
    def personas_payload(cls) -> list:
        return [{"id": pid, "label_en": p["label_en"], "label_pt": p["label_pt"]}
                for pid, p in cls.PERSONAS.items()]

    @classmethod
    def apply_persona(cls, profile: Dict[str, Any], persona_id: str | None) -> Dict[str, Any]:
        """Override the AI-inferred persona when the learner picked one."""
        preset = cls.PERSONAS.get((persona_id or "auto").strip().lower())
        if preset and preset.get("persona_title"):
            profile["persona_title"] = preset["persona_title"]
            profile["tone_of_voice"] = preset["tone_of_voice"]
            profile["selected_persona"] = persona_id
        else:
            profile["selected_persona"] = "auto"
        return profile

    @classmethod
    async def classify(cls, topic: str, level: str = "Básico", persona: str | None = None) -> Dict[str, Any]:
        system_prompt = (
            "Você é o Orquestrador Epistemológico e Pedagógico da Trivium.\n"
            "Sua missão é desenhar a alma pedagógica de um curso envolvente, fascinante e memorável (Padrão Masterclass / Coursera / Hitch).\n"
            "O objetivo central de QUALQUER curso na Trivium é ser GOSTOSO DE LER, CATIVANTE E FÁCIL DE ENTENDER DO ZERO ABSOLUTO, mesmo em temas técnicos densos.\n\n"
            "Diretrizes obrigatórias para o perfil:\n"
            "1. Persona: Um mentor carismático, apaixonado e acessível, que domina o assunto profundamente mas fala de forma simples e envolvente.\n"
            "2. Tom de Voz: OBRIGATORIAMENTE conversacional, fluido, convidativo e visual. Proibido tom de relatório burocrático ou enciclopédia fria.\n\n"
            "Retorne ESTRITAMENTE um objeto JSON válido (sem markdown extra) com a seguinte estrutura:\n"
            "{\n"
            '  "dynamic_domain_name": "Nome descritivo e instigante do campo",\n'
            '  "persona_title": "O mentor ideal (ex: \'Engenheiro Apaixonado e Mentor Prático\')",\n'
            '  "tone_of_voice": "Instrução enfática de escrita: conversa direta com o leitor, metáforas vívidas, ritmo agradável e clareza absoluta.",\n'
            '  "visual_archetype": "Descreva em inglês de 1 a 3 objetos físicos tangíveis da disciplina no estilo gravura editorial clássica (máximo 4 elementos visuais). Sem pessoas nem rostos.",\n'
            '  "case_study_format": "Uma história ou cenário prático real e intrigante que demonstre o conceito em ação."\n'
            "}"
        )
        user_prompt = f"Tema solicitado: '{topic}'\nNível de profundidade: '{level}'"

        try:
            raw_response = await LLMGateway.generate_text(
                system_prompt,
                user_prompt,
                max_tokens=500,
                timeout=25
            )
            raw_clean = raw_response.strip()
            # Localiza JSON
            start = raw_clean.find("{")
            end = raw_clean.rfind("}")
            if start != -1 and end != -1 and end > start:
                raw_clean = raw_clean[start:end+1]

            data = json.loads(repair_json(raw_clean))
            profile = {
                "dynamic_domain_name": str(data.get("dynamic_domain_name") or cls.DEFAULT_PROFILE["dynamic_domain_name"]).strip(),
                "persona_title": str(data.get("persona_title") or cls.DEFAULT_PROFILE["persona_title"]).strip(),
                "tone_of_voice": str(data.get("tone_of_voice") or cls.DEFAULT_PROFILE["tone_of_voice"]).strip(),
                "evaluation_rubric_core": str(data.get("evaluation_rubric_core") or cls.DEFAULT_PROFILE["evaluation_rubric_core"]).strip(),
                "visual_archetype": str(data.get("visual_archetype") or cls.DEFAULT_PROFILE["visual_archetype"]).strip(),
                "case_study_format": str(data.get("case_study_format") or cls.DEFAULT_PROFILE["case_study_format"]).strip(),
            }
            logger.info(f"[DomainClassifier] Perfil gerado para '{topic}': {profile['dynamic_domain_name']} ({profile['persona_title']})")
            return cls.apply_persona(profile, persona)
        except Exception as e:
            logger.warning(f"[DomainClassifier] Fallback heurístico ativado para '{topic}': {e}")
            fallback = dict(cls.DEFAULT_PROFILE)
            fallback["dynamic_domain_name"] = f"Estudos Especializados em {topic}"
            fallback["persona_title"] = f"Especialista e Pesquisador em {topic}"
            return cls.apply_persona(fallback, persona)
