from __future__ import annotations

from string import Formatter


class PromptManager:
    """
    Administra y renderiza prompts reutilizables
    para los diferentes módulos de ARMS-AI.
    """

    PROMPTS: dict[str, str] = {
        "portfolio_analysis": (
            "Pregunta del usuario:\n"
            "{question}\n\n"
            "Resumen del motor de decisiones:\n"
            "{decision_summary}\n\n"
            "Responde de forma clara, profesional "
            "y accionable."
        ),
        "risk_explanation": (
            "Explica el nivel de riesgo del portafolio "
            "usando esta información:\n"
            "{risk_summary}"
        ),
        "executive_summary": (
            "Genera un resumen ejecutivo con base en:\n"
            "{analysis_summary}"
        ),
    }

    SYSTEM_PROMPTS: dict[str, str] = {
        "financial_copilot": (
            "Eres ARMS-AI, un copiloto financiero "
            "profesional. Explicas métricas, riesgos "
            "y recomendaciones con claridad, sin "
            "inventar datos ni garantizar resultados."
        ),
        "executive_analyst": (
            "Eres ARMS-AI, un analista ejecutivo "
            "orientado a generar reportes breves, "
            "precisos y profesionales."
        ),
    }

    def available_prompts(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            self.PROMPTS
        )

    def render(
        self,
        *,
        name: str,
        variables: dict[str, object],
    ) -> str:
        normalized_name = (
            str(name)
            .strip()
            .lower()
        )

        if normalized_name not in self.PROMPTS:
            raise ValueError(
                "prompt no reconocido."
            )

        template = self.PROMPTS[
            normalized_name
        ]

        required_variables = {
            field_name
            for _, field_name, _, _
            in Formatter().parse(
                template
            )
            if field_name
        }

        provided_variables = set(
            variables
        )

        missing_variables = (
            required_variables
            - provided_variables
        )

        if missing_variables:
            missing_list = ", ".join(
                sorted(
                    missing_variables
                )
            )

            raise ValueError(
                "variables debe incluir: "
                f"{missing_list}."
            )

        normalized_variables = {
            key: str(value).strip()
            for key, value
            in variables.items()
        }

        return template.format(
            **normalized_variables
        )

    def system_prompt(
        self,
        *,
        role: str,
    ) -> str:
        normalized_role = (
            str(role)
            .strip()
            .lower()
        )

        if (
            normalized_role
            not in self.SYSTEM_PROMPTS
        ):
            raise ValueError(
                "role no reconocido."
            )

        return self.SYSTEM_PROMPTS[
            normalized_role
        ]
