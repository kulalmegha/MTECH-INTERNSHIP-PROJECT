"""
Script to evaluate emotion and sentiment models on GoEmotions test split,
generate confusion matrix plot, evaluate 15 synthetic victim check-in sentences,
and output documentation for docs/model_evaluation.md.
"""
import os
import sys
import json
sys.path.insert(0, os.path.abspath("backend"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from datasets import load_dataset
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from transformers import pipeline

from app.ai.nlp_service import (
    GO_EMOTIONS_MAPPING,
    RuleBasedOfflineNLPService,
    map_go_emotion_to_category,
)

TARGET_CLASSES = ["fear/worry", "sadness", "anger", "joy", "neutral", "other"]

# Published sentiment grouping for GoEmotions:
# positive: admiration, amusement, approval, caring, desire, excitement, gratitude, joy, love, optimism, pride, relief
# negative: anger, annoyance, disappointment, disapproval, disgust, embarrassment, fear, grief, nervousness, remorse, sadness
# neutral: neutral
POSITIVE_EMOTIONS = {
    "admiration", "amusement", "approval", "caring", "desire", "excitement",
    "gratitude", "joy", "love", "optimism", "pride", "relief"
}
NEGATIVE_EMOTIONS = {
    "anger", "annoyance", "disappointment", "disapproval", "disgust",
    "embarrassment", "fear", "grief", "nervousness", "remorse", "sadness"
}


def get_sentiment_from_emotions(emotion_list):
    has_pos = any(e in POSITIVE_EMOTIONS for e in emotion_list)
    has_neg = any(e in NEGATIVE_EMOTIONS for e in emotion_list)
    if has_pos and not has_neg:
        return "positive"
    elif has_neg and not has_pos:
        return "negative"
    else:
        return "neutral"


def main():
    print("Loading GoEmotions simplified dataset...")
    # Load test split
    ds = load_dataset("google-research-datasets/go_emotions", "simplified", split="test")
    raw_labels = ds.features["labels"].feature.names
    print(f"Total test instances: {len(ds)}, number of raw labels: {len(raw_labels)}")

    # We evaluate on a representative subset of single-label examples for clean multiclass metrics
    # (single label allows standard multiclass confusion matrix and per-class precision/recall)
    single_label_samples = []
    for item in ds:
        labels = item["labels"]
        if len(labels) == 1:
            raw_emo = raw_labels[labels[0]]
            grouped_emo = map_go_emotion_to_category(raw_emo)
            sent = "positive" if raw_emo in POSITIVE_EMOTIONS else ("negative" if raw_emo in NEGATIVE_EMOTIONS else "neutral")
            single_label_samples.append({
                "text": item["text"],
                "raw_emotion": raw_emo,
                "grouped_emotion": grouped_emo,
                "sentiment": sent,
            })

    print(f"Found {len(single_label_samples)} single-label test samples.", flush=True)

    # Evaluate on a representative sample of 250 test examples for fast local CPU evaluation
    sample_size = min(250, len(single_label_samples))
    eval_set = single_label_samples[:sample_size]

    print(f"Loading emotion classification pipeline (SamLowe/roberta-base-go_emotions)...", flush=True)
    try:
        emo_pipe = pipeline("text-classification", model="SamLowe/roberta-base-go_emotions", device=-1)
        print("Transformer model loaded successfully!", flush=True)
    except Exception as e:
        print(f"Could not load transformer pipeline: {e}. Using offline evaluator.", flush=True)
        emo_pipe = None

    y_true_emo = [s["grouped_emotion"] for s in eval_set]
    y_pred_emo = []

    texts = [s["text"] for s in eval_set]

    if emo_pipe is not None:
        print(f"Running inference on {len(texts)} samples in batches...", flush=True)
        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            preds = emo_pipe(batch, truncation=True, max_length=128)
            for p in preds:
                y_pred_emo.append(map_go_emotion_to_category(p["label"]))
            print(f"Evaluated {min(i + batch_size, len(texts))}/{len(texts)} samples...", flush=True)
    else:
        offline = RuleBasedOfflineNLPService()
        for t in texts:
            y_pred_emo.append(offline.analyze_text(t)["emotion_label"])

    # Compute Emotion Metrics
    acc = accuracy_score(y_true_emo, y_pred_emo)
    macro_f1 = f1_score(y_true_emo, y_pred_emo, labels=TARGET_CLASSES, average="macro", zero_division=0)
    report = classification_report(y_true_emo, y_pred_emo, labels=TARGET_CLASSES, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true_emo, y_pred_emo, labels=TARGET_CLASSES)

    print("\n--- Emotion Classification Results ---")
    print(f"Accuracy: {acc:.4f}")
    print(f"Macro F1: {macro_f1:.4f}")
    for cls in TARGET_CLASSES:
        metrics = report.get(cls, {})
        print(f"  {cls:12s} Precision: {metrics.get('precision', 0):.4f} | Recall: {metrics.get('recall', 0):.4f} | F1: {metrics.get('f1-score', 0):.4f}")

    # Plot Confusion Matrix
    os.makedirs("docs", exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    ax.figure.colorbar(im, ax=ax)
    ax.set(
        xticks=np.arange(len(TARGET_CLASSES)),
        yticks=np.arange(len(TARGET_CLASSES)),
        xticklabels=TARGET_CLASSES,
        yticklabels=TARGET_CLASSES,
        title="Emotion Classification Confusion Matrix\n(GoEmotions 6-Class Grouped)",
        ylabel="True Label",
        xlabel="Predicted Label",
    )
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    # Annotate values
    thresh = cm.max() / 2.0
    for i in range(len(TARGET_CLASSES)):
        for j in range(len(TARGET_CLASSES)):
            ax.text(
                j, i, format(cm[i, j], "d"),
                ha="center", va="center",
                color="white" if cm[i, j] > thresh else "black"
            )
    fig.tight_layout()
    cm_path = os.path.join("docs", "confusion_matrix.png")
    plt.savefig(cm_path, dpi=200)
    plt.close()
    print(f"Saved confusion matrix plot to {cm_path}")

    # Sentiment evaluation
    print("\nLoading sentiment pipeline (cardiffnlp/twitter-roberta-base-sentiment-latest)...")
    try:
        sent_pipe = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment-latest", device=-1)
    except Exception as e:
        print(f"Could not load sentiment model: {e}")
        sent_pipe = None

    sent_eval_set = eval_set[:500]  # 500 samples
    y_true_sent = [s["sentiment"] for s in sent_eval_set]
    y_pred_sent = []

    if sent_pipe is not None:
        sent_texts = [s["text"] for s in sent_eval_set]
        for i in range(0, len(sent_texts), 64):
            batch = sent_texts[i : i + 64]
            preds = sent_pipe(batch, truncation=True, max_length=128)
            for p in preds:
                lbl = p["label"].lower()
                if "neg" in lbl or lbl == "label_0":
                    y_pred_sent.append("negative")
                elif "pos" in lbl or lbl == "label_2":
                    y_pred_sent.append("positive")
                else:
                    y_pred_sent.append("neutral")
    else:
        offline = RuleBasedOfflineNLPService()
        for s in sent_eval_set:
            y_pred_sent.append(offline.analyze_text(s["text"])["sentiment_label"])

    sent_acc = accuracy_score(y_true_sent, y_pred_sent)
    sent_macro_f1 = f1_score(y_true_sent, y_pred_sent, average="macro", zero_division=0)
    print(f"Sentiment Accuracy: {sent_acc:.4f}, Macro F1: {sent_macro_f1:.4f}")

    # Evaluate 15 Hand-Written Synthetic Check-In Sentences
    synthetic_sentences = [
        ("I am worried about the upcoming court hearing, and I have not been sleeping properly.", "Anticipatory anxiety / Insomnia"),
        ("They drove past my house again last night shouting threats. I feel terrified.", "Active intimidation / Threat"),
        ("I feel completely numb and empty inside. Nothing seems to matter anymore.", "Depressive numbness / Helplessness"),
        ("I cannot stop crying today. The grief is overwhelming and heavy.", "Acute grief / Somatic bereavement"),
        ("I am so furious at the perpetrators walking free while we live in hiding.", "Trauma-related rage / Injustice"),
        ("I met with the legal aid advocate today and felt a glimmer of hope.", "Positive resilience / Advocacy connection"),
        ("We moved to a safehouse and for the first time in months I felt safe.", "Relief / Physical safety restored"),
        ("Every sudden noise outside sends my heart racing with panic.", "Hyperarousal / PTSD startle response"),
        ("I feel isolated from everyone in my community since the incident happened.", "Social stigma / Alienation"),
        ("The nightmares keep waking me up in cold sweats, but I am trying to cope.", "Trauma intrusion / Coping effort"),
        ("I need to talk to someone right now, I cannot manage these panic attacks alone.", "Acute crisis / Voluntary outreach"),
        ("Things are quiet today. Just doing normal chores at home.", "Routine baseline / Neutral activity"),
        ("I am deeply grateful for the counsellor checking in on me and my family.", "Social gratitude / Supportive bond"),
        ("I feel so bitter and resentful about everything that was taken from us.", "Resentment / Long-term grievance"),
        ("I managed to take a short walk outside today without feeling completely overwhelmed.", "Behavioral recovery milestone"),
    ]

    print("\nEvaluating 15 synthetic check-in sentences...")
    synth_results = []
    for text, context in synthetic_sentences:
        # Sentiment
        if sent_pipe is not None:
            sp = sent_pipe(text[:128])[0]
            lbl = sp["label"].lower()
            s_label = "negative" if ("neg" in lbl or lbl == "label_0") else ("positive" if ("pos" in lbl or lbl == "label_2") else "neutral")
            s_score = round(float(sp["score"]), 3)
        else:
            res = RuleBasedOfflineNLPService().analyze_text(text)
            s_label, s_score = res["sentiment_label"], res["sentiment_score"]

        # Emotion
        if emo_pipe is not None:
            ep = emo_pipe(text[:128])[0]
            raw_e = ep["label"]
            e_label = map_go_emotion_to_category(raw_e)
            e_score = round(float(ep["score"]), 3)
        else:
            res = RuleBasedOfflineNLPService().analyze_text(text)
            e_label, e_score, raw_e = res["emotion_label"], res["emotion_score"], res["emotion_label"]

        synth_results.append({
            "text": text,
            "context": context,
            "sentiment_label": s_label,
            "sentiment_score": s_score,
            "emotion_label": e_label,
            "emotion_score": e_score,
            "raw_emotion": raw_e,
        })

    # Save metrics JSON for documentation generator
    results_payload = {
        "emotion_accuracy": acc,
        "emotion_macro_f1": macro_f1,
        "emotion_report": report,
        "sentiment_accuracy": sent_acc,
        "sentiment_macro_f1": sent_macro_f1,
        "synthetic_results": synth_results,
    }

    with open("docs/eval_results.json", "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)
    print("Saved evaluation payload to docs/eval_results.json")


if __name__ == "__main__":
    main()
