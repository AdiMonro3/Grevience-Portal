"""Complaint text -> category (+ confidence) and urgency."""

import logging
import re
from dataclasses import dataclass, field

import joblib

from app.config import settings

log = logging.getLogger(__name__)

# Urgency is rule-based on purpose: it is easy to explain on a demo and to tune.
# Each pattern is (regex, reason shown to officers).
URGENT_PATTERNS = [
    (r"accident|injur|\bhurt\b|ghayal|\bchot\b|gir (rahe|rahi|raha|gaya|gayi|gaye)\b", "people getting hurt"),
    (r"\bshock\b|current (lag|maar)|karant|live wire|spark|nange? taar|naked (electric )?wire", "electrical danger"),
    (r"\bfire\b|\baag\b|\bsmoke\b|dhu[a]+n|burning", "fire / smoke"),
    (r"danger|khatra|khatarnak|hazard|\bunsafe\b", "danger"),
    (r"\bchild|\bkids?\b|bacch?(e|on|a)\b|students?\b", "children at risk"),
    (r"hospital|ambulance|dengue|malaria|cholera|bimar|\bsick\b|diarrh|fever|bukhar|bite|kaat", "health risk"),
    (r"(open|khula) manhole|manhole (is )?(open|khula)|without cover", "open manhole"),
    (r"collaps|fallen|\bfell\b|may fall|tilted|jhuk", "structure may fall"),
    (r"block(ed|ing)? (the )?(road|traffic)|rasta (band|rok)|sadak band", "road blocked"),
    (r"emergency", "marked emergency"),
]
ELEVATED_PATTERNS = [
    (r"\b\d+\s*(din|days?|hafte|weeks?|mahine|months?)\b|\b(a|one|ek) (week|month|hafte|mahine)\b|kai (din|hafte)|many days|several days|since (last|past)", "pending for days"),
    (r"\bagain\b|phir se|multiple times|kai baar|repeated|already (made|complained)", "repeat problem"),
    (r"smell|stink|badb[ou]+|rotting|sad rahi", "foul smell"),
    (r"elderly|old (people|man|woman)|buzurg|senior citizen", "elderly affected"),
    (r"urgent|turant|jaldi|asap", "marked urgent"),
]
_URGENT = [(re.compile(p, re.I), reason) for p, reason in URGENT_PATTERNS]
_ELEVATED = [(re.compile(p, re.I), reason) for p, reason in ELEVATED_PATTERNS]


def score_urgency(text: str) -> tuple[int, list[str]]:
    """1 = normal, 2 = elevated, 3 = urgent, plus the reasons that matched."""
    urgent = [reason for rx, reason in _URGENT if rx.search(text)]
    elevated = [reason for rx, reason in _ELEVATED if rx.search(text)]
    level = 3 if urgent else 2 if elevated else 1
    return level, urgent + elevated


@dataclass
class Prediction:
    category_code: str
    confidence: float
    alternatives: list[tuple[str, float]] = field(default_factory=list)
    urgency: int = 1
    urgency_reasons: list[str] = field(default_factory=list)


class ComplaintClassifier:
    def __init__(self) -> None:
        self._model = None

    def load(self) -> None:
        if not settings.model_path.exists():
            log.warning("No model at %s, training one now...", settings.model_path)
            from app.ml.train import train_and_save

            train_and_save(settings.model_path, verbose=False)
        self._model = joblib.load(settings.model_path)
        log.info("Loaded complaint classifier with %d categories", len(self._model.classes_))

    @property
    def labels(self) -> list[str]:
        if self._model is None:
            self.load()
        return list(self._model.classes_)

    def predict(self, text: str) -> Prediction:
        if self._model is None:
            self.load()
        clean = " ".join(text.split())
        probs = self._model.predict_proba([clean])[0]
        ranked = sorted(zip(self._model.classes_, probs), key=lambda p: p[1], reverse=True)
        urgency, reasons = score_urgency(clean)
        return Prediction(
            category_code=str(ranked[0][0]),
            confidence=round(float(ranked[0][1]), 3),
            alternatives=[(str(c), round(float(p), 3)) for c, p in ranked[1:3]],
            urgency=urgency,
            urgency_reasons=reasons,
        )


classifier = ComplaintClassifier()
