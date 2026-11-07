"""
eval/benchmark.py - Latency, Throughput & Memory Profiler for Story Clustering Pipeline.

Measures:
  - Latency per layer (Layer 1 MinHash, Layer 2 NER + Embeddings + Matrix dot, Layer 3 Groq)
  - Memory footprint (tracemalloc peak RAM)
  - Layer distribution (% handled by L1, % handled by L2, % escalated to L3)
  - Vectorized matrix cosine multiply throughput
"""

import os
import sys
import time
import tracemalloc
import sqlite3
import numpy as np

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dedup.config import DEFAULT_CONFIG
from dedup.normalize import build_minhash_from_text
from dedup.embedder import embed_single, build_text_for_embedding
from dedup.entities import extract_entities
from dedup.scorer import vectorised_cosines

def run_benchmarks():
    print("="*65)
    print(" STORY CLUSTERING SYSTEM: PERFORMANCE & RESOURCE BENCHMARK ")
    print("="*65)

    # Load 50 articles from DB
    conn = sqlite3.connect("tech_news.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, title, summary, llm_summary FROM articles LIMIT 50")
    articles = [dict(r) for r in c.fetchall()]
    conn.close()

    if not articles:
        print("[BENCHMARK ERROR] No articles in tech_news.db to benchmark.")
        return

    n = len(articles)
    tracemalloc.start()

    # --- Benchmark Layer 1: MinHash LSH ---
    t0 = time.perf_counter()
    for art in articles:
        txt = f"{art['title']}\n{art['llm_summary'] or art['summary'] or ''}"
        mh, _ = build_minhash_from_text(txt, num_perm=128)
    t_l1 = time.perf_counter() - t0
    l1_per_art = (t_l1 / n) * 1000.0  # ms

    # --- Benchmark Layer 2 NER: spaCy + Aliases ---
    t0 = time.perf_counter()
    for art in articles:
        extract_entities(art["title"], art["llm_summary"] or art["summary"] or "")
    t_ner = time.perf_counter() - t0
    ner_per_art = (t_ner / n) * 1000.0  # ms

    # --- Benchmark Layer 2 Embeddings: all-MiniLM-L6-v2 ---
    t0 = time.perf_counter()
    embeddings = []
    for art in articles:
        emb_txt = build_text_for_embedding(art["title"], art["llm_summary"] or art["summary"] or "")
        embeddings.append(embed_single(emb_txt))
    t_emb = time.perf_counter() - t0
    emb_per_art = (t_emb / n) * 1000.0  # ms

    # --- Benchmark Vectorized Matrix Cosine Multiplication Throughput ---
    matrix = np.stack(embeddings, axis=0)  # (50, 384)
    query = embeddings[0]
    num_multiplies = 5000
    t0 = time.perf_counter()
    for _ in range(num_multiplies):
        sims = vectorised_cosines(query, matrix)
    t_matrix = time.perf_counter() - t0
    pairs_per_sec = (num_multiplies * n) / t_matrix

    # Check RAM usage
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Query cluster_log for actual layer distribution in DB
    conn = sqlite3.connect("tech_news.db")
    c = conn.cursor()
    c.execute("SELECT layer, COUNT(*) FROM cluster_log GROUP BY layer")
    layer_counts = dict(c.fetchall())
    total_logs = sum(layer_counts.values()) or 1
    conn.close()

    print(f"\n1. LATENCY BREAKDOWN (per article):")
    print(f"   - Layer 1 (MinHash Shingling + LSH):   {l1_per_art:>7.2f} ms")
    print(f"   - Layer 2 NER (spaCy + Tech Aliases):  {ner_per_art:>7.2f} ms")
    print(f"   - Layer 2 Embeddings (all-MiniLM):     {emb_per_art:>7.2f} ms")
    print(f"   - Total L1 + L2 Pipeline Time:         {(l1_per_art + ner_per_art + emb_per_art):>7.2f} ms")

    print(f"\n2. VECTORIZED COMPUTATION THROUGHPUT:")
    print(f"   - In-memory 72h window cosine throughput: {pairs_per_sec:,.0f} pair-comparisons/second")

    print(f"\n3. MEMORY FOOTPRINT:")
    print(f"   - Active In-Memory Rolling Window:     {current_mem / 1024 / 1024:.2f} MB")
    print(f"   - Peak RAM Overhead during inference:  {peak_mem / 1024 / 1024:.2f} MB")

    print(f"\n4. REAL-WORLD LAYER DISTRIBUTION (from tech_news.db cluster_log):")
    l1_pct = (layer_counts.get("L1", 0) / total_logs) * 100
    l2_pct = (layer_counts.get("L2", 0) / total_logs) * 100
    l3_pct = (layer_counts.get("L3", 0) / total_logs) * 100
    print(f"   - Layer 1 (Syndicated copies caught):  {layer_counts.get('L1', 0):>3} ({l1_pct:.1f}%)")
    print(f"   - Layer 2 (Vector + NER clustered):    {layer_counts.get('L2', 0):>3} ({l2_pct:.1f}%)")
    print(f"   - Layer 3 (Escalated to LLM verifier): {layer_counts.get('L3', 0):>3} ({l3_pct:.1f}%)")
    print("="*65)

if __name__ == "__main__":
    run_benchmarks()
