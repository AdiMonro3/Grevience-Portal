"""Train the complaint category classifier and save it to app/ml/model.joblib.

    cd backend && uv run python -m app.ml.train

Model: TF-IDF on words (1-2 grams) + character n-grams (3-5, robust to Hinglish
spelling like paani/pani, gaddha/gadda) -> multinomial logistic regression.
"""

import csv
import random
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import FeatureUnion, Pipeline

from app.config import settings
from app.ml.training_data import LOCATIONS, PREFIXES, SEEDS, SUFFIXES

EXTRA_DATA = Path(__file__).parent / "data" / "extra.csv"  # optional: text,label
VARIANTS_PER_SEED = 6


def build_dataset(seed: int = 42) -> tuple[list[str], list[str], list[int]]:
    """Returns texts, labels and a group id per row (the seed sentence it came from)."""
    rng = random.Random(seed)
    texts, labels, groups = [], [], []
    group = 0
    for label, sentences in SEEDS.items():
        for sentence in sentences:
            texts.append(sentence)
            labels.append(label)
            groups.append(group)
            for _ in range(VARIANTS_PER_SEED):
                texts.append(
                    rng.choice(PREFIXES) + sentence + rng.choice(LOCATIONS) + rng.choice(SUFFIXES)
                )
                labels.append(label)
                groups.append(group)
            group += 1

    if EXTRA_DATA.exists():  # e.g. admin corrections exported later (Phase 4)
        with EXTRA_DATA.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("text") and row.get("label") in SEEDS:
                    texts.append(row["text"])
                    labels.append(row["label"])
                    groups.append(group)
                    group += 1
    return texts, labels, groups


def make_pipeline() -> Pipeline:
    features = FeatureUnion(
        [
            ("words", TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True)),
            (
                "chars",
                TfidfVectorizer(
                    lowercase=True, analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True
                ),
            ),
        ]
    )
    return Pipeline([("features", features), ("clf", LogisticRegression(C=20, max_iter=3000))])


def evaluate(texts, labels, groups) -> float:
    """Cross-validation where every variant of a seed sentence stays in the same fold,
    so the score reflects sentences the model has never seen."""
    texts, labels = np.array(texts, dtype=object), np.array(labels)
    scores = []
    for train_idx, test_idx in GroupKFold(n_splits=5).split(texts, labels, groups):
        model = make_pipeline().fit(texts[train_idx], labels[train_idx])
        scores.append((model.predict(texts[test_idx]) == labels[test_idx]).mean())
    return float(np.mean(scores))


def train_and_save(path: Path | None = None, verbose: bool = True) -> Pipeline:
    path = path or settings.model_path
    texts, labels, groups = build_dataset()
    if verbose:
        print(f"Training on {len(texts)} examples, {len(set(labels))} categories")
        print(f"Grouped 5-fold CV accuracy (unseen sentences): {evaluate(texts, labels, groups):.1%}")
    model = make_pipeline().fit(texts, labels)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    if verbose:
        print(f"Saved model to {path}")
    return model


if __name__ == "__main__":
    model = train_and_save()
    samples = [
        "Hamare sector mein 4 din se paani nahi aa raha, tanki khali hai",
        "sadak pe bada gaddha hai, bike wale gir rahe hain",
        "There are electric wires hanging near the park, kids play there",
        "Garbage dumped outside the school since a week",
        "kuch problem hai please dekho",
    ]
    print("\nSample predictions:")
    for text in samples:
        probs = model.predict_proba([text])[0]
        best = int(probs.argmax())
        print(f"  {probs[best]:.2f}  {model.classes_[best]:<18} <- {text}")
