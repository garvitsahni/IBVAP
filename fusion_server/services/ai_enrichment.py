"""AI Enrichment Service — LLaVA-based natural language alert explanation."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AIEnrichmentService:
    """Enriches fired alerts with natural language explanations using LLaVA."""

    def __init__(self, model_name: str = "llava-hf/llava-1.5-7b-hf"):
        self._model_name = model_name
        self._model = None
        self._processor = None
        self._initialized = False

    def _lazy_init(self):
        """Initialize model on first use."""
        if self._initialized:
            return
        try:
            from transformers import LlavaForConditionalGeneration, AutoProcessor
            logger.info(f"Loading LLaVA model: {self._model_name}")
            self._processor = AutoProcessor.from_pretrained(self._model_name)
            self._model = LlavaForConditionalGeneration.from_pretrained(
                self._model_name,
                torch_dtype="auto",
                device_map="auto",
            )
            self._initialized = True
            logger.info("LLaVA model loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load LLaVA: {e}. Using template fallback.")
            self._initialized = True

    def enrich(self, alert_data: dict) -> str:
        """
        Generate natural language explanation for an alert.
        Returns explanation string.
        """
        try:
            return self._call_llava(alert_data)
        except Exception as e:
            logger.warning(f"LLaVA enrichment failed: {e}. Using template.")
            return self._template_explanation(alert_data)

    def _call_llava(self, alert_data: dict) -> str:
        """Call LLaVA model for explanation generation."""
        self._lazy_init()

        if self._model is None:
            return self._template_explanation(alert_data)

        prompt = self._build_prompt(alert_data)

        inputs = self._processor(text=prompt, return_tensors="pt")
        if hasattr(self._model, 'device'):
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        output = self._model.generate(**inputs, max_new_tokens=200)
        response = self._processor.decode(output[0], skip_special_tokens=True)

        # Extract just the explanation part
        if "ASSISTANT:" in response:
            response = response.split("ASSISTANT:")[-1].strip()

        return response

    def _build_prompt(self, alert_data: dict) -> str:
        """Build prompt for LLaVA."""
        reason = alert_data.get("reason", "unknown")
        camera = alert_data.get("camera_id", "unknown")
        score = alert_data.get("threat_score", 0.0)
        trajectory = alert_data.get("trajectory", {})

        prompt = (
            f"USER: Describe this security alert in detail. "
            f"Alert type: {reason}. Camera: {camera}. "
            f"Threat score: {score:.0%}. "
        )

        if trajectory.get("history"):
            prompt += f"The object moved through {len(trajectory['history'])} positions. "

        prompt += (
            "Provide a concise, professional security assessment. "
            "ASSISTANT:"
        )
        return prompt

    def _template_explanation(self, alert_data: dict) -> str:
        """Template-based fallback explanation."""
        reason = alert_data.get("reason", "unknown")
        camera = alert_data.get("camera_id", "unknown")
        score = alert_data.get("threat_score", 0.0)
        obj_id = alert_data.get("object_id", "unknown")

        templates = {
            "enter": f"Object {obj_id} entered restricted zone on {camera}. Threat level: {score:.0%}.",
            "exit": f"Object {obj_id} exited monitored area on {camera}. Threat level: {score:.0%}.",
            "dwell": f"Object {obj_id} loitering in restricted area on {camera}. Threat level: {score:.0%}.",
            "loitering": f"Object {obj_id} detected loitering on {camera}. Threat level: {score:.0%}.",
            "path_reversal": f"Object {obj_id} reversed direction near restricted area on {camera}. Threat level: {score:.0%}.",
            "group_clustering": f"Group activity detected on {camera}. Threat level: {score:.0%}.",
            "watchlist_match": f"Object {obj_id} matched watchlist entry on {camera}. Threat level: {score:.0%}.",
        }

        return templates.get(reason, f"Alert triggered on {camera}: {reason}. Threat level: {score:.0%}.")
