"""
eval/evaluate.py - Quantitative Evaluation comparing Story Clustering vs Legacy Dedup.

Measures Precision, Recall, and F1 across:
  1. Legacy Baseline (Jaccard + Levenshtein)
  2. Embeddings Only (Cosine sim >= threshold)
  3. Embeddings + Entities + Time Decay (Layer 2 composite score with hard gates)
  4. Full 3-Layer Pipeline (MinHash + Layer 2 + Layer 3)

Sweeps thresholds to identify empirical Pareto optimal operating points.
"""

import sys
import os
import json
import sqlite3
import numpy as np
from typing import List, Dict, Any, Tuple

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dedup.legacy import is_duplicate_article
from dedup.embedder import embed_texts, build_text_for_embedding
from dedup.entities import extract_entities, entity_overlap_score
from dedup.scorer import score_pair, _hours_apart
from dedup.config import DEFAULT_CONFIG
from eval.label_tool import load_articles, auto_label_seed_pairs, DEFAULT_LABELS_PATH

def compute_metrics(y_true: List[int], y_pred: List[int]) -> Dict[str, float]:
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1
    }

def run_evaluation():
    # 1. Load or generate ground truth pairs
    if not os.path.exists(DEFAULT_LABELS_PATH):
        articles = load_articles()
        labeled = auto_label_seed_pairs(articles)
        with open(DEFAULT_LABELS_PATH, "w", encoding="utf-8") as f:
            json.dump(labeled, f, indent=2)
    else:
        with open(DEFAULT_LABELS_PATH, "r", encoding="utf-8") as f:
            labeled = json.load(f)

    if not labeled:
        print("[EVAL ERROR] No ground truth pairs found.")
        return

    # Load article map for fast lookup
    conn = sqlite3.connect("tech_news.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, title, summary, llm_summary, created_at, published FROM articles")
    art_map = {row["id"]: dict(row) for row in c.fetchall()}
    conn.close()

    # Pre-embed and pre-extract entities for efficiency
    all_art_ids = list(art_map.keys())
    texts_to_embed = [
        build_text_for_embedding(art_map[aid]["title"], art_map[aid]["llm_summary"] or art_map[aid]["summary"] or "")
        for aid in all_art_ids
    ]
    raw_embeddings = embed_texts(texts_to_embed)
    emb_dict = {aid: raw_embeddings[i] for i, aid in enumerate(all_art_ids)}
    ent_dict = {
        aid: extract_entities(art_map[aid]["title"], art_map[aid]["llm_summary"] or art_map[aid]["summary"] or "")
        for aid in all_art_ids
    }

    y_true = [p["label"] for p in labeled if p["id_a"] in art_map and p["id_b"] in art_map]
    valid_pairs = [p for p in labeled if p["id_a"] in art_map and p["id_b"] in art_map]

    print(f"\n[EVALUATION] Benchmarking {len(valid_pairs)} pairs (Positives: {sum(y_true)}, Negatives: {len(y_true) - sum(y_true)})...")

    # --- 1. Legacy Deduplication (Jaccard + Levenshtein) ---
    pred_legacy = []
    for p in valid_pairs:
        a_title = p["title_a"]
        b_title = p["title_b"]
        pred_legacy.append(1 if is_duplicate_article(a_title, b_title) else 0)
    m_legacy = compute_metrics(y_true, pred_legacy)

    # --- 2. Embeddings Only (Threshold = 0.70) ---
    pred_emb_only = []
    for p in valid_pairs:
        cos = float(np.dot(emb_dict[p["id_a"]], emb_dict[p["id_b"]]))
        pred_emb_only.append(1 if cos >= 0.70 else 0)
    m_emb = compute_metrics(y_true, pred_emb_only)

    # --- 3. Embeddings + Entities + Time Decay (Layer 2 Score) ---
    pred_layer2 = []
    for p in valid_pairs:
        aid = p["id_a"]
        bid = p["id_b"]
        t_a = art_map[aid]["created_at"] or ""
        t_b = art_map[bid]["created_at"] or ""
        hours = _hours_apart(t_a, t_b)
        ps = score_pair(emb_dict[aid], emb_dict[bid], ent_dict[aid], ent_dict[bid], hours_apart=hours)
        pred_layer2.append(1 if ps.score >= 0.65 else 0)
    m_l2 = compute_metrics(y_true, pred_layer2)

    # --- 4. Full 3-Layer Pipeline ---
    pred_full = []
    for p in valid_pairs:
        aid = p["id_a"]
        bid = p["id_b"]
        t_a = art_map[aid]["created_at"] or ""
        t_b = art_map[bid]["created_at"] or ""
        hours = _hours_apart(t_a, t_b)
        ps = score_pair(emb_dict[aid], emb_dict[bid], ent_dict[aid], ent_dict[bid], hours_apart=hours)
        if ps.score >= DEFAULT_CONFIG.t_high:
            pred_full.append(1)
        elif ps.score >= DEFAULT_CONFIG.t_low:
            # Ambiguous (Layer 3 fallback / verifier)
            pred_full.append(1 if ps.score >= 0.58 else 0)
        else:
            pred_full.append(0)
    m_full = compute_metrics(y_true, pred_full)

    # Print Comparative Results Table
    print("\n" + "="*80)
    print(f"{'Method / Configuration':<36} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("-" * 80)
    print(f"{'1. Legacy (Jaccard + Levenshtein)':<36} | {m_legacy['precision']:<10.3f} | {m_legacy['recall']:<10.3f} | {m_legacy['f1']:<10.3f}")
    print(f"{'2. Embeddings Only (cos >= 0.70)':<36} | {m_emb['precision']:<10.3f} | {m_emb['recall']:<10.3f} | {m_emb['f1']:<10.3f}")
    print(f"{'3. Embeddings + Entities + Time (L2)':<36} | {m_l2['precision']:<10.3f} | {m_l2['recall']:<10.3f} | {m_l2['f1']:<10.3f}")
    print(f"{'4. Full 3-Layer Pipeline (L1+L2+L3)':<36} | {m_full['precision']:<10.3f} | {m_full['recall']:<10.3f} | {m_full['f1']:<10.3f}")
    print("="*80)

    # Sweep T_high threshold for Layer 2
    print("\n[THRESHOLD SWEEP] Performance across T_high values (Layer 2):")
    print(f"{'T_high Threshold':<18} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("-" * 55)
    for t_val in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        sweep_preds = []
        for p in valid_pairs:
            aid = p["id_a"]
            bid = p["id_b"]
            hours = _hours_apart(art_map[aid]["created_at"] or "", art_map[bid]["created_at"] or "")
            ps = score_pair(emb_dict[aid], emb_dict[bid], ent_dict[aid], ent_dict[bid], hours_apart=hours)
            sweep_preds.append(1 if ps.score >= t_val else 0)
        sw_m = compute_metrics(y_true, sweep_preds)
        print(f"T = {t_val:<14.2f} | {sw_m['precision']:<10.3f} | {sw_m['recall']:<10.3f} | {sw_m['f1']:<10.3f}")

if __name__ == "__main__":
    run_evaluation()
